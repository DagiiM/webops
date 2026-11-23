"""Exercise actual Makefile routing and safe lifecycle retry entrypoints."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[4]
LIFECYCLE = REPO / "provisioning/versions/v1.0.0/lifecycle"
sys.path.insert(0, str(LIFECYCLE))
import installation_inventory as inv
sys.path.remove(str(LIFECYCLE))


class MakeInstallRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.project = base / "project"
        self.project.mkdir()
        shutil.copy2(REPO / "Makefile", self.project / "Makefile")
        prod = self.project / "provisioning/versions/v1.0.0/lifecycle/install.sh"
        dev = self.project / "provisioning/versions/v1.0.0/dev/quickstart.sh"
        for p, text in ((prod, '#!/bin/sh\necho "PRODUCTION:$WEBOPS_SMART_INSTALL"\n'),
                        (dev, "#!/bin/sh\necho DEVELOPMENT\n")):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
            p.chmod(0o755)
        self.bin = base / "bin"
        self.bin.mkdir()
        for name, content in (
            ("id", '#!/bin/sh\necho "${FAKE_UID:-0}"\n'),
            ("flock", '#!/bin/sh\nshift 4\nexec "$@"\n'),
            ("sudo", '#!/bin/sh\nexec "$@"\n'),
        ):
            p = self.bin / name
            p.write_text(content)
            p.chmod(0o755)
        self.env = {**os.environ, "PATH": str(self.bin) + ":" + os.environ["PATH"]}

    def run_target(self, name, **env):
        return subprocess.run(["make", "-s", name], cwd=self.project,
                              env={**self.env, **env}, capture_output=True,
                              text=True, timeout=12)

    def test_make_install_is_smart_production(self):
        r = self.run_target("install")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PRODUCTION:true", r.stdout)
        self.assertNotIn("DEVELOPMENT", r.stdout)

    def test_make_install_with_nonroot_uses_sudo(self):
        r = self.run_target("install", FAKE_UID="1000")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PRODUCTION:true", r.stdout)

    def test_development_is_separate(self):
        for target in ("dev-install", "install-dev"):
            with self.subTest(target=target):
                r = self.run_target(target)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("DEVELOPMENT", r.stdout)
                self.assertNotIn("PRODUCTION:true", r.stdout)


class LifecycleRetryEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "installed/webops"
        self.lifecycle = self.root / "provisioning/versions/v1.0.0/lifecycle"
        self.lifecycle.mkdir(parents=True)
        (self.root / inv.MARKER).write_text("v1.0.0")
        for name in ("installation_inventory.py", "installation_recovery.py"):
            shutil.copy2(LIFECYCLE / name, self.lifecycle / name)
        s = (LIFECYCLE / "install.sh").read_text()
        s = s.replace('readonly ROLLBACK_BASE_DIR="/var/backups/webops-install"',
                      'readonly ROLLBACK_BASE_DIR="' + str(base / "backup") + '"')
        s = s[:s.rindex('main "$@"')]
        s += """
