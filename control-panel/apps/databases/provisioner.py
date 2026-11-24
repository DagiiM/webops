"""Managed databases: real, private database instances provisioned on this host.

"Deploying a database" here means a running server (or file) that exists after one click, with
generated credentials and nothing left for the operator to configure:

* PostgreSQL  its own cluster (initdb) with its own data directory and port
* Redis       its own redis-server with its own data directory, port and password
* SQLite      a WAL-mode database file (no process)

Safety properties, all enforced here rather than in the views:

* Servers listen on 127.0.0.1 only, on a port from a private range. Reaching them from outside the
  host is a deliberate operator decision (tunnel or proxy), never a default.
* Only fixed vendor binaries are executed, with argument lists (no shell). Nothing a user types
  becomes a command line, a path or part of a config file: names are validated, paths are derived from
  the database's numeric id, and generated passwords are URL-safe so they need no quoting.
* Passwords are generated here, handed to initdb through a 0600 file and to Redis through a 0600 config
  file, and stored encrypted. They never appear in argv, logs or error messages.
* Resource use is bounded (connections, memory, instances per user and per host).
* The panel does not run as root, and neither do the engines.

Instances are daemonised, so they survive a panel restart. After a host restart run
``manage.py start_managed_databases`` (start-stack does this) to bring them back.
"""
import glob
import logging
import os
import re
import secrets
import shlex
import shutil
import socket
import sqlite3
import subprocess
import time
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

ENGINES = ("postgresql", "redis", "sqlite")
PORT_RANGE = (20000, 20999)
MAX_PER_USER = 5
MAX_PER_USER_STAFF = 20
MAX_PER_HOST = 30
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,29}$")
_DIR_RE = re.compile(r"^\d+-[a-z][a-z0-9_]{1,29}$")
START_TIMEOUT = 40


class ProvisionError(Exception):
    """A failure whose message is safe to show to the user."""


# ───────────────────────────── discovery ─────────────────────────────

def root() -> Path:
    configured = getattr(settings, "WEBOPS_DATABASES_ROOT", None)
    return Path(configured) if configured else Path(settings.WEBOPS_INSTALL_PATH) / "databases"


def _pg_bin(name):
    extra = getattr(settings, "WEBOPS_PG_BIN_DIR", None)
    if extra and os.access(os.path.join(extra, name), os.X_OK):
        return os.path.join(extra, name)
    found = shutil.which(name)
    if found:
        return found

    def version(path):
        m = re.search(r"/postgresql/(\d+)/", path)
        return int(m.group(1)) if m else 0
    for path in sorted(glob.glob(f"/usr/lib/postgresql/*/bin/{name}"), key=version, reverse=True):
        if os.access(path, os.X_OK):
            return path
    return None


def _redis_bin():
    return shutil.which("redis-server")


def _version(argv):
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", out)
    return m.group(1) if m else ""


def engine_info():
    """What can be deployed on this host right now."""
    pg = [_pg_bin(n) for n in ("initdb", "pg_ctl", "postgres")]
    redis = _redis_bin()
    return {
        "postgresql": {"label": "PostgreSQL", "available": all(pg), "version": _version([pg[2], "--version"]) if all(pg) else "",
                       "blurb": "Relational database for most web apps.",
                       "hint": "PostgreSQL server software is not installed on this host. Ask an operator to run: apt-get install postgresql"},
        "redis": {"label": "Redis", "available": bool(redis), "version": _version([redis, "--version"]) if redis else "",
                  "blurb": "In-memory cache, queues and sessions.",
                  "hint": "Redis server software is not installed on this host. Ask an operator to run: apt-get install redis-server"},
        "sqlite": {"label": "SQLite", "available": True, "version": sqlite3.sqlite_version,
                   "blurb": "A single file. Nothing to run; best for small apps.", "hint": ""},
    }


def can_deploy(user):
    from .models import Database
    managed = Database.objects.filter(managed=True, is_deleted=False)
    if managed.count() >= MAX_PER_HOST:
        return False, "This host has reached its limit of managed databases. Delete one you no longer need."
    limit = MAX_PER_USER_STAFF if user.is_staff else MAX_PER_USER
    if managed.filter(created_by=user).count() >= limit:
        return False, f"You can have up to {limit} managed databases. Delete one you no longer need."
    return True, ""


