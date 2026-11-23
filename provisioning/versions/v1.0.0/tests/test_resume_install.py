"""Safety regressions for preconfigured and interrupted WebOps installation."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

VERSION = Path(__file__).resolve().parents[1]
INSTALL = VERSION / "lifecycle" / "install.sh"
INVENTORY = VERSION / "lifecycle" / "installation_inventory.py"
spec = importlib.util.spec_from_file_location("webops_inventory_test", INVENTORY)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class InstallerResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / "installed" / "webops"
        self.version = self.root / "provisioning" / "versions" / "v1.0.0"
        self.lifecycle = self.version / "lifecycle"
        self.lifecycle.mkdir(parents=True)
        (self.version / "bin").mkdir()
        (self.version / "bin" / "webops").write_text("#!/bin/sh\nexit 0\n")
        (self.version / "bin" / "webops").chmod(0o755)
        shutil.copy2(INVENTORY, self.lifecycle / INVENTORY.name)
        (self.root / mod.MARKER).write_text("v1.0.0\n")
        self.config = self.root / "config.env"
        self.config.write_text("WEBOPS_ROOT=" + str(self.root) + "\nCUSTOM_SECRET=KEEP\n")
        self.backup = base / "backup"
        self.state = self.backup / "installation-inventory"
        self.system = base / "fake-system"

    def capture(self, sealed=False):
        with mock.patch.object(mod, "command", return_value=""):
            mod.capture(self.state, self.root, self.system)
            if sealed:
                mod.seal(self.state, self.system)

    def run_validation(self, fresh=False, resume=False):
        source = INSTALL.read_text()
        old = 'readonly ROLLBACK_BASE_DIR="/var/backups/webops-install"'
        self.assertIn(old, source)
        source = source.replace(old, 'readonly ROLLBACK_BASE_DIR="' + str(self.backup) + '"')
        source = source[:source.rindex('main "$@"')]
        if resume:
            source += "\nINSTALL_RESUME=true\n"
        source += "\nvalidate_environment\ncreate_default_config\n"
        local = self.lifecycle / "validate-only.sh"
        local.write_text(source)
        env = os.environ.copy()
        env["WEBOPS_INSTALL_ROOT"] = str(self.root)
        env["WEBOPS_NEW_INSTALL_COPY"] = "true" if fresh else "false"
        return subprocess.run(["bash", str(local)], env=env, text=True, capture_output=True)

    def test_brand_new_copy_accepts_config_without_overwriting(self):
        original = self.config.read_bytes()
        result = self.run_validation(fresh=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_bytes(), original)
        self.assertIn("Fresh installation with existing source config", result.stdout)

    def test_fresh_copy_without_config_creates_one(self):
        self.config.unlink()
        result = self.run_validation(fresh=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.config.is_file())
        self.assertIn("WEBOPS_ROOT=" + str(self.root), self.config.read_text())

    def test_old_staged_root_cannot_overwrite_config(self):
        result = self.run_validation()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Previously staged", result.stderr)
        self.assertIn("CUSTOM_SECRET=KEEP", self.config.read_text())

    def test_untracked_legacy_config_remains_blocked(self):
        (self.root / mod.MARKER).unlink()
        result = self.run_validation()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Existing WebOps configuration", result.stderr)

    def test_resume_captured_inventory_preserves_original_baseline(self):
        self.capture()
        result = self.run_validation(resume=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mod.load(self.state)["status"], "captured")
        self.assertIn("CUSTOM_SECRET=KEEP", self.config.read_text())

    def test_resume_sealed_inventory_is_rejected(self):
        self.capture(sealed=True)
        result = self.run_validation(resume=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot resume", result.stderr)

    def test_resume_without_baseline_is_rejected(self):
        result = self.run_validation(resume=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot resume", result.stderr)

    def test_advanced_installation_cannot_resume_automatically(self):
        self.capture()
        mod.begin_system_changes(self.state)
        result = self.run_validation(resume=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot resume", result.stderr)
        self.assertEqual(mod.load(self.state)["phase"], "system-changes-started")

    def test_begin_barrier_is_single_use(self):
        self.capture()
        mod.begin_system_changes(self.state)
        with self.assertRaisesRegex(ValueError, "already advanced"):
            mod.begin_system_changes(self.state)

    def test_resume_for_other_root_is_rejected(self):
        self.capture()
        other = Path(self.tmp.name) / "not-the-install-root"
        other.mkdir()
        with self.assertRaisesRegex(ValueError, "different installation root"):
            mod.check_resume(self.state, str(other))

    def run_fake_main(self, health=0, setup=0):
        source = INSTALL.read_text().replace(
            'readonly ROLLBACK_BASE_DIR="/var/backups/webops-install"',
            'readonly ROLLBACK_BASE_DIR="' + str(self.backup) + '"')
        source = source[:source.rindex('main "$@"')]
        source += """
init_logging() { :; }
copy_to_install_location() { :; }
show_welcome() { :; }
validate_environment() { :; }
run_installation_preflight() { :; }
run_installation() { echo setup >> "$EVENT_LOG"; return "$SETUP_EXIT"; }
verify_installation() { echo health >> "$EVENT_LOG"; return "$HEALTH_EXIT"; }
rollback_installation() { echo rollback >> "$EVENT_LOG"; }
print_completion_message() { echo complete >> "$EVENT_LOG"; }
log_info() { :; }
log_error() { echo "$*" >&2; }
main --resume
"""
        script = self.lifecycle / "main-harness.sh"
        script.write_text(source)
        events = Path(self.tmp.name) / "events.log"
        env = os.environ.copy()
        env.update(WEBOPS_INSTALL_ROOT=str(self.root), HEALTH_EXIT=str(health),
                   SETUP_EXIT=str(setup), EVENT_LOG=str(events))
        result = subprocess.run(["bash", str(script)], env=env, text=True,
                                capture_output=True, timeout=20)
        return result, events.read_text().splitlines() if events.exists() else []

    def test_main_seals_only_after_health_pass(self):
        self.capture()
        result, events = self.run_fake_main()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, ["setup", "health", "complete"])
        data = mod.load(self.state)
        self.assertEqual(data["status"], "sealed")
        self.assertTrue(data.get("health_verified_at"))

    def test_main_health_failure_remains_incomplete_on_retry(self):
        self.capture()
        result, events = self.run_fake_main(health=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, ["setup", "health"])
        data = mod.load(self.state)
        self.assertEqual((data["status"], data["phase"]),
                         ("captured", "setup-completed"))
        retry = self.run_validation()
        self.assertNotEqual(retry.returncode, 0)
        self.assertIn("Existing installation inventory", retry.stderr)

    def test_main_setup_failure_is_not_sealed(self):
        self.capture()
        result, events = self.run_fake_main(setup=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, ["setup"])
        self.assertEqual(mod.load(self.state)["status"], "captured")

    def test_inventory_inspection_is_non_destructive(self):
        self.assertEqual(mod.inspect_inventory(self.state)["status"], "missing")
        self.capture()
        self.assertEqual(mod.inspect_inventory(self.state)["status"], "captured")
        self.assertEqual(mod.load(self.state)["status"], "captured")


if __name__ == "__main__":
    unittest.main()