init_logging() { :; }
copy_to_install_location() { :; }
show_welcome() { echo WIZARD; }
validate_environment() { echo VALID; }
run_installation_preflight() { :; }
run_installation() { echo EXECUTED_SETUP; return 0; }
verify_installation() { echo CHECK_HEALTH; return "${FAKE_HEALTH:-0}"; }
print_completion_message() { :; }
apply_hostname() { echo CHANGE_HOSTNAME; }
main "$@"
"""
        self.script = self.lifecycle / "install.sh"
        self.script.write_text(s)
        self.state = base / "backup/installation-inventory"
        self.system = base / "fake-system"
        self.data = self.root / "deployments/important.db"
        self.data.parent.mkdir()
        self.data.write_text("KEEP")
        self.env = {**os.environ, "WEBOPS_INSTALL_ROOT": str(self.root),
                    "WEBOPS_SMART_INSTALL": "true"}

    def capture(self, phase):
        with mock.patch.object(inv, "command", return_value=""):
            inv.capture(self.state, self.root, self.system)
        if phase != "baseline-captured":
            inv.begin_system_changes(self.state)
        if phase == "setup-completed":
            inv.mark_setup_completed(self.state)

    def run_installer(self, *args, **env):
        return subprocess.run(["bash", str(self.script), *args],
                              env={**self.env, **env}, text=True,
                              capture_output=True, timeout=12)

    def test_auto_resume_safe_preflight_without_new_wizard_choices(self):
        self.capture("baseline-captured")
        r = self.run_installer()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("EXECUTED_SETUP", r.stdout)
        self.assertEqual(inv.load(self.state)["status"], "sealed")
        self.assertEqual(self.data.read_text(), "KEEP")

    def test_auto_resume_finalizes_completed_setup_without_replaying(self):
        self.capture("setup-completed")
        r = self.run_installer()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("EXECUTED_SETUP", r.stdout)
        self.assertEqual(inv.load(self.state)["status"], "sealed")

    def test_unhealthy_completed_setup_is_not_sealed(self):
        self.capture("setup-completed")
        r = self.run_installer(FAKE_HEALTH="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(inv.load(self.state)["status"], "captured")
        self.assertEqual(self.data.read_text(), "KEEP")

    def test_partial_host_setup_never_replays_or_prompts(self):
        self.capture("system-changes-started")
        r = self.run_installer()
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("EXECUTED_SETUP", r.stdout)
        self.assertNotIn("WIZARD", r.stdout)
        self.assertEqual(self.data.read_text(), "KEEP")


    def make_fake_systemctl(self, refuse_start=False):
        fake = self.root.parent / "bin"
        fake.mkdir(exist_ok=True)
        unit = fake / "systemctl"
        unit.write_text("""#!/bin/sh
if [ "$1" = "is-active" ]; then
  if [ "$3" = "webops-worker" ] && [ ! -e "$FAKE_READY" ]; then exit 3; fi
  exit 0
fi
if [ "$1" = "cat" ]; then exit 0; fi
if [ "$1" = "start" ]; then
  echo "$2" >> "$FAKE_STARTED"
  if [ "$2" = "webops-worker" ]; then
    if [ "$FAKE_REFUSE_START" = "1" ]; then exit 1; fi
    touch "$FAKE_READY"
    exit 0
  fi
  exit 9
fi
exit 7
""")
        unit.chmod(0o755)
        ready = self.root.parent / "worker-ready"
        started = self.root.parent / "started-list"
        script = self.script.read_text()
        script = script.replace('main "$@"\n', """
verify_installation() { [ -e "$FAKE_READY" ]; }
main "$@"
""")
        self.script.write_text(script)
        return {
            "PATH": str(fake) + os.pathsep + os.environ["PATH"],
            "FAKE_READY": str(ready), "FAKE_STARTED": str(started),
            "FAKE_REFUSE_START": "1" if refuse_start else "0"
        }, ready, started

    def test_healthy_existing_install_does_not_reinstall(self):
        self.capture("baseline-captured")
        with mock.patch.object(inv, "command", return_value=""):
            inv.seal(self.state, self.system)
        env, ready, started = self.make_fake_systemctl()
        ready.touch()
        r = self.run_installer("--verify-repair", **env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("EXECUTED_SETUP", r.stdout)
        self.assertFalse(started.exists())

    def test_health_retry_only_starts_webops_owned_unit(self):
        self.capture("baseline-captured")
        with mock.patch.object(inv, "command", return_value=""):
            inv.seal(self.state, self.system)
        env, ready, started = self.make_fake_systemctl()
        r = self.run_installer("--verify-repair", **env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(started.read_text().splitlines(), ["webops-worker"])
        self.assertTrue(ready.exists())
        self.assertEqual(self.data.read_text(), "KEEP")

    def test_health_only_does_not_restart_services(self):
        self.capture("baseline-captured")
        with mock.patch.object(inv, "command", return_value=""):
            inv.seal(self.state, self.system)
        env, ready, started = self.make_fake_systemctl()
        r = self.run_installer("--verify", **env)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(started.exists())
        self.assertEqual(self.data.read_text(), "KEEP")

    def test_failed_service_recovery_fails_without_reinstall(self):
        self.capture("baseline-captured")
        with mock.patch.object(inv, "command", return_value=""):
            inv.seal(self.state, self.system)
        env, ready, started = self.make_fake_systemctl(refuse_start=True)
        r = self.run_installer("--verify-repair", **env)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("EXECUTED_SETUP", r.stdout)
        self.assertEqual(started.read_text().splitlines(), ["webops-worker"])
        self.assertEqual(inv.load(self.state)["status"], "sealed")


if __name__ == "__main__":
    unittest.main()
