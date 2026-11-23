"""Executable monitoring installation contracts; fake service operations are isolated.

Separate from real Grafana smoke testing: these cases test the production
Bash functions without touching the runner's actual systemd or /etc files.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

MONITORING = Path(__file__).resolve().parents[1] / "addons" / "monitoring.sh"


class MonitoringStartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.env = {
            **os.environ,
            "WEBOPS_ROOT": str(self.base / "source-data"),
            "WEBOPS_MONITORING_LOG_DIR": str(self.base / "private-diagnostics"),
            "MONITORING_GRAFANA_MAX_ATTEMPTS": "3",
            "MONITORING_GRAFANA_POLL_SECONDS": "0",
            "MOCK_CURL_COUNT": str(self.base / "curl-count"),
        }
        self.setup = r'''
source "@@MONITORING@@"
systemctl() {
  case "$1" in
    start)
      if [[ "$2" == "grafana-server" && "@@{TEST_GRAFANA_START_FAIL:-0}" == "1" ]]; then
        return 1
      fi
      return 0 ;;
    is-failed)
      [[ "@@{TEST_GRAFANA_FAILED:-0}" == "1" ]] ;;
    is-active)
      [[ "@@{TEST_GRAFANA_ACTIVE:-1}" == "1" ]] ;;
    status) echo "MOCK_SYSTEMD_STATUS"; return 0 ;;
    *) return 0 ;;
  esac
}
curl() {
  case "$*" in
    *"/-/healthy"*) echo "prometheus ok"; return 0 ;;
    *"/api/health"*)
      local count=0
      [[ -e "$MOCK_CURL_COUNT" ]] && count="$(cat "$MOCK_CURL_COUNT")"
      count=$((count + 1))
      echo "$count" > "$MOCK_CURL_COUNT"
      if [[ "@@{TEST_CURL_ERROR:-0}" == "1" ]]; then return 7; fi
      if ((count < @@{TEST_GRAFANA_READY_AFTER:-1})); then return 7; fi
      if [[ "@@{TEST_UNRELATED_200:-0}" == "1" ]]; then
        echo "<html>not Grafana</html>"
      elif [[ "@@{TEST_DATABASE_ERROR:-0}" == "1" ]]; then
        echo '{"database":"error","version":"13.3.1"}'
      else
        echo '{"database":"ok","version":"13.3.1"}'
      fi
      return 0 ;;
    *) return 7 ;;
  esac
}
sleep() { :; }
journalctl() { echo "PRIVATE_MOCK_TOKEN_MUST_NOT_PRINT_TO_CONSOLE"; }
'''.replace('@@MONITORING@@', str(MONITORING)).replace('@@', '$')

    def run_shell(self, action, **vars):
        env = {**self.env, **{k: str(v) for k, v in vars.items()}}
        return subprocess.run(["bash", "-c", "set -euo pipefail\n" +
                               self.setup + "\n" + action + "\n"],
                              env=env, capture_output=True, text=True, timeout=15)

    def test_real_function_healthy_on_first_attempt(self):
        r = self.run_shell("setup_monitoring_services")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("database health verified", r.stdout)
        self.assertEqual((self.base / "curl-count").read_text().strip(), "1")

    def test_retries_slow_grafana_then_passes(self):
        r = self.run_shell("setup_monitoring_services", TEST_GRAFANA_READY_AFTER=3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.base / "curl-count").read_text().strip(), "3")

    def test_generic_http_200_is_not_accepted(self):
        r = self.run_shell("setup_monitoring_services", TEST_UNRELATED_200=1)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Detailed Grafana diagnostics", r.stderr)

    def test_database_unhealthy_is_not_accepted(self):
        r = self.run_shell("setup_monitoring_services", TEST_DATABASE_ERROR=1)
        self.assertNotEqual(r.returncode, 0)

    def test_connection_failure_produces_protected_report(self):
        r = self.run_shell("setup_monitoring_services", TEST_CURL_ERROR=1)
        self.assertNotEqual(r.returncode, 0)
        reports = list((self.base / "private-diagnostics").glob("grafana-startup-*.log"))
        self.assertEqual(len(reports), 1, r.stdout + r.stderr)
        self.assertEqual(reports[0].stat().st_mode & 0o777, 0o600)
        self.assertIn("PRIVATE_MOCK_TOKEN", reports[0].read_text())
        self.assertNotIn("PRIVATE_MOCK_TOKEN", r.stdout + r.stderr)

    def test_failed_systemd_start_reports_status(self):
        r = self.run_shell("setup_monitoring_services", TEST_GRAFANA_START_FAIL=1)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Could not start systemd service: grafana-server", r.stderr)

    def test_systemd_failed_state_stops_early(self):
        r = self.run_shell("setup_monitoring_services",
                           TEST_GRAFANA_FAILED=1, TEST_CURL_ERROR=1)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((self.base / "curl-count").read_text().strip(), "1")
        self.assertIn("entered failed state", r.stderr)

    def test_invalid_retry_settings_are_rejected(self):
        for value in ("0", "61", "x", "100000"):
            with self.subTest(value=value):
                r = self.run_shell("setup_monitoring_services",
                                   MONITORING_GRAFANA_MAX_ATTEMPTS=value)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("must be 1-60", r.stderr)

    def test_repair_healthy_performs_no_restart(self):
        r = self.run_shell("repair_grafana_only")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("no changes necessary", r.stdout)

    def test_repair_unhealthy_then_healthy(self):
        r = self.run_shell("repair_grafana_only", TEST_GRAFANA_READY_AFTER=2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Grafana recovered", r.stdout)

    def test_repair_failed_start_is_not_silently_successful(self):
        r = self.run_shell("repair_grafana_only",
                           TEST_GRAFANA_START_FAIL=1, TEST_CURL_ERROR=1)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("could not be started", r.stderr.lower())

    def test_readonly_doctor_saves_no_report(self):
        r = self.run_shell("diagnose_monitoring_readonly")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.base / "private-diagnostics").exists())

    def test_doctor_detects_missing_health(self):
        r = self.run_shell("diagnose_monitoring_readonly", TEST_DATABASE_ERROR=1)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("checks did not pass", r.stderr)


class GrafanaConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        source = MONITORING.read_text()
        start = source.index("configure_grafana() {")
        end = source.index("create_monitoring_systemd_services() {", start)
        body = source[start:end]
        self.cfg = self.base / "grafana.ini"
        self.provisioning = self.base / "provisioning"
        self.data = self.base / "data"
        self.dashboards = self.data / "dashboards"
        body = body.replace("/etc/grafana/grafana.ini", str(self.cfg))
        body = body.replace("/etc/grafana/provisioning", str(self.provisioning))
        body = body.replace("/var/lib/grafana/dashboards", str(self.dashboards))
        self.runner = self.base / "test-config.sh"
        self.runner.write_text("""
