import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import SimpleTestCase
from apps.services.recovery import create_snapshot, verify_snapshot, stage_restore
from apps.services.background.sqlite_adapter import SQLiteBackgroundProcessor

class RecoveryTests(SimpleTestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.control = self.root / "control.sqlite3"
        with sqlite3.connect(self.control) as db:
            db.execute("CREATE TABLE records(id INTEGER PRIMARY KEY, value TEXT)")
            db.execute("INSERT INTO records VALUES(1,'fixture')")
        self.queue = SQLiteBackgroundProcessor(self.root / "jobs.sqlite3", {"deploy": lambda pk: pk})
        self.queue.submit("deploy", 1)
        self.queue.claim()
        self.queue.submit("deploy", 2)
        self.queue.heartbeat()

    def backup(self):
        return create_snapshot(self.control, self.queue.path, self.root / "backups")

    def test_restore_quarantines_jobs_and_preserves_live_state(self):
        path = self.backup()
        self.assertEqual(verify_snapshot(path)["version"], 1)
        restored, count = stage_restore(path, self.root / "restore")
        self.assertEqual(count, 2)
        with sqlite3.connect(restored / "control.sqlite3") as db:
            self.assertEqual(db.execute("SELECT value FROM records").fetchone()[0], "fixture")
        with sqlite3.connect(restored / "jobs.sqlite3") as db:
            self.assertEqual(db.execute("SELECT DISTINCT state FROM jobs").fetchall(), [("failed",)])
            self.assertEqual(db.execute("SELECT count(*) FROM worker").fetchone()[0], 0)
        self.assertEqual(self.queue.get_status()["pending_tasks"], 1)
        self.assertEqual(self.queue.get_status()["running_tasks"], 1)

    def test_corruption_is_rejected(self):
        path = self.backup()
        with (path / "control.sqlite3").open("ab") as f:
            f.write(b"corrupt")
        with self.assertRaises(ValueError):
            verify_snapshot(path)
        with self.assertRaises(ValueError):
            stage_restore(path, self.root / "restore")

    def test_private_permissions_and_no_overwrite(self):
        path = self.backup()
        second = self.backup()
        self.assertNotEqual(path, second)
        self.assertEqual(path.stat().st_mode & 0o777, 0o700)
        self.assertEqual((path / "control.sqlite3").stat().st_mode & 0o777, 0o600)

    def test_reject_symlink(self):
        path = self.backup()
        (path / "jobs.sqlite3").unlink()
        (path / "jobs.sqlite3").symlink_to(self.queue.path)
        with self.assertRaises(ValueError):
            verify_snapshot(path)
