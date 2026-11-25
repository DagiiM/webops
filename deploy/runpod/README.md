# Running the panel on a Runpod pod with a persistent volume

A Runpod pod's container disk is wiped whenever the pod stops, restarts or is edited. The network volume mounted at
`/workspace` is not. `boot.sh` makes the pod restart-proof by keeping all state on the volume and rebuilding the rest.

| Lives on the volume (`/workspace`) | Rebuilt by `boot.sh` on every start |
|---|---|
| code (`webops/`), virtualenv (`venv/`) | apt packages (PostgreSQL, Redis, SQLite, git), the `webops` user |
| SQLite database, `.env` (keys), supervisor programs | settings files copied from `deploy/runpod/config/` |
| managed-database **backups** (`webops-data/backups/databases`) | managed databases, **restored from backup** |
| LLM model files / state | supervisord and the panel, queue worker and backup loop |

Managed databases run from the pod's local disk (`/var/lib/webops-databases`) because the volume is a network
filesystem that ignores `chmod` for non-root users, which PostgreSQL requires. They are backed up to the volume every
15 minutes, so an unplanned restart loses at most that much database writes; a clean stop/start loses none.

## Set up

1. Create a network volume and a pod in the same data center with the volume mounted at `/workspace`, port `8000/http`
   exposed, and the start command
   `sh -c 'if [ -x /workspace/bin/boot.sh ]; then /workspace/bin/boot.sh; fi; exec sleep infinity'`.
2. Clone the repository to `/workspace/webops` and create the wrapper:
   `mkdir -p /workspace/bin && printf '#!/bin/sh\nexec sh /workspace/webops/deploy/runpod/boot.sh\n' > /workspace/bin/boot.sh && chmod +x /workspace/bin/boot.sh`
3. Run `/workspace/bin/boot.sh` once (or restart the pod). The first run takes a few minutes (packages, virtualenv)
   and writes a fresh `.env` with new keys for this pod's address. Progress is in `/workspace/webops-data/boot.log`.
4. Create the first admin: `cd /workspace/webops/control-panel && ../../venv/bin/python manage.py createsuperuser`
   with `DJANGO_SETTINGS_MODULE=config.runpod_preview` set.

## Updating

`git pull` in `/workspace/webops`, then run `boot.sh` again (it migrates, refreshes settings and reloads supervisor).
Change `requirements.lock` to have it reinstall packages.

## Limits

* Files on the volume cannot be protected with permissions from other processes in the pod (the volume ignores
  `chmod` for non-root): `.env` is readable by anything that runs in the same pod. Treat the pod as one trust domain.
* SQLite on a network volume is slower than on local disk (about 25 commits/s was measured). It is fine for one
  panel; move `DATABASE_URL` to PostgreSQL for more.
* The public address (`https://<pod id>-8000.proxy.runpod.net`) is tied to the pod id; a new pod means new address,
  `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and anything that points at it (LLM clients, remote workers).
