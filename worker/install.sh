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
# The token: supplied, already present, or made here. Only its SHA-256 is ever printed.
TOKEN_FILE=/etc/webops-worker/token
if [ -n "${WEBOPS_WORKER_TOKEN:-}" ]; then
  case "$WEBOPS_WORKER_TOKEN" in wops_wrk_*) ;; *) echo "WEBOPS_WORKER_TOKEN must start with wops_wrk_" >&2; exit 1;; esac
  (umask 077; printf '%s\n' "$WEBOPS_WORKER_TOKEN" > "$TOKEN_FILE")
elif [ ! -s "$TOKEN_FILE" ]; then
  (umask 077; python3 -c "import secrets;print('wops_wrk_'+secrets.token_urlsafe(32))" > "$TOKEN_FILE")
fi
chmod 0600 "$TOKEN_FILE"
DIGEST=$(python3 -c "import hashlib,sys;print(hashlib.sha256(open('$TOKEN_FILE').read().strip().encode()).hexdigest())")

# Containers have no init system: start supervisord ourselves when it is not already running.
if supervisorctl status >/dev/null 2>&1; then
  supervisorctl reread >/dev/null && supervisorctl update >/dev/null && supervisorctl restart webops-worker >/dev/null 2>&1 || true
else
  mkdir -p /var/log
  supervisord -c /etc/supervisor/supervisord.conf
fi

echo
echo "Worker installed and started as '$NAME'. Register it on the panel (once) with:"
echo
echo "  cd <panel>/control-panel && python manage.py register_worker --name '$NAME' --digest $DIGEST"
echo
echo "It shows as Online on the Workers page within about 30 seconds of registration."
