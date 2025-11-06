#!/bin/bash
#
# WebOps Platform Installer
# Quick installation script for the WebOps hosting platform
#
# Usage: sudo ./install.sh
#
# This script performs a complete installation of the WebOps platform
# including base system hardening and core components.
#

set -euo pipefail

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration
readonly WEBOPS_VERSION="v1.0.0"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEBOPS_VERSION_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
WEBOPS_PLATFORM_DIR="$(dirname "$(dirname "$WEBOPS_VERSION_DIR")")"
readonly SCRIPT_DIR WEBOPS_VERSION_DIR WEBOPS_PLATFORM_DIR
readonly WEBOPS_BIN="${WEBOPS_VERSION_DIR}/bin/webops"

# Logging setup
readonly LOG_DIR="/var/log/webops"
readonly INSTALL_LOG="${LOG_DIR}/install-$(date +%Y%m%d-%H%M%S).log"

# Initialize logging
init_logging() {
    # Create log directory
    mkdir -p "$LOG_DIR"
    chmod 755 "$LOG_DIR"

    # Redirect all output to log file and console
    exec > >(tee -a "$INSTALL_LOG")
    exec 2>&1

    echo "Installation log: $INSTALL_LOG"
    echo "Started at: $(date)"
    echo ""
}

#=============================================================================
# Configuration Functions
#=============================================================================

load_config() {
    local config_file="${WEBOPS_PLATFORM_DIR}/config.env"

    if [[ -f "$config_file" ]]; then
        # Source the config file
        set +u  # Temporarily allow unset variables
        source "$config_file"
        set -u
        return 0
    fi
    return 1
}

#=============================================================================
# Logging Functions
#=============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

#=============================================================================
# Installation Functions
#=============================================================================

copy_to_install_location() {
    local target_root current_root
    target_root="${WEBOPS_INSTALL_ROOT:-/opt/webops}"
    current_root="$(dirname "$(dirname "$WEBOPS_PLATFORM_DIR")")"

    # Normalize paths for comparison
    target_root="$(readlink -f "$target_root" 2>/dev/null || echo "$target_root")"
    current_root="$(readlink -f "$current_root" 2>/dev/null || echo "$current_root")"

    # Check if we're already at the target location
    if [[ "$current_root" == "$target_root" ]]; then
        log_info "Already running from installation directory: $target_root"
        return 0
    fi

    log_step "Copying WebOps to installation directory..."
    log_info "Source: $current_root"
    log_info "Target: $target_root"

    # Create parent directory if needed
    mkdir -p "$(dirname "$target_root")"

    # Check if target already exists
    if [[ -d "$target_root" ]]; then
        log_warn "Target directory already exists: $target_root"
        read -p "Remove existing installation and continue? (yes/no): " -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            log_info "Installation cancelled by user"
            exit 0
        fi
        log_info "Removing existing directory..."
        rm -rf "$target_root"
    fi

    # Copy repository to target location
    log_info "Copying repository to $target_root..."
    cp -a "$current_root" "$target_root"

    # Verify copy succeeded
    if [[ ! -d "$target_root/.webops/versions/${WEBOPS_VERSION}" ]]; then
        log_error "Failed to copy repository to $target_root"
        exit 1
    fi

    log_success "Repository copied successfully ✓"

    # Re-execute from new location
    local new_script="$target_root/.webops/versions/${WEBOPS_VERSION}/lifecycle/install.sh"

    log_info "Re-executing installer from $target_root..."
    echo ""

    # Export flag to prevent infinite loop
    export WEBOPS_ALREADY_RELOCATED=true

    exec "$new_script" "$@"
}

validate_environment() {
    log_step "Validating installation environment..."

    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi

    # Check if WebOps platform exists
    if [[ ! -d "${WEBOPS_VERSION_DIR}" ]]; then
        log_error "WebOps platform version ${WEBOPS_VERSION} not found"
        log_error "Please ensure you're running this script from the WebOps repository root"
        exit 1
    fi

    # Check if webops binary exists
    if [[ ! -x "${WEBOPS_BIN}" ]]; then
        log_error "WebOps binary not found: ${WEBOPS_BIN}"
        exit 1
    fi

    # Check for existing installation
    if [[ -f "${WEBOPS_PLATFORM_DIR}/config.env" ]]; then
        log_warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_warn "⚠️  WARNING: Existing WebOps installation detected"
        log_warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_warn ""
        log_warn "Config file exists: ${WEBOPS_PLATFORM_DIR}/config.env"
        log_warn ""
        log_warn "Running install again may:"
        log_warn "  • Overwrite existing configuration"
        log_warn "  • Reset SSH settings"
        log_warn "  • Restart services (causing downtime)"
        log_warn ""
        log_warn "If you want to:"
        log_warn "  • Update: Use '${WEBOPS_BIN} update' instead"
        log_warn "  • Repair: Use './.webops/versions/${WEBOPS_VERSION}/lifecycle/repair.sh' instead"
        log_warn "  • Reinstall: Remove ${WEBOPS_PLATFORM_DIR}/config.env first"
        log_warn ""
        read -p "Continue anyway? (type 'yes' to proceed): " -r
        echo ""
        if [[ ! $REPLY == "yes" ]]; then
            log_info "Installation cancelled by user"
            exit 0
        fi
        log_warn "Proceeding with installation (may overwrite existing setup)..."
    fi

    log_info "Environment validation passed ✓"
}

