#!/usr/bin/env bash
# Set the system default 'python' to a specified installed Python version.
#
# This script helps set the system-wide "python" command to a chosen, already
# installed Python interpreter. It prefers to use the system alternatives
# mechanism (update-alternatives on Debian/Ubuntu, alternatives on RHEL/CentOS)
# and falls back to creating a symlink at /usr/local/bin/python when no
# alternatives tool is available.
#
# Usage:
#   sudo ./scripts/set-default-python.sh 3.11
#
# Dry-run (no changes):
#   ./scripts/set-default-python.sh 3.11 --dry-run
#
# Examples:
#   # Make system default python point to the python3.11 binary
#   sudo ./scripts/set-default-python.sh 3.11
#
# Safety notes:
# - The script will not overwrite a non-symlink file at /usr/local/bin/python.
# - Run with sudo to make system changes. In dry-run mode you don't need sudo.
# - If your environment relies on a virtualenv, pyenv, or distro package manager
#   tools, prefer using those (they're safer than changing the global 'python').
#
# macOS and Windows:
# - macOS: prefer 'pyenv' or Homebrew: 'brew install python@3.x' then
#   'brew link --force --overwrite python@3.x'. Do not run this script on macOS.
# - Windows: use the Python installer, the 'py' launcher, or tools like pyenv-win.

set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 <major.minor> [--dry-run]

This script will attempt to set the system default 'python' interpreter to
an installed Python version (for example '3.11'). It prefers using
update-alternatives (Debian/Ubuntu) or alternatives (Red Hat/CentOS),
falling back to updating a /usr/local/bin/python symlink when necessary.

Examples:
  sudo $0 3.11
  $0 3.11 --dry-run

Notes:
- Must be run as root or with sudo to modify system links or alternatives.
- Only supports Linux. macOS and Windows are not supported here; see comments
  below for hints.
EOF
}

if [[ ${#@} -lt 1 ]]; then
  usage
  exit 2
fi

TARGET_VERSION=$1
DRY_RUN=false
if [[ ${2:-} == "--dry-run" ]]; then
  DRY_RUN=true
fi

# Candidate binary names to look for
CANDIDATES=("python${TARGET_VERSION}" "python${TARGET_VERSION%.*}" "python3.${TARGET_VERSION##*.}" "python3")

find_python_binary() {
  for name in "${CANDIDATES[@]}"; do
    if command -v "$name" >/dev/null 2>&1; then
      echo "$(command -v $name)"
      return 0
    fi
  done
  return 1
}

PY_BIN=$(find_python_binary || true)
if [[ -z "$PY_BIN" ]]; then
  echo "No python binary matching version '$TARGET_VERSION' found in PATH."
  echo "Install the desired Python (apt/dnf/pyenv) and try again."
  exit 3
fi

echo "Found python candidate: $PY_BIN"

if [[ "$DRY_RUN" == true ]]; then
  echo "Dry run - no changes will be made."
fi

# Helper to run commands or echo on dry-run
run() {
  # Accept both string commands and arrays. If multiple args provided treat as array.
  if [[ $# -gt 1 ]]; then
    local cmd=("$@")
    if [[ "$DRY_RUN" == true ]]; then
      printf "+ %q\n" "${cmd[@]}"
    else
      printf "+ %q\n" "${cmd[@]}"
      "${cmd[@]}"
    fi
  else
    local cmd_str="$1"
    if [[ "$DRY_RUN" == true ]]; then
      echo "+ $cmd_str"
    else
      echo "+ $cmd_str"
      bash -c "$cmd_str"
    fi
  fi
}

# Detect if update-alternatives exists
if command -v update-alternatives >/dev/null 2>&1; then
  alt_cmd=update-alternatives
elif command -v alternatives >/dev/null 2>&1; then
  alt_cmd=alternatives
else
  alt_cmd=""
fi

if [[ -n "$alt_cmd" ]]; then
  echo "Using $alt_cmd to configure 'python' alternatives."
  # Register the alternative if not present
  if $alt_cmd --display python >/dev/null 2>&1; then
    echo "python alternative already registered. Adding candidate if missing..."
  fi

  # Determine priority from version (major*100 + minor)
  MAJOR=$(echo "$TARGET_VERSION" | cut -d. -f1)
  MINOR=$(echo "$TARGET_VERSION" | cut -d. -f2 || echo 0)
  PRIORITY=$(( MAJOR * 100 + MINOR ))

  # Install alternative for the provided candidate
  if [[ "$alt_cmd" == "update-alternatives" ]]; then
    # add --force to register target even if path differs
    CMD_ADD=("$alt_cmd" --install /usr/bin/python python "$PY_BIN" "$PRIORITY")
  else
    # alternatives on some RHEL systems uses --install as well
    CMD_ADD=("$alt_cmd" --install /usr/bin/python python "$PY_BIN" "$PRIORITY")
  fi

  # If running as non-root, advise sudo
  if [[ $EUID -ne 0 && "$DRY_RUN" == false ]]; then
    echo "Note: Non-root user. Commands will fail without sudo. Re-run with sudo."
  fi

  run "${CMD_ADD[@]}"
  # Set it as the auto or manual selection
  run "$alt_cmd --set python $PY_BIN || true"

else
  echo "No alternatives system detected. Falling back to symlink at /usr/local/bin/python"
  SYMLINK=/usr/local/bin/python
  if [[ -e "$SYMLINK" && ! -L "$SYMLINK" ]]; then
    echo "Existing /usr/local/bin/python is not a symlink. Skipping to avoid overwriting a real file."
    exit 4
  fi

  if [[ $EUID -ne 0 && "$DRY_RUN" == false ]]; then
    echo "Note: Non-root user. Commands will fail without sudo. Re-run with sudo."
  fi

  run "ln -sf $PY_BIN $SYMLINK"
fi

# Verification
echo "Verification: which python -> $(command -v python || true)"
if command -v python >/dev/null 2>&1; then
  echo "python --version -> $(python --version 2>&1)"
else
  echo "python is not in PATH after change. You may need to re-open your shell or add /usr/local/bin to PATH."
fi

# macOS / Windows notes (non-executed):
# - macOS: Use 'brew install python@3.x' then 'brew link --force --overwrite python@3.x' or use pyenv.
# - Windows: Use the Python installer or 'py' launcher. You can set a default with 'py -3.11' or update PATH.

exit 0
