#!/bin/sh
# Bring the WebOps panel up on a Runpod pod whose /workspace is a persistent network volume.
#
# Everything that must survive lives on the volume (code, virtualenv, SQLite database, .env, supervisor
# programs, database backups). Everything on the container disk (apt packages, the user, running managed
# databases) is rebuilt here, so a stop/start/restart/redeploy of the pod comes back by itself.
#
# Idempotent: run it again at any time. The pod's start command should be
#     sh -c 'if [ -x /workspace/bin/boot.sh ]; then /workspace/bin/boot.sh; fi; exec sleep infinity'
# with /workspace/bin/boot.sh a one-line wrapper:  exec sh /workspace/webops/deploy/runpod/boot.sh
set -eu

W=${WEBOPS_VOLUME:-/workspace}
REPO=$W/webops
APP=$REPO/control-panel
DATA=$W/webops-data
RT=$DATA/runtime
VENV=$W/venv
LOCK=$REPO/deploy/runpod/requirements.lock
DBROOT=${WEBOPS_DATABASES_ROOT:-/var/lib/webops-databases}
BACKUPS=$DATA/backups/databases
APPUSER=webops
SETTINGS=config.runpod_preview
SUPERVISORD_CONF=$RT/supervisord.conf

log() { echo "[boot $(date -u +%H:%M:%S)] $*"; }

mkdir -p "$DATA"
exec >>"$DATA/boot.log" 2>&1
log "start"

# 1. System packages (container disk: reinstalled after every restart) ---------------------------------------
if ! ls /usr/lib/postgresql/*/bin/initdb >/dev/null 2>&1 || ! command -v redis-server >/dev/null 2>&1 \
   || ! command -v git >/dev/null 2>&1 || ! command -v sqlite3 >/dev/null 2>&1; then
  log "installing system packages"
  mkdir -p /etc/postgresql-common
  printf 'create_main_cluster = false\n' > /etc/postgresql-common/createcluster.conf   # we create our own instances
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends postgresql redis-server sqlite3 git ca-certificates >/dev/null
fi

# 2. Unprivileged service user ---------------------------------------------------------------------------------
id "$APPUSER" >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash "$APPUSER"
mkdir -p "$RT/programs" "$BACKUPS" "$DBROOT"
chown "$APPUSER:$APPUSER" "$DBROOT"; chmod 700 "$DBROOT"
chown -R "$APPUSER:$APPUSER" "$DATA" 2>/dev/null || true

# 3. Python environment (on the volume: built once, rebuilt only when the lock file changes) -------------------
if [ ! -x "$VENV/bin/python" ]; then
  log "creating virtualenv"
  python3 -m venv "$VENV"
fi
STAMP=$VENV/.lock.sha256
WANT=$(sha256sum "$LOCK" | cut -d' ' -f1)
if [ "$(cat "$STAMP" 2>/dev/null || true)" != "$WANT" ]; then
  log "installing python packages"
  "$VENV/bin/pip" install -q --no-input -r "$LOCK"
  echo "$WANT" > "$STAMP"
fi

# 4. Settings + environment -----------------------------------------------------------------------------------
cp "$REPO/deploy/runpod/settings/runpod_preview.py" "$REPO/deploy/runpod/settings/runpod_asgi.py" "$APP/config/"
ENVFILE=$APP/.env
if [ ! -f "$ENVFILE" ]; then
  log "first boot: generating $ENVFILE"
  umask 077
  SECRET=$("$VENV/bin/python" -c 'import secrets;print(secrets.token_urlsafe(50))')
  FERNET=$("$VENV/bin/python" -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')
  HOST="${RUNPOD_POD_ID:-localhost}-8000.proxy.runpod.net"
  cat > "$ENVFILE" <<ENV
DEBUG=False
SECRET_KEY=$SECRET
ENCRYPTION_KEY=$FERNET
ALLOWED_HOSTS=$HOST,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://$HOST
DATABASE_URL=sqlite:///$DATA/db.sqlite3
WEBOPS_INSTALL_PATH=$DATA
WEBOPS_USER=$APPUSER
WEBOPS_BG_PROCESSOR=sqlite
USE_X_FORWARDED_HOST=True
ENV
fi
chown "$APPUSER:$APPUSER" "$ENVFILE"
mkdir -p "$APP/staticfiles" "$APP/logs" "$APP/media"
chown -R "$APPUSER:$APPUSER" "$APP/staticfiles" "$APP/logs" "$APP/media" 2>/dev/null || true

# 5. Supervisor programs --------------------------------------------------------------------------------------
cat > "$SUPERVISORD_CONF" <<CONF
[unix_http_server]
file=$RT/supervisor.sock
chmod=0600
[supervisord]
logfile=$RT/supervisord.log
pidfile=$RT/supervisord.pid
childlogdir=$RT
[rpcinterface:supervisor]
supervisor.rpcinterface_factory=supervisor.rpcinterface:make_main_rpcinterface
[supervisorctl]
serverurl=unix://$RT/supervisor.sock
[include]
files=$RT/programs/*.ini
CONF

program() {   # name, command, extra-environment, stopwaitsecs
  cat > "$RT/programs/$1.ini" <<INI
[program:$1]
command=$2
directory=$APP
environment=DJANGO_SETTINGS_MODULE="$SETTINGS",WEBOPS_BG_PROCESSOR="sqlite",PYTHONUNBUFFERED="1",WEBOPS_DATABASES_ROOT="$DBROOT",WEBOPS_DATABASE_BACKUP_DIR="$BACKUPS",WEBOPS_SUPERVISORCTL="$VENV/bin/supervisorctl",PATH="$VENV/bin:/usr/local/bin:/usr/bin:/bin"
autostart=true
autorestart=true
startsecs=3
startretries=5
stopasgroup=true
killasgroup=true
stopwaitsecs=${4:-15}
stdout_logfile=$RT/$1.stdout.log
stderr_logfile=$RT/$1.stderr.log
stdout_logfile_maxbytes=5MB
stderr_logfile_maxbytes=5MB
stdout_logfile_backups=2
stderr_logfile_backups=2
INI
}
program webops-panel "$VENV/bin/daphne -b 0.0.0.0 -p 8000 --proxy-headers config.runpod_asgi:application" "" 15
program webops-queue-worker "$VENV/bin/python manage.py run_background_worker" "" 650
program webops-db-backup "sh -c 'while true; do sleep 900; $VENV/bin/python manage.py backup_managed_databases; done'" "" 650
chown -R "$APPUSER:$APPUSER" "$RT" 2>/dev/null || true

# 6. Database schema, static files, managed databases ----------------------------------------------------------
as_app() { runuser -u "$APPUSER" -- env PATH="$VENV/bin:/usr/local/bin:/usr/bin:/bin" PYTHONPATH="$APP" \
  DJANGO_SETTINGS_MODULE="$SETTINGS" WEBOPS_BG_PROCESSOR=sqlite WEBOPS_DATABASES_ROOT="$DBROOT" \
  WEBOPS_DATABASE_BACKUP_DIR="$BACKUPS" "$@"; }
cd "$APP"
as_app "$VENV/bin/python" manage.py migrate --noinput 2>&1 | grep -v '^INFO\|^WARNING' || true
as_app "$VENV/bin/python" manage.py collectstatic --noinput >/dev/null 2>&1 || true
log "reconciling managed databases (restores any whose files are gone from their newest backup)"
as_app "$VENV/bin/python" manage.py start_managed_databases 2>&1 | grep -v '^INFO\|^WARNING' || true

# 7. Start supervisord (it starts the panel, queue worker and backup loop, and restarts them if they crash) -----
if as_app "$VENV/bin/supervisorctl" -c "$SUPERVISORD_CONF" status >/dev/null 2>&1; then
  log "supervisord already running; reloading programs"
  as_app "$VENV/bin/supervisorctl" -c "$SUPERVISORD_CONF" update >/dev/null 2>&1 || true
else
  rm -f "$RT/supervisor.sock"
  as_app "$VENV/bin/supervisord" -c "$SUPERVISORD_CONF"
fi
sleep 6
as_app "$VENV/bin/supervisorctl" -c "$SUPERVISORD_CONF" status || true
log "done"
