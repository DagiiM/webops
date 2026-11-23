"""Fail-closed SSH policy and port-preflight regression tests.

All mutable paths are replaced with temporary directories; no host sshd
or public SSH endpoint is changed by these tests.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

VERSION = Path(__file__).resolve().parents[1]
BASE = VERSION / "setup" / "base.sh"
VALIDATE = VERSION / "setup" / "validate.sh"


def extract(path, name, next_name):
    s = path.read_text()
    return s[s.index(name + "() {"):s.index(next_name + "() {")]


class SSHPreservationTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.config = self.root / "sshd_config"
        self.dropins = self.root / "sshd_config.d"
        self.dropins.mkdir()
        self.policy = self.dropins / "99-webops.conf"
        self.config.write_text(f"Include {self.dropins}/*.conf\nPort 2222\n# keep provider settings\n")
        self.keys = self.root / "authorized_keys"
        self.keys.write_text("ssh-ed25519 " + "A"*55 + " test\n")
        fn = extract(BASE, "configure_ssh_hardening", "configure_sudo_access")
        fn = fn.replace("/etc/ssh/sshd_config.d", str(self.dropins))
        fn = fn.replace("/etc/ssh/sshd_config", str(self.config))
        fn = fn.replace("/root/.ssh/authorized_keys", str(self.keys))
        self.fn = fn
        self.effective = self.root / "effective"
        self.effective.write_text("permitrootlogin yes\npasswordauthentication yes\nmaxauthtries 3\npubkeyauthentication yes\n")
        self.restart = self.root / "restarted"

    def run_policy(self, enabled="false", consent=None, root="yes", password="yes", tries="3",
                   fail_restart=False, fail_validation=False):
        shell = """set -euo pipefail
