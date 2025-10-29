#!/bin/bash
#
# WebOps VPS Setup Script - Versioned Platform Edition
# Transforms a fresh Ubuntu/Debian VPS into a complete hosting platform
#
# Usage: sudo ./setup.sh [options]
#
# This script delegates to the versioned WebOps platform for improved reliability
# and maintainability while preserving backward compatibility.
#

set -euo pipefail

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Platform version configuration (not readonly to allow CLI override)
WEBOPS_VERSION="${WEBOPS_VERSION:-v1.0.0}"
readonly WEBOPS_PLATFORM_DIR="$(pwd)/.webops"
readonly WEBOPS_VERSION_DIR="${WEBOPS_PLATFORM_DIR}/versions/${WEBOPS_VERSION}"
readonly WEBOPS_BIN="${WEBOPS_VERSION_DIR}/bin/webops"

# Legacy configuration for backward compatibility
readonly WEBOPS_USER="webops"
readonly WEBOPS_DIR="${WEBOPS_DIR:-/opt/webops}"
readonly CONTROL_PANEL_DIR="${WEBOPS_DIR}/control-panel"
readonly DEPLOYMENTS_DIR="${WEBOPS_DIR}/deployments"
readonly SHARED_DIR="${WEBOPS_DIR}/shared"
readonly BACKUPS_DIR="${WEBOPS_DIR}/backups"
readonly LOGS_DIR="${WEBOPS_DIR}/logs"

# Python version
readonly PYTHON_VERSION_DEFAULT="3.11"
PYTHON_VERSION="${PYTHON_VERSION_DEFAULT}"
INSTALL_PYTHON=false

# Automation flags (can be set via CLI)
AUTO_YES=false
AUTO_DRYRUN_PYTHON=false
AUTO_APPLY_PYTHON=false
RECOMMEND_ONLY=false
USE_LEGACY=false

# PostgreSQL version
readonly POSTGRES_VERSION="14"

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

usage() {
    cat <<EOF
Usage: $0 [options]

Options:
  --yes, -y               Assume yes for prompts (non-interactive)
  --auto-dryrun-python    Automatically run the python helper in dry-run mode
  --auto-apply-python     Automatically apply the python default change (requires sudo)
  --recommend-only        Only print and run the recommendation helper, then exit
  --install-python        Install Python ${PYTHON_VERSION_DEFAULT} from deadsnakes PPA
  --python-version VER    Set specific Python version (default: ${PYTHON_VERSION_DEFAULT})
  --legacy                Use legacy setup script instead of versioned platform
  --version VER           Use specific WebOps platform version (default: ${WEBOPS_VERSION})
  --help, -h              Show this help message

Environment Variables:
  WEBOPS_VERSION          Platform version to use (default: v1.0.0)
EOF
}

parse_cli_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes|-y)
                AUTO_YES=true
                shift
                ;;
            --auto-dryrun-python)
                AUTO_DRYRUN_PYTHON=true
                shift
                ;;
            --auto-apply-python)
                AUTO_APPLY_PYTHON=true
                shift
                ;;
            --install-python)
                INSTALL_PYTHON=true
                shift
                ;;
            --python-version)
                if [[ -n ${2:-} ]]; then
                    PYTHON_VERSION="$2"
                    shift 2
                else
                    log_error "--python-version requires an argument"
                    exit 1
                fi
                ;;
            --recommend-only)
                RECOMMEND_ONLY=true
                shift
                ;;
            --legacy)
                USE_LEGACY=true
                shift
                ;;
            --version)
                if [[ -n ${2:-} ]]; then
                    export WEBOPS_VERSION="$2"
                    # For version query, just delegate to webops binary and exit
                    if [[ -x "${WEBOPS_BIN}" ]]; then
                        "${WEBOPS_BIN}" version
                        exit 0
                    else
                        log_error "WebOps binary not found: ${WEBOPS_BIN}"
                        exit 1
                    fi
                else
                    log_error "--version requires an argument"
                    exit 1
                fi
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            --*)
                log_error "Unknown option: $1"
                exit 1
                ;;
            *)
                shift
                ;;
        esac
    done
}

