"""Managed databases: validation and safety rules (always run) and real engine lifecycles (run when possible).

The lifecycle tests start real PostgreSQL / Redis servers, which refuse to run as root, so they are skipped
for root and when the server software is missing.
"""
import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock, skipIf

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.databases import provisioner as pv
from apps.databases.models import Database

User = get_user_model()


class Base(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wo-managed-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.override = override_settings(WEBOPS_DATABASES_ROOT=str(self.tmp))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.user = User.objects.create_user("owner", "o@example.com", "pw-123456-x")

    def make(self, name="shop", kind="postgresql", **kw):
        port = None if kind == "sqlite" else pv.allocate_port()
        return Database.objects.create(name=name, db_type=kind, managed=True, created_by=self.user, port=port, **kw)


class RulesTests(Base):
    def test_slug(self):
        self.assertEqual(pv.slug("My-Shop_1"), "my_shop_1")
        for bad in ("", "a", "1abc", "has space", "a" * 31, "semi;colon", "../etc", "naïve", None, 5, "x'y"):
            with self.assertRaises(pv.ProvisionError, msg=repr(bad)):
                pv.slug(bad)

    def test_instance_dir_is_derived_from_id_and_stays_inside_root(self):
        db = self.make("shop")
        d = pv.instance_dir(db)
        self.assertEqual(d, (self.tmp / f"{db.pk}-shop").resolve())
        self.assertTrue(d.is_relative_to(self.tmp.resolve()))

    def test_ports_are_in_range_unique_and_loopback_free(self):
        a, b = self.make("one"), self.make("two")
        self.assertNotEqual(a.port, b.port)
        for p in (a.port, b.port):
            self.assertTrue(pv.PORT_RANGE[0] <= p <= pv.PORT_RANGE[1])

    def test_port_in_use_is_skipped(self):
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            busy = s.getsockname()[1]
            with mock.patch.object(pv, "PORT_RANGE", (busy, busy + 1)):
                self.assertEqual(pv.allocate_port(), busy + 1)

    def test_limits(self):
        for i in range(pv.MAX_PER_USER):
            self.make(f"db{i}", "sqlite")
        ok, why = pv.can_deploy(self.user)
        self.assertFalse(ok)
        self.assertIn(str(pv.MAX_PER_USER), why)
        staff = User.objects.create_user("boss", "b@example.com", "pw-123456-x", is_staff=True)
        self.assertTrue(pv.can_deploy(staff)[0])
        with mock.patch.object(pv, "MAX_PER_HOST", 1):
            self.assertFalse(pv.can_deploy(staff)[0])

    def test_engine_info_reports_missing_software_with_a_hint(self):
        with mock.patch.object(pv, "_pg_bin", return_value=None), mock.patch.object(pv, "_redis_bin", return_value=None):
            info = pv.engine_info()
        self.assertFalse(info["postgresql"]["available"])
        self.assertIn("apt-get install postgresql", info["postgresql"]["hint"])
        self.assertFalse(info["redis"]["available"])
        self.assertTrue(info["sqlite"]["available"])

    def test_provision_refuses_when_engine_missing(self):
        db = self.make("shop")
        with mock.patch.object(pv, "_pg_bin", return_value=None):
            with self.assertRaises(pv.ProvisionError) as cm:
                pv.provision(db)
        self.assertIn("not installed", str(cm.exception))
        self.assertFalse(any(self.tmp.iterdir()))          # nothing left behind

    def test_unsupported_type_refused(self):
        db = self.make("shop", "mysql")
        with self.assertRaises(pv.ProvisionError):
            pv.provision(db)

    def test_password_never_in_argv_or_errors(self):
        db = self.make("shop")
        seen = []

        def fake_run(argv, *a, **k):
            seen.append(list(argv))
            return mock.Mock(returncode=1, stdout="", stderr="boom")
        with mock.patch.object(pv, "_pg_bin", side_effect=lambda n: "/bin/" + n), \
             mock.patch.object(pv.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(pv.secrets, "token_urlsafe", return_value="SECRET-PASSWORD-123"):
            with self.assertRaises(pv.ProvisionError) as cm:
                pv.provision(db)
        self.assertNotIn("SECRET-PASSWORD-123", str(cm.exception))
        self.assertTrue(seen)
        self.assertFalse(any("SECRET-PASSWORD-123" in a for argv in seen for a in argv))
        init = next(argv for argv in seen if argv[0].endswith("initdb"))
        self.assertTrue(any(a.startswith("--pwfile=") for a in init))
        self.assertFalse((pv.instance_dir(db) / ".pw").exists())       # password file removed
        self.assertFalse(pv.instance_dir(db).exists())                  # failed provision cleaned up

    def test_servers_bind_loopback_only(self):
        db = self.make("shop")
        self.assertIn("listen_addresses=127.0.0.1", pv._pg_options(db, self.tmp))
        self.assertIn("bind 127.0.0.1\n", pv._redis_conf(db, self.tmp, "pw"))
        self.assertIn("requirepass", pv._redis_conf(db, self.tmp, "pw"))

    def test_destroy_stays_in_its_directory_and_refuses_symlinks(self):
        db = self.make("shop", "sqlite")
        other = self.tmp / "precious"
        other.mkdir()
        (other / "keep.txt").write_text("x")
        d = pv.instance_dir(db)
        d.symlink_to(other)
        with self.assertRaises(pv.ProvisionError):
            pv.destroy(db)
        self.assertTrue((other / "keep.txt").exists())

    def test_connection_url_quotes_password(self):
        from apps.core.utils import encrypt_password
        db = self.make("shop", host="127.0.0.1", username="shop_user", database_name="shop", password=encrypt_password("a/b@c:d"))
        url = pv.connection_url(db)
        self.assertEqual(url, f"postgresql://shop_user:a%2Fb%40c%3Ad@127.0.0.1:{db.port}/shop")


class SqliteLifecycle(Base):
    def test_full_lifecycle(self):
        db = self.make("notes", "sqlite")
        pv.provision(db)
        db.refresh_from_db()
        self.assertTrue(Path(db.database_name).is_file())
        self.assertEqual(oct(Path(db.database_name).stat().st_mode & 0o777), "0o600")
        self.assertEqual(pv.status(db), "running")
        self.assertTrue(pv.check(db)[0])
        self.assertEqual(pv.connection_url(db), "sqlite:///" + db.database_name)
        pv.destroy(db)
        self.assertEqual(pv.status(db), "missing")
        self.assertFalse(pv.instance_dir(db).exists())


def _can_run_servers():
    return os.geteuid() != 0


@skipIf(not _can_run_servers(), "database servers cannot run as root")
class PostgresLifecycle(Base):
    def setUp(self):
        super().setUp()
        if not pv.engine_info()["postgresql"]["available"]:
            self.skipTest("PostgreSQL server software not installed")

    def test_full_lifecycle(self):
        db = self.make("shop")
        self.addCleanup(lambda: pv.destroy(db, missing_ok=True))
        pv.provision(db)
        db.refresh_from_db()
        self.assertEqual((db.host, db.username, db.database_name), ("127.0.0.1", "shop_user", "shop"))
        self.assertNotIn(pv._password(db), db.password)               # stored encrypted
        self.assertEqual(pv.status(db), "running")
        ok, msg = pv.check(db)
        self.assertTrue(ok, msg)
        # real client, real data
        conn = pv._pg_connect(db, pv._password(db), "shop")
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("CREATE TABLE t(a int)")
        cur.execute("INSERT INTO t VALUES (42)")
        conn.close()
        # wrong password is refused
        import psycopg2
        with self.assertRaises(psycopg2.OperationalError):
            pv._pg_connect(db, "wrong", "shop")
        # stop / start / data survives
        pv.stop(db)
        self.assertEqual(pv.status(db), "stopped")
        self.assertFalse(pv.check(db)[0])
        pv.start(db)
        conn = pv._pg_connect(db, pv._password(db), "shop")
        cur = conn.cursor()
        cur.execute("SELECT a FROM t")
        self.assertEqual(cur.fetchone()[0], 42)
        conn.close()
        pv.restart(db)
        self.assertEqual(pv.status(db), "running")
        # reconcile restarts a stopped instance
        pv.stop(db)
        self.assertIn(("shop", "started"), pv.reconcile())
        self.assertEqual(pv.status(db), "running")
        # destroy
        port = db.port
        pv.destroy(db)
        self.assertFalse(pv._port_open(port))
        self.assertEqual(pv.status(db), "missing")


@skipIf(not _can_run_servers(), "database servers cannot run as root")
class RedisLifecycle(Base):
    def setUp(self):
        super().setUp()
        if not pv.engine_info()["redis"]["available"]:
            self.skipTest("Redis server software not installed")

    def test_full_lifecycle(self):
        db = self.make("cache", "redis")
        self.addCleanup(lambda: pv.destroy(db, missing_ok=True))
        pv.provision(db)
        db.refresh_from_db()
        pw = pv._password(db)
        self.assertEqual(pv.status(db), "running")
        ok, msg = pv.check(db)
        self.assertTrue(ok, msg)
        # unauthenticated access is refused
        self.assertTrue(pv._redis_talk(db.port, "", "PING").startswith("-NOAUTH"))
        self.assertEqual(pv._redis_talk(db.port, pw, "SET", "k", "v"), "+OK")
        pv.restart(db)
        self.assertEqual(pv._redis_talk(db.port, pw, "DBSIZE"), ":1")        # persisted across restart
        mode = oct((pv.instance_dir(db) / "redis.conf").stat().st_mode & 0o777)
        self.assertEqual(mode, "0o600")
        port = db.port
        pv.destroy(db)
        self.assertFalse(pv._port_open(port))


class BackupBase(Base):
    def setUp(self):
        super().setUp()
        self.backups = Path(tempfile.mkdtemp(prefix="wo-backups-"))
        self.addCleanup(shutil.rmtree, self.backups, True)
        override = override_settings(WEBOPS_DATABASE_BACKUP_DIR=str(self.backups))
        override.enable()
        self.addCleanup(override.disable)

    def wipe_local_disk(self, db):
        """What a pod restart does: instance files vanish, backups (on the persistent volume) stay."""
        pv.destroy(db, missing_ok=True, keep_backups=True)
        self.assertEqual(pv.status(db), "missing")


class BackupRules(BackupBase):
    def test_backup_dir_is_derived_and_inside_backup_root(self):
        db = self.make("shop")
        self.assertEqual(pv.backup_dir(db), (self.backups / f"{db.pk}-shop").resolve())

    def test_backup_requires_a_running_instance(self):
        db = self.make("shop")
        with self.assertRaises(pv.ProvisionError):
            pv.backup(db)

    def test_restore_without_a_backup_is_an_error_not_a_silent_empty_database(self):
        db = self.make("notes", "sqlite")
        with self.assertRaises(pv.ProvisionError):
            pv.restore_missing(db)
        self.assertIn(("notes", "failed: The database's files are missing and there is no backup to restore from."),
                      pv.reconcile())

    def test_restore_does_nothing_when_files_exist(self):
        db = self.make("notes", "sqlite")
        pv.provision(db)
        self.assertFalse(pv.restore_missing(db))

    def test_destroy_removes_backups_unless_kept(self):
        db = self.make("notes", "sqlite")
        pv.provision(db)
        pv.backup(db)
        pv.destroy(db, keep_backups=True)
        self.assertEqual(len(pv.backups(db)), 1)
        pv.destroy(db)
        self.assertFalse(pv.backup_dir(db).exists())


class SqliteBackup(BackupBase):
    def test_backup_prune_wipe_and_restore(self):
        import sqlite3
        db = self.make("notes", "sqlite")
        pv.provision(db)
        db.refresh_from_db()
        conn = sqlite3.connect(db.database_name)
        conn.execute("CREATE TABLE t(a int)")
        conn.execute("INSERT INTO t VALUES (7)")
        conn.commit()
        conn.close()
        with mock.patch.object(pv.time, "strftime", side_effect=[f"2026010{i}T000000Z" for i in range(1, 9)]):
            for _ in range(pv.KEEP_BACKUPS + 2):
                pv.backup(db)
        self.assertEqual(len(pv.backups(db)), pv.KEEP_BACKUPS)                  # old ones pruned
        self.assertEqual(oct(pv.backup_dir(db).stat().st_mode & 0o777), "0o700")
        self.wipe_local_disk(db)
        self.assertIn(("notes", "restored from backup"), pv.reconcile())
        conn = sqlite3.connect(db.database_name)
        self.assertEqual(conn.execute("SELECT a FROM t").fetchall(), [(7,)])
        conn.close()

    def test_failed_backup_leaves_no_partial_file(self):
        db = self.make("notes", "sqlite")
        pv.provision(db)
        with mock.patch.object(pv.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(pv.ProvisionError):
                pv.backup(db)
        self.assertEqual(list(pv.backup_dir(db).iterdir()), [])


@skipIf(not _can_run_servers(), "database servers cannot run as root")
class PostgresBackup(BackupBase):
    def setUp(self):
        super().setUp()
        if not pv.engine_info()["postgresql"]["available"] or not pv._pg_bin("pg_dump"):
            self.skipTest("PostgreSQL server software not installed")

    def test_backup_wipe_restore_keeps_data_and_password(self):
        db = self.make("shop")
        self.addCleanup(lambda: pv.destroy(db, missing_ok=True))
        pv.provision(db)
        db.refresh_from_db()
        password = pv._password(db)
        conn = pv._pg_connect(db, password, "shop")
        conn.autocommit = True
        conn.cursor().execute("CREATE TABLE t(a int); INSERT INTO t VALUES (42)")
        conn.close()
        path = pv.backup(db)
        self.assertEqual(path.suffix, ".dump")
        self.assertEqual(oct(path.stat().st_mode & 0o777)[-3:], "600")          # pg_dump output is private
        self.assertNotIn(password.encode(), path.read_bytes())                  # no credential inside the dump
        pv.stop(db)
        self.wipe_local_disk(db)
        self.assertIn(("shop", "restored from backup"), pv.reconcile())
        self.assertEqual(pv.status(db), "running")
        conn = pv._pg_connect(db, password, "shop")                             # same stored password works
        cur = conn.cursor()
        cur.execute("SELECT a FROM t")
        self.assertEqual(cur.fetchone()[0], 42)
        conn.close()

    def test_corrupt_backup_fails_cleanly_and_removes_the_half_built_instance(self):
        db = self.make("shop")
        self.addCleanup(lambda: pv.destroy(db, missing_ok=True, keep_backups=True))
        pv.provision(db)
        pv.backup(db)
        pv.stop(db)
        self.wipe_local_disk(db)
        pv.backups(db)[0].write_bytes(b"not a dump")
        with self.assertRaises(pv.ProvisionError):
            pv.restore_missing(db)
        self.assertEqual(pv.status(db), "missing")
        self.assertFalse(pv._port_open(db.port))


@skipIf(not _can_run_servers(), "database servers cannot run as root")
class RedisBackup(BackupBase):
    def setUp(self):
        super().setUp()
        if not pv.engine_info()["redis"]["available"]:
            self.skipTest("Redis server software not installed")

    def test_backup_wipe_restore_keeps_keys(self):
        db = self.make("cache", "redis")
        self.addCleanup(lambda: pv.destroy(db, missing_ok=True))
        pv.provision(db)
        db.refresh_from_db()
        pw = pv._password(db)
        self.assertEqual(pv._redis_talk(db.port, pw, "SET", "k", "v"), "+OK")
        pv.backup(db)
        pv.stop(db)
        self.wipe_local_disk(db)
        self.assertIn(("cache", "restored from backup"), pv.reconcile())
        self.assertEqual(pv._redis_talk(db.port, pw, "DBSIZE"), ":1")
        self.assertTrue(pv._redis_talk(db.port, "", "PING").startswith("-NOAUTH"))


class BackupCommand(BackupBase):
    def test_command_reports_each_database(self):
        from io import StringIO
        from django.core.management import call_command
        db = self.make("notes", "sqlite")
        pv.provision(db)
        out = StringIO()
        call_command("backup_managed_databases", stdout=out)
        self.assertIn("notes: backed up", out.getvalue())
        self.assertEqual(len(pv.backups(db)), 1)
