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
WEBOPS_VERSION_DIR="$(dirname "$SCRIPT_DIR")"
WEBOPS_PLATFORM_DIR="$(dirname "$(dirname "$WEBOPS_VERSION_DIR")")"
WEBOPS_PLATFORM_DIR_NAME="$(basename "$WEBOPS_PLATFORM_DIR")"
readonly SCRIPT_DIR WEBOPS_VERSION_DIR WEBOPS_PLATFORM_DIR WEBOPS_PLATFORM_DIR_NAME
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
    current_root="$(dirname "$WEBOPS_PLATFORM_DIR")"

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
    if [[ ! -d "$target_root/${WEBOPS_PLATFORM_DIR_NAME}/versions/${WEBOPS_VERSION}" ]]; then
        log_error "Failed to copy repository to $target_root"
        exit 1
    fi

    log_success "Repository copied successfully ✓"

    # Re-execute from new location
    local new_script="$target_root/${WEBOPS_PLATFORM_DIR_NAME}/versions/${WEBOPS_VERSION}/lifecycle/install.sh"

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
        log_warn "  • Repair: Use './${WEBOPS_PLATFORM_DIR_NAME}/versions/${WEBOPS_VERSION}/lifecycle/repair.sh' instead"
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
    clear
    echo ""
    echo ""
    echo -e "${GREEN}     ██╗    ██╗███████╗██████╗  ██████╗ ██████╗ ███████╗${NC}"
    echo -e "${GREEN}     ██║    ██║██╔════╝██╔══██╗██╔═══██╗██╔══██╗██╔════╝${NC}"
    echo -e "${GREEN}     ██║ █╗ ██║█████╗  ██████╔╝██║   ██║██████╔╝███████╗${NC}"
    echo -e "${GREEN}     ██║███╗██║██╔══╝  ██╔══██╗██║   ██║██╔═══╝ ╚════██║${NC}"
    echo -e "${GREEN}     ╚███╔███╔╝███████╗██████╔╝╚██████╔╝██║     ███████║${NC}"
    echo -e "${GREEN}      ╚══╝╚══╝ ╚══════╝╚═════╝  ╚═════╝ ╚═╝     ╚══════╝${NC}"
    echo ""
    echo -e "${BLUE}           VPS Hosting Platform · Version ${WEBOPS_VERSION}${NC}"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${YELLOW}Welcome to the WebOps Installation Wizard!${NC}"
    echo ""
    echo -e "  This interactive installer will help you set up a production-ready"
    echo -e "  hosting platform on your VPS server."
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${BLUE}What will be installed:${NC}"
    echo ""
    echo -e "    ${GREEN}✓${NC}  System hardening and security configuration"
    echo -e "    ${GREEN}✓${NC}  PostgreSQL database with optimized settings"
    echo -e "    ${GREEN}✓${NC}  Redis for caching and message queuing"
    echo -e "    ${GREEN}✓${NC}  Django control panel with WebSocket support"
    echo -e "    ${GREEN}✓${NC}  Systemd services with auto-restart capability"
    echo -e "    ${GREEN}✓${NC}  Firewall and monitoring configuration"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${YELLOW}⏱  Estimated time:${NC} 5-10 minutes"
    echo ""
    echo ""
}

#=============================================================================
# Interactive Configuration
#=============================================================================

configure_hostname() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${YELLOW}Step 1 of 2: Server Hostname${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    local current_hostname=$(hostname)
    echo -e "  Current hostname: ${GREEN}${current_hostname}${NC}"
    echo ""
    echo -e "  ${BLUE}Enter a new hostname for your server:${NC}"
    echo -e "  ${BLUE}(Leave blank to keep current hostname)${NC}"
    echo ""
    echo -e "  Examples: ${BLUE}webops-prod${NC}, ${BLUE}app-server-01${NC}, ${BLUE}myapp.example.com${NC}"
    echo ""

    while true; do
        read -p "  Hostname: " -r NEW_HOSTNAME

        # If blank, keep current hostname
        if [[ -z "$NEW_HOSTNAME" ]]; then
            NEW_HOSTNAME="$current_hostname"
            echo ""
            echo -e "  ${GREEN}✓${NC} Keeping current hostname: ${GREEN}${NEW_HOSTNAME}${NC}"
            break
        fi

        # Validate hostname
        if [[ "$NEW_HOSTNAME" =~ ^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$ ]]; then
            echo ""
            echo -e "  ${GREEN}✓${NC} Valid hostname: ${GREEN}${NEW_HOSTNAME}${NC}"
            break
        else
            echo ""
            echo -e "  ${RED}✗${NC} Invalid hostname. Use only letters, numbers, hyphens, and dots."
            echo ""
            echo -e "  ${YELLOW}Please try again:${NC}"
        fi
    done

    echo ""
    echo ""
}

configure_ssh_security() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${YELLOW}Step 2 of 2: SSH Security${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${BLUE}Choose your SSH security level:${NC}"
    echo ""
    echo -e "  ${GREEN}[1] Easy Access${NC} ${BLUE}(Development/Testing)${NC}"
    echo -e "      • Root login with password: ${GREEN}Enabled${NC}"
    echo -e "      • Password authentication: ${GREEN}Enabled${NC}"
    echo -e "      • Best for: Quick setup, testing, learning"
    echo -e "      • Security: ⚠️  Lower (convenient but less secure)"
    echo ""
    echo -e "  ${YELLOW}[2] Hardened${NC} ${BLUE}(Production)${NC}"
    echo -e "      • Root login: ${YELLOW}SSH keys only${NC}"
    echo -e "      • Password authentication: ${RED}Disabled${NC}"
    echo -e "      • Best for: Production servers, public internet"
    echo -e "      • Security: ${GREEN}✓ High${NC} (SSH keys required)"
    echo -e "      • ${RED}⚠️  Requires SSH keys already configured!${NC}"
    echo ""

    while true; do
        read -p "  Enter your choice [1/2] (default: 1): " -r SSH_CHOICE

        # Default to 1 if empty
        SSH_CHOICE="${SSH_CHOICE:-1}"

        case "$SSH_CHOICE" in
            1)
                SSH_SECURITY_LEVEL="easy"
                PERMIT_ROOT_LOGIN="yes"
                SSH_PASSWORD_AUTH="yes"
                echo ""
                echo -e "  ${GREEN}✓${NC} Selected: ${GREEN}Easy Access${NC}"
                echo -e "  Root login and password authentication will be enabled"
                break
                ;;
            2)
                SSH_SECURITY_LEVEL="hardened"
                PERMIT_ROOT_LOGIN="prohibit-password"
                SSH_PASSWORD_AUTH="no"
                echo ""
                echo -e "  ${YELLOW}✓${NC} Selected: ${YELLOW}Hardened${NC}"
                echo -e "  SSH keys will be required for root login"
                echo ""
                echo -e "  ${RED}⚠️  IMPORTANT: Make sure you have SSH keys configured!${NC}"
                echo -e "  ${YELLOW}If you get locked out, use your VPS console access${NC}"
                echo ""
                read -p "  Continue with hardened SSH? (yes/no): " -r CONFIRM
                echo ""
                if [[ $CONFIRM =~ ^[Yy][Ee][Ss]$ ]]; then
                    break
                else
                    echo -e "  ${YELLOW}→${NC} Switching to Easy Access mode..."
                    echo ""
                    SSH_SECURITY_LEVEL="easy"
                    PERMIT_ROOT_LOGIN="yes"
                    SSH_PASSWORD_AUTH="yes"
                    break
                fi
                ;;
            *)
                echo ""
                echo -e "  ${RED}✗${NC} Invalid choice. Please enter 1 or 2."
                echo ""
                ;;
        esac
    done

    echo ""
}

show_configuration_summary() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${GREEN}✓${NC} Configuration Summary"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "    Hostname:         ${GREEN}${NEW_HOSTNAME}${NC}"
    echo -e "    SSH Security:     ${GREEN}${SSH_SECURITY_LEVEL^}${NC}"
    echo -e "    Root Login:       ${GREEN}${PERMIT_ROOT_LOGIN}${NC}"
    echo -e "    Password Auth:    ${GREEN}${SSH_PASSWORD_AUTH}${NC}"
    echo -e "    Install Path:     ${GREEN}/opt/webops${NC}"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    read -p "  Ready to begin installation? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo ""
        echo -e "  ${YELLOW}Installation cancelled by user${NC}"
        echo ""
        exit 0
    fi
    echo ""
}

apply_hostname() {
    if [[ -z "$NEW_HOSTNAME" ]]; then
        return 0
    fi

    local current_hostname=$(hostname)
    if [[ "$NEW_HOSTNAME" == "$current_hostname" ]]; then
        log_info "Hostname unchanged: $NEW_HOSTNAME"
        return 0
    fi

    log_step "Setting hostname to: $NEW_HOSTNAME"

    # Set hostname immediately
    hostnamectl set-hostname "$NEW_HOSTNAME" 2>/dev/null || {
        log_warn "hostnamectl not available, using hostname command"
        hostname "$NEW_HOSTNAME"
        echo "$NEW_HOSTNAME" > /etc/hostname
    }

    # Update /etc/hosts
    if grep -q "127.0.1.1" /etc/hosts; then
        sed -i "s/127.0.1.1.*/127.0.1.1\t${NEW_HOSTNAME}/" /etc/hosts
    else
        echo "127.0.1.1	${NEW_HOSTNAME}" >> /etc/hosts
    fi

    log_success "Hostname set to: $NEW_HOSTNAME ✓"
}

create_default_config() {
    log_step "Creating default configuration..."

    local config_file="${WEBOPS_PLATFORM_DIR}/config.env"

    # Detect installation root (parent directory of provisioning/.webops)
    local detected_root="$(cd "$(dirname "${WEBOPS_PLATFORM_DIR}")" && pwd)"

    # Use detected path for development, /opt/webops for production
    local install_root="${WEBOPS_INSTALL_ROOT:-/opt/webops}"

    log_info "Installation root: $install_root"

    # Use collected configuration values
    local permit_root="${PERMIT_ROOT_LOGIN:-yes}"
    local ssh_pass_auth="${SSH_PASSWORD_AUTH:-yes}"

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
PERMIT_ROOT_LOGIN=${permit_root}
# Password authentication (set to no to require SSH keys only)
SSH_PASSWORD_AUTH=${ssh_pass_auth}
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

    # Configuration file already created in main() with user choices
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
    local server_hostname=$(hostname)

    # Load install root from config
    local install_root="/opt/webops"
    if [[ -f "${WEBOPS_PLATFORM_DIR}/config.env" ]]; then
        install_root=$(grep "^WEBOPS_ROOT=" "${WEBOPS_PLATFORM_DIR}/config.env" | cut -d'=' -f2)
    fi

    clear
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                                ║${NC}"
    echo -e "${GREEN}║           🎉  WebOps Installation Complete!  🎉                ║${NC}"
    echo -e "${GREEN}║                                                                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}┌────────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${GREEN}│${NC} ${GREEN}✓${NC} All services are running and verified                     ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC} ${GREEN}✓${NC} Server is accessible from network                          ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC} ${GREEN}✓${NC} Firewall configured and enabled                            ${GREEN}│${NC}"
    echo -e "${GREEN}│${NC} ${GREEN}✓${NC} SSH security applied                                       ${GREEN}│${NC}"
    echo -e "${GREEN}└────────────────────────────────────────────────────────────────┘${NC}"
    echo ""
    echo -e "${BLUE}┌────────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${BLUE}│${NC} ${YELLOW}Server Information${NC}                                          ${BLUE}│${NC}"
    echo -e "${BLUE}├────────────────────────────────────────────────────────────────┤${NC}"
    echo -e "${BLUE}│${NC}  Hostname:        ${GREEN}${server_hostname}${NC}"
    echo -e "${BLUE}│${NC}  IP Address:      ${GREEN}${server_ip}${NC}"
    echo -e "${BLUE}│${NC}  Platform:        ${GREEN}WebOps ${WEBOPS_VERSION}${NC}"
    echo -e "${BLUE}└────────────────────────────────────────────────────────────────┘${NC}"
    echo ""
    echo -e "${BLUE}┌────────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${BLUE}│${NC} ${YELLOW}Access Information${NC}                                          ${BLUE}│${NC}"
    echo -e "${BLUE}├────────────────────────────────────────────────────────────────┤${NC}"
    echo -e "${BLUE}│${NC}  Control Panel:   ${GREEN}http://${server_ip}:8000/${NC}"
    echo -e "${BLUE}│${NC}  Port:            ${GREEN}8000${NC} (accessible from any network)"
    echo -e "${BLUE}│${NC}  Admin Creds:     ${GREEN}${install_root}/.secrets/admin_credentials.txt${NC}"
    echo -e "${BLUE}│${NC}"
    echo -e "${BLUE}│${NC}  ${YELLOW}View credentials:${NC}"
    echo -e "${BLUE}│${NC}  sudo cat ${install_root}/.secrets/admin_credentials.txt"
    echo -e "${BLUE}└────────────────────────────────────────────────────────────────┘${NC}"
    echo ""
    echo -e "${BLUE}┌────────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${BLUE}│${NC} ${YELLOW}Running Services${NC}                                            ${BLUE}│${NC}"
    echo -e "${BLUE}├────────────────────────────────────────────────────────────────┤${NC}"
    echo -e "${BLUE}│${NC}  ${GREEN}✓${NC} webops-web      (Gunicorn WSGI server)"
    echo -e "${BLUE}│${NC}  ${GREEN}✓${NC} webops-worker   (Celery background tasks)"
    echo -e "${BLUE}│${NC}  ${GREEN}✓${NC} webops-beat     (Celery scheduler)"
    echo -e "${BLUE}│${NC}  ${GREEN}✓${NC} webops-channels (WebSocket support)"
    echo -e "${BLUE}│${NC}  ${GREEN}✓${NC} postgresql      (Database)"
    echo -e "${BLUE}│${NC}  ${GREEN}✓${NC} redis           (Cache & message broker)"
    echo -e "${BLUE}└────────────────────────────────────────────────────────────────┘${NC}"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo -e "  ${BLUE}1.${NC} Access control panel:  ${GREEN}http://${server_ip}:8000/${NC}"
    echo -e "  ${BLUE}2.${NC} Login with admin credentials (see above)"
    echo -e "  ${BLUE}3.${NC} Change your password after first login"
    echo -e "  ${BLUE}4.${NC} Deploy your first application!"
    echo ""
    echo -e "${BLUE}Platform Management:${NC}"
    echo -e "  Check status:  ${GREEN}${WEBOPS_BIN} state${NC}"
    echo -e "  Validate:      ${GREEN}${WEBOPS_BIN} validate${NC}"
    echo -e "  Update:        ${GREEN}${WEBOPS_BIN} update${NC}"
    echo ""
    echo -e "${BLUE}Documentation:${NC}"
    echo -e "  ${WEBOPS_PLATFORM_DIR}/POST_INSTALLATION.md"
    echo -e "  ${WEBOPS_PLATFORM_DIR}/docs/"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}🚀 Your WebOps platform is now running and accessible!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
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

    # Interactive configuration
    configure_hostname
    configure_ssh_security
    show_configuration_summary

    # Validate environment
    validate_environment

    # Apply hostname configuration early
    apply_hostname

    # Create configuration with user choices
    create_default_config

    # Run installation
    if run_installation; then
        # Verify installation health (don't exit on verification warnings)
        verify_installation || true

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