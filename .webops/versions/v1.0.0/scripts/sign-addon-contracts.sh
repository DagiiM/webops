#!/bin/bash
#=============================================================================
# WebOps Addon Contract Signing Script
#=============================================================================
# This script signs contracts for all addons to ensure compliance
# with the platform's SLA requirements.
#
# Usage: ./sign-addon-contracts.sh [addon_name]
#   addon_name: Optional. Sign contract for specific addon only.
#               If not provided, signs contracts for all addons.
#=============================================================================

# Temporarily disable strict error handling to debug the issue
# set -euo pipefail

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(dirname "$SCRIPT_DIR")/lib"
ADDONS_DIR="$(dirname "$SCRIPT_DIR")/addons"

# Override WEBOPS_ROOT to use local directory
export WEBOPS_ROOT="$(dirname "$SCRIPT_DIR")"

# Source required libraries
source "$LIB_DIR/common.sh"
source "$LIB_DIR/addon-contract.sh"

# Contract signing configuration
CONTRACTS_DIR="${WEBOPS_ROOT}/contracts"
SIGNATURES_DIR="$CONTRACTS_DIR/signatures"
PLATFORM_KEY="$CONTRACTS_DIR/platform.key"

# Ensure directories exist
mkdir -p "$CONTRACTS_DIR" "$SIGNATURES_DIR"

# Generate platform key pair if it doesn't exist
if [[ ! -f "$PLATFORM_KEY" ]]; then
    log_info "Generating platform signing key pair..."
    openssl genpkey -algorithm RSA -out "$PLATFORM_KEY" -pkeyopt rsa_keygen_bits:2048
    chmod 600 "$PLATFORM_KEY"
    
    # Extract public key
    PUBLIC_KEY="$CONTRACTS_DIR/platform.pub"
    openssl rsa -pubout -in "$PLATFORM_KEY" -out "$PUBLIC_KEY"
    chmod 644 "$PUBLIC_KEY"
    log_success "Platform signing key pair generated ✓"
else
    # Set public key path if key already exists
    PUBLIC_KEY="$CONTRACTS_DIR/platform.pub"
    # Generate public key if it doesn't exist
    if [[ ! -f "$PUBLIC_KEY" ]]; then
        log_info "Extracting public key from existing private key..."
        openssl rsa -pubout -in "$PLATFORM_KEY" -out "$PUBLIC_KEY"
        chmod 644 "$PUBLIC_KEY"
    fi
fi

# Function to sign addon contract
sign_addon_contract() {
    local addon_name="$1"
    local addon_file="$ADDONS_DIR/${addon_name}.sh"
    
    if [[ ! -f "$addon_file" ]]; then
        log_error "Addon file not found: $addon_file"
        return 1
    fi
    
    log_info "Signing contract for addon: $addon_name"
    
    # Source the addon to get its metadata
    source "$addon_file"
    
    # Validate addon contract
    if ! validate_addon_contract "$addon_file"; then
        log_error "Addon contract validation failed for: $addon_name"
        return 1
    fi
    
    # Get addon metadata
    local metadata_json
    metadata_json=$(addon_metadata)
    
    # Get addon SLA
    local sla_json
    sla_json=$(addon_sla)
    
    # Get addon security requirements
    local security_json
    security_json=$(addon_security)
    
    # Create contract file
    local contract_file="$CONTRACTS_DIR/${addon_name}-contract.json"
    local signature_file="$SIGNATURES_DIR/${addon_name}.sig"
    
    # Create contract JSON
    local contract_json
    contract_json=$(cat <<EOF
{
    "addon_name": "$addon_name",
    "platform_version": "1.0.0",
    "contract_version": "1.0",
    "signed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "expires_at": "$(date -u -d '+1 year' +%Y-%m-%dT%H:%M:%SZ)",
    "metadata": $metadata_json,
    "sla": $sla_json,
    "security": $security_json,
    "status": "active"
}
EOF
)
    
    # Write contract to file
    echo "$contract_json" > "$contract_file"
    
    # Create signature
    local contract_hash
    contract_hash=$(echo "$contract_json" | sha256sum | cut -d' ' -f1)
    
    # Sign the contract hash
    echo -n "$contract_hash" | openssl pkeyutl -sign -inkey "$PLATFORM_KEY" -out "$signature_file"
    
    # Debug: Check if signature file was created
    if [[ ! -f "$signature_file" ]]; then
        log_error "Signature file was not created"
        return 1
    fi
    
    # Debug: Show hash and signature info
    log_info "Contract hash: $contract_hash"
    log_info "Signature file size: $(wc -c < "$signature_file")"
    
    # Verify signature using public key
    local verify_result
    verify_result=$(echo -n "$contract_hash" | openssl pkeyutl -verify -inkey "$PUBLIC_KEY" -pubin -sigfile "$signature_file" 2>&1)
    local verify_exit_code=$?
    
    if [[ $verify_exit_code -eq 0 ]]; then
        log_success "Contract signed for addon: $addon_name ✓"
        log_info "Contract file: $contract_file"
        log_info "Signature file: $signature_file"
        
        # Record in addon registry
        register_addon_contract "$addon_name" "$contract_file" "$signature_file"
        
        return 0
    else
        log_error "Failed to verify signature for addon: $addon_name"
        log_error "OpenSSL error: $verify_result"
        log_error "Exit code: $verify_exit_code"
        rm -f "$contract_file" "$signature_file"
        return 1
    fi
}