#=============================================================================
# Platform Detection and Validation
#=============================================================================

detect_platform() {
    log_step "Detecting WebOps platform..."
    
    if [[ ! -d "${WEBOPS_PLATFORM_DIR}" ]]; then
        log_error "WebOps platform directory not found: ${WEBOPS_PLATFORM_DIR}"
        log_error "Please ensure you're running this script from the WebOps repository root"
        exit 1
    fi
    
    if [[ ! -d "${WEBOPS_VERSION_DIR}" ]]; then
        log_error "WebOps version ${WEBOPS_VERSION} not found: ${WEBOPS_VERSION_DIR}"
        log_error "Available versions:"
        find "${WEBOPS_PLATFORM_DIR}/versions" -maxdepth 1 -type d -name "v*" -exec basename {} \; 2>/dev/null | sort || echo "  No versions found"
        exit 1
    fi
    
    if [[ ! -x "${WEBOPS_BIN}" ]]; then
        log_error "WebOps binary not found or not executable: ${WEBOPS_BIN}"
        exit 1
    fi
    
    log_info "Platform detected: WebOps ${WEBOPS_VERSION} ✓"
}

validate_environment() {
    log_step "Validating environment..."
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
    
    # Check OS
    if [[ ! -f /etc/os-release ]]; then
        log_error "Cannot detect OS. Only Ubuntu 22.04+ and Debian 11+ are supported."
        exit 1
    fi
    
    source /etc/os-release
    
    if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
        log_error "Unsupported OS: $ID. Only Ubuntu and Debian are supported."
        exit 1
    fi
    
    log_info "Environment validation passed ✓"
}

#=============================================================================
# Legacy Functions (for backward compatibility)
#=============================================================================

recommend_python_default() {
    # Inform the operator about the recommended approach to setting the system 'python'
    log_step "Python default recommendation"

    cat <<-EOF
It is recommended to avoid changing the system 'python' global unless you
understand the implications. Many system utilities expect 'python3' to be
available but not necessarily 'python' pointing to a specific version.

This setup prefers using 'python3' and registers the requested Python with
the alternatives system. If you want to change the global 'python' to
point to the installed ${PYTHON_VERSION}, you can run the helper script that
attempts to do this safely.

Helper script: scripts/set-default-python.sh

You can run a dry-run to see what would change:
  ./scripts/set-default-python.sh ${PYTHON_VERSION} --dry-run

Or run with sudo to apply the change system-wide:
  sudo ./scripts/set-default-python.sh ${PYTHON_VERSION}

If you rely on system packages, use 'python3' or a virtual environment
instead of changing the global 'python'.
EOF

    # Non-interactive automation support
    if [[ "$AUTO_APPLY_PYTHON" == true ]]; then
        log_info "AUTO_APPLY_PYTHON enabled: applying python default automatically"
        if [[ -x "./scripts/set-default-python.sh" ]]; then
            if ! command -v sudo &> /dev/null; then
                log_error "sudo command not available but required for auto-apply. Aborting auto-apply."
                return 2
            fi
            if ! sudo -n true 2>/dev/null; then
                log_warn "sudo will prompt for a password. Running auto-apply may block or fail in non-interactive environments."
            fi
            sudo ./scripts/set-default-python.sh ${PYTHON_VERSION} || { log_error "Auto-apply failed"; return 3; }
        else
            log_warn "Helper script ./scripts/set-default-python.sh not found or not executable."
            return 4
        fi
        return
    fi

    if [[ "$AUTO_DRYRUN_PYTHON" == true ]]; then
        log_info "AUTO_DRYRUN_PYTHON enabled: running helper dry-run"
        if [[ -x "./scripts/set-default-python.sh" ]]; then
            ./scripts/set-default-python.sh ${PYTHON_VERSION} --dry-run || true
        else
            log_warn "Helper script ./scripts/set-default-python.sh not found or not executable."
        fi
        return
    fi

    # Offer interactive prompt only if not in automation mode
    if [[ -t 0 && "$AUTO_YES" != true ]]; then
        read -p "Run helper dry-run now? (Y/n) " -r
        echo
        if [[ -z "$REPLY" || "$REPLY" =~ ^[Yy] ]]; then
            if [[ -x "./scripts/set-default-python.sh" ]]; then
                ./scripts/set-default-python.sh ${PYTHON_VERSION} --dry-run || true
            else
                log_warn "Helper script ./scripts/set-default-python.sh not found or not executable."
            fi
        fi
    elif [[ "$AUTO_YES" == true ]]; then
        log_info "AUTO_YES enabled: skipping prompt and running dry-run"
        if [[ -x "./scripts/set-default-python.sh" ]]; then
            ./scripts/set-default-python.sh ${PYTHON_VERSION} --dry-run || true
        else
            log_warn "Helper script ./scripts/set-default-python.sh not found or not executable."
        fi
    else
        log_info "Non-interactive shell: skipping helper dry-run prompt."
    fi
}

