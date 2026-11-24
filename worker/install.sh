#!/bin/sh
# Install the WebOps build worker on a fresh Debian/Ubuntu machine. Run as root. Idempotent.
#   WEBOPS_PANEL_URL=https://your-panel sh install.sh
# Then put the worker token (shown once on the panel's Workers page) in /etc/webops-worker/token and start it.
set -eu
[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
: "${WEBOPS_PANEL_URL:?set WEBOPS_PANEL_URL to the panel's https address}"
HERE="$(cd "$(dirname "$0")" && pwd)"
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
install -m 0644 "$HERE/webops_worker.py" /opt/webops-worker/webops_worker.py
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
echo "Installed. Save the token to /etc/webops-worker/token (mode 0600), then: supervisorctl reread && supervisorctl update"
