"""Regression tests for the reversible WebOps platform installation inventory.

No root privileges or actual service/package operations are used: the system
filesystem is rooted under a temporary directory for every test.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "lifecycle" / "installation_inventory.py"
INSTALL = SCRIPT.parent / "install.sh"
UNINSTALL = SCRIPT.parent / "uninstall.sh"
PLATFORM_CLI = SCRIPT.parent.parent / "bin" / "webops"
BASE_SETUP = SCRIPT.parent.parent / "setup" / "base.sh"
spec = importlib.util.spec_from_file_location("webops_install_inventory", SCRIPT)
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class ReversibleInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.system = base / "fake-system"
        self.root = base / "installed" / "webops"
        self.state = base / "private-inventory"
        self.root.mkdir(parents=True)
        (self.root / inventory.MARKER).write_text("v1.0.0")
        self.file = self.root / "provisioning" / "install.sh"
        self.file.parent.mkdir()
        self.file.write_text("WebOps program")
        self.settings = self.system / "etc" / "ssh" / "sshd_config"
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text("PermitRootLogin prohibit-password\n")
        self.fake_command = mock.patch.object(inventory, "command", side_effect=self.command)
        self.fake_command.start()
        self.addCleanup(self.fake_command.stop)

    @staticmethod
    def command(*args):
        if args[0] == "dpkg-query":
            return "nginx\npostgresql-14\n"
        if args[0] == "hostnamectl":
            return "original-host"
        if args[0] == "ufw":
            return "Status: inactive"
        return ""

    def setup_install(self):
        inventory.capture(self.state, self.root, self.system)
        self.settings.write_text("PermitRootLogin yes\n")
        new = self.system / "etc" / "sudoers.d" / "webops"
        new.parent.mkdir(parents=True, exist_ok=True)
        new.write_text("webops ALL=NOPASSWD:ALL")
        data = self.root / "deployments" / "user-app" / "database.sqlite"
        data.parent.mkdir(parents=True)
        data.write_text("KEEP MY DATA")
        inventory.seal(self.state, self.system)
        return new, data

    def test_normal_uninstall_restores_original_config_without_deleting_data(self):
        added, data = self.setup_install()
        report = inventory.plan_or_uninstall(self.state, self.system, apply=True)
        self.assertEqual(self.settings.read_text(), "PermitRootLogin prohibit-password\n")
        self.assertFalse(added.exists())
        self.assertTrue(data.exists())
        self.assertEqual(data.read_text(), "KEEP MY DATA")
        self.assertFalse(self.file.exists())
        self.assertIn("/etc/ssh/sshd_config", report["restored"])
        self.assertTrue(self.root.exists())
        self.assertIn("nginx", inventory.load(self.state)["packages_before"])

    def test_preview_has_no_side_effects(self):
        added, data = self.setup_install()
        report = inventory.plan_or_uninstall(self.state, self.system, apply=False)
        self.assertEqual(self.settings.read_text(), "PermitRootLogin yes\n")
        self.assertTrue(added.exists())
        self.assertTrue(data.exists())
        self.assertTrue(self.file.exists())
        self.assertIn(str(self.file), report["removed"])
        self.assertEqual(inventory.load(self.state)["status"], "sealed")

    def test_user_modified_system_config_is_preserved_and_reported(self):
        self.setup_install()
        self.settings.write_text("PermitRootLogin without-password\n")
        report = inventory.plan_or_uninstall(self.state, self.system, apply=True)
        self.assertEqual(self.settings.read_text(), "PermitRootLogin without-password\n")
        self.assertTrue(any("changed since installation" in x for x in report["preserved"]))

    def test_user_modified_program_file_is_preserved(self):
        self.setup_install()
        self.file.write_text("User customization")
        report = inventory.plan_or_uninstall(self.state, self.system, apply=True)
        self.assertEqual(self.file.read_text(), "User customization")
        self.assertTrue(any("changed since installation" in x for x in report["preserved"]))

    def test_untracked_user_files_are_preserved(self):
        self.setup_install()
        other = self.root / "notes.txt"
        other.write_text("not inventoried")
        inventory.plan_or_uninstall(self.state, self.system, apply=True)
        self.assertEqual(other.read_text(), "not inventoried")

    def test_purge_requires_proven_ownership(self):
        self.setup_install()
        state = inventory.load(self.state)
        state["owned_root"] = False
        inventory.atomic_save(self.state, state)
        with self.assertRaisesRegex(ValueError, "ownership"):
            inventory.plan_or_uninstall(self.state, self.system, apply=True, purge_data=True)
        self.assertTrue((self.root / "deployments").exists())

    def test_explicit_purge_removes_managed_data(self):
        self.setup_install()
        report = inventory.plan_or_uninstall(self.state, self.system, apply=True, purge_data=True)
        self.assertFalse((self.root / "deployments").exists())
        self.assertTrue(any("data purge" in x for x in report["removed"]))

    def test_purge_does_not_follow_a_user_data_symlink(self):
        self.setup_install()
        external = Path(self.temp.name) / "valuable"
        external.mkdir()
        (external / "keep.txt").write_text("safe")
        link = self.root / "backups"
        link.symlink_to(external, target_is_directory=True)
        report = inventory.plan_or_uninstall(self.state, self.system, apply=True, purge_data=True)
        self.assertEqual((external / "keep.txt").read_text(), "safe")
        self.assertTrue(any("(symlink)" in x for x in report["preserved"]))

    def test_managed_directory_restored_from_backup(self):
        directory = self.system / "etc" / "ufw"
        directory.mkdir(parents=True)
        (directory / "user.rules").write_text("prior rules")
        self.setup_install()
        (directory / "user.rules").write_text("installed rules")
        # Re-seal with the simulated installer-applied UFW changes.
        state = inventory.load(self.state)
        state["config"]["/etc/ufw"]["after"] = inventory.signature(directory)
        inventory.atomic_save(self.state, state)
        inventory.plan_or_uninstall(self.state, self.system, apply=True)
        self.assertEqual((directory / "user.rules").read_text(), "prior rules")

    def test_managed_directory_modified_after_install_remains_intact(self):
        directory = self.system / "etc" / "ufw"
        directory.mkdir(parents=True)
        (directory / "user.rules").write_text("prior rules")
        self.setup_install()
        (directory / "user.rules").write_text("operator new rules")
        report = inventory.plan_or_uninstall(self.state, self.system, apply=True)
        self.assertEqual((directory / "user.rules").read_text(), "operator new rules")
        self.assertTrue(any("/etc/ufw" in x for x in report["preserved"]))

    def test_unowned_install_root_is_not_cleaned(self):
        (self.root / inventory.MARKER).unlink()
        self.setup_install()
        inventory.plan_or_uninstall(self.state, self.system, apply=True)
        self.assertTrue(self.file.exists())

    def test_missing_marker_aborts_before_removing_anything(self):
        self.setup_install()
        (self.root / inventory.MARKER).unlink()
        with self.assertRaisesRegex(ValueError, "marker missing"):
            inventory.plan_or_uninstall(self.state, self.system, apply=True)
        self.assertTrue(self.file.exists())
        self.assertEqual(self.settings.read_text(), "PermitRootLogin yes\n")

    def test_inventory_must_be_sealed(self):
        inventory.capture(self.state, self.root, self.system)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            inventory.plan_or_uninstall(self.state, self.system, apply=True)

    def test_capture_cannot_overwrite_previous_installation(self):
        inventory.capture(self.state, self.root, self.system)
        with self.assertRaisesRegex(ValueError, "already exists"):
            inventory.capture(self.state, self.root, self.system)

    def test_second_uninstall_is_rejected(self):
        self.setup_install()
        inventory.plan_or_uninstall(self.state, self.system, apply=True)
        with self.assertRaisesRegex(ValueError, "already been uninstalled"):
            inventory.plan_or_uninstall(self.state, self.system, apply=True)

    def test_root_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            inventory.valid_install_root("/")
        with self.assertRaises(ValueError):
            inventory.valid_install_root("/tmp/something/..")
        with self.assertRaises(ValueError):
            inventory.valid_install_root("relative")

    def test_relative_manifest_path_traversal_rejected(self):
        self.setup_install()
        state = inventory.load(self.state)
        state["tracked_files"]["../../outside"] = "file:any"
        inventory.atomic_save(self.state, state)
        with self.assertRaisesRegex(ValueError, "Unsafe inventory entry"):
            inventory.plan_or_uninstall(self.state, self.system, apply=True)

    def test_simulated_system_never_executes_service_commands_on_uninstall(self):
        self.setup_install()
        with mock.patch.object(inventory.subprocess, "run") as proc:
            inventory.plan_or_uninstall(self.state, self.system, apply=True)
            proc.assert_not_called()

    def test_public_commands_use_safe_guards(self):
        text = UNINSTALL.read_text()
        self.assertIn("installation-inventory", text)
        self.assertIn("--confirm-purge", text)
        self.assertNotIn("apt-get remove", text)
        self.assertNotIn("rm -rf", text)
        install = INSTALL.read_text()
        self.assertIn('if [[ -e "$target_root" ]]', install)
        self.assertIn("installation_inventory.py", install)
        self.assertLess(install.index("prepare_rollback_snapshot\n", install.index("main() {", 0) if False else
                                      install.rindex("main() {")),
                        install.index("    apply_hostname\n", install.rindex("main() {")))

    def test_platform_cli_uninstall_uses_lifecycle_script_before_state_creation(self):
        content = PLATFORM_CLI.read_text()
        self.assertIn('if [[ "$command" == "uninstall"', content)
        self.assertIn('exec "${SCRIPT_DIR}/../lifecycle/uninstall.sh" "$@"', content)
        self.assertLess(content.index('exec "${SCRIPT_DIR}/../lifecycle/uninstall.sh"'),
                        content.index('ensure_directory "${WEBOPS_PLATFORM}/versions"',
                                      content.rindex('main() {')))

    def test_firewall_setup_does_not_reset_existing_rules(self):
        content = BASE_SETUP.read_text()
        self.assertNotIn("ufw --force reset", content)
        self.assertNotIn("firewall-cmd --set-default-zone=public", content)
        self.assertIn("Existing active UFW detected", content)
        self.assertIn("Existing active firewalld detected", content)

    def test_missing_inventory_cli_fails_closed(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "uninstall", "--state-dir",
             str(self.state), "--system-root", str(self.system)],
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error", result.stderr.lower())

    def test_corrupt_backup_refuses_every_change(self):
        self.setup_install()
        backup = self.state / "originals"
        prior = inventory.load(self.state)
        index = prior["config"]["/etc/ssh/sshd_config"]["backup"]
        (backup / index).write_text("corrupted")
        with self.assertRaisesRegex(ValueError, "corrupted"):
            inventory.plan_or_uninstall(self.state, self.system, apply=True)
        self.assertEqual(self.settings.read_text(), "PermitRootLogin yes\n")
        self.assertTrue(self.file.exists())

    def test_untracked_sibling_outside_owned_root_survives(self):
        self.setup_install()
        outside = self.root.parent / "another-project" / "app.txt"
        outside.parent.mkdir()
        outside.write_text("unrelated")
        inventory.plan_or_uninstall(self.state, self.system, apply=True, purge_data=True)
        self.assertEqual(outside.read_text(), "unrelated")

    def test_config_not_touched_by_installer_stays_intact(self):
        unchanged = self.system / "etc" / "fstab"
        unchanged.parent.mkdir(parents=True, exist_ok=True)
        unchanged.write_text("original mount\\n")
        self.setup_install()
        report = inventory.plan_or_uninstall(self.state, self.system, apply=True)
        self.assertEqual(unchanged.read_text(), "original mount\\n")
        self.assertNotIn("/etc/fstab", report["restored"])

    def test_symlinked_program_file_removes_link_not_target(self):
        target = Path(self.temp.name) / "unrelated.txt"
        target.write_text("external file")
        link = self.root / "link"
        link.symlink_to(target)
        self.setup_install()
        inventory.plan_or_uninstall(self.state, self.system, apply=True)
        self.assertFalse(link.is_symlink())
        self.assertEqual(target.read_text(), "external file")

    def test_ownership_requires_marker_at_capture(self):
        (self.root / inventory.MARKER).unlink()
        captured = inventory.capture(self.state, self.root, self.system)
        self.assertFalse(captured["owned_root"])
        self.assertEqual(captured["status"], "captured")

    def test_preview_and_actual_command_line_in_sandbox(self):
        self.setup_install()
        command = [sys.executable, str(SCRIPT), "plan", "--state-dir",
                   str(self.state), "--system-root", str(self.system)]
        preview = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(json.loads(preview.stdout)["restored"][0], "/etc/ssh/sshd_config")
        self.assertTrue(self.file.exists())
        command[2] = "uninstall"
        remove = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(remove.returncode, 0, remove.stderr)
        self.assertFalse(self.file.exists())

    def test_no_untracked_file_is_deleted_on_purge(self):
        self.setup_install()
        custom = self.root / "custom-file-created-later"
        custom.write_text("retain")
        inventory.plan_or_uninstall(self.state, self.system, apply=True, purge_data=True)
        self.assertEqual(custom.read_text(), "retain")

    def test_unknown_install_state_is_rejected(self):
        self.setup_install()
        data = inventory.load(self.state)
        data["status"] = "suspicious"
        inventory.atomic_save(self.state, data)
        with self.assertRaisesRegex(ValueError, "Invalid"):
            inventory.plan_or_uninstall(self.state, self.system, apply=True)



if __name__ == "__main__":
    unittest.main()