def slug(name):
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ProvisionError("Use 2 to 30 characters: a letter first, then letters, digits, hyphens or underscores.")
    return name.lower().replace("-", "_")


# ───────────────────────────── paths and ports ─────────────────────────────

def instance_dir(db) -> Path:
    """This database's own directory: <root>/<id>-<slug>. The name is regex-validated, so it cannot
    traverse, and a symbolic link in its place is refused rather than followed."""
    name = f"{db.pk}-{slug(db.name)}"
    if not _DIR_RE.match(name):
        raise ProvisionError("Invalid database name.")
    path = root().resolve() / name
    if path.is_symlink():
        raise ProvisionError("Refusing to use a symbolic link as a database directory.")
    return path


def allocate_port():
    from .models import Database
    used = set(Database.objects.exclude(port__isnull=True).values_list("port", flat=True))
    low, high = PORT_RANGE
    start = low + secrets.randbelow(high - low + 1)
    for offset in range(high - low + 1):
        port = low + (start - low + offset) % (high - low + 1)
        if port in used:
            continue
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
        return port
    raise ProvisionError("No free port is available for a new database.")


def _env(directory):
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(directory), "LANG": "C", "LC_ALL": "C"}


def _write_private(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(text)


def _run(argv, directory, timeout=60):
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=str(directory),
                              env=_env(directory), stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise ProvisionError("The database server did not respond in time.")
    except OSError:
        raise ProvisionError("The database server software could not be run on this host.")
    return done


# ───────────────────────────── PostgreSQL ─────────────────────────────

def _pg_options(db, directory):
    return " ".join(["-p", str(int(db.port)), "-c", "listen_addresses=127.0.0.1",
                     "-c", "unix_socket_directories=" + shlex.quote(str(directory)),
                     "-c", "max_connections=50", "-c", "shared_buffers=64MB"])


def _pg_connect(db, password, dbname="postgres"):
    import psycopg2
    return psycopg2.connect(host="127.0.0.1", port=int(db.port), user=db.username, password=password,
                            dbname=dbname, connect_timeout=3)


def _pg_provision(db, directory, password):
    data = directory / "data"
    pwfile = directory / ".pw"
    _write_private(pwfile, password + "\n")
    try:
        done = _run([_pg_bin("initdb"), "-D", str(data), "-U", db.username, "--auth=scram-sha-256", "-E", "UTF8",
                     "--no-locale", "--pwfile=" + str(pwfile)], directory)
    finally:
        pwfile.unlink(missing_ok=True)
    if done.returncode != 0:
        logger.error("initdb failed for database %s: %s", db.pk, done.stderr[-500:])
        raise ProvisionError("PostgreSQL could not initialise its data directory.")
    os.chmod(data, 0o700)
    _pg_start(db, directory)
    try:
        import psycopg2
        from psycopg2 import sql
        conn = _pg_connect(db, password)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db.database_name)))
        conn.close()
    except Exception:
        logger.exception("Creating the database failed for %s", db.pk)
        raise ProvisionError("PostgreSQL started but the database could not be created.")


def _pg_start(db, directory):
    if _pg_status(db, directory) == "running":
        return
    done = _run([_pg_bin("pg_ctl"), "-D", str(directory / "data"), "-l", str(directory / "server.log"), "-w",
                 "-t", str(START_TIMEOUT), "-o", _pg_options(db, directory), "start"], directory, START_TIMEOUT + 15)
    if done.returncode != 0:
        logger.error("pg_ctl start failed for database %s: %s", db.pk, (done.stderr or done.stdout)[-500:])
        raise ProvisionError("PostgreSQL did not start. Check that its port is free and the data directory is intact.")


def _pg_stop(db, directory):
    if not (directory / "data").is_dir() or _pg_status(db, directory) != "running":
        return
    done = _run([_pg_bin("pg_ctl"), "-D", str(directory / "data"), "-m", "fast", "-w", "-t", "30", "stop"], directory, 45)
    if done.returncode != 0:
        raise ProvisionError("PostgreSQL did not stop cleanly.")