show_welcome() {
    echo -e "${BLUE}"
    cat <<'EOF'
╦ ╦┌─┐┌┐ ╔═╗┌─┐┌─┐
║║║├┤ ├┴┐║ ║├─┘└─┐
╚╩╝└─┘└─┘╚═╝┴  └─┘
VPS Hosting Platform Installer
EOF
    echo -e "${NC}"

    echo -e "${GREEN}Welcome to WebOps Platform Installation!${NC}"
    echo -e "${BLUE}Version:${NC} ${WEBOPS_VERSION}"
    echo ""
    echo -e "${YELLOW}This installer will:${NC}"
    echo "  • Harden the base system for security"
    echo "  • Install core WebOps platform components"
    echo "  • Configure PostgreSQL database"
    echo "  • Set up monitoring and logging"
    echo "  • Install the Django control panel"
    echo ""

    echo -e "${RED}⚠️  IMPORTANT SECURITY CHANGES:${NC}"
    echo -e "${YELLOW}By default, this installer will:${NC}"
    echo "  • Configure SSH to allow root login with keys only (prohibit-password)"
    echo "  • Disable SSH password authentication (SSH keys required)"
    echo "  • Configure firewall rules (SSH, HTTP, HTTPS)"
    echo ""
    echo -e "${YELLOW}Before continuing, ensure you have:${NC}"
    echo "  ✓ SSH key-based authentication set up for this server"
    echo "  ✓ Console/VNC access to your server (backup access method)"
    echo "  ✓ Reviewed the configuration that will be created"
    echo ""
    echo -e "${BLUE}To customize SSH security settings:${NC}"
    echo "  • To disable SSH hardening: set ENABLE_SSH_HARDENING=false"
    echo "  • To disable root login entirely: set PERMIT_ROOT_LOGIN=no"
    echo "  • To allow password auth: set SSH_PASSWORD_AUTH=yes"
    echo "  • Edit ${WEBOPS_PLATFORM_DIR}/config.env after this step"
    echo ""

    read -p "Do you want to continue? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "Installation cancelled"
        exit 0
    fi
    echo ""
}

create_default_config() {
    log_step "Creating default configuration..."

    local config_file="${WEBOPS_PLATFORM_DIR}/config.env"

    # Detect installation root (parent directory of .webops)
    local detected_root="$(cd "$(dirname "${WEBOPS_PLATFORM_DIR}")" && pwd)"

    # Use detected path for development, /opt/webops for production
    local install_root="${WEBOPS_INSTALL_ROOT:-/opt/webops}"

    log_info "Installation root: $install_root"

    # Create default configuration
    cat > "$config_file" <<EOF
# WebOps Platform Configuration
# Generated by install.sh on $(date)

# Platform Configuration
WEBOPS_VERSION=${WEBOPS_VERSION}
WEBOPS_PLATFORM_DIR=${WEBOPS_PLATFORM_DIR}

# System Configuration
WEBOPS_USER=webops
WEBOPS_ROOT=${install_root}
CONTROL_PANEL_DIR=${install_root}/control-panel
DEPLOYMENTS_DIR=${install_root}/deployments
SHARED_DIR=${install_root}/shared
BACKUPS_DIR=${install_root}/backups
WEBOPS_DATA_DIR=${install_root}/data
WEBOPS_LOG_DIR=/var/log/webops
WEBOPS_RUN_DIR=/var/run/webops

# Database Configuration
POSTGRES_ENABLED=true
POSTGRES_VERSION=14
POSTGRES_DATA_DIR=${install_root}/postgresql/data

# Control Panel Configuration
CONTROL_PANEL_ENABLED=true
CONTROL_PANEL_PORT=8000
CONTROL_PANEL_HOST=0.0.0.0

# Monitoring Configuration
MONITORING_ENABLED=true
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000

# Security Configuration
ENABLE_FIREWALL=true
ENABLE_FAIL2BAN=true
ENABLE_AUTO_UPDATES=false

# SSH Security Configuration
# Set ENABLE_SSH_HARDENING=false to skip SSH hardening entirely
ENABLE_SSH_HARDENING=true
# Root login options: no, yes, prohibit-password, forced-commands-only
PERMIT_ROOT_LOGIN=prohibit-password
# Password authentication (set to yes to allow password login as fallback)
SSH_PASSWORD_AUTH=no
# Maximum authentication attempts before disconnect
SSH_MAX_AUTH_TRIES=3

# Feature Flags
ENABLE_KUBERNETES=false
ENABLE_KVM=false
ENABLE_PATRONI=false
EOF

    log_info "Default configuration created at $config_file"
}