#!/bin/bash
set -euo pipefail
log_info() { :; }
log_step() { :; }
log_warn() { :; }
log_success() { :; }
ensure_directory() { mkdir -p "$1"; }
chown() { :; }
GRAFANA_DATA_DIR="@@DATA@@"
GRAFANA_PORT=3000
PROMETHEUS_PORT=9090
GRAFANA_USER=grafana
GRAFANA_FRESH_PACKAGE="@@{TEST_FRESH:-false}"
""".replace('@@DATA@@', str(self.data)).replace('@@', '$') +
                               body + "\nconfigure_grafana\n")
        self.runner.chmod(0o755)

    def configure(self, fresh):
        return subprocess.run(["bash", str(self.runner)], env={**os.environ,
                              "TEST_FRESH": "true" if fresh else "false"},
                              capture_output=True, text=True, timeout=15)

    def test_new_package_configuration_backed_up_and_created(self):
        self.cfg.write_text("PACKAGE DEFAULT\n")
        r = self.configure(fresh=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("# WebOps Grafana Configuration", self.cfg.read_text())
        self.assertEqual((self.base / "grafana.ini.webops-package-original").read_text(),
                         "PACKAGE DEFAULT\n")
        self.assertEqual(self.cfg.stat().st_mode & 0o777, 0o640)

    def test_credentials_remain_stable_across_install_retries(self):
        self.cfg.write_text("PACKAGE DEFAULT\n")
        self.assertEqual(self.configure(fresh=True).returncode, 0)
        old = self.cfg.read_bytes()
        self.assertEqual(self.configure(fresh=False).returncode, 0)
        self.assertEqual(self.cfg.read_bytes(), old)

    def test_administrator_grafana_configuration_is_preserved(self):
        self.cfg.write_text("EXTERNAL CUSTOM CONFIGURATION\n")
        r = self.configure(fresh=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cfg.read_text(), "EXTERNAL CUSTOM CONFIGURATION\n")

    def test_custom_dashboard_is_preserved_on_retry(self):
        self.cfg.write_text("PACKAGE DEFAULT\n")
        self.assertEqual(self.configure(fresh=True).returncode, 0)
        overview = self.dashboards / "webops" / "overview.json"
        overview.write_text('{"custom":"do not overwrite"}')
        self.assertEqual(self.configure(fresh=False).returncode, 0)
        self.assertEqual(overview.read_text(), '{"custom":"do not overwrite"}')

    def test_other_app_datasource_is_preserved(self):
        other = self.provisioning / "datasources" / "prometheus.yml"
        other.parent.mkdir(parents=True)
        other.write_text("NOT WEBOPS CONFIG\n")
        self.cfg.write_text("OTHER ADMIN SETTINGS\n")
        self.assertEqual(self.configure(fresh=False).returncode, 0)
        self.assertEqual(other.read_text(), "NOT WEBOPS CONFIG\n")

    def test_monitoring_script_uses_scoped_apt_key(self):
        source = MONITORING.read_text()
        self.assertNotIn("apt-key add", source)
        self.assertIn("signed-by=/etc/apt/keyrings/grafana.asc", source)
        self.assertIn("gpg-full.key", source)
        self.assertIn('is_component_installed "$ADDON_NAME"', source)


if __name__ == "__main__":
    unittest.main()