log_info() { :; }
log_success() { :; }
log_error() { printf '%s\n' "$*" >&2; }
sshd() {
    if [[ "$1" == "-T" ]]; then cat "$FAKE_EFFECTIVE"; return 0; fi
    if [[ "$FAKE_VALIDATION_FAIL" == "true" ]]; then return 1; fi
    return 0
}
service_restart() {
    if [[ "$FAKE_RESTART_FAIL" == "true" ]]; then return 1; fi
    printf 'ok\n' >> "$FAKE_RESTART_TRACE"
}
""" + self.fn + """
ENABLE_SSH_HARDENING="$FAKE_ENABLED"
PERMIT_ROOT_LOGIN="$FAKE_ROOT"
SSH_PASSWORD_AUTH="$FAKE_PASSWORD"
SSH_MAX_AUTH_TRIES="$FAKE_TRIES"
if [[ "$FAKE_CONSENT" != "unset" ]]; then SSH_ACCESS_CHANGE_CONFIRMED="$FAKE_CONSENT"; fi
configure_ssh_hardening
"""
        env = {**os.environ, "FAKE_EFFECTIVE":str(self.effective),
               "FAKE_RESTART_TRACE":str(self.restart),
               "FAKE_ENABLED":enabled, "FAKE_ROOT":root,
               "FAKE_PASSWORD":password, "FAKE_TRIES":tries,
               "FAKE_CONSENT":consent if consent is not None else "unset",
               "FAKE_RESTART_FAIL":str(fail_restart).lower(),
               "FAKE_VALIDATION_FAIL":str(fail_validation).lower()}
        return subprocess.run(["bash", "-c", shell], env=env, text=True, capture_output=True, timeout=10)

    def test_default_keeps_server_config_exactly(self):
        original = self.config.read_bytes()
        r = self.run_policy()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.config.read_bytes(), original)
        self.assertFalse(self.policy.exists())
        self.assertFalse(self.restart.exists())

    def test_opt_in_required_even_with_existing_hardening_flag(self):
        original = self.config.read_bytes()
        r = self.run_policy(enabled="true")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SSH_ACCESS_CHANGE_CONFIRMED", r.stderr)
        self.assertEqual(self.config.read_bytes(), original)
        self.assertFalse(self.policy.exists())

    def test_explicit_easy_access_creates_only_dropin(self):
        original = self.config.read_bytes()
        r = self.run_policy(enabled="true", consent="true")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PasswordAuthentication yes", self.policy.read_text())
        self.assertEqual(original, self.config.read_bytes())
        self.assertTrue(self.restart.exists())

    def test_effective_mismatch_rolls_back_existing_dropin(self):
        self.policy.write_text("# WebOps explicitly opted-in SSH policy\nprior WebOps policy\n")
        self.effective.write_text("permitrootlogin yes\npasswordauthentication no\nmaxauthtries 3\npubkeyauthentication yes\n")
        r = self.run_policy(enabled="true", consent="true")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.policy.read_text(), "# WebOps explicitly opted-in SSH policy\nprior WebOps policy\n")
        self.assertFalse(self.restart.exists())

    def test_effective_mismatch_removes_new_dropin(self):
        self.effective.write_text("permitrootlogin no\npasswordauthentication yes\nmaxauthtries 3\npubkeyauthentication yes\n")
        r = self.run_policy(enabled="true", consent="true")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.policy.exists())

    def test_service_restart_failure_restores_previous_policy(self):
        self.policy.write_text("# WebOps explicitly opted-in SSH policy\noriginal policy\n")
        r = self.run_policy(enabled="true", consent="true", fail_restart=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.policy.read_text(), "# WebOps explicitly opted-in SSH policy\noriginal policy\n")
        self.assertEqual(self.config.read_text().splitlines()[1], "Port 2222")

    def test_existing_invalid_sshd_config_is_preserved(self):
        r = self.run_policy(enabled="true", consent="true", fail_validation=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.policy.exists())

    def test_unrecognized_policy_is_rejected(self):
        r = self.run_policy(enabled="true", consent="true", root="no", password="no")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.policy.exists())

    def test_malformed_attempt_limit_is_rejected(self):
        for n in ("-1", "0", "2", "21", "3;exit 0", "ABC"):
            with self.subTest(n=n):
                r = self.run_policy(enabled="true", consent="true", tries=n)
                self.assertNotEqual(r.returncode, 0)
                self.assertFalse(self.policy.exists())

    def test_missing_include_refuses_unsafe_primary_config_rewrite(self):
        self.config.write_text("PasswordAuthentication yes\n")
        r = self.run_policy(enabled="true", consent="true")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.config.read_text(), "PasswordAuthentication yes\n")
        self.assertFalse(self.policy.exists())

    def test_symlinked_dropin_is_never_followed(self):
        outsider = self.root / "outside"
        outsider.write_text("KEEP")
        self.policy.symlink_to(outsider)
        r = self.run_policy(enabled="true", consent="true")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(outsider.read_text(), "KEEP")

    def test_key_only_accepts_real_openssh_normalized_policy(self):
        self.effective.write_text(
            "permitrootlogin without-password\npasswordauthentication no\n"
            "maxauthtries 3\npubkeyauthentication yes\n"
        )
        r = self.run_policy(
            enabled="true", consent="true",
            root="prohibit-password", password="no",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.policy.exists())
        self.assertEqual(self.config.read_text().splitlines()[1], "Port 2222")

    def test_key_only_requires_root_authorized_key(self):
        self.keys.unlink()
        r = self.run_policy(enabled="true", consent="true", root="prohibit-password", password="no")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.policy.exists())


class PreflightPortTests(unittest.TestCase):
    def run_ports(self, function):
        fn = extract(VALIDATE, "validate_ports", "validate_disk_io")
        shell = """set -euo pipefail
