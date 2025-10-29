#!/bin/bash
#=============================================================================
# Simple Debug Script for Addon Contract Signing
#=============================================================================

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADDONS_DIR="$(dirname "$SCRIPT_DIR")/addons"

echo "Debug: Script directory: $SCRIPT_DIR"
echo "Debug: Addons directory: $ADDONS_DIR"

# Find all addon files
echo "Debug: Looking for addon files..."
for addon_file in "$ADDONS_DIR"/*.sh; do
    if [[ -f "$addon_file" ]]; then
        addon_name=$(basename "$addon_file" .sh)
        echo "Debug: Found addon: $addon_name (file: $addon_file)"
    fi
done

echo "Debug: Script completed successfully"