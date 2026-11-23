"""Regression tests for recovering old staged copies and bundled repository config."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[4]
LC = REPO / "provisioning/versions/v1.0.0/lifecycle"
sys.path.insert(0, str(LC))
import installation_recovery as recovery
import installation_inventory as inventory
sys.path.remove(str(LC))


class StagedRefreshSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "installed/webops"
        self.folder = self.root / "provisioning/versions/v1.0.0/lifecycle"
        self.folder.mkdir(parents=True)
        (self.root / inventory.MARKER).write_text("v1.0.0")
        for name in ("install.sh", "installation_inventory.py",
                     "installation_recovery.py"):
            (self.folder / name).write_text("OLD STAGED SCRIPT\n")
        self.state = self.base / "backup/installation-inventory"
        self.data = self.root / "deployments/custom.db"
        self.data.parent.mkdir()
        self.data.write_text("USER DATA")
        for relative in (
            "provisioning/versions/v1.0.0/bin/webops",
            "provisioning/versions/v1.0.0/addons/monitoring.sh",
            "provisioning/versions/v1.0.0/lib/common.sh",
            "provisioning/versions/v1.0.0/setup/validate.sh",
        ):
            extra = self.root / relative
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text("OLD STAGED PLATFORM CODE")
        recovery.write_stage(self.root)

    def refresh(self):
        return recovery.refresh_trusted_stage(self.root, self.state, LC)

    def test_old_scripts_are_safely_refreshed_and_backed_up(self):
        report = self.refresh()
        self.assertEqual(report["status"], "staged")
        backup = Path(report["backup"])
        self.assertEqual((backup / "provisioning/versions/v1.0.0/lifecycle/install.sh").read_text(), "OLD STAGED SCRIPT\n")
        self.assertEqual((self.folder / "install.sh").read_bytes(),
                         (LC / "install.sh").read_bytes())
        self.assertEqual(self.data.read_text(), "USER DATA")
        self.assertEqual((self.root / "provisioning/versions/v1.0.0/addons/monitoring.sh").read_bytes(),
                         (REPO / "provisioning/versions/v1.0.0/addons/monitoring.sh").read_bytes())
        self.assertEqual(recovery.inspect(self.root, self.state)["action"], "staged")

    def test_unchanged_bundled_config_is_ignored_in_staged_copy(self):
        (self.root / "config.env").write_bytes((REPO / "config.env").read_bytes())
        self.refresh()
        self.assertFalse((self.root / "config.env").exists())
        self.assertTrue((REPO / "config.env").exists())

    def test_custom_config_is_never_deleted(self):
        (self.root / "config.env").write_text("WEBOPS_ROOT=/apps/custom\nCUSTOM_TOKEN=keep")
        self.refresh()
        self.assertIn("CUSTOM_TOKEN=keep", (self.root / "config.env").read_text())

    def test_invalid_stage_refused_without_overwrite(self):
        (self.root / recovery.STAGE).write_text("INVALID")
        with self.assertRaises(ValueError):
            self.refresh()
        self.assertEqual((self.folder / "install.sh").read_text(), "OLD STAGED SCRIPT\n")

    def test_host_modified_inventory_never_refreshes_stage(self):
        with mock.patch.object(inventory, "command", return_value=""):
            inventory.capture(self.state, self.root, self.base / "system-root")
        inventory.begin_system_changes(self.state)
        with self.assertRaises(ValueError):
            self.refresh()
        self.assertEqual(self.data.read_text(), "USER DATA")

    def test_symlinked_installer_target_refused(self):
        outside = self.base / "other-app"
        outside.write_text("CANNOT CHANGE")
        (self.folder / "install.sh").unlink()
        (self.folder / "install.sh").symlink_to(outside)
        with self.assertRaises(ValueError):
            self.refresh()
        self.assertEqual(outside.read_text(), "CANNOT CHANGE")

    def test_stale_installer_detection_preserves_original_root(self):
        old = (self.folder / "install.sh").read_bytes()
        self.refresh()
        self.assertNotEqual(old, (self.folder / "install.sh").read_bytes())
        self.assertTrue((self.root / inventory.MARKER).is_file())


class FreshInstallConfigTests(unittest.TestCase):
    def test_actual_copy_function_removes_only_git_bundled_default(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            src = base / "source"
            dst = base / "destination"
            lc = src / "provisioning/versions/v1.0.0/lifecycle"
            lc.mkdir(parents=True)
            (lc / "install.sh").write_text("#!/bin/sh\nexit 0\n")
            original = (REPO / "config.env").read_bytes()
            (src / "config.env").write_bytes(original)
            for cmd in (
                ["git", "init", "-q", str(src)],
                ["git", "-C", str(src), "add", "."],
                ["git", "-C", str(src), "-c", "user.name=Test",
                 "-c", "user.email=test@example.test", "commit", "-qm", "baseline"],
            ):
                result = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            script_text = (LC / "install.sh").read_text()
            fn = script_text[script_text.index("copy_to_install_location() {"):
                             script_text.index("validate_environment() {")]
            harness = base / "exercise-copy.sh"
            harness.write_text("""
#!/bin/bash
set -euo pipefail
WEBOPS_INSTALL_ROOT="@@DST@@"
WEBOPS_PLATFORM_DIR="@@SRC@@/provisioning"
WEBOPS_PLATFORM_DIR_NAME=provisioning
WEBOPS_VERSION=v1.0.0
ROLLBACK_BASE_DIR="@@BACKUP@@"
SCRIPT_DIR="@@LC@@"
INSTALL_RECOVER_STAGED=false
log_step() { :; }
log_info() { :; }
log_success() { :; }
log_error() { echo "$*" >&2; }
exec() { echo "READY_TO_CONTINUE"; }
""".replace("@@DST@@", str(dst)).replace("@@SRC@@", str(src))
              .replace("@@BACKUP@@", str(base / "backup"))
              .replace("@@LC@@", str(LC)) + fn + "\ncopy_to_install_location\n")
            r = subprocess.run(["bash", str(harness)], capture_output=True,
                               text=True, timeout=15)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("READY_TO_CONTINUE", r.stdout)
            self.assertFalse((dst / "config.env").exists())
            self.assertTrue((src / "config.env").exists())


if __name__ == "__main__":
    unittest.main()
