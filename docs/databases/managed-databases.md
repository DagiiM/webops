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

It starts every managed database that is stopped. Status means "the port accepts connections". A server that crashes stays stopped until it is started again (from the page, or by this command); it is not auto-restarted.

## Known limits

* MySQL, MongoDB and Pinecone are still *Connect existing* only (saved connection details, not deployed).
* No automatic backups, no remote access, no per-database resource tuning yet.
* In a container whose PID 1 does not reap children (such as `sleep infinity`), each PostgreSQL stop leaves a few harmless defunct process entries until the container restarts.