def _port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=1):
            return True
    except OSError:
        return False


def _pg_status(db, directory):
    if not (directory / "data").is_dir():
        return "missing"
    ctl = _pg_bin("pg_ctl")
    if not ctl:
        return "stopped"
    done = _run([ctl, "-D", str(directory / "data"), "status"], directory, 10)
    return "running" if done.returncode == 0 else "stopped"


# ───────────────────────────── Redis ─────────────────────────────

def _resp(*args):
    out = b"*%d\r\n" % len(args)
    for a in args:
        raw = a if isinstance(a, bytes) else str(a).encode()
        out += b"$%d\r\n%s\r\n" % (len(raw), raw)
    return out


def _redis_talk(port, password, *command, timeout=3):
    """Send AUTH (when set) and one command; return the first reply line of the command."""
    with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout) as sock:
        sock.settimeout(timeout)
        reader = sock.makefile("rb")
        if password:
            sock.sendall(_resp("AUTH", password))
            if not reader.readline().startswith(b"+OK"):
                raise ProvisionError("Redis rejected the stored password.")
        sock.sendall(_resp(*command))
        return reader.readline().strip().decode("utf-8", "replace")


def _redis_conf(db, directory, password):
    return "\n".join([
        "bind 127.0.0.1", f"port {int(db.port)}", f'requirepass "{password}"', "protected-mode yes",
        f"dir {directory / 'data'}", "appendonly yes", "save 60 1", "daemonize yes",
        f"pidfile {directory / 'redis.pid'}", f"logfile {directory / 'redis.log'}",
        "maxmemory 128mb", "maxmemory-policy noeviction", "",
    ])


def _redis_provision(db, directory, password):
    (directory / "data").mkdir(mode=0o700)
    _write_private(directory / "redis.conf", _redis_conf(db, directory, password))
    _redis_start(db, directory)


def _redis_start(db, directory, password=None):
    if _redis_status(db, directory, password) == "running":
        return
    conf = directory / "redis.conf"
    if not conf.is_file():
        raise ProvisionError("This Redis instance's configuration is missing.")
    done = _run([_redis_bin(), str(conf)], directory, 20)
    if done.returncode != 0:
        logger.error("redis-server failed for database %s: %s", db.pk, (done.stderr or done.stdout)[-500:])
        raise ProvisionError("Redis did not start.")
    deadline = time.time() + START_TIMEOUT
    while time.time() < deadline:
        if _port_open(db.port):
            return
        time.sleep(0.2)
    raise ProvisionError("Redis did not become ready in time.")


def _redis_status(db, directory, password=None):
    if not (directory / "redis.conf").is_file():
        return "missing"
    return "running" if _port_open(db.port) else "stopped"


def _redis_stop(db, directory, password):
    if _redis_status(db, directory) != "running":
        return
    try:
        _redis_talk(db.port, password, "SHUTDOWN", "SAVE")
    except (OSError, ProvisionError):
        pass       # SHUTDOWN closes the connection without a reply
    deadline = time.time() + 15
    while time.time() < deadline and _port_open(db.port):
        time.sleep(0.2)
    if _port_open(db.port):
        raise ProvisionError("Redis did not stop cleanly.")


# ───────────────────────────── SQLite ─────────────────────────────

def _sqlite_path(db, directory):
    return directory / (slug(db.name) + ".sqlite3")


def _sqlite_provision(db, directory):
    path = _sqlite_path(db, directory)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
    finally:
        conn.close()
    os.chmod(path, 0o600)


# ───────────────────────────── public API ─────────────────────────────

def _password(db):
    from apps.core.utils import decrypt_password
    return decrypt_password(db.password) if db.password else ""


