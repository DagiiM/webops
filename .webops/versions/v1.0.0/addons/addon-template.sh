#!/bin/bash
#
# WebOps System Addon Template
#
# This template shows the required functions that all system addons MUST implement
# to be compatible with the unified addon system.
#
# Copy this file to create a new addon and implement each function.
#

set -euo pipefail

# Source common libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh" || true
source "${SCRIPT_DIR}/../lib/state.sh" || true

#=============================================================================
# REQUIRED: Addon Metadata
#=============================================================================
# This function MUST return JSON with addon information
# Called by the API layer to discover and register the addon

addon_metadata() {
    cat <<'EOF'
{
  "name": "example-addon",
  "display_name": "Example Addon",
  "version": "1.0.0",
  "description": "Example system addon demonstrating the contract",
  "category": "infrastructure",
  "maintainer": "WebOps Team",
  "license": "MIT",
  "documentation_url": "https://webops.dev/docs/addons/example",
  "depends": [],
  "provides": ["example-service"],
  "conflicts": []
}
EOF
}

#=============================================================================
# REQUIRED: Pre-flight Validation
#=============================================================================
# Check if the addon can be installed on this system
# Returns JSON with validation results

addon_validate() {
    local errors=()
    local warnings=()

    # Example: Check OS version
    if ! command -v systemctl &>/dev/null; then
        errors+=("systemd is required but not found")
    fi

    # Example: Check disk space
    local available_gb=$(df -BG / | awk 'NR==2 {print $4}' | sed 's/G//')
    if [[ $available_gb -lt 10 ]]; then
        warnings+=("Low disk space: ${available_gb}GB available, 10GB recommended")
    fi

    # Build JSON response
    local valid="true"
    if [[ ${#errors[@]} -gt 0 ]]; then
        valid="false"
    fi

    cat <<EOF
{
  "valid": $valid,
  "errors": [$(printf '"%s",' "${errors[@]}" | sed 's/,$//')]|,
  "warnings": [$(printf '"%s",' "${warnings[@]}" | sed 's/,$//')]
}
EOF
}

#=============================================================================
# REQUIRED: Install Addon
#=============================================================================
# Install the addon with optional configuration from stdin
# Configuration is provided as JSON via stdin
# Returns: exit code 0 on success, non-zero on failure

addon_install() {
    log_step "Installing example addon..."

    # Read configuration from stdin if provided
    local config=""
    if [[ -p /dev/stdin ]]; then
        config=$(cat)
    fi

    # Parse config with jq if available
    if command -v jq &>/dev/null && [[ -n "$config" ]]; then
        # Example: Get custom setting from config
        local custom_setting=$(echo "$config" | jq -r '.custom_setting // "default"')
        log_info "Using custom setting: $custom_setting"
    fi

    # Installation steps
    log_info "Step 1: Installing packages..."
    # pkg_install example-package

    log_info "Step 2: Creating directories..."
    # ensure_directory "/opt/example" "root:root" "755"

    log_info "Step 3: Configuring service..."
    # configure_service

    log_info "Step 4: Starting service..."
    # systemctl enable --now example.service

    log_success "Example addon installed successfully ✓"

    # Return version info (optional)
    cat <<'EOF'
{
  "version": "1.0.0",
  "message": "Installation completed successfully"
}
EOF

    return 0
}

#=============================================================================
# REQUIRED: Uninstall Addon
#=============================================================================
# Uninstall the addon
# Args:
#   $1: keep_data - "true" or "false" (default: true)
# Returns: exit code 0 on success

addon_uninstall() {
    local keep_data="${1:-true}"

    log_step "Uninstalling example addon..."

    # Stop services
    log_info "Stopping services..."
    # systemctl stop example.service || true
    # systemctl disable example.service || true

    # Remove packages
    log_info "Removing packages..."
    # pkg_remove example-package

    # Handle data
    if [[ "$keep_data" == "false" ]]; then
        log_warning "Removing data..."
        # rm -rf /var/lib/example
    else
        log_info "Keeping data (use keep_data=false to remove)"
    fi

    log_success "Example addon uninstalled ✓"

    return 0
}

#=============================================================================
# REQUIRED: Get Status
#=============================================================================
# Get current installation and health status
# Returns JSON with status information

addon_status() {
    local status="not_installed"
    local health="unknown"
    local version=""
    local details="{}"

    # Check if installed
    # if systemctl is-active --quiet example.service; then
    #     status="installed"
    #     health="healthy"
    #     version="1.0.0"
    # elif systemctl is-failed --quiet example.service; then
    #     status="installed"
    #     health="unhealthy"
    #     version="1.0.0"
    # fi

    # For this template, return not_installed
    cat <<EOF
{
  "status": "$status",
  "health": "$health",
  "version": "$version",
  "message": "",
  "details": $details
}
EOF
}

#=============================================================================
# REQUIRED: Configure Addon
#=============================================================================
# Apply configuration to the addon
# Configuration is provided as JSON via stdin

addon_configure() {
    log_step "Configuring example addon..."

    # Read configuration from stdin
    local config=""
    if [[ -p /dev/stdin ]]; then
        config=$(cat)
    fi

    if [[ -z "$config" ]]; then
        log_error "No configuration provided"
        return 1
    fi

    # Parse and apply configuration
    if command -v jq &>/dev/null; then
        # Example: Extract settings
        local port=$(echo "$config" | jq -r '.port // 8080')
        local workers=$(echo "$config" | jq -r '.workers // 4')

        log_info "Applying configuration: port=$port, workers=$workers"

        # Write config file
        # cat > /etc/example/config.conf <<CONF
        # port = $port
        # workers = $workers
        # CONF

        # Restart service if needed
        # systemctl restart example.service
    fi

    log_success "Configuration applied ✓"

    cat <<'EOF'
{
  "message": "Configuration applied successfully"
}
EOF

    return 0
}

#=============================================================================
# OPTIONAL: Health Check
#=============================================================================
# Perform detailed health check (optional, addon_status is used if not present)

addon_health_check() {
    local health="healthy"
    local issues=()

    # Check service status
    # if ! systemctl is-active --quiet example.service; then
    #     health="unhealthy"
    #     issues+=("Service is not running")
    # fi

    # Check connectivity
    # if ! curl -sf http://localhost:8080/health &>/dev/null; then
    #     health="unhealthy"
    #     issues+=("Health endpoint not responding")
    # fi

    cat <<EOF
{
  "health": "$health",
  "issues": [$(printf '"%s",' "${issues[@]}" | sed 's/,$//')]
}
EOF
}

#=============================================================================
# OPTIONAL: Metrics
#=============================================================================
# Return addon-specific metrics (optional)

addon_metrics() {
    cat <<'EOF'
{
  "requests_total": 1234,
  "requests_per_second": 42,
  "error_rate": 0.001,
  "uptime_seconds": 86400
}
EOF
}

#=============================================================================
# OPTIONAL: Backup
#=============================================================================
# Create a backup of addon data (optional)
# Args:
#   $1: backup_path - where to store the backup

addon_backup() {
    local backup_path="${1:-/tmp/example-backup}"

    log_step "Creating backup..."

    # Create backup
    # tar czf "$backup_path/example-$(date +%Y%m%d-%H%M%S).tar.gz" \
    #     /var/lib/example \
    #     /etc/example

    log_success "Backup created at $backup_path"

    return 0
}

#=============================================================================
# OPTIONAL: Restore
#=============================================================================
# Restore addon from backup (optional)
# Args:
#   $1: backup_file - path to backup file

addon_restore() {
    local backup_file="$1"

    if [[ ! -f "$backup_file" ]]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi

    log_step "Restoring from backup..."

    # Stop service
    # systemctl stop example.service

    # Restore files
    # tar xzf "$backup_file" -C /

    # Start service
    # systemctl start example.service

    log_success "Restore completed ✓"

    return 0
}

#=============================================================================
# Main entry point (for CLI usage)
#=============================================================================

# If script is executed directly (not sourced), run the function specified
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ $# -eq 0 ]]; then
        echo "Usage: $0 <function> [args...]"
        echo ""
        echo "Available functions:"
        echo "  metadata       - Show addon metadata"
        echo "  validate       - Run pre-flight validation"
        echo "  install        - Install the addon"
        echo "  uninstall      - Uninstall the addon"
        echo "  status         - Get installation status"
        echo "  configure      - Configure the addon"
        echo "  health_check   - Perform health check"
        echo "  metrics        - Get addon metrics"
        exit 1
    fi

    func="addon_$1"
    shift

    if declare -f "$func" >/dev/null 2>&1; then
        "$func" "$@"
    else
        echo "Error: Unknown function: $func"
        exit 1
    fi
fi
