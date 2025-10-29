#!/bin/bash
#
# WebOps Common Library
# Provides logging, configuration loading, and shared utilities
#

# Color codes for output
if [[ -z "${RED:-}" ]]; then
    readonly RED='\033[0;31m'
fi
if [[ -z "${GREEN:-}" ]]; then
    readonly GREEN='\033[0;32m'
fi
if [[ -z "${YELLOW:-}" ]]; then
    readonly YELLOW='\033[1;33m'
fi
if [[ -z "${BLUE:-}" ]]; then
    readonly BLUE='\033[0;34m'
fi
if [[ -z "${NC:-}" ]]; then
    readonly NC='\033[0m' # No Color
fi

# Default paths
if [[ -z "${WEBOPS_ROOT:-}" ]]; then
    WEBOPS_ROOT="${WEBOPS_ROOT:-/webops}"
fi
WEBOPS_PLATFORM="${WEBOPS_ROOT}/.webops"
WEBOPS_CONFIG="${WEBOPS_ROOT}/config.env"
WEBOPS_SECRETS="${WEBOPS_ROOT}/secrets"
WEBOPS_TEMPLATES="${WEBOPS_ROOT}/templates"

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

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

#=============================================================================
# Configuration Management
#=============================================================================

load_config() {
    # Load configuration from config.env if it exists
    if [[ -f "${WEBOPS_CONFIG}" ]]; then
        log_info "Loading configuration from ${WEBOPS_CONFIG}"
        # shellcheck disable=SC1090
        source "${WEBOPS_CONFIG}"
    else
        log_warn "Configuration file not found: ${WEBOPS_CONFIG}"
        log_warn "Using default values"
    fi
}

get_config() {
    # Get a configuration value
    local key="$1"
    local default="${2:-}"

    load_config

    # Use environment variable if set, otherwise use default
    echo "${!key:-$default}"
}

#=============================================================================
# Validation Functions
#=============================================================================

check_root() {
    # Check if script is running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        return 1
    fi
    log_info "Running as root ✓"
    return 0
}

check_internet() {
    # Check internet connectivity
    if ! ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
        log_error "No internet connectivity"
        return 1
    fi
    log_info "Internet connectivity ✓"
    return 0
}

check_dns() {
    # Check DNS resolution
    if ! nslookup google.com &>/dev/null; then
        log_error "DNS resolution failed"
        return 1
    fi
    log_info "DNS resolution ✓"
    return 0
}

#=============================================================================
# Utility Functions
#=============================================================================

retry() {
    # Retry a command up to N times with exponential backoff
    local max_attempts="${1:-3}"
    local delay="${2:-5}"
    local attempt=1
    shift 2
    local cmd="$@"

    while (( attempt <= max_attempts )); do
        if eval "$cmd"; then
            return 0
        fi

        if (( attempt < max_attempts )); then
            log_warn "Command failed. Retrying in ${delay}s (attempt ${attempt}/${max_attempts})"
            sleep "$delay"
            delay=$((delay * 2))
        fi

        ((attempt++))
    done

    log_error "Command failed after ${max_attempts} attempts"
    return 1
}

ensure_directory() {
    # Ensure directory exists with proper permissions
    local dir="$1"
    local owner="${2:-root:root}"
    local perms="${3:-755}"

    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir"
        log_info "Created directory: $dir"
    fi

    chown "$owner" "$dir"
    chmod "$perms" "$dir"
}

load_secret() {
    # Load a secret from the secrets directory
    local secret_name="$1"
    local secret_file="${WEBOPS_SECRETS}/${secret_name}.secret"

    if [[ ! -f "$secret_file" ]]; then
        log_error "Secret not found: $secret_file"
        return 1
    fi

    # Check permissions
    local perms=$(stat -c "%a" "$secret_file")
    if [[ "$perms" != "600" ]]; then
        log_warn "Insecure permissions on $secret_file (should be 600)"
    fi

    cat "$secret_file"
}

#=============================================================================
# Platform Version Management
#=============================================================================

get_platform_version() {
    # Get the current platform version
    if [[ -L "${WEBOPS_PLATFORM}/current" ]]; then
        basename "$(readlink -f "${WEBOPS_PLATFORM}/current")"
    else
        echo "unknown"
    fi
}

set_platform_version() {
    # Set the active platform version via symlink
    local version="$1"
    local version_path="${WEBOPS_PLATFORM}/versions/${version}"

    if [[ ! -d "$version_path" ]]; then
        log_error "Version not found: $version"
        return 1
    fi

    # Atomic symlink update
    ln -sfn "$version_path" "${WEBOPS_PLATFORM}/current"
    log_success "Platform version set to: $version"
}

#=============================================================================
# Service Management
#=============================================================================

systemd_service_exists() {
    # Check if systemd service exists
    local service="$1"
    systemctl list-unit-files | grep -q "^${service}.service"
}

systemd_service_running() {
    # Check if systemd service is running
    local service="$1"
    systemctl is-active --quiet "$service"
}

systemd_service_enabled() {
    # Check if systemd service is enabled
    local service="$1"
    systemctl is-enabled --quiet "$service"
}
