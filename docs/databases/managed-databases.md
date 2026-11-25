# Managed databases

**Databases → Deploy database** creates a real database on the WebOps host with generated credentials and starts it. Nothing else to configure.

| Engine | What you get | Needs on the host |
| --- | --- | --- |
| PostgreSQL | its own cluster, data directory and port | `apt-get install postgresql` (do not enable the default service) |
| Redis | its own server with a password, append-only persistence, 128 MB cap | `apt-get install redis-server` |
| SQLite | a WAL-mode file, no process | nothing |

The deploy page greys out an engine whose server software is missing and tells you the command to run.

## Using it

The detail page shows a ready-to-paste connection URL (`DATABASE_URL` or `REDIS_URL`) plus Test connection, Restart, Stop and Start. Servers listen on `127.0.0.1` only, on a port from 20000–20999, so apps on the same host connect directly. Reaching one from elsewhere is a deliberate operator choice (SSH tunnel or proxy), never a default.

Each PostgreSQL instance has one role that owns its database and is a superuser of that private instance, so migrations just work. The instance is dedicated to that one database.

## Safety

* Only fixed vendor binaries are run, with argument lists (no shell). Names are validated; paths come from the database id; symbolic links are refused.
* Passwords are generated, passed to initdb and Redis through 0600 files (never on a command line), stored encrypted and never logged.
* Limits: 5 managed databases per user (20 for staff), 30 per host. PostgreSQL: 50 connections, 64 MB shared buffers.
* Deleting asks you to type the name and permanently removes the instance and its files. There is no recycle bin, so keep your own backups (`pg_dump`, `redis-cli --rdb`, copy the SQLite file).
* The panel and the engines run as the panel's non-root user.

## Restarts

Instances are daemonised and survive a panel restart. After a host restart run:

```bash
python manage.py start_managed_databases
```

It starts every managed database that is stopped, and **rebuilds any whose files are gone from its newest backup** (see below). Status means "the port accepts connections". A server that crashes stays stopped until it is started again (from the page, or by this command); it is not auto-restarted.

## Backups

```bash
python manage.py backup_managed_databases
```

writes a consistent backup of every running instance (`pg_dump -Fc`, a Redis `SAVE` snapshot, or SQLite's online backup API) to `WEBOPS_DATABASE_BACKUP_DIR` (default `<install path>/../backups/databases`), keeps the newest five per database, and writes each file privately (mode 0600 in a 0700 directory) via a temporary name so a failed backup never leaves a half-written file. Credentials are not stored inside the dump.

Point `WEBOPS_DATABASE_BACKUP_DIR` at storage that outlives the machine, and `WEBOPS_DATABASES_ROOT` at fast local disk if the persistent storage is a network filesystem. After a machine replacement, `start_managed_databases` finds each instance's files missing and restores it from its newest backup, with the same port and the same stored password. If files are missing and there is **no** backup the database is reported as failed; it is never silently replaced by an empty one. Deleting a database deletes its backups too.

Backups are only as fresh as the last run: run the command on a schedule (the Runpod deployment does so every 15 minutes), and expect to lose up to that long of writes on an unplanned restart. Redis keeps RDB snapshots only (`save 60 1`, `save 300 10`) so that a single file is the whole state.

## Known limits

* MySQL, MongoDB and Pinecone are still *Connect existing* only (saved connection details, not deployed).
* No remote access and no per-database resource tuning yet. Backups run only when the command is scheduled, and restore is whole-instance (no point-in-time recovery).
* In a container whose PID 1 does not reap children (such as `sleep infinity`), each PostgreSQL stop leaves a few harmless defunct process entries until the container restarts.
