#!/bin/sh
# One-command install (and update) of the WebOps panel on a Runpod pod whose /workspace is a persistent volume.
#
#   curl -fsSL https://raw.githubusercontent.com/DagiiM/webops/<ref>/deploy/runpod/install.sh | WEBOPS_REF=<ref> sh
#
# Clones the repository onto the volume, installs a tiny /workspace/bin/boot.sh wrapper, then runs boot.sh, which
# builds everything else and creates the first administrator. Safe to run again: it updates to WEBOPS_REF.
#
#   WEBOPS_REF     branch, tag or commit to install (default main; pin a tag or commit for production)
#   WEBOPS_REPO    git URL (default the upstream repository)
#   WEBOPS_VOLUME  persistent mount point (default /workspace)
#   WEBOPS_ADMIN_USERNAME / WEBOPS_ADMIN_EMAIL / WEBOPS_ADMIN_PASSWORD   optional first-admin settings
set -eu

W=${WEBOPS_VOLUME:-/workspace}
REF=${WEBOPS_REF:-main}
URL=${WEBOPS_REPO:-https://github.com/DagiiM/webops.git}
REPO=$W/webops

[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
if ! grep -q " $W " /proc/mounts 2>/dev/null; then
  echo "WARNING: $W is not a separate mount. Without a persistent volume everything is lost when the pod restarts." >&2
fi
if ! command -v git >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq && apt-get install -y -qq --no-install-recommends git ca-certificates >/dev/null
fi

mkdir -p "$W/bin"
g() { git -c safe.directory='*' -C "$REPO" "$@"; }
if [ -d "$REPO/.git" ]; then
  echo "Updating $REPO to $REF"
else
  echo "Cloning $URL"
  git clone -q --no-checkout "$URL" "$REPO"
fi
g fetch -q origin "$REF"
if g ls-remote --exit-code --heads origin "$REF" >/dev/null 2>&1; then
  g checkout -q -f -B "$REF" FETCH_HEAD            # a branch: stay on it so a later `git pull` works
else
  g checkout -q -f --detach FETCH_HEAD             # a tag or commit
fi
echo "At $(g rev-parse --short HEAD)"

printf '#!/bin/sh\nexec sh %s/deploy/runpod/boot.sh\n' "$REPO" > "$W/bin/boot.sh"
chmod +x "$W/bin/boot.sh"

echo "Running boot.sh (first run takes several minutes; progress: $W/webops-data/boot.log)"
sh "$REPO/deploy/runpod/boot.sh" || { echo "boot.sh failed; see $W/webops-data/boot.log" >&2; tail -20 "$W/webops-data/boot.log" >&2; exit 1; }

HOST="${RUNPOD_POD_ID:+$RUNPOD_POD_ID-8000.proxy.runpod.net}"
echo
echo "WebOps is running."
[ -n "$HOST" ] && echo "  Address:  https://$HOST/"
if [ -f "$W/webops-data/initial-admin.txt" ]; then
  echo "  Admin:    username and generated password are in $W/webops-data/initial-admin.txt"
  echo "            (read it, sign in, change the password, then delete the file)"
fi
echo "  Restart:  the pod's start command should run $W/bin/boot.sh (see deploy/runpod/README.md)"
