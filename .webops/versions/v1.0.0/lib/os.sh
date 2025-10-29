#!/bin/bash
#
# WebOps OS Detection and Abstraction
# Provides OS-agnostic interface for package management and system operations
#

# Source common library
if [[ -z "${SCRIPT_DIR:-}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
source "${SCRIPT_DIR}/../lib/common.sh"

# OS-specific handlers directory
OS_HANDLERS_DIR="${SCRIPT_DIR}/../os"

#=============================================================================
# OS Detection
#=============================================================================

detect_os() {
    # Detect operating system and version
    if [[ ! -f /etc/os-release ]]; then
        log_error "Cannot detect OS (missing /etc/os-release)"
        return 1
    fi

    # shellcheck disable=SC1091
    source /etc/os-release

    # Check for OS override in config
    if [[ -n "${OS_OVERRIDE:-}" ]]; then
        log_warn "OS detection overridden: $OS_OVERRIDE"
        OS_ID="$OS_OVERRIDE"
    else
        OS_ID="$ID"
    fi

    OS_VERSION="$VERSION_ID"
    OS_NAME="$PRETTY_NAME"

    export OS_ID OS_VERSION OS_NAME

    log_info "Detected OS: $OS_NAME"
}

validate_os() {
    # Validate that OS is supported
    detect_os

    case "$OS_ID" in
        ubuntu)
            if [[ ! "$OS_VERSION" =~ ^(20.04|22.04|24.04)$ ]]; then
                log_warn "Ubuntu version $OS_VERSION is not officially tested"
                log_warn "Supported versions: 20.04, 22.04, 24.04"
            fi
            ;;
        debian)
            if [[ ! "$OS_VERSION" =~ ^(11|12)$ ]]; then
                log_warn "Debian version $OS_VERSION is not officially tested"
                log_warn "Supported versions: 11, 12"
            fi
            ;;
        rocky|almalinux)
            if [[ ! "$OS_VERSION" =~ ^(8|9)$ ]]; then
                log_warn "RHEL-based version $OS_VERSION is not officially tested"
                log_warn "Supported versions: 8, 9"
            fi
            ;;
        *)
            log_error "Unsupported OS: $OS_ID"
            log_error "Supported: Ubuntu, Debian, Rocky Linux, AlmaLinux"
            return 1
            ;;
    esac

    log_info "OS validation passed ✓"
    return 0
}

#=============================================================================
# OS Handler Loading
#=============================================================================

load_os_handler() {
    # Load OS-specific handler
    detect_os

    local handler_file="${OS_HANDLERS_DIR}/${OS_ID}.sh"

    if [[ ! -f "$handler_file" ]]; then
        log_error "OS handler not found: $handler_file"
        log_error "OS '$OS_ID' is not supported"
        return 1
    fi

    # shellcheck disable=SC1090
    source "$handler_file"
    log_info "Loaded OS handler for $OS_ID"
}

#=============================================================================
# OS-Agnostic Package Management Interface
#=============================================================================

# These functions delegate to OS-specific handlers

pkg_update() {
    # Update package manager cache
    os_pkg_update
}

pkg_install() {
    # Install packages
    os_pkg_install "$@"
}

pkg_remove() {
    # Remove packages
    os_pkg_remove "$@"
}

pkg_installed() {
    # Check if package is installed
    os_pkg_installed "$@"
}

#=============================================================================
# OS-Agnostic Service Management Interface
#=============================================================================

service_start() {
    # Start service
    os_service_start "$@"
}

service_stop() {
    # Stop service
    os_service_stop "$@"
}

service_restart() {
    # Restart service
    os_service_restart "$@"
}

service_enable() {
    # Enable service at boot
    os_service_enable "$@"
}

service_disable() {
    # Disable service at boot
    os_service_disable "$@"
}

#=============================================================================
# OS-Agnostic Firewall Interface
#=============================================================================

firewall_open_port() {
    # Open firewall port
    os_firewall_open_port "$@"
}

firewall_close_port() {
    # Close firewall port
    os_firewall_close_port "$@"
}

firewall_enable() {
    # Enable firewall
    os_firewall_enable
}

firewall_disable() {
    # Disable firewall
    os_firewall_disable
}

#=============================================================================
# System Information
#=============================================================================

get_total_memory() {
    # Get total system memory in MB
    free -m | awk '/^Mem:/{print $2}'
}

get_total_cpus() {
    # Get total CPU cores
    nproc
}

get_total_disk() {
    # Get total disk space in GB
    df -BG / | awk 'NR==2{print $2}' | sed 's/G//'
}

#=============================================================================
# Initialization
#=============================================================================

# Auto-load OS handler when sourced
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    load_os_handler
fi
