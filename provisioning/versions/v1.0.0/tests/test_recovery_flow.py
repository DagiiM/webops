"""Preflight-only self-healing installer tests; run with no actual system changes."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

VERSION = Path(__file__).resolve().parents[1]
LIFECYCLE = VERSION / "lifecycle"
RECOVERY = LIFECYCLE / "installation_recovery.py"
INVENTORY = LIFECYCLE / "installation_inventory.py"
INSTALL = LIFECYCLE / "install.sh"
sys.path.insert(0, str(LIFECYCLE))
try:
    import installation_recovery as recovery
    import installation_inventory as inventory
finally:
    sys.path.remove(str(LIFECYCLE))


class SmartInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / "install" / "webops"
        self.state = base / "backup" / "installation-inventory"
        self.fake_system = base / "etc"
        self.source_root = base / "source"
        self.source_version = self.source_root / "provisioning" / "versions" / "v1.0.0"
        self.source_lifecycle = self.source_version / "lifecycle"
        self.source_lifecycle.mkdir(parents=True)
        shutil.copy2(INVENTORY, self.source_lifecycle / INVENTORY.name)
        shutil.copy2(RECOVERY, self.source_lifecycle / RECOVERY.name)

    def make_root(self, marker=True, stage=False):
        script = self.root / "provisioning/versions/v1.0.0/lifecycle/install.sh"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("#!/bin/sh\nprintf 'DELEGATED:%s\n' \"$*\"\n")
        script.chmod(0o755)
        if marker:
            (self.root / inventory.MARKER).write_text("v1.0.0\n")
        if stage:
            recovery.write_stage(self.root)
        return script

    def capture(self, status="captured", phase="baseline-captured"):
        with mock.patch.object(inventory, "command", return_value=""):
            inventory.capture(self.state, self.root, self.fake_system)
            if status == "sealed":
                inventory.seal(self.state, self.fake_system)
            elif status == "removed":
                data = inventory.load(self.state)
                data["status"] = "removed"
                inventory.atomic_save(self.state, data)
            elif phase != "baseline-captured":
                inventory.begin_system_changes(self.state)

    def inspect(self):
        return recovery.inspect(self.root, self.state)["action"]

    def test_fresh_target(self):
        self.assertEqual(self.inspect(), "fresh")

    def test_new_staged_root(self):
        self.make_root(stage=True)
        self.assertEqual(self.inspect(), "staged")

    def test_legacy_root_with_marker_but_no_stage_is_not_guessed(self):
        self.make_root()
        self.assertEqual(self.inspect(), "manual")

    def test_foreign_directory_rejected(self):
        self.make_root(marker=False)
        self.assertEqual(self.inspect(), "manual")

    def test_symlink_target_rejected(self):
        external = Path(self.tmp.name) / "external"
        external.mkdir()
        self.root.parent.mkdir(parents=True)
        self.root.symlink_to(external, target_is_directory=True)
        self.assertEqual(self.inspect(), "unsafe")

    def test_staged_file_with_unexpected_root_cannot_replay(self):
        self.make_root(stage=True)
        stage = self.root / recovery.STAGE
        data = json.loads(stage.read_text())
        data["target"] = "/tmp/somebody-elses-tree"
        stage.write_text(json.dumps(data))
        self.assertEqual(self.inspect(), "manual")

    def test_staged_file_corrupted_cannot_replay(self):
        self.make_root(stage=True)
        (self.root / recovery.STAGE).write_text("{unfinished json")
        self.assertEqual(self.inspect(), "manual")

    def test_inventory_verified_resume(self):
        self.make_root()
        self.capture()
        self.assertEqual(self.inspect(), "resume")

    def test_inventory_system_changes_started_require_repair(self):
        self.make_root(stage=True)
        self.capture(phase="system-changes-started")
        self.assertEqual(self.inspect(), "repair")

    def direct_installed_root_reentry(self):
        lifecycle = self.root / "provisioning/versions/v1.0.0/lifecycle"
        shutil.copy2(RECOVERY, lifecycle / "installation_recovery.py")
        shutil.copy2(INVENTORY, lifecycle / "installation_inventory.py")
        source = INSTALL.read_text().replace(
            'readonly ROLLBACK_BASE_DIR="/var/backups/webops-install"',
            'readonly ROLLBACK_BASE_DIR="' + str(self.state.parent) + '"')
        source = source[:source.rindex('main "$@"')]
        source += "\ncopy_to_install_location\n"
        script = self.root / "provisioning/versions/v1.0.0/lifecycle/direct-reentry.sh"
        script.write_text(source)
        return subprocess.run(["bash", str(script)], env=self.env(),
                              capture_output=True, text=True, timeout=10)

    def test_direct_rerun_of_verified_install_is_no_op(self):
        self.make_root()
        self.capture(status="sealed")
        result = self.direct_installed_root_reentry()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already installed", result.stdout)
        self.assertEqual(inventory.load(self.state)["status"], "sealed")

    def test_direct_rerun_of_partial_install_requires_repair(self):
        self.make_root()
        self.capture(phase="system-changes-started")
        important = self.root / "database.sqlite"
        important.write_text("KEEP DATA")
        result = self.direct_installed_root_reentry()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("needs operator review", result.stderr)
        self.assertEqual(important.read_text(), "KEEP DATA")

    def test_legacy_sealed_without_health_proof_requires_repair(self):
        self.make_root()
        self.capture(status="sealed")
        data = inventory.load(self.state)
        data.pop("health_verified_at", None)
        inventory.atomic_save(self.state, data)
        self.assertEqual(self.inspect(), "repair")
        result = self.execute_handoff()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"action": "repair"', result.stderr)

    def test_failed_health_does_not_retry_unsafe_partial_install(self):
        self.make_root()
        self.capture(phase="system-changes-started")
        status = recovery.inspect(self.root, self.state)
        self.assertEqual(status["action"], "repair")
        result = self.execute_handoff()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("DELEGATED", result.stdout)

    def test_inventory_sealed_means_skip_duplicate_install(self):
        self.make_root()
        self.capture(status="sealed")
        self.assertEqual(self.inspect(), "installed")

    def test_inventory_removed_is_not_automatically_reinstalled(self):
        self.make_root()
        self.capture(status="removed")
        self.assertEqual(self.inspect(), "manual")

    def test_wrong_root_inventory_is_not_used(self):
        self.make_root()
        self.capture()
        data = inventory.load(self.state)
        data["install_root"] = str(Path(self.tmp.name) / "another")
        inventory.atomic_save(self.state, data)
        self.assertEqual(self.inspect(), "manual")

    def test_copy_stage_before_system_changes_then_advance(self):
        self.make_root(stage=True)
        userfile = self.root / "config.env"
        userfile.write_text("TOKEN=keep\n")
        recovery.advance_stage(self.root)
        self.assertEqual(self.inspect(), "manual")
        self.assertEqual(userfile.read_text(), "TOKEN=keep\n")

    def test_duplicate_stage_write_fails_closed(self):
        self.make_root(stage=True)
        with self.assertRaisesRegex(ValueError, "already exists"):
            recovery.write_stage(self.root)

    def test_doctor_from_source_is_read_only(self):
        self.make_root()
        self.make_harness(doctor=True)
        cmd = [str(self.source_lifecycle / "test-install.sh"), "--doctor"]
        result = subprocess.run(["bash", *cmd], capture_output=True, text=True,
                                env=self.env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["action"], "manual")
        self.assertFalse((self.state / "inventory.json").exists())

    def env(self):
        env = os.environ.copy()
        env["WEBOPS_INSTALL_ROOT"] = str(self.root)
        env.pop("WEBOPS_ALREADY_RELOCATED", None)
        env.pop("WEBOPS_NEW_INSTALL_COPY", None)
        return env

    def make_harness(self, doctor=False, recover=False):
        # Execute the real entrypoint preflight functions with an isolated
        # destination and a harmless installed-script stand-in.
        src = INSTALL.read_text()
        src = src.replace(
            'readonly ROLLBACK_BASE_DIR="/var/backups/webops-install"',
            'readonly ROLLBACK_BASE_DIR="' + str(self.state.parent) + '"')
        src = src[:src.rindex('main "$@"')]
        src += ('\nmain "$@"\n' if doctor else
                ('\nINSTALL_RECOVER_STAGED=true\n' if recover else '') +
                '\ncopy_to_install_location\n')
        harness = self.source_lifecycle / "test-install.sh"
        harness.write_text(src)
        return harness

    def execute_handoff(self, recover=False, answer=None):
        harness = self.make_harness(recover=recover)
        env = self.env()
        if recover:
            # Isolate service checks from the Runpod host.
            mocked_bin = Path(self.tmp.name) / "fake-systemctl-bin"
            mocked_bin.mkdir(exist_ok=True)
            shim = mocked_bin / "systemctl"
            shim.write_text("#!/bin/sh\necho inactive\n")
            shim.chmod(0o755)
            env["PATH"] = str(mocked_bin) + os.pathsep + env["PATH"]
        return subprocess.run(["bash", str(harness)], env=env,
                              input=answer, capture_output=True, text=True)

    def test_staged_retry_delegates_without_overwrite(self):
        self.make_root(stage=True)
        keep = self.root / "config.env"
        keep.write_text("KEEP=secret\n")
        result = self.execute_handoff()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DELEGATED:", result.stdout)
        self.assertEqual(keep.read_text(), "KEEP=secret\n")

    def test_verified_resume_delegates_to_installed_script(self):
        self.make_root()
        self.capture()
        result = self.execute_handoff()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DELEGATED:--resume", result.stdout)

    def test_completed_install_does_not_run_installer_again(self):
        self.make_root()
        self.capture(status="sealed")
        result = self.execute_handoff()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("DELEGATED", result.stdout)
        self.assertIn("already installed", result.stdout)

    def test_old_untracked_stage_does_not_overwrite(self):
        self.make_root()
        important = self.root / "database.db"
        important.write_text("important")
        result = self.execute_handoff()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(important.read_text(), "important")
        self.assertIn("Legacy staged install has no trusted prior baseline", result.stderr)

    def test_half_applied_install_does_not_replay(self):
        self.make_root()
        self.capture(phase="system-changes-started")
        result = self.execute_handoff()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"action": "repair"', result.stderr)

    def test_guarded_adoption_preserves_config_and_backs_up_original_script(self):
        installed = self.make_root()
        original = installed.read_bytes()
        config = self.root / "config.env"
        config.write_bytes(b"API_TOKEN=secret\n")
        fresh = self.source_lifecycle / "install.sh"
        fresh.write_text("#!/bin/sh\necho DELEGATED-NEW\n")
        result = recovery.adopt_staged(self.root, self.state,
                                       self.source_lifecycle, self.fake_system)
        self.assertEqual(self.inspect(), "staged")
        self.assertEqual(config.read_bytes(), b"API_TOKEN=secret\n")
        self.assertEqual((Path(result["backup"]) / "install.sh").read_bytes(), original)
        self.assertEqual(installed.read_bytes(), fresh.read_bytes())
        self.assertFalse((self.state / "inventory.json").exists())

    def test_guarded_adoption_rejects_existing_webops_service(self):
        self.make_root()
        service = self.fake_system / "etc/systemd/system/webops-web.service"
        service.parent.mkdir(parents=True)
        service.write_text("existing webops service")
        with self.assertRaisesRegex(ValueError, "system modifications"):
            recovery.adopt_staged(self.root, self.state,
                                  self.source_lifecycle, self.fake_system)
        self.assertEqual(self.inspect(), "manual")

    def test_guarded_adoption_rejects_existing_user_data(self):
        self.make_root()
        (self.root / "deployments").mkdir()
        with self.assertRaisesRegex(ValueError, "managed state"):
            recovery.legacy_preflight_check(self.root, self.state, self.fake_system)

    def test_guarded_adoption_rejects_existing_inventory(self):
        self.make_root()
        self.capture()
        with self.assertRaises(ValueError):
            recovery.legacy_preflight_check(self.root, self.state, self.fake_system)

    def test_legacy_recovery_cancel_is_no_op(self):
        original = self.make_root()
        old = original.read_bytes()
        result = self.execute_handoff(recover=True, answer="no\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(original.read_bytes(), old)
        self.assertEqual(self.inspect(), "manual")

    def test_legacy_recovery_requires_explicit_confirmation(self):
        self.make_root()
        installed = self.source_lifecycle / "install.sh"
        installed.write_text("#!/bin/sh\necho DELEGATED-NEW\n")
        result = self.execute_handoff(recover=True, answer="RECOVER PREFLIGHT COPY\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DELEGATED-NEW", result.stdout)
        self.assertEqual(self.inspect(), "staged")

    def test_recovery_option_refuses_nonexistent_root(self):
        result = self.execute_handoff(recover=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.root.exists())

    def test_first_install_records_stage_before_handoff(self):
        source_script = self.source_lifecycle / "install.sh"
        source_script.write_text("#!/bin/sh\necho FIRST-HANDOFF\n")
        source_script.chmod(0o755)
        result = self.execute_handoff()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FIRST-HANDOFF", result.stdout)
        self.assertEqual(self.inspect(), "staged")
        self.assertTrue((self.root / inventory.MARKER).is_file())

    def test_recovery_rejects_mismatched_configured_root(self):
        self.make_root()
        (self.root / "config.env").write_text("WEBOPS_ROOT=/other/instance\n")
        with self.assertRaisesRegex(ValueError, "different installation root"):
            recovery.legacy_preflight_check(self.root, self.state, self.fake_system)

    def test_recovery_rejects_symlinked_configuration(self):
        self.make_root()
        external = Path(self.tmp.name) / "shared-config"
        external.write_text("WEBOPS_ROOT=/opt/webops\n")
        (self.root / "config.env").symlink_to(external)
        with self.assertRaisesRegex(ValueError, "Symlinked"):
            recovery.legacy_preflight_check(self.root, self.state, self.fake_system)

    def test_recovery_rejects_preexisting_platform_state(self):
        self.make_root()
        path = self.root / "provisioning/.install_state"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("INSTALL_STAGE=installed")
        with self.assertRaisesRegex(ValueError, "managed state"):
            recovery.legacy_preflight_check(self.root, self.state, self.fake_system)

    def test_different_unrelated_tree_does_not_become_install(self):
        self.make_root(marker=False)
        result = self.execute_handoff()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.inspect(), "manual")


if __name__ == "__main__":
    unittest.main()