#=============================================================================
# Versioned Platform Functions
#=============================================================================

run_platform_install() {
    log_step "Running WebOps platform installation..."
    
    # Create configuration file for the platform
    local config_file="/tmp/webops-setup-config.env"
    cat > "$config_file" <<EOF
# WebOps Setup Configuration
# Generated by setup.sh on $(date)

# Platform Configuration
WEBOPS_VERSION=${WEBOPS_VERSION}
WEBOPS_PLATFORM_DIR=${WEBOPS_PLATFORM_DIR}
WEBOPS_VERSION_DIR=${WEBOPS_VERSION_DIR}

# System Configuration
WEBOPS_USER=${WEBOPS_USER}
WEBOPS_DIR=${WEBOPS_DIR}
CONTROL_PANEL_DIR=${CONTROL_PANEL_DIR}
DEPLOYMENTS_DIR=${DEPLOYMENTS_DIR}
SHARED_DIR=${SHARED_DIR}
BACKUPS_DIR=${BACKUPS_DIR}
LOGS_DIR=${LOGS_DIR}

# Python Configuration
PYTHON_VERSION=${PYTHON_VERSION}
INSTALL_PYTHON=${INSTALL_PYTHON}

# PostgreSQL Configuration
POSTGRES_VERSION=${POSTGRES_VERSION}

# Automation Flags
AUTO_YES=${AUTO_YES}
AUTO_DRYRUN_PYTHON=${AUTO_DRYRUN_PYTHON}
AUTO_APPLY_PYTHON=${AUTO_APPLY_PYTHON}
RECOMMEND_ONLY=${RECOMMEND_ONLY}
EOF

    # Run the platform installation
    log_info "Executing: ${WEBOPS_BIN} install --config ${config_file}"
    
    if [[ "$AUTO_YES" == true ]]; then
        "${WEBOPS_BIN}" install --config "$config_file" --yes
    else
        "${WEBOPS_BIN}" install --config "$config_file"
    fi
    
    local exit_code=$?
    
    # Clean up config file
    rm -f "$config_file"
    
    if [[ $exit_code -eq 0 ]]; then
        log_info "Platform installation completed successfully ✓"
    else
        log_error "Platform installation failed with exit code: $exit_code"
        exit $exit_code
    fi
}

run_platform_apply() {
    log_step "Applying WebOps platform configuration..."
    
    # Check if config.env exists
    local config_file="${WEBOPS_PLATFORM_DIR}/config.env"
    if [[ ! -f "$config_file" ]]; then
        log_warn "No configuration file found at $config_file"
        log_warn "Creating default configuration..."
        
        # Copy template if it exists
        if [[ -f "${WEBOPS_VERSION_DIR}/config.env.template" ]]; then
            cp "${WEBOPS_VERSION_DIR}/config.env.template" "$config_file"
            log_info "Default configuration created from template"
        else
            log_error "No configuration template found"
            exit 1
        fi
    fi
    
    # Apply the configuration
    if [[ "$AUTO_YES" == true ]]; then
        "${WEBOPS_BIN}" apply --config "$config_file" --yes
    else
        "${WEBOPS_BIN}" apply --config "$config_file"
    fi
    
    local exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        log_info "Platform configuration applied successfully ✓"
    else
        log_error "Platform configuration failed with exit code: $exit_code"
        exit $exit_code
    fi
}

