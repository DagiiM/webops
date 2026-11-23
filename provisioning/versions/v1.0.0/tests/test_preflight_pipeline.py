"""Ensure read-only prerequisite failures remain safely resumable."""
from pathlib import Path
import os
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/"lib/common.sh"
VALIDATE=ROOT/"setup/validate.sh"
INSTALL=ROOT/"lifecycle/install.sh"
BIN=ROOT/"bin/webops"


class ProductionPreflightTests(unittest.TestCase):
    def bash(self, fragment):
        return subprocess.run(["bash","-c","set -euo pipefail\nsource \""+
                               str(LIB)+"\"\n"+fragment],
                              text=True,capture_output=True,timeout=15)

    def test_https_success_is_enough_even_when_ping_is_blocked(self):
        r=self.bash('ping() { return 1; }\ncurl() { return 0; }\ncheck_internet')
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn("HTTPS connectivity",r.stdout)

    def test_https_failure_is_reported(self):
        r=self.bash('curl() { return 7; }\ncheck_internet')
        self.assertNotEqual(r.returncode,0)
        self.assertIn("HTTPS package/download endpoints",r.stderr)

    def test_dns_uses_getent_without_nslookup(self):
        r=self.bash('getent() { return 0; }\nnslookup() { return 1; }\ncheck_dns')
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_no_fake_systemd_version_check(self):
        s=VALIDATE.read_text()
        self.assertIn("cat /proc/1/comm",s)
        self.assertIn("systemctl list-units",s)
        self.assertNotIn('if ! systemctl --version',s)

    def test_preflight_occurs_before_inventory_system_changes(self):
        s=INSTALL.read_text()
        after=s[s.rindex("main() {"):]
        self.assertLess(after.index("if ! run_installation_preflight"),
                        after.index("installation_inventory.py\" begin"))
        self.assertIn("WEBOPS_PREFLIGHT_VERIFIED=true",s)
        self.assertIn('WEBOPS_PREFLIGHT_VERIFIED:-false',BIN.read_text())

    def test_disk_io_uses_unique_temporary_file(self):
        s=VALIDATE.read_text()
        self.assertIn("mktemp /tmp/webops_io_test.",s)
        self.assertNotIn('local test_file="/tmp/webops_io_test"',s)


if __name__=="__main__":
    unittest.main()