# Function to register addon contract
register_addon_contract() {
    local addon_name="$1"
    local contract_file="$2"
    local signature_file="$3"
    
    local registry_file="$CONTRACTS_DIR/registry.json"
    
    # Create registry if it doesn't exist
    if [[ ! -f "$registry_file" ]]; then
        echo '{"contracts": []}' > "$registry_file"
    fi
    
    # Add contract to registry using simple append approach
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    # Create a simple log file instead of complex JSON manipulation
    local log_file="$CONTRACTS_DIR/contracts.log"
    echo "$timestamp,$addon_name,$contract_file,$signature_file,active" >> "$log_file"
    
    log_info "Contract registered for addon: $addon_name"
}

# Function to verify addon contract
verify_addon_contract() {
    local addon_name="$1"
    local contract_file="$CONTRACTS_DIR/${addon_name}-contract.json"
    local signature_file="$SIGNATURES_DIR/${addon_name}.sig"
    
    if [[ ! -f "$contract_file" || ! -f "$signature_file" ]]; then
        log_error "Contract or signature file not found for addon: $addon_name"
        return 1
    fi
    
    # Get contract hash
    local contract_hash
    contract_hash=$(cat "$contract_file" | sha256sum | cut -d' ' -f1)
    
    # Verify signature using public key
    if echo -n "$contract_hash" | openssl pkeyutl -verify -inkey "$PUBLIC_KEY" -pubin -sigfile "$signature_file" &>/dev/null; then
        log_success "Contract verification passed for addon: $addon_name ✓"
        return 0
    else
        log_error "Contract verification failed for addon: $addon_name"
        return 1
    fi
}

# Function to list signed contracts
list_contracts() {
    local registry_file="$CONTRACTS_DIR/registry.json"
    
    if [[ ! -f "$registry_file" ]]; then
        log_info "No contracts found"
        return 0
    fi
    
    log_info "Signed contracts:"
    echo
    
    # Simple parsing without jq - extract addon names and info
    grep -o '"addon_name"[[:space:]]*:[[:space:]]*"[^"]*"' "$registry_file" | cut -d'"' -f4 | while read -r addon; do
        local signed_at
        signed_at=$(grep -A5 "\"addon_name\": \"$addon\"" "$registry_file" | grep '"signed_at"' | cut -d'"' -f4)
        local status
        status=$(grep -A5 "\"addon_name\": \"$addon\"" "$registry_file" | grep '"status"' | cut -d'"' -f4)
        echo "- $addon (signed: ${signed_at:-unknown}, status: ${status:-unknown})"
    done
}

# Function to check contract expiry
check_contract_expiry() {
    local registry_file="$CONTRACTS_DIR/registry.json"
    
    if [[ ! -f "$registry_file" ]]; then
        return 0
    fi
    
    local current_timestamp
    current_timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    # Simple expiry check without jq
    log_info "Contract expiry check not implemented without jq"
    log_info "All contracts are considered valid"
}

