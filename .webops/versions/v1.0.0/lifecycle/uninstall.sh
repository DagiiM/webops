#!/bin/bash
#
# WebOps Platform Uninstaller
# Complete removal of the WebOps hosting platform
#
# Usage: sudo ./uninstall.sh [options]
#
# This script removes all WebOps components, services, and data
# Use with caution - this is a destructive operation
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
readonly WEBOPS_PLATFORM_DIR="$(pwd)/.webops"
readonly WEBOPS_VERSION_DIR="${WEBOPS_PLATFORM_DIR}/versions/${WEBOPS_VERSION}"
readonly WEBOPS_BIN="${WEBOPS_VERSION_DIR}/bin/webops"

# Uninstall options
PURGE_DATA=false
FORCE=false
DRY_RUN=false

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

log_dry() {
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $1"
    fi
}

#=============================================================================
# Help and Usage
#=============================================================================

show_help() {
    cat <<EOF
WebOps Platform Uninstaller

USAGE:
    sudo $0 [options]

OPTIONS:
    --purge-data         Remove all data (databases, deployments, logs)
    --force              Skip confirmation prompts
    --dry-run            Show what would be removed without executing
    --help, -h           Show this help message

EXAMPLES:
    $0                    # Remove platform but keep data
    $0 --purge-data       # Remove platform and all data
    $0 --dry-run          # Preview what would be removed

WARNING: This is a destructive operation that will remove WebOps services,
configuration, and optionally all data. Backup important data before proceeding.
EOF
}

#=============================================================================
# Parse Arguments
#=============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --purge-data)
                PURGE_DATA=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

#=============================================================================
# Validation Functions
#=============================================================================

validate_environment() {
    log_step "Validating uninstall environment..."
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
    
    # Check if WebOps platform exists
    if [[ ! -d "${WEBOPS_VERSION_DIR}" ]]; then
        log_error "WebOps platform version ${WEBOPS_VERSION} not found"
        exit 1
    fi
    
    # Check if webops binary exists
    if [[ ! -x "${WEBOPS_BIN}" ]]; then
        log_error "WebOps binary not found: ${WEBOPS_BIN}"
        exit 1
    fi
    
    log_info "Environment validation passed ✓"
}

confirm_uninstall() {
    if [[ "$FORCE" == "true" ]]; then
        return 0
    fi
    
    echo ""
    echo -e "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                                                               ║${NC}"
    echo -e "${RED}║  ⚠️  DANGER: WebOps Platform Uninstall                     ║${NC}"
    echo -e "${RED}║                                                               ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    if [[ "$PURGE_DATA" == "true" ]]; then
        echo -e "${YELLOW}This will COMPLETELY remove:${NC}"
        echo "  • All WebOps services and configurations"
        echo "  • All databases and data"
        echo "  • All deployed applications"
        echo "  • All logs and backups"
        echo "  • All user data"
        echo ""
        echo -e "${RED}THIS ACTION IS IRREVERSIBLE!${NC}"
    else
        echo -e "${YELLOW}This will remove:${NC}"
        echo "  • All WebOps services and configurations"
        echo "  • Platform binaries and scripts"
        echo "  • Systemd services"
        echo "  • Nginx configurations"
        echo ""
        echo -e "${GREEN}Data will be preserved:${NC}"
        echo "  • Databases in /opt/webops/postgresql/data"
        echo "  • Deployments in /opt/webops/deployments"
        echo "  • Logs in /opt/webops/logs"
        echo "  • Backups in /opt/webops/backups"
    fi
    
    echo ""
    read -p "Are you sure you want to continue? Type 'UNINSTALL' to confirm: " -r
    echo ""
    
    if [[ "$REPLY" != "UNINSTALL" ]]; then
        log_info "Uninstall cancelled by user"
        exit 0
    fi
}

#=============================================================================
# Uninstall Functions
#=============================================================================

stop_webops_services() {
    log_step "Stopping WebOps services..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would stop all WebOps services"
        return 0
    fi
    
    # Stop all webops services
    local services=(
        "webops-web"
        "webops-worker"
        "webops-beat"
        "postgresql"
        "redis-server"
        "nginx"
    )
    
    for service in "${services[@]}"; do
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            log_info "Stopping service: $service"
            systemctl stop "$service" || log_warn "Failed to stop $service"
        fi
        
        if systemctl is-enabled --quiet "$service" 2>/dev/null; then
            log_info "Disabling service: $service"
            systemctl disable "$service" || log_warn "Failed to disable $service"
        fi
    done
    
    log_info "All WebOps services stopped ✓"
}