log_step() { :; }
log_warn() { echo WARN:"$*"; }
log_info() { echo INFO:"$*"; }
log_error() { echo ERROR:"$*" >&2; }
""" + function + "\n" + fn + "\nvalidate_ports\n"
        return subprocess.run(["bash", "-c", shell], text=True, capture_output=True, timeout=10)

    def test_failed_ss_must_fail_preflight(self):
        r = self.run_ports("ss() { return 127; }")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ss failed", r.stderr)
        self.assertNotIn("is available", r.stdout)

    def test_missing_ss_must_fail_preflight(self):
        r = self.run_ports("command() { if [[ \"$1\" == -v && \"$2\" == ss ]]; then return 1; fi; builtin command \"$@\"; }")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unavailable", r.stderr)

    def test_occupied_ports_warn_but_do_not_claim_available(self):
        r = self.run_ports("ss() { printf 'tcp LISTEN 0 128 0.0.0.0:80 0.0.0.0:*\n'; }")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Port 80 is in use", r.stdout)
        self.assertNotIn("Port 80 is available", r.stdout)

    def test_empty_listening_ports_report_available(self):
        r = self.run_ports("ss() { printf 'Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port\n'; }")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Port 443 is available", r.stdout)

    def test_port_8080_does_not_count_as_80(self):
        r = self.run_ports("ss() { printf 'tcp LISTEN 0 128 0.0.0.0:8080 0.0.0.0:*\n'; }")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Port 80 is available", r.stdout)

    def test_top_level_preflight_propagates_uninspectable_port_error(self):
        self.assertIn("validate_ports || failed=1", VALIDATE.read_text())


class FirewallConnectionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.trace = Path(self.t.name) / "firewall.log"
        self.fn = extract(BASE, "get_ssh_listener_ports", "configure_firewall")
        self.fn += extract(BASE, "configure_ufw", "configure_firewalld")
        whole = BASE.read_text()
        self.fn += whole[whole.index("configure_firewalld() {"):whole.index("#=============================================================================\n# Package Management and Updates")]

    def call(self, function="configure_ufw", ssh_ports="port 22\nport 2222\n",
             connection="198.51.100.8 5555 192.0.2.12 2200",
             active=False, fail_sshd=False):
        script = """set -euo pipefail
log_info() { :; }
log_error() { echo ERROR:"$*" >&2; }
log_warn() { :; }
sshd() {
   if [[ "$FAKE_SSHD_FAIL" == "true" ]]; then return 1; fi
   if [[ "$1" == "-T" ]]; then printf '%s' "$FAKE_PORTS"; fi
}
ufw() {
   if [[ "$1" == status ]]; then
      if [[ "$FAKE_ACTIVE" == true ]]; then echo "Status: active"; else echo "Status: inactive"; fi
      return 0
   fi
   echo "ufw $*" >> "$FAKE_TRACE"
}
firewall-cmd() {
   if [[ "$1" == --state ]]; then return 1; fi
   echo "firewall-cmd $*" >> "$FAKE_TRACE"
}
firewall-offline-cmd() { echo "offline $*" >> "$FAKE_TRACE"; }
pkg_install() { echo "pkg $*" >> "$FAKE_TRACE"; }
service_enable() { echo "enable $*" >> "$FAKE_TRACE"; }
service_restart() { echo "restart $*" >> "$FAKE_TRACE"; }
""" + self.fn + "\n" + function + "\n"
        env = {**os.environ, "FAKE_PORTS":ssh_ports, "FAKE_TRACE":str(self.trace),
               "FAKE_ACTIVE":str(active).lower(), "FAKE_SSHD_FAIL":str(fail_sshd).lower()}
        if connection is None:
            env.pop("SSH_CONNECTION", None)
        else:
            env["SSH_CONNECTION"] = connection
        return subprocess.run(["bash", "-c", script], capture_output=True,
                              text=True, env=env, timeout=10)

    def events(self):
        return self.trace.read_text().splitlines() if self.trace.exists() else []

    def test_ufw_allows_custom_listener_and_active_port_before_enable(self):
        r = self.call()
        self.assertEqual(r.returncode, 0, r.stderr)
        events = self.events()
        self.assertIn("ufw allow 2222/tcp comment SSH", events)
        self.assertIn("ufw allow 2200/tcp comment SSH", events)
        self.assertLess(events.index("ufw allow 2200/tcp comment SSH"), events.index("ufw --force enable"))

    def test_ufw_unknown_listener_does_not_enable_default_deny(self):
        r = self.call(ssh_ports="", connection=None)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.events(), [])

    def test_ufw_invalid_connected_port_fails_closed(self):
        r = self.call(connection="198.51.100.3 4444 192.0.2.3 bad")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.events(), [])

    def test_ufw_existing_policy_is_preserved(self):
        r = self.call(active=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.events(), [])

    def test_ufw_sshd_failure_does_not_enable(self):
        r = self.call(fail_sshd=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.events(), [])

    def test_firewalld_authorizes_ports_before_start(self):
        r = self.call(function="configure_firewalld")
        self.assertEqual(r.returncode, 0, r.stderr)
        events = self.events()
        self.assertIn("offline --add-port=2222/tcp", events)
        self.assertIn("offline --add-port=2200/tcp", events)
        self.assertLess(events.index("offline --add-port=2200/tcp"), events.index("restart firewalld"))


if __name__ == "__main__":
    unittest.main()
