#!/bin/bash
#
# WebOps Common OS Functions
# Shared functions used by all OS handlers
#

# Package installation with retry
install_with_retry() {
    local max_attempts=3
    local delay=5
    local package="$1"

    for attempt in $(seq 1 $max_attempts); do
        log_info "Installing $package (attempt $attempt/$max_attempts)"

        if os_pkg_install "$package"; then
            log_success "$package installed successfully"
            return 0
        fi

        if (( attempt < max_attempts )); then
            log_warn "Installation failed. Retrying in ${delay}s..."
            sleep "$delay"
            delay=$((delay * 2))
        fi
    done

    log_error "Failed to install $package after $max_attempts attempts"
    return 1
}

# Check if command exists
command_exists() {
    command -v "$1" &>/dev/null
}

# Wait for package manager lock
wait_for_lock() {
    local max_wait=300  # 5 minutes
    local waited=0

    while fuser /var/lib/dpkg/lock-frontend &>/dev/null || \
          fuser /var/lib/apt/lists/lock &>/dev/null; do

        if (( waited >= max_wait )); then
            log_error "Timeout waiting for package manager lock"
            return 1
        fi

        log_info "Waiting for package manager lock..."
        sleep 10
        waited=$((waited + 10))
    done

    return 0
}
