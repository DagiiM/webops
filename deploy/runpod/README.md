# Running the panel on a Runpod pod with a persistent volume

A Runpod pod's container disk is wiped whenever the pod stops, restarts or is edited. The network volume mounted at
`/workspace` is not. `boot.sh` makes the pod restart-proof by keeping all state on the volume and rebuilding the rest.

| Lives on the volume (`/workspace`) | Rebuilt by `boot.sh` on every start |
|---|---|
| code (`webops/`), virtualenv (`venv/`) | apt packages (PostgreSQL, Redis, SQLite, git), the `webops` user |
| SQLite database, `.env` (keys), supervisor programs | settings files copied from `deploy/runpod/settings/` |
| managed-database **backups** (`webops-data/backups/databases`) | managed databases, **restored from backup** |
| LLM model files / state | supervisord and the panel, queue worker and backup loop |

Managed databases run from the pod's local disk (`/var/lib/webops-databases`) because the volume is a network
filesystem that ignores `chmod` for non-root users, which PostgreSQL requires. They are backed up to the volume every
15 minutes, so an unplanned restart loses at most that much database writes; a clean stop/start loses none.

## Set up (one command)

Create a network volume and a pod in the same data center, with the volume mounted at `/workspace`, port `8000/http`
exposed, and this **start command** (pin `<ref>` to a release tag or commit for production; `main` follows development):

```bash
sh -c 'if [ -x /workspace/bin/boot.sh ]; then /workspace/bin/boot.sh; else curl -fsSL https://raw.githubusercontent.com/DagiiM/webops/<ref>/deploy/runpod/install.sh | WEBOPS_REF=<ref> sh; fi; exec sleep infinity'
```

That is all. The first start installs everything (several minutes; progress in `/workspace/webops-data/boot.log`),
and every later start just brings the stack back. Then:

* The address is `https://<pod id>-8000.proxy.runpod.net/`.
* The first administrator is `admin`; the generated password is in `/workspace/webops-data/initial-admin.txt`
  (read it from the pod's terminal, sign in, change it, delete the file). To choose your own, set the pod environment
  variables `WEBOPS_ADMIN_USERNAME`, `WEBOPS_ADMIN_EMAIL` and `WEBOPS_ADMIN_PASSWORD` (12+ characters) before the
  first start; use a Runpod secret for the password.
* Prefer a shell? From any pod with the volume mounted: `curl -fsSL .../install.sh | WEBOPS_REF=<ref> sh`.

The pod and volume themselves must be created in the Runpod console or API (the installer runs inside the pod).

## Build workers

On a separate machine (a plain pod is fine), one command installs the agent, makes its own token and starts it:

```bash
curl -fsSL https://raw.githubusercontent.com/DagiiM/webops/<ref>/worker/install.sh | WEBOPS_PANEL_URL=https://<panel address> WEBOPS_REF=<ref> sh
```

It then prints a single `register_worker` command containing only the token's hash; run it once on the panel
(`cd /workspace/webops/control-panel` with the panel's settings). A pod's disk is wiped on restart: to make a
worker rebuild itself, set `WEBOPS_WORKER_TOKEN` and `WEBOPS_WORKER_NAME` as pod environment variables, register the
token's hash once, and use the same `curl ... | sh` line in the pod's start command.

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