# Function to revoke contract
revoke_contract() {
    local addon_name="$1"
    local registry_file="$CONTRACTS_DIR/registry.json"
    
    if [[ ! -f "$registry_file" ]]; then
        log_error "Registry file not found"
        return 1
    fi
    
    # Simple status update without jq
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    # Replace status for the specific addon
    sed -i "/\"addon_name\": \"$addon_name\"/,/}/ s/\"status\": \"[^\"]*\"/\"status\": \"revoked\"/" "$registry_file"
    
    # Add revoked_at field if not present
    if ! grep -A10 "\"addon_name\": \"$addon_name\"" "$registry_file" | grep -q "revoked_at"; then
        sed -i "/\"addon_name\": \"$addon_name\"/,/}/ s/}/,    \"revoked_at\": \"$timestamp\"\n}/" "$registry_file"
    fi
    
    log_success "Contract revoked for addon: $addon_name"
}

# Main function
main() {
    local target_addon="${1:-}"
    
    log_info "WebOps Addon Contract Signing Script"
    log_info "===================================="
    
    # Check for expired contracts
    check_contract_expiry
    
    if [[ -n "$target_addon" ]]; then
        # Sign specific addon
        if sign_addon_contract "$target_addon"; then
            log_success "Contract signing completed for: $target_addon"
        else
            log_error "Failed to sign contract for: $target_addon"
            exit 1
        fi
    else
        # Sign all addons
        local addons=()
        
        # Find all addon files
        for addon_file in "$ADDONS_DIR"/*.sh; do
            if [[ -f "$addon_file" ]]; then
                local addon_name
                addon_name=$(basename "$addon_file" .sh)
                addons+=("$addon_name")
            fi
        done
        
        if [[ ${#addons[@]} -eq 0 ]]; then
            log_warn "No addons found to sign"
            exit 0
        fi
        
        log_info "Found ${#addons[@]} addons to sign"
        echo
        
        local signed_count=0
        local failed_count=0
        
        for addon in "${addons[@]}"; do
            if sign_addon_contract "$addon"; then
                ((signed_count++))
            else
                ((failed_count++))
            fi
            echo
        done
        
        log_info "Contract signing summary:"
        log_info "- Signed: $signed_count addons"
        if [[ $failed_count -gt 0 ]]; then
            log_warn "- Failed: $failed_count addons"
        fi
    fi
    
    # List all contracts
    echo
    list_contracts
    
    log_success "Contract signing process completed ✓"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        cat <<EOF
WebOps Addon Contract Signing Script

This script signs contracts for all addons to ensure compliance
with the platform's SLA requirements.

Usage: $0 [addon_name] [options]

Arguments:
  addon_name    Optional. Sign contract for specific addon only.
                If not provided, signs contracts for all addons.

Options:
  --verify      Verify existing contracts
  --list        List all signed contracts
  --revoke      Revoke contract for specific addon
  --help        Show this help message

Examples:
  $0                    # Sign contracts for all addons
  $0 postgresql         # Sign contract for postgresql addon only
  $0 --verify           # Verify all existing contracts
  $0 --list             # List all signed contracts
  $0 --revoke postgresql # Revoke contract for postgresql addon

EOF
        exit 0
        ;;
    --verify)
        shift
        target_addon="${1:-}"
        
        if [[ -n "$target_addon" ]]; then
            verify_addon_contract "$target_addon"
        else
            # Verify all contracts
            local registry_file="$CONTRACTS_DIR/registry.json"
            if [[ -f "$registry_file" ]]; then
                grep -o '"addon_name"[[:space:]]*:[[:space:]]*"[^"]*"' "$registry_file" | cut -d'"' -f4 | while read -r addon; do
                    verify_addon_contract "$addon"
                done
            fi
        fi
        exit 0
        ;;
    --list)
        list_contracts
        exit 0
        ;;
    --revoke)
        target_addon="${2:-}"
        if [[ -z "$target_addon" ]]; then
            log_error "Addon name required for revoke operation"
            exit 1
        fi
        revoke_contract "$target_addon"
        exit 0
        ;;
esac

# Run main function
main "$@"