#!/bin/bash
#
# WebOps Addon Contract Hash Fix Script
# Adds missing validation_hash fields to existing contracts
#

set -euo pipefail

# Source libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
source "${SCRIPT_DIR}/../lib/addon-contract.sh"

# Contract directory
CONTRACTS_DIR="${SCRIPT_DIR}/../contracts"

# Function to add validation hash to a contract file
add_validation_hash() {
    local addon_name="$1"
    local contract_file="${CONTRACTS_DIR}/${addon_name}-contract.json"
    
    if [[ ! -f "$contract_file" ]]; then
        log_warn "Contract file not found: $contract_file"
        return 1
    fi
    
    log_info "Adding validation hash to $addon_name contract..."
    
    # Generate hash for the addon
    local addon_file="${SCRIPT_DIR}/../addons/${addon_name}.sh"
    local hash
    hash=$(generate_contract_hash "$addon_file")
    
    if [[ -z "$hash" ]]; then
        log_error "Failed to generate hash for $addon_name"
        return 1
    fi
    
    # Add validation_hash before the closing brace
    # This is a simple sed replacement that works without jq
    sed -i "s/\"status\": \"active\"/\"validation_hash\": \"$hash\",\n    \"status\": \"active\"/" "$contract_file"
    
    log_success "Added validation hash to $addon_name contract"
}

# Process all addon contracts
echo "Fixing validation hashes in all addon contracts..."
echo

for addon in autorecovery etcd kubernetes kvm monitoring patroni postgresql; do
    echo "Processing: $addon"
    add_validation_hash "$addon"
    echo
done

echo "All contract hashes have been fixed!"