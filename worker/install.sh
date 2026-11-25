#!/bin/sh
# Install the WebOps build worker on a fresh Debian/Ubuntu machine. Run as root. Idempotent.
#   WEBOPS_PANEL_URL=https://your-panel sh install.sh
# or, with nothing downloaded first:
#   curl -fsSL https://raw.githubusercontent.com/DagiiM/webops/<ref>/worker/install.sh | WEBOPS_PANEL_URL=https://your-panel WEBOPS_REF=<ref> sh
#
# The worker makes its own token (kept in /etc/webops-worker/token) and prints a one-line command that registers
# only the token's hash on the panel, so the token never has to be copied anywhere. Optional settings:
#   WEBOPS_WORKER_NAME    name shown on the panel's Workers page (default: this machine's hostname)
#   WEBOPS_WORKER_TOKEN   use this token instead of generating one (for machines rebuilt from scratch on every start;
#                         make it with: python3 -c "import secrets;print('wops_wrk_'+secrets.token_urlsafe(32))")
#   WEBOPS_REF            branch, tag or commit to download the agent from (default main)
#   WEBOPS_WORKER_STATE   a folder on a persistent volume (e.g. /workspace/webops-worker). The token is then kept there
#                         ENCRYPTED, and this script restores it after every restart so the worker comes back on its own
#                         with no re-registration. Nothing else is stored there: see "Persistent volumes" in README.md.
set -eu
[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
: "${WEBOPS_PANEL_URL:?set WEBOPS_PANEL_URL to the panel's https address}"
HERE="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo /nonexistent)"
REF=${WEBOPS_REF:-main}
NAME=${WEBOPS_WORKER_NAME:-$(hostname)}
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y -qq --no-install-recommends ca-certificates curl build-essential pkg-config libssl-dev git python3 python3-venv python3-pip nodejs npm supervisor

# Rust, system-wide and read-only for jobs (each job gets its own CARGO_HOME for downloaded crates).
if [ ! -x /opt/rust/cargo/bin/cargo ]; then
  export CARGO_HOME=/opt/rust/cargo RUSTUP_HOME=/opt/rust/rustup
  curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --no-modify-path
fi
chmod -R a+rX /opt/rust

# The agent, its token directory and its jobs directory.
install -d -m 0755 /opt/webops-worker
if [ -f "$HERE/webops_worker.py" ]; then
  install -m 0644 "$HERE/webops_worker.py" /opt/webops-worker/webops_worker.py
else
  curl -fsSL "https://raw.githubusercontent.com/DagiiM/webops/$REF/worker/webops_worker.py" -o /opt/webops-worker/webops_worker.py
  chmod 0644 /opt/webops-worker/webops_worker.py
fi
install -d -m 0700 /etc/webops-worker
install -d -m 0711 /var/lib/webops-worker /var/lib/webops-worker/jobs

cat > /etc/supervisor/conf.d/webops-worker.conf <<CONF
[program:webops-worker]
command=/usr/bin/python3 /opt/webops-worker/webops_worker.py
environment=WEBOPS_PANEL_URL="${WEBOPS_PANEL_URL}",PYTHONUNBUFFERED="1"
autostart=true
autorestart=true
startsecs=5
user=root
stdout_logfile=/var/log/webops-worker.log
stderr_logfile=/var/log/webops-worker.log
stdout_logfile_maxbytes=5MB
stdout_logfile_backups=2
CONF
# The token: supplied, restored from the sealed copy, already present, or made here. Only its SHA-256 is ever printed.
#
# A network volume does not enforce file permissions (any user on the machine can read any file on it), and build jobs
# run as unprivileged users on this same machine. So the token is never written to the volume in the clear: it is
# sealed with a key derived from $RUNPOD_API_KEY, which Runpod puts in the environment of the container's root
# process (build jobs never see it). The plaintext token lives only on the container's own disk, mode 0600.
TOKEN_FILE=/etc/webops-worker/token
STATE=${WEBOPS_WORKER_STATE:-}
SEALED=
FRESH=0
seal_key() { printf 'webops-worker-token:%s' "$RUNPOD_API_KEY" | sha256sum | cut -d' ' -f1; }
if [ -n "$STATE" ]; then
  [ -n "${RUNPOD_API_KEY:-}" ] || { echo "WEBOPS_WORKER_STATE needs RUNPOD_API_KEY in the environment (it is set inside Runpod pods)" >&2; exit 1; }
  mkdir -p "$STATE"; SEALED=$STATE/token.enc
fi
if [ -n "${WEBOPS_WORKER_TOKEN:-}" ]; then
  case "$WEBOPS_WORKER_TOKEN" in wops_wrk_*) ;; *) echo "WEBOPS_WORKER_TOKEN must start with wops_wrk_" >&2; exit 1;; esac
  (umask 077; printf '%s\n' "$WEBOPS_WORKER_TOKEN" > "$TOKEN_FILE")