def provision(db):
    """Create and start the instance for a saved Database row (managed=True). Raises ProvisionError."""
    from apps.core.utils import encrypt_password
    if db.db_type not in ENGINES:
        raise ProvisionError("That database type cannot be deployed on this host.")
    if not engine_info()[db.db_type]["available"]:
        raise ProvisionError(engine_info()[db.db_type]["hint"])
    name = slug(db.name)
    directory = instance_dir(db)
    root().mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.mkdir(mode=0o700)
    password = secrets.token_urlsafe(24)
    try:
        if db.db_type == "postgresql":
            db.host, db.username, db.database_name = "127.0.0.1", name + "_user", name
            _pg_provision(db, directory, password)
        elif db.db_type == "redis":
            db.host, db.username, db.database_name = "127.0.0.1", "", ""
            _redis_provision(db, directory, password)
        else:
            db.host, db.port, db.username = "", None, ""
            db.database_name = str(_sqlite_path(db, directory))
            _sqlite_provision(db, directory)
            password = ""
    except Exception:
        destroy(db, missing_ok=True)
        raise
    db.password = encrypt_password(password) if password else ""
    db.metadata = {**(db.metadata or {}), "engine_version": engine_info()[db.db_type]["version"], "managed_dir": directory.name}
    db.save()


def status(db):
    """'running', 'stopped' or 'missing'. Never raises for a healthy installation."""
    try:
        directory = instance_dir(db)
    except ProvisionError:
        return "missing"
    if not directory.is_dir():
        return "missing"
    try:
        if db.db_type == "postgresql":
            return _pg_status(db, directory)
        if db.db_type == "redis":
            return _redis_status(db, directory)
        return "running" if _sqlite_path(db, directory).is_file() else "missing"
    except (ProvisionError, OSError):
        return "stopped"


def start(db):
    directory = instance_dir(db)
    if not directory.is_dir():
        raise ProvisionError("This database's files are missing.")
    if db.db_type == "postgresql":
        _pg_start(db, directory)
    elif db.db_type == "redis":
        _redis_start(db, directory)


def stop(db):
    directory = instance_dir(db)
    if db.db_type == "postgresql":
        _pg_stop(db, directory)
    elif db.db_type == "redis":
        _redis_stop(db, directory, _password(db))


def restart(db):
    stop(db)
    start(db)


def check(db):
    """Prove the stored credentials work: (ok, message)."""
    try:
        if status(db) != "running":
            return False, "The database is not running."
        if db.db_type == "postgresql":
            conn = _pg_connect(db, _password(db), db.database_name)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            conn.close()
            return True, "Connected and ran a query."
        if db.db_type == "redis":
            return (True, "Connected and got PONG.") if _redis_talk(db.port, _password(db), "PING") == "+PONG" else (False, "Redis did not answer PING.")
        conn = sqlite3.connect(db.database_name)
        conn.execute("SELECT 1")
        conn.close()
        return True, "Opened the file and ran a query."
    except Exception:
        logger.exception("Managed database check failed for %s", db.pk)
        return False, "Could not connect with the stored credentials."


def destroy(db, missing_ok=False):
    """Stop the instance and delete its files. Only ever touches this database's own directory."""
    directory = instance_dir(db)
    if not directory.exists():
        return
    try:
        stop(db)
    except ProvisionError:
        if not missing_ok:
            raise
        logger.warning("Stopping database %s during cleanup failed", db.pk)
    shutil.rmtree(directory)


def connection_url(db):
    from urllib.parse import quote
    pw = _password(db)
    if db.db_type == "postgresql":
        return f"postgresql://{db.username}:{quote(pw, safe='')}@127.0.0.1:{db.port}/{db.database_name}"
    if db.db_type == "redis":
        return f"redis://:{quote(pw, safe='')}@127.0.0.1:{db.port}/0"
    return f"sqlite:///{db.database_name}"


def reconcile():
    """Start every managed instance that should be running but is not. Returns [(name, outcome)]."""
    from .models import Database
    results = []
    for db in Database.objects.filter(managed=True, is_deleted=False, is_active=True):
        try:
            if status(db) == "stopped":
                start(db)
                results.append((db.name, "started"))
            else:
                results.append((db.name, status(db)))
        except ProvisionError as exc:
            results.append((db.name, f"failed: {exc}"))
    return results
