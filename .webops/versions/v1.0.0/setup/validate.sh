#!/bin/bash
#
# WebOps Pre-Flight Validation
# Validates system meets requirements before installation
#

set -euo pipefail

# Source libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
source "${SCRIPT_DIR}/../lib/os.sh"

#=============================================================================
# Validation Functions
#=============================================================================

validate_root() {
    # Check if running as root
    log_step "Checking root privileges..."
    check_root
}

validate_os() {
    # Validate operating system
    log_step "Validating operating system..."
    validate_os
}

validate_resources() {
    # Check system resources
    log_step "Checking system resources..."

    local min_memory=2048  # MB
    local min_cpus=2
    local min_disk=20      # GB

    local total_memory=$(get_total_memory)
    local total_cpus=$(get_total_cpus)
    local total_disk=$(get_total_disk)

    log_info "Memory: ${total_memory}MB (minimum: ${min_memory}MB)"
    log_info "CPUs: ${total_cpus} (minimum: ${min_cpus})"
    log_info "Disk: ${total_disk}GB (minimum: ${min_disk}GB)"

    local failed=0

    if (( total_memory < min_memory )); then
        log_error "Insufficient memory: ${total_memory}MB < ${min_memory}MB"
        failed=1
    fi

    if (( total_cpus < min_cpus )); then
        log_error "Insufficient CPUs: ${total_cpus} < ${min_cpus}"
        failed=1
    fi

    if (( total_disk < min_disk )); then
        log_error "Insufficient disk space: ${total_disk}GB < ${min_disk}GB"
        failed=1
    fi

    if (( failed == 1 )); then
        return 1
    fi

    log_success "System resources check passed ✓"
}

validate_network() {
    # Validate network connectivity
    log_step "Checking network connectivity..."

    if ! check_internet; then
        log_error "No internet connectivity"
        return 1
    fi

    if ! check_dns; then
        log_error "DNS resolution failed"
        return 1
    fi

    log_success "Network connectivity check passed ✓"
}

validate_systemd() {
    # Check if systemd is available
    log_step "Checking systemd..."

    if ! command -v systemctl &>/dev/null; then
        log_error "systemd is not available"
        log_error "WebOps requires systemd for service management"
        return 1
    fi

    if ! systemctl --version &>/dev/null; then
        log_error "systemd is not functioning properly"
        return 1
    fi

    log_success "systemd check passed ✓"
}

validate_ports() {
    # Check if required ports are available
    log_step "Checking port availability..."

    local required_ports=(80 443 22)
    local failed=0

    for port in "${required_ports[@]}"; do
        if ss -tuln | grep -q ":${port} "; then
            log_warn "Port $port is already in use"
            # Don't fail for port 22 (SSH)
            if [[ "$port" != "22" ]]; then
                failed=1
            fi
        else
            log_info "Port $port is available ✓"
        fi
    done

    if (( failed == 1 )); then
        log_warn "Some required ports are in use (may need manual configuration)"
    fi

    return 0  # Don't fail validation for port conflicts
}

validate_disk_io() {
    # Test disk I/O performance
    log_step "Testing disk I/O performance..."

    local test_file="/tmp/webops_io_test"
    local min_speed=50  # MB/s

    # Write test
    local write_speed=$(dd if=/dev/zero of="$test_file" bs=1M count=100 2>&1 | \
        grep -oP '\d+(\.\d+)? MB/s' | grep -oP '\d+(\.\d+)?' | head -1)

    rm -f "$test_file"

    if [[ -z "$write_speed" ]]; then
        log_warn "Could not measure disk I/O speed"
        return 0
    fi

    write_speed=${write_speed%.*}

    log_info "Disk write speed: ${write_speed}MB/s"

    if (( write_speed < min_speed )); then
        log_warn "Disk I/O speed is below recommended: ${write_speed}MB/s < ${min_speed}MB/s"
        log_warn "This may affect performance but will not prevent installation"
    else
        log_success "Disk I/O performance check passed ✓"
    fi

    return 0
}

validate_existing_installation() {
    # Check for existing WebOps installation
    log_step "Checking for existing installation..."

    if [[ -f "${WEBOPS_ROOT}/config.env" ]]; then
        log_warn "Existing WebOps configuration found"
        log_warn "This may be an upgrade or migration"
    fi

    if [[ -L "${WEBOPS_PLATFORM}/current" ]]; then
        local current_version=$(get_platform_version)
        log_info "Existing WebOps version: $current_version"
    fi
}

#=============================================================================
# Main Validation
#=============================================================================

run_all_validations() {
    # Run all validation checks
    log_info "Running pre-flight validation checks..."
    echo ""

    local failed=0

    validate_root || failed=1
    validate_os || failed=1
    validate_systemd || failed=1
    validate_resources || failed=1
    validate_network || failed=1
    validate_ports || true  # Don't fail on port conflicts
    validate_disk_io || true  # Don't fail on I/O performance
    validate_existing_installation || true

    echo ""

    if (( failed == 1 )); then
        log_error "Pre-flight validation failed"
        log_error "Please resolve the issues above before proceeding"
        return 1
    fi

    log_success "All pre-flight validation checks passed ✓"
    return 0
}

#=============================================================================
# Script Execution
#=============================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Script is being executed directly
    run_all_validations
    exit $?
fi