remove_webops_packages() {
    log_step "Removing WebOps packages..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would remove WebOps packages"
        return 0
    fi
    
    # Remove packages if they were installed by WebOps
    local packages=(
        "postgresql-14"
        "postgresql-contrib"
        "redis-server"
        "nginx"
        "python3-pip"
        "python3-venv"
        "certbot"
        "python3-certbot-nginx"
    )
    
    for package in "${packages[@]}"; do
        if dpkg -l | grep -q "^ii  $package "; then
            log_info "Removing package: $package"
            apt-get remove --purge -y "$package" || log_warn "Failed to remove $package"
        fi
    done
    
    # Auto-remove unused packages
    log_info "Removing unused packages..."
    apt-get autoremove -y || log_warn "Failed to autoremove packages"
    
    log_info "WebOps packages removed ✓"
}

remove_webops_directories() {
    log_step "Removing WebOps directories..."
    
    local directories=(
        "/opt/webops"
        "/etc/webops"
        "/var/log/webops"
        "/var/lib/webops"
    )
    
    if [[ "$PURGE_DATA" == "true" ]]; then
        directories+=(
            "/opt/webops/postgresql/data"
            "/opt/webops/deployments"
            "/opt/webops/backups"
        )
    fi
    
    for dir in "${directories[@]}"; do
        if [[ -d "$dir" ]]; then
            if [[ "$DRY_RUN" == "true" ]]; then
                log_dry "Would remove directory: $dir"
            else
                log_info "Removing directory: $dir"
                rm -rf "$dir" || log_warn "Failed to remove $dir"
            fi
        fi
    done
    
    log_info "WebOps directories removed ✓"
}

remove_webops_users() {
    log_step "Removing WebOps users..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would remove webops user"
        return 0
    fi
    
    # Remove webops user if it exists
    if id "webops" &>/dev/null; then
        log_info "Removing user: webops"
        userdel -r "webops" || log_warn "Failed to remove webops user"
    fi
    
    log_info "WebOps users removed ✓"
}

remove_webops_configurations() {
    log_step "Removing WebOps configurations..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would remove WebOps configurations"
        return 0
    fi
    
    # Remove nginx configurations
    local nginx_configs=(
        "/etc/nginx/sites-available/webops"
        "/etc/nginx/sites-enabled/webops"
        "/etc/nginx/conf.d/webops"
    )
    
    for config in "${nginx_configs[@]}"; do
        if [[ -f "$config" ]]; then
            log_info "Removing nginx config: $config"
            rm -f "$config"
        fi
    done
    
    # Remove systemd services
    local systemd_services=(
        "/etc/systemd/system/webops-web.service"
        "/etc/systemd/system/webops-worker.service"
        "/etc/systemd/system/webops-beat.service"
    )
    
    for service in "${systemd_services[@]}"; do
        if [[ -f "$service" ]]; then
            log_info "Removing systemd service: $service"
            rm -f "$service"
            systemctl daemon-reload
        fi
    done
    
    log_info "WebOps configurations removed ✓"
}

remove_platform_files() {
    log_step "Removing platform files..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would remove platform directory: ${WEBOPS_PLATFORM_DIR}"
        return 0
    fi
    
    if [[ -d "${WEBOPS_PLATFORM_DIR}" ]]; then
        log_info "Removing platform directory: ${WEBOPS_PLATFORM_DIR}"
        rm -rf "${WEBOPS_PLATFORM_DIR}"
    fi
    
    log_info "Platform files removed ✓"
}

cleanup_system() {
    log_step "Cleaning up system..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would clean up system"
        return 0
    fi
    
    # Reload systemd
    systemctl daemon-reload
    
    # Restart nginx if it's still installed
    if command -v nginx &>/dev/null; then
        systemctl reload nginx || log_warn "Failed to reload nginx"
    fi
    
    log_info "System cleanup completed ✓"
}

#=============================================================================
# Main Uninstall Flow
#=============================================================================

main() {
    # Parse arguments
    parse_args "$@"
    
    # Show welcome message
    echo -e "${BLUE}"
    cat <<'EOF'
╦ ╦┌─┐┌┐ ╔═╗┌─┐┌─┐
║║║├┤ ├┴┐║ ║├─┘└─┐
╚╩╝└─┘└─┘╚═╝┴  └─┘
VPS Hosting Platform Uninstaller
EOF
    echo -e "${NC}"
    
    # Validate environment
    validate_environment
    
    # Confirm uninstall
    confirm_uninstall
    
    # Execute uninstall steps
    stop_webops_services
    remove_webops_configurations
    remove_webops_packages
    remove_webops_directories
    remove_webops_users
    remove_platform_files
    cleanup_system
    
    # Show completion message
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║  ✅  WebOps Platform Uninstall Complete                    ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    if [[ "$PURGE_DATA" == "true" ]]; then
        echo -e "${RED}All WebOps components and data have been removed.${NC}"
    else
        echo -e "${YELLOW}WebOps components have been removed.${NC}"
        echo -e "${GREEN}Data has been preserved in:${NC}"
        echo "  • /opt/webops/postgresql/data"
        echo "  • /opt/webops/deployments"
        echo "  • /opt/webops/logs"
        echo "  • /opt/webops/backups"
    fi
    
    echo ""
    echo -e "${BLUE}System is now clean of WebOps platform.${NC}"
}

# Run main function with all arguments
main "$@"