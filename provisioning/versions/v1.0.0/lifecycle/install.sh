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
readonly DEFAULT_INSTALL_ROOT="/opt/webops"

# Logging setup
readonly LOG_DIR="/var/log/webops"
readonly INSTALL_LOG="${LOG_DIR}/install-$(date +%Y%m%d-%H%M%S).log"
readonly ROLLBACK_BASE_DIR="/var/backups/webops-install"
ROLLBACK_DIR=""
ROLLBACK_PREPARED=false
INSTALL_RESUME=false
INSTALL_DOCTOR=false
INSTALL_RECOVER_STAGED=false
WEBOPS_NEW_INSTALL_COPY="${WEBOPS_NEW_INSTALL_COPY:-false}"

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
    local config_file
    config_file="$(resolve_config_file_for_read)"

    if [[ -f "$config_file" ]]; then
        # Source the config file
        set +u  # Temporarily allow unset variables
        # shellcheck disable=SC1090
        source "$config_file"
        set -u
        return 0
    fi
    return 1
}

get_primary_config_file() {
    echo "$(dirname "${WEBOPS_PLATFORM_DIR}")/config.env"
}

get_legacy_config_file() {
    echo "${WEBOPS_PLATFORM_DIR}/config.env"
}

resolve_config_file_for_read() {
    local primary legacy
    primary="$(get_primary_config_file)"
    legacy="$(get_legacy_config_file)"

    if [[ -f "$primary" ]]; then
        echo "$primary"
    elif [[ -f "$legacy" ]]; then
        echo "$legacy"
    else
        echo "$primary"
    fi
}

detect_install_root() {
    local install_root
    install_root="${WEBOPS_INSTALL_ROOT:-$DEFAULT_INSTALL_ROOT}"

    local config_file
    config_file="$(resolve_config_file_for_read)"
    if [[ -f "$config_file" ]]; then
        local configured_root
        configured_root="$(grep "^WEBOPS_ROOT=" "$config_file" | tail -n 1 | cut -d'=' -f2- || true)"
        if [[ -n "$configured_root" ]]; then
            install_root="$configured_root"
        fi
    fi

    echo "$install_root"
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

    # A symlinked installation destination is never silently followed.
    if [[ -L "$target_root" ]]; then
        log_error "Refusing symlinked installation destination: $target_root"
        exit 1
    fi

    # Normalize paths for comparison
    target_root="$(readlink -f "$target_root" 2>/dev/null || echo "$target_root")"
    current_root="$(readlink -f "$current_root" 2>/dev/null || echo "$current_root")"

    # Check if we're already at the target location
    if [[ "$current_root" == "$target_root" ]]; then
        if [[ "$INSTALL_RECOVER_STAGED" == "true" ]]; then
            log_error "Run --recover-staged from the updated source checkout"
            exit 1
        fi
        # Direct invocations from an existing install root must also classify
        # previous attempts; otherwise they could redo setup or misreport success.
        if [[ -f "$target_root/.webops-install-origin" ||
              -f "$ROLLBACK_BASE_DIR/installation-inventory/inventory.json" ]]; then
            local state_json action
            state_json="$(python3 "${SCRIPT_DIR}/installation_recovery.py" inspect \
                --target "$target_root" --state-dir "$ROLLBACK_BASE_DIR/installation-inventory")" || {
                log_error "Cannot inspect previous installation"
                exit 1
            }
            action="$(printf '%s' "$state_json" | python3 -c \
                'import json,sys;print(json.load(sys.stdin)["action"])')" || exit 1
            case "$action" in
                installed)
                    log_info "WebOps already installed and previously passed health verification"
                    log_info "No installation changes made; use --doctor for a recorded-state report"
                    exit 0 ;;
                resume)
                    log_info "Detected safely resumable pre-system-change installation"
                    INSTALL_RESUME=true ;;
                staged)
                    log_info "Completing staged installation without overwriting configuration"
                    WEBOPS_NEW_INSTALL_COPY=true ;;
                *)
                    log_error "Existing installation needs operator review: $state_json"
                    log_error "Do not reinstall over an incomplete or unverified installation"
                    exit 1 ;;
            esac
        fi
        log_info "Already running from installation directory: $target_root"
        return 0
    fi

    log_step "Copying WebOps to installation directory..."
    log_info "Source: $current_root"
    log_info "Target: $target_root"

    # Create parent directory if needed
    mkdir -p "$(dirname "$target_root")"

    # Self-heal only when trusted installation history permits it.
    if [[ -e "$target_root" || -L "$target_root" ]]; then
        local decision_json action installed_script
        decision_json="$(python3 "${SCRIPT_DIR}/installation_recovery.py" inspect \
            --target "$target_root" --state-dir "${ROLLBACK_BASE_DIR}/installation-inventory")" || {
            log_error "Recovery inspection failed; no files were overwritten"
            exit 1
        }
        action="$(printf '%s' "$decision_json" | python3 -c \
            'import json,sys;print(json.load(sys.stdin)["action"])')" || exit 1
        installed_script="$target_root/${WEBOPS_PLATFORM_DIR_NAME}/versions/${WEBOPS_VERSION}/lifecycle/install.sh"
        case "$action" in
            staged)
                log_info "Self-healing staged copy: no system modifications recorded"
                export WEBOPS_ALREADY_RELOCATED=true WEBOPS_NEW_INSTALL_COPY=true
                exec "$installed_script"
                ;;
            resume)
                log_info "Resuming verified interrupted installation from original baseline"
                export WEBOPS_ALREADY_RELOCATED=true
                exec "$installed_script" --resume
                ;;
            installed)
                log_info "WebOps already installed and previously passed installation verification at $target_root"
                log_info "Skipping duplicate setup; use --doctor or the health dashboard for current health"
                exit 0
                ;;
            manual)
                if [[ "$INSTALL_RECOVER_STAGED" == "true" ]]; then
                    python3 "${SCRIPT_DIR}/installation_recovery.py" legacy-check \
                        --target "$target_root" \
                        --state-dir "${ROLLBACK_BASE_DIR}/installation-inventory" || {
                        log_error "Host shows existing WebOps state; refuse adoption"
                        exit 1
                    }
                    log_warn "Legacy staged copy has no original installation baseline."
                    log_warn "Recovery assumes NO earlier installer changed host settings."
                    log_warn "Only platform lifecycle scripts will be refreshed; backups saved."
                    read -r -p "Type 'RECOVER PREFLIGHT COPY' only after verifying that: " answer
                    if [[ "$answer" != "RECOVER PREFLIGHT COPY" ]]; then
                        log_error "Recovery cancelled without modifying installed files"
                        exit 1
                    fi
                    python3 "${SCRIPT_DIR}/installation_recovery.py" adopt \
                        --target "$target_root" --source-dir "$SCRIPT_DIR" \
                        --state-dir "${ROLLBACK_BASE_DIR}/installation-inventory" || exit 1
                    log_info "Staged copy recovered; continuing install from its existing root"
                    export WEBOPS_ALREADY_RELOCATED=true WEBOPS_NEW_INSTALL_COPY=true
                    exec "$installed_script"
                fi
                log_error "Legacy staged install has no trusted prior baseline"
                log_error "Use install.sh --doctor; --recover-staged requires explicit verification"
                exit 1
                ;;
            *)
                log_error "Cannot safely auto-heal existing root: $target_root"
                log_error "$decision_json"
                log_error "Use install.sh --doctor for a read-only diagnosis"
                log_error "Configuration and data were not overwritten"
                exit 1
                ;;
        esac
    fi

    if [[ "$INSTALL_RECOVER_STAGED" == "true" ]]; then
        log_error "No staged installation exists; use the normal install command"
        exit 1
    fi

    # Copy repository to target location
    log_info "Copying repository to $target_root..."
    cp -a "$current_root" "$target_root"
    # Ownership evidence for a tree copied into a previously absent root.
    printf '%s\n' "$WEBOPS_VERSION" > "${target_root}/.webops-install-origin"
    chmod 600 "${target_root}/.webops-install-origin"
    python3 "${SCRIPT_DIR}/installation_recovery.py" stage --target "$target_root" || {
        log_error "Could not record staged-copy state; refusing to continue"
        exit 1
    }

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
    export WEBOPS_NEW_INSTALL_COPY=true

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

    local primary_config legacy_config existing_config="" state_file root
    primary_config="$(get_primary_config_file)"
    legacy_config="$(get_legacy_config_file)"
    root="$(detect_install_root)"
    state_file="${ROLLBACK_BASE_DIR}/installation-inventory/inventory.json"
    if [[ -f "$primary_config" ]]; then
        existing_config="$primary_config"
    elif [[ -f "$legacy_config" ]]; then
        existing_config="$legacy_config"
    fi
    if [[ "$INSTALL_RESUME" == "true" ]]; then
        if [[ -z "$existing_config" ]] || ! python3 "${SCRIPT_DIR}/installation_inventory.py" check-resume \
            --state-dir "${ROLLBACK_BASE_DIR}/installation-inventory" --install-root "$root"; then
            log_error "Cannot resume: matching captured baseline and configuration required"
            exit 1
        fi
        log_info "Verified interrupted installation; configuration preserved"
        return 0
    fi
    if [[ -f "$state_file" ]]; then
        log_error "Existing installation inventory found; refusing to overwrite history"
        log_error "Use --resume only for a captured, incomplete install"
        exit 1
    fi
    if [[ -f "$root/.webops-install-origin" && "$WEBOPS_NEW_INSTALL_COPY" != "true" ]]; then
        log_error "Previously staged WebOps root found; refusing untracked reinstall"
        exit 1
    fi
    if [[ -n "$existing_config" ]]; then
        if [[ "$WEBOPS_NEW_INSTALL_COPY" == "true" &&
              -f "$root/.webops-install-origin" &&
              "$primary_config" == "$root/config.env" ]]; then
            log_info "Fresh installation with existing source config; preserving: $existing_config"
        else
            log_error "Existing WebOps configuration found: $existing_config"
            log_error "Refusing untracked reinstall; inspect the existing installation state"
            exit 1
        fi
    fi

    log_info "Environment validation passed ✓"
}

show_welcome() {
    clear || true
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

    local config_file
    config_file="$(get_primary_config_file)"
    local legacy_config
    legacy_config="$(get_legacy_config_file)"
    # A preconfigured source file is authoritative. Never silently replace it.
    if [[ -e "$config_file" || -L "$config_file" ]]; then
        log_info "Preserving existing configuration: $config_file"
        return 0
    fi
    if [[ -e "$legacy_config" || -L "$legacy_config" ]]; then
        log_error "Legacy-only configuration exists; refusing overwrite"
        return 1
    fi

    # Detect installation root (parent directory of provisioning/.webops)
    local detected_root="$(cd "$(dirname "${WEBOPS_PLATFORM_DIR}")" && pwd)"

    # Use detected path for development, /opt/webops for production
    local install_root="${WEBOPS_INSTALL_ROOT:-$DEFAULT_INSTALL_ROOT}"

    log_info "Installation root: $install_root"

    # Use collected configuration values
    local permit_root="${PERMIT_ROOT_LOGIN:-yes}"
    local ssh_pass_auth="${SSH_PASSWORD_AUTH:-yes}"

    # Create default configuration
    cat > "$config_file" <<EOF
# WebOps Platform Configuration
# Generated by install.sh on $(date)

# Platform Configuration
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

    if [[ "$legacy_config" != "$config_file" ]]; then
        ln -sfn "$config_file" "$legacy_config"
        log_info "Legacy config link updated: $legacy_config -> $config_file"
    fi
}

prepare_rollback_snapshot() {
    log_step "Creating pre-install rollback snapshot..."

    local install_root
    install_root="$(detect_install_root)"

    mkdir -p "$ROLLBACK_BASE_DIR"
    chmod 700 "$ROLLBACK_BASE_DIR"

    ROLLBACK_DIR="${ROLLBACK_BASE_DIR}/snapshot-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$ROLLBACK_DIR"
    chmod 700 "$ROLLBACK_DIR"

    echo "$install_root" > "${ROLLBACK_DIR}/install_root.txt"

    # Capture service state so rollback can restore previous runtime state.
    local state_file="${ROLLBACK_DIR}/services.state"
    : > "$state_file"
    local services=("postgresql" "redis-server" "webops-web" "webops-worker" "webops-beat" "webops-channels")
    for service in "${services[@]}"; do
        local active_state enabled_state
        active_state="$(systemctl is-active "$service" 2>/dev/null || echo "unknown")"
        enabled_state="$(systemctl is-enabled "$service" 2>/dev/null || echo "unknown")"
        echo "${service}|${active_state}|${enabled_state}" >> "$state_file"
    done

    # Backup system files affected by installation.
    if [[ -f "/etc/ssh/sshd_config" ]]; then
        cp -a "/etc/ssh/sshd_config" "${ROLLBACK_DIR}/sshd_config.bak"
    fi

    local unit_files=(
        "/etc/systemd/system/webops-web.service"
        "/etc/systemd/system/webops-worker.service"
        "/etc/systemd/system/webops-beat.service"
        "/etc/systemd/system/webops-channels.service"
    )
    for unit in "${unit_files[@]}"; do
        if [[ -f "$unit" ]]; then
            cp -a "$unit" "${ROLLBACK_DIR}/$(basename "$unit").bak"
        fi
    done

    # Backup installation tree when it exists.
    if [[ -d "$install_root" ]]; then
        local install_parent install_name
        install_parent="$(dirname "$install_root")"
        install_name="$(basename "$install_root")"
        tar czf "${ROLLBACK_DIR}/install-root.tar.gz" \
            --exclude="${install_name}/backups" \
            --exclude="${install_name}/logs" \
            -C "$install_parent" "$install_name"
    fi

    ROLLBACK_PREPARED=true
    log_info "Rollback snapshot saved: ${ROLLBACK_DIR}"
}

rollback_installation() {
    # Restoring a historical whole-tree archive with rm -rf would destroy
    # database/uploads/deployments created after the snapshot. Configuration,
    # service and package changes are not a full atomic transaction either.
    # Fail closed: keep all data and independent snapshots for manual repair.
    log_warn "Partial installation detected; automatic destructive rollback disabled."
    log_warn "Preserving application data, installation inventory and rollback evidence."
    log_warn "Review snapshots under: $ROLLBACK_BASE_DIR"
    log_warn "Run install.sh --doctor before any further installation attempt."
    return 1
}

run_installation() {
    log_step "Starting WebOps platform installation..."

    local config_file install_root
    config_file="$(resolve_config_file_for_read)"
    install_root="${WEBOPS_INSTALL_ROOT:-$DEFAULT_INSTALL_ROOT}"
    if [[ -f "$config_file" ]]; then
        install_root="$(grep "^WEBOPS_ROOT=" "$config_file" | tail -n 1 | cut -d'=' -f2- || true)"
        install_root="${install_root:-${WEBOPS_INSTALL_ROOT:-$DEFAULT_INSTALL_ROOT}}"
    fi

    log_info "Executing: WEBOPS_ROOT=${install_root} ${WEBOPS_BIN} install"

    if WEBOPS_ROOT="${install_root}" "${WEBOPS_BIN}" install; then
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
    local services=("postgresql" "redis-server" "webops-web" "webops-worker" "webops-beat" "webops-channels")

    for service in "${services[@]}"; do
        ((total_checks += 1))
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            log_info "✓ $service is running"
        else
            log_warn "✗ $service is not running"
            ((failed_checks += 1))
        fi
    done

    # Check Redis connectivity
    ((total_checks += 1))
    if redis-cli ping &>/dev/null; then
        log_info "✓ Redis is responding to PING"
    else
        log_warn "✗ Redis is not responding"
        ((failed_checks += 1))
    fi

    # Check PostgreSQL connectivity
    ((total_checks += 1))
    if sudo -u postgres psql -c "SELECT 1" &>/dev/null; then
        log_info "✓ PostgreSQL is accepting connections"
    else
        log_warn "✗ PostgreSQL is not accepting connections"
        ((failed_checks += 1))
    fi

    # Check control panel port
    ((total_checks += 1))
    if ss -tulpn | grep -q ":8000 "; then
        log_info "✓ Control panel is listening on port 8000"
    else
        log_warn "✗ Control panel is not listening on port 8000"
        ((failed_checks += 1))
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
    local install_root="${WEBOPS_INSTALL_ROOT:-$DEFAULT_INSTALL_ROOT}"
    local config_file
    config_file="$(resolve_config_file_for_read)"
    if [[ -f "$config_file" ]]; then
        install_root=$(grep "^WEBOPS_ROOT=" "$config_file" | cut -d'=' -f2)
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
    if [[ "${1:-}" == "--resume" && $# -eq 1 ]]; then
        INSTALL_RESUME=true
    elif [[ "${1:-}" == "--doctor" && $# -eq 1 ]]; then
        INSTALL_DOCTOR=true
    elif [[ "${1:-}" == "--recover-staged" && $# -eq 1 ]]; then
        INSTALL_RECOVER_STAGED=true
    elif [[ $# -gt 0 ]]; then
        log_error "Supported options: --doctor, --resume, --recover-staged"
        exit 2
    fi
    if [[ "$INSTALL_DOCTOR" == "true" ]]; then
        python3 "${SCRIPT_DIR}/installation_recovery.py" inspect \
            --target "${WEBOPS_INSTALL_ROOT:-/opt/webops}" \
            --state-dir "${ROLLBACK_BASE_DIR}/installation-inventory"
        exit $?
    fi
    # Initialize logging
    init_logging

    # Copy to install location if not already there (unless already relocated)
    if [[ "${WEBOPS_ALREADY_RELOCATED:-false}" != "true" ]]; then
        copy_to_install_location "$@"
    fi

    # Show welcome message
    show_welcome

    if [[ "$INSTALL_RESUME" == "true" ]]; then
        # Reuse the original before-state, never capture a partially modified host.
        validate_environment
        log_info "Resuming with previously captured baseline; configuration unchanged"
    else
        if [[ "$WEBOPS_NEW_INSTALL_COPY" == "true" &&
              -f "$(get_primary_config_file)" ]]; then
            # Existing user config is authoritative. Do not ask for choices
            # that would silently be ignored by the preconfigured installer.
            log_warn "Using a preconfigured source config; interactive SSH/hostname choices are skipped."
            read -r -p "Preserve the copied settings and install? (yes/no): " answer
            if [[ "$answer" != "yes" ]]; then
                log_info "Installation cancelled without modifying system configuration"
                exit 0
            fi
            NEW_HOSTNAME=""
        else
            configure_hostname
            configure_ssh_security
            show_configuration_summary
        fi
        validate_environment
        prepare_rollback_snapshot
        python3 "${SCRIPT_DIR}/installation_inventory.py" capture \
            --state-dir "${ROLLBACK_BASE_DIR}/installation-inventory" \
            --install-root "$(detect_install_root)" || {
            log_error "Cannot record pre-install inventory; aborting"
            exit 1
        }
        create_default_config
    fi

    # Unexpected command failures must also leave a diagnosable failure journal.
    # EXIT trap is registered only after baseline inventory was established.
    record_installation_exit() {
        local result="$1"
        if [[ "$result" -ne 0 ]]; then
            python3 "${SCRIPT_DIR}/installation_inventory.py" fail \
                --state-dir "${ROLLBACK_BASE_DIR}/installation-inventory" \
                --reason "Installer stopped with exit status $result" >/dev/null 2>&1 || true
        fi
    }
    trap 'record_installation_exit "$?"' EXIT

    # Mark the last safe automatic-resume point before any host changes.
    if ! python3 "${SCRIPT_DIR}/installation_inventory.py" begin \
        --state-dir "${ROLLBACK_BASE_DIR}/installation-inventory"; then
        log_error "Cannot advance the installation inventory; refusing system changes"
        exit 1
    fi
    # The existing staged copy must never look preflight-safe once host work starts.
    if [[ -f "$(detect_install_root)/.webops-install-stage.json" ]]; then
        python3 "${SCRIPT_DIR}/installation_recovery.py" advance \
            --target "$(detect_install_root)" || {
            log_error "Could not advance stage marker; refusing host changes"
            exit 1
        }
    fi
    if [[ "$INSTALL_RESUME" != "true" ]]; then
        apply_hostname
    fi

    # A successful setup command is not proof of a working installation.
    # Never seal installation history until service and network checks pass.
    if run_installation; then
        if ! verify_installation; then
            log_error "Installation health verification failed; status remains incomplete."
            log_error "A later install attempt must diagnose or repair this installation."
            if [[ "$INSTALL_RESUME" != "true" ]]; then
                rollback_installation || log_warn "Automatic rollback was not fully successful"
            fi
            exit 1
        fi
        if ! python3 "${SCRIPT_DIR}/installation_inventory.py" seal \
            --state-dir "${ROLLBACK_BASE_DIR}/installation-inventory"; then
            log_error "Could not seal the installation inventory"
            rollback_installation || true
            exit 1
        fi

        # Display failures cannot negate an already verified installation.
        print_completion_message || log_warn "Installation verified; completion summary unavailable"

        log_info "Installation log saved to: $INSTALL_LOG"
        exit 0
    else
        if [[ "$INSTALL_RESUME" == "true" ]]; then
            log_warn "Resume failed; original inventory preserved for recovery."
        else
            rollback_installation || log_warn "Automatic rollback was not fully successful"
        fi
        log_error "Installation failed. Please check the logs above."
        log_error "Full log available at: $INSTALL_LOG"
        exit 1
    fi
}

# Run main function
main "$@"
