#!/bin/bash
#=============================================================================
# Debug version of WebOps Addon Contract Signing Script
#=============================================================================

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(dirname "$SCRIPT_DIR")/lib"
ADDONS_DIR="$(dirname "$SCRIPT_DIR")/addons"

# Override WEBOPS_ROOT to use local directory
export WEBOPS_ROOT="$(dirname "$SCRIPT_DIR")"

# Source required libraries
source "$LIB_DIR/common.sh"

# Contract signing configuration
CONTRACTS_DIR="${WEBOPS_ROOT}/contracts"
SIGNATURES_DIR="$CONTRACTS_DIR/signatures"

# Ensure directories exist
mkdir -p "$CONTRACTS_DIR" "$SIGNATURES_DIR"

log_info "Debug: WebOps Addon Contract Signing Script"
log_info "Debug: ===================================="

# Find all addon files
addons=()
for addon_file in "$ADDONS_DIR"/*.sh; do
    if [[ -f "$addon_file" ]]; then
        local addon_name
        addon_name=$(basename "$addon_file" .sh)
        addons+=("$addon_name")
        log_info "Debug: Found addon: $addon_name"
    fi
done

log_info "Debug: Total addons found: ${#addons[@]}"
log_info "Debug: Addons list: ${addons[*]}"

# Process each addon with detailed logging
for addon in "${addons[@]}"; do
    log_info "Debug: ===== Starting processing for addon: $addon ====="
    
    # Check if addon file exists
    local addon_file="$ADDONS_DIR/${addon}.sh"
    if [[ ! -f "$addon_file" ]]; then
        log_error "Debug: Addon file not found: $addon_file"
        continue
    fi
    
    log_info "Debug: Addon file exists: $addon_file"
    
    # Try to source the addon
    log_info "Debug: Attempting to source addon file..."
    if source "$addon_file"; then
        log_info "Debug: Successfully sourced addon file"
    else
        log_error "Debug: Failed to source addon file"
        continue
    fi
    
    # Check if required functions exist
    log_info "Debug: Checking for required functions..."
    
    if declare -f addon_metadata >/dev/null; then
        log_info "Debug: addon_metadata function exists"
    else
        log_error "Debug: addon_metadata function missing"
        continue
    fi
    
    if declare -f addon_sla >/dev/null; then
        log_info "Debug: addon_sla function exists"
    else
        log_error "Debug: addon_sla function missing"
        continue
    fi
    
    if declare -f addon_security >/dev/null; then
        log_info "Debug: addon_security function exists"
    else
        log_error "Debug: addon_security function missing"
        continue
    fi
    
    log_info "Debug: ===== Completed processing for addon: $addon ====="
    echo
done

log_info "Debug: Script completed successfully"