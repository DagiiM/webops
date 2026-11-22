"""Regression tests for WebOps development quick start on minimal Ubuntu VPSes.

Execute the actual quick-start preflight and dependency bootstrap within
temporary projects with fake Python/venv commands. Never touch the host's
package manager, credentials, or database.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

UPSTREAM = Path(__file__).resolve().parents[1] / "dev" / "quickstart.sh"


class QuickstartBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "webops"
        self.panel = self.root / "control-panel"
        self.panel.mkdir(parents=True)
        self.script = self.root / "provisioning/versions/v1.0.0/dev/quickstart.sh"
        self.script.parent.mkdir(parents=True)
        # Only execute through step 3, before env, migrations and admin setup.
        content = UPSTREAM.read_text()
        content = content[:content.index("# Step 4: Generate .env file if not exists")]
        content += '\nprintf "BOOTSTRAP_COMPLETED\\n"\n'
        self.script.write_text(content)
        self.commands = Path(self.tmp.name) / "bin"
        self.commands.mkdir()
        self.fake_python = self.commands / "python3"
        self.fake_python.write_text("""#!/bin/sh
if [ "$1" = "--version" ]; then echo "Python 3.12.3"; exit 0; fi
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  if [ "$TEST_VENV_FAIL" = 1 ]; then exit 2; fi
  mkdir -p venv/bin
  printf '%s\\n' 'export PATH="$(pwd)/venv/bin:$PATH"' > venv/bin/activate
  cp "$TEST_MOCK_VENV_PYTHON" venv/bin/python
  chmod +x venv/bin/python
  exit 0
fi
echo "Unexpected python3 call: $*" >&2
exit 15
""")
        self.fake_python.chmod(0o755)
        self.venv_python = Path(self.tmp.name) / "venv-python"
        self.venv_python.write_text("""#!/bin/sh
if [ "$1" = "-m" ] && [ "$2" = "pip" ] && [ "$3" = "--version" ]; then
  if [ "$TEST_VENV_PIP_MISSING" = 1 ] && [ ! -e venv/pip-ready ]; then exit 1; fi
  echo "pip 24.0"; exit 0
fi
if [ "$1" = "-m" ] && [ "$2" = "ensurepip" ]; then
  if [ "$TEST_ENSUREPIP_FAIL" = 1 ]; then exit 3; fi
  touch venv/pip-ready
  exit 0
fi
if [ "$1" = "-m" ] && [ "$2" = "pip" ] && [ "$3" = "install" ]; then
  if [ "$TEST_DEP_INSTALL_FAIL" = 1 ] && [ "$4" = "-r" ]; then exit 4; fi
  exit 0
fi
echo "Unexpected venv python call: $*" >&2
exit 17
""")
        self.venv_python.chmod(0o755)
        self.env = os.environ.copy()
        self.env["TEST_MOCK_VENV_PYTHON"] = str(self.venv_python)
        self.env["WEBOPS_SKIP_DEPENDENCY_CHECK"] = "1"
        # No /usr/local/bin: pip3 there must NOT be needed.
        self.env["PATH"] = str(self.commands) + ":/usr/bin:/bin"
        (self.root / ".env").write_text("EXISTING_SECRET=keep\n")
        (self.panel / "db.sqlite3").write_bytes(b"existing database bytes")
        (self.panel / "requirements.txt").write_text("test-package==1\n")

    def run_bootstrap(self, **env_overrides):
        environment = {**self.env, **env_overrides}
        result = subprocess.run(
            ["bash", str(self.script)], env=environment, text=True,
            capture_output=True, timeout=20)
        self.assertEqual((self.root / ".env").read_text(), "EXISTING_SECRET=keep\n")
        self.assertEqual((self.panel / "db.sqlite3").read_bytes(),
                         b"existing database bytes")
        return result

    def test_error_guidance_never_recommends_database_deletion(self):
        content = UPSTREAM.read_text()
        start = content.index("cleanup_on_failure() {")
        end = content.index("trap cleanup_on_failure ERR", start)
        cleanup = content[start:end]
        self.assertNotIn("rm -rf venv", cleanup)
        self.assertNotIn("rm -f control-panel/db.sqlite3", cleanup)
        self.assertNotIn("rm -f ${ENV_FILE}", cleanup)
        self.assertIn("database", cleanup)

    def test_missing_global_pip3_does_not_block_install(self):
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("BOOTSTRAP_COMPLETED", result.stdout)
        self.assertNotIn("Required command not found: pip3", result.stdout)
        self.assertTrue((self.panel / "venv/bin/python").exists())

    def test_missing_venv_pip_is_repaired_without_system_pip(self):
        result = self.run_bootstrap(TEST_VENV_PIP_MISSING="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("pip repaired", result.stdout)
        self.assertTrue((self.panel / "venv/pip-ready").exists())

    def test_missing_venv_package_explains_ubuntu_fix(self):
        result = self.run_bootstrap(TEST_VENV_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sudo apt-get update && sudo apt-get install -y python3-venv",
                      result.stdout)

    def test_missing_ensurepip_fails_safely_without_data_loss(self):
        result = self.run_bootstrap(TEST_VENV_PIP_MISSING="1",
                                    TEST_ENSUREPIP_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot initialize pip", result.stdout)

    def test_failed_dependency_install_preserves_existing_data(self):
        result = self.run_bootstrap(TEST_DEP_INSTALL_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Failed to install dependencies", result.stdout)

    def test_incomplete_venv_is_preserved_on_retry(self):
        broken = self.panel / "venv"
        broken.mkdir()
        (broken / "important-file.txt").write_text("retain this data")
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        old = list(self.panel.glob("venv.incomplete-*/important-file.txt"))
        self.assertEqual(len(old), 1)
        self.assertEqual(old[0].read_text(), "retain this data")

    def test_valid_venv_is_reused(self):
        self.assertEqual(self.run_bootstrap().returncode, 0)
        first = self.panel / "venv/bin/python"
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(first.exists())
        self.assertEqual(list(self.panel.glob("venv.incomplete-*")), [])

    def test_symlinked_venv_is_not_modified(self):
        foreign = Path(self.tmp.name) / "foreign-venv"
        foreign.mkdir()
        (foreign / "valuable.txt").write_text("safe")
        (self.panel / "venv").symlink_to(foreign, target_is_directory=True)
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((foreign / "valuable.txt").read_text(), "safe")
        self.assertFalse((self.panel / "venv").is_symlink())


if __name__ == "__main__":
    unittest.main()