elif [ -n "$SEALED" ] && [ -s "$SEALED" ] && (umask 077; WEBOPS_SEAL=$(seal_key) openssl enc -d -aes-256-cbc -pbkdf2 -pass env:WEBOPS_SEAL -in "$SEALED" -out "$TOKEN_FILE.new" 2>/dev/null) && grep -q '^wops_wrk_' "$TOKEN_FILE.new"; then
  mv -f "$TOKEN_FILE.new" "$TOKEN_FILE"
  echo "Restored the worker token from its sealed copy in $STATE."
else
  rm -f "$TOKEN_FILE.new"
  if [ -n "$SEALED" ] && [ -s "$SEALED" ]; then
    echo "The sealed token in $STATE could not be opened (the pod's key changed); making a new token." >&2
  fi
  if [ ! -s "$TOKEN_FILE" ] || [ -n "$SEALED" ]; then
    (umask 077; python3 -c "import secrets;print('wops_wrk_'+secrets.token_urlsafe(32))" > "$TOKEN_FILE")
    FRESH=1
  fi
fi
chmod 0600 "$TOKEN_FILE"
if [ -n "$SEALED" ] && { [ "$FRESH" = 1 ] || [ ! -s "$SEALED" ]; }; then
  (umask 077; WEBOPS_SEAL=$(seal_key) openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:WEBOPS_SEAL -in "$TOKEN_FILE" -out "$SEALED.tmp" && mv -f "$SEALED.tmp" "$SEALED")
fi
DIGEST=$(python3 -c "import hashlib,sys;print(hashlib.sha256(open('$TOKEN_FILE').read().strip().encode()).hexdigest())")

# Containers have no init system: start supervisord ourselves when it is not already running.
# (`supervisorctl status` fails whenever any program is not running, so test the process itself.)
SUP_PID=$(cat /var/run/supervisord.pid 2>/dev/null || true)
if [ -n "$SUP_PID" ] && kill -0 "$SUP_PID" 2>/dev/null; then
  supervisorctl reread >/dev/null 2>&1 || true
  supervisorctl update >/dev/null 2>&1 || true
  supervisorctl restart webops-worker >/dev/null 2>&1 || true
else
  mkdir -p /var/log
  env -u RUNPOD_API_KEY supervisord -c /etc/supervisor/supervisord.conf     # the agent does not need the key
fi

echo
if [ -n "$SEALED" ] && [ "$FRESH" = 0 ]; then
  echo "Worker '$NAME' started with its restored token; it is already registered, nothing more to do."
else
  echo "Worker installed and started as '$NAME'. Register it on the panel (once) with:"
  echo
  echo "  cd <panel>/control-panel && python manage.py register_worker --name '$NAME' --digest $DIGEST"
  echo
  echo "It shows as Online on the Workers page within about 30 seconds of registration."
fi
