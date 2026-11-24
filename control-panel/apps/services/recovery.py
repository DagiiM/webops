"""Private, verifiable SQLite snapshots; restore only into a fresh staging directory."""
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from contextlib import closing

FILES = ("control.sqlite3", "jobs.sqlite3")

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def connect_read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Expected an existing regular SQLite file")
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=15)

def integrity(path):
    with closing(connect_read(path)) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite integrity check failed")

def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)

def snapshot_file(source, destination):
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with closing(connect_read(source)) as src, closing(sqlite3.connect(destination)) as dst:
        deadline = time.monotonic() + 120
        def progress(*_):
            if time.monotonic() > deadline:
                raise TimeoutError("SQLite snapshot exceeded time limit")
        src.backup(dst, pages=256, progress=progress, sleep=0.05)
        dst.execute("PRAGMA journal_mode=DELETE")
    integrity(destination)
    with destination.open("rb") as f:
        os.fsync(f.fileno())

def private_directory(path):
    path = Path(path)
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.is_symlink() or not path.is_dir() or path.stat().st_mode & 0o077:
        raise ValueError("Destination parent must be a private directory (0700)")
    return path

def create_snapshot(control, queue, parent):
    parent = private_directory(parent)
    stage = Path(tempfile.mkdtemp(prefix=".snapshot-", dir=parent))
    try:
        entries = {}
        for name, source in zip(FILES, (control, queue)):
            target = stage / name
            snapshot_file(Path(source), target)
            entries[name] = {"sha256": digest(target), "bytes": target.stat().st_size}
        manifest = {"version": 1, "created_unix": int(time.time()), "files": entries,
                    "consistency": "independent-online-snapshots",
                    "automatic_queue_replay": False}
        fd = os.open(stage / "manifest.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(manifest, f, sort_keys=True, indent=2)
            f.flush()
            os.fsync(f.fileno())
        sync_dir(stage)
        final = parent / stage.name.removeprefix(".")
        stage.rename(final)
        sync_dir(parent)
        return final
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise

def verify_snapshot(directory):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Invalid snapshot directory")
    m = directory / "manifest.json"
    if m.is_symlink() or not m.is_file() or m.stat().st_size > 16384:
        raise ValueError("Invalid snapshot manifest")
    manifest = json.loads(m.read_text())
    if manifest.get("version") != 1 or set(manifest.get("files", {})) != set(FILES):
        raise ValueError("Unsupported snapshot manifest")
    for name in FILES:
        path = directory / name
        record = manifest["files"][name]
        if path.is_symlink() or not path.is_file() or path.stat().st_size != record["bytes"] or digest(path) != record["sha256"]:
            raise ValueError("Snapshot checksum or size mismatch: " + name)
        integrity(path)
    return manifest

def stage_restore(snapshot, parent):
    """Restore checked copies, quarantine unfinished jobs, never replace live files."""
    snapshot = Path(snapshot)
    verify_snapshot(snapshot)
    parent = private_directory(parent)
    stage = Path(tempfile.mkdtemp(prefix=".restore-", dir=parent))
    try:
        for name in FILES:
            target = stage / name
            snapshot_file(snapshot / name, target)
        # Verify the source again after copying. No job is automatically replayed.
        verify_snapshot(snapshot)
        with closing(sqlite3.connect(stage / "jobs.sqlite3")) as db, db:
            changed = db.execute(
                "UPDATE jobs SET state='failed', error=?, updated=? WHERE state IN ('pending','started')",
                ("Restored backup; reconcile with actual workload before retrying", time.time())
            ).rowcount
            db.execute("DELETE FROM worker")
        # Do not change live or restored deployment records automatically: they
        # may refer to external processes. Reconciliation is mandatory.
        for name in FILES:
            integrity(stage / name)
        final = parent / stage.name.removeprefix(".")
        sync_dir(stage)
        stage.rename(final)
        sync_dir(parent)
        return final, changed
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
