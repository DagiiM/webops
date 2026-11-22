"""Health-check contracts with harmless command shims for Runpod and CI."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

INSTALL = Path(__file__).resolve().parents[1] / "lifecycle" / "install.sh"


class HealthCheckContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        mocks = {
            "systemctl": '#!/bin/sh\nexit "${TEST_SYSTEMCTL_EXIT:-0}"\n',
            "redis-cli": '#!/bin/sh\nexit "${TEST_REDIS_EXIT:-0}"\n',
            "sudo": '#!/bin/sh\nexit "${TEST_POSTGRES_EXIT:-0}"\n',
            "ss": '#!/bin/sh\nif [ "${TEST_PORT_OPEN:-yes}" = "yes" ]; then echo "LISTEN 0 128 0.0.0.0:8000 0.0.0.0:*"; else echo "LISTEN 0 128 0.0.0.0:5000 0.0.0.0:*"; fi\n',
        }
        for name, code in mocks.items():
            path = self.bin / name
            path.write_text(code)
            path.chmod(0o755)
        script = INSTALL.read_text()
        script = script[:script.rindex('main "$@"')]
        script += '\nif verify_installation; then echo VERIFIED; else echo UNHEALTHY; exit 1; fi\n'
        self.script = self.root / "check-health.sh"
        self.script.write_text(script)

    def check(self, **overrides):
        env = os.environ.copy()
        env.update(overrides)
        env["PATH"] = str(self.bin) + os.pathsep + env["PATH"]
        return subprocess.run(["bash", str(self.script)], env=env, text=True,
                              capture_output=True, timeout=10)

    def test_all_service_network_checks_pass(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("VERIFIED", result.stdout)
        self.assertIn("(9/9)", result.stdout)

    def test_stopped_service_rejects_install(self):
        result = self.check(TEST_SYSTEMCTL_EXIT="3")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("UNHEALTHY", result.stdout)

    def test_unresponsive_redis_rejects_install(self):
        result = self.check(TEST_REDIS_EXIT="1")
        self.assertNotEqual(result.returncode, 0)

    def test_unavailable_postgres_rejects_install(self):
        result = self.check(TEST_POSTGRES_EXIT="1")
        self.assertNotEqual(result.returncode, 0)

    def test_missing_control_panel_listener_rejects_install(self):
        result = self.check(TEST_PORT_OPEN="no")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("UNHEALTHY", result.stdout)


if __name__ == "__main__":
    unittest.main()