#=============================================================================
# Legacy Setup Functions (fallback)
#=============================================================================

run_legacy_setup() {
    log_warn "Running legacy setup script..."
    log_warn "Consider migrating to the versioned platform for better reliability"
    
    # Check if legacy setup script exists
    local legacy_script="$(pwd)/setup.legacy.sh"
    if [[ ! -f "$legacy_script" ]]; then
        log_error "Legacy setup script not found: $legacy_script"
        exit 1
    fi
    
    # Make it executable
    chmod +x "$legacy_script"
    
    # Run with the same arguments
    exec "$legacy_script" "$@"
}

#=============================================================================
# Success Message
#=============================================================================

print_success_message() {
    local server_ip=$(hostname -I | awk '{print $1}')

    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║  🎉  WebOps Installation Complete!                           ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Platform Version:${NC} ${WEBOPS_VERSION}"
    echo -e "${BLUE}Control Panel URL:${NC} http://${server_ip}/"
    echo ""
    echo -e "${YELLOW}Admin Credentials:${NC}"
    echo "  Location: /opt/webops/.secrets/admin_credentials.txt"
    echo "  View with: sudo cat /opt/webops/.secrets/admin_credentials.txt"
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
    
    # Final validation - ensure all critical services are running
    echo -e "${YELLOW}Final Validation:${NC}"
    local validation_errors=0
    
    if ! systemctl is-active --quiet postgresql; then
        echo "  ✗ PostgreSQL service validation failed"
        validation_errors=$((validation_errors + 1))
    fi
    
    if ! systemctl is-active --quiet redis-server; then
        echo "  ✗ Redis service validation failed"
        validation_errors=$((validation_errors + 1))
    fi
    
    if ! systemctl is-active --quiet nginx; then
        echo "  ✗ Nginx service validation failed"
        validation_errors=$((validation_errors + 1))
    fi
    
    if ! systemctl is-active --quiet webops-web; then
        echo "  ✗ WebOps Web service validation failed"
        validation_errors=$((validation_errors + 1))
    fi
    
    if [[ $validation_errors -eq 0 ]]; then
        echo "  ✓ All critical services validated successfully"
        echo ""
        echo -e "${GREEN}Installation completed successfully with no critical errors!${NC}"
        exit 0
    else
        echo "  ✗ $validation_errors critical service(s) failed validation"
        echo ""
        echo -e "${YELLOW}Warning: Installation completed but some services may need attention.${NC}"
        echo -e "${YELLOW}Run '${WEBOPS_BIN} validate' for detailed diagnostics.${NC}"
        exit 0  # Don't fail the installation for service issues that can be resolved post-install
    fi
}

#=============================================================================
# Main Installation Flow
#=============================================================================

main() {
    parse_cli_args "$@"
    
    echo -e "${BLUE}"
    cat <<'EOF'
╦ ╦┌─┐┌┐ ╔═╗┌─┐┌─┐
║║║├┤ ├┴┐║ ║├─┘└─┐
╚╩╝└─┘└─┘╚═╝┴  └─┘
VPS Hosting Platform Setup - Versioned Platform Edition
EOF
    echo -e "${NC}"
    
    # If recommend-only mode, run recommendation and exit
    if [[ "$RECOMMEND_ONLY" == true ]]; then
        recommend_python_default
        log_info "Recommend-only mode complete. Exiting."
        exit 0
    fi
    
    # Choose installation method
    if [[ "$USE_LEGACY" == true ]]; then
        run_legacy_setup "$@"
        return $?
    fi
    
    # Versioned platform installation
    validate_environment
    detect_platform
    
    # Run platform installation
    run_platform_install
    
    # Apply configuration
    run_platform_apply
    
    # Run Python recommendations if needed
    recommend_python_default
    
    # Print success message
    print_success_message
}

# Run main function with all arguments
main "$@"