run_installation() {
    log_step "Starting WebOps platform installation..."
    
    # Create configuration file
    create_default_config
    
    # Run the platform installation
    log_info "Executing: ${WEBOPS_BIN} install --config ${WEBOPS_PLATFORM_DIR}/config.env --yes"
    
    if "${WEBOPS_BIN}" install --config "${WEBOPS_PLATFORM_DIR}/config.env" --yes; then
        log_success "WebOps platform installation completed successfully ✓"
        return 0
    else
        log_error "WebOps platform installation failed"
        return 1
    fi
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

verify_installation() {
    log_step "Verifying installation health..."

    local failed_checks=0
    local total_checks=0

    # Check critical services
    local services=("postgresql" "redis-server" "webops-web" "webops-worker")

    for service in "${services[@]}"; do
        ((total_checks++))
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            log_info "✓ $service is running"
        else
            log_warn "✗ $service is not running"
            ((failed_checks++))
        fi
    done

    # Check Redis connectivity
    ((total_checks++))
    if redis-cli ping &>/dev/null; then
        log_info "✓ Redis is responding to PING"
    else
        log_warn "✗ Redis is not responding"
        ((failed_checks++))
    fi

    # Check PostgreSQL connectivity
    ((total_checks++))
    if sudo -u postgres psql -c "SELECT 1" &>/dev/null; then
        log_info "✓ PostgreSQL is accepting connections"
    else
        log_warn "✗ PostgreSQL is not accepting connections"
        ((failed_checks++))
    fi

    # Check control panel port
    ((total_checks++))
    if ss -tulpn | grep -q ":8000 "; then
        log_info "✓ Control panel is listening on port 8000"
    else
        log_warn "✗ Control panel is not listening on port 8000"
        ((failed_checks++))
    fi

    # Summary
    echo ""
    if [[ $failed_checks -eq 0 ]]; then
        log_success "All health checks passed ($total_checks/$total_checks) ✓"
        return 0
    else
        log_warn "Health checks: $(($total_checks - $failed_checks))/$total_checks passed, $failed_checks failed"
        log_warn "Some services may need manual investigation"
        return 1
    fi
}

print_completion_message() {
    local server_ip=$(hostname -I | awk '{print $1}')

    # Load install root from config
    local install_root="/opt/webops"
    if [[ -f "${WEBOPS_PLATFORM_DIR}/config.env" ]]; then
        install_root=$(grep "^WEBOPS_ROOT=" "${WEBOPS_PLATFORM_DIR}/config.env" | cut -d'=' -f2)
    fi

    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║  🎉  WebOps Installation Complete!                           ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Platform Version:${NC} ${WEBOPS_VERSION}"
    echo -e "${BLUE}Control Panel URL:${NC} http://${server_ip}:8000/"
    echo ""
    echo -e "${YELLOW}Admin Credentials:${NC}"
    echo "  Location: ${install_root}/.secrets/admin_credentials.txt"
    echo "  View with: sudo cat ${install_root}/.secrets/admin_credentials.txt"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Access the control panel in your browser"
    echo "  2. Login with the admin credentials"
    echo "  3. Change your password after first login"
    echo "  4. Deploy your first application!"
    echo ""
    echo -e "${YELLOW}Platform Management:${NC}"
    echo "  Status: ${WEBOPS_BIN} state"
    echo "  Validate: ${WEBOPS_BIN} validate"
    echo "  Update: ${WEBOPS_BIN} update"
    echo "  Rollback: ${WEBOPS_BIN} rollback"
    echo ""
    echo -e "${BLUE}Documentation:${NC} ${WEBOPS_PLATFORM_DIR}/docs/"
    echo ""
    echo -e "${GREEN}Installation completed successfully! 🚀${NC}"
}

#=============================================================================
# Main Installation Flow
#=============================================================================

main() {
    # Initialize logging
    init_logging

    # Copy to install location if not already there (unless already relocated)
    if [[ "${WEBOPS_ALREADY_RELOCATED:-false}" != "true" ]]; then
        copy_to_install_location "$@"
    fi

    # Show welcome message
    show_welcome

    # Validate environment
    validate_environment

    # Run installation
    if run_installation; then
        # Verify installation health
        verify_installation

        # Print completion message
        print_completion_message

        log_info "Installation log saved to: $INSTALL_LOG"
        exit 0
    else
        log_error "Installation failed. Please check the logs above."
        log_error "Full log available at: $INSTALL_LOG"
        exit 1
    fi
}

# Run main function
main "$@"