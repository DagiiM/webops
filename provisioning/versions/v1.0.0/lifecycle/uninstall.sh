#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INVENTORY="${SCRIPT_DIR}/installation_inventory.py"
STATE_DIR="/var/backups/webops-install/installation-inventory"
DRY_RUN=false
PURGE_DATA=false
FORCE=false
CONFIRM_PURGE=false
usage() {
  cat <<'EOF'
Usage: sudo ./uninstall.sh [--dry-run] [--purge-data] [--force] [--confirm-purge]
Default: remove only recorded WebOps changes while preserving data and
pre-existing packages, shared services, and user-modified configuration.
EOF
}
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --purge-data) PURGE_DATA=true ;;
    --force) FORCE=true ;;
    --confirm-purge) CONFIRM_PURGE=true ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done
if (( EUID != 0 )); then
  echo "sudo/root access required, including for the protected inventory preview" >&2
  exit 1
fi
if [[ ! -f "$INVENTORY" || ! -f "${STATE_DIR}/inventory.json" ]]; then
  echo "Refusing legacy uninstall: no verifiable installation inventory." >&2
  exit 1
fi
args=(--state-dir "$STATE_DIR")
if [[ "$PURGE_DATA" == true ]]; then args+=(--purge-data); fi
python3 "$INVENTORY" plan "${args[@]}"
if [[ "$DRY_RUN" == true ]]; then
  echo "Dry run only; no changes were made."
  exit 0
fi
if [[ "$PURGE_DATA" == true && "$FORCE" == true && "$CONFIRM_PURGE" != true ]]; then
  echo "--purge-data with --force requires --confirm-purge" >&2
  exit 2
fi
if [[ "$FORCE" != true ]]; then
  if [[ "$PURGE_DATA" == true ]]; then
    read -r -p "Type PURGE WEBOPS DATA to permanently delete managed data: " answer
    [[ "$answer" == "PURGE WEBOPS DATA" ]] || { echo "Cancelled."; exit 1; }
  else
    read -r -p "Type UNINSTALL to remove WebOps files and keep data: " answer
    [[ "$answer" == "UNINSTALL" ]] || { echo "Cancelled."; exit 1; }
  fi
fi
python3 "$INVENTORY" uninstall "${args[@]}"
echo "Uninstall completed; review preserved resources and warnings."
