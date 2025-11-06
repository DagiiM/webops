#!/bin/bash
#
# WebOps Ubuntu Handler
# Ubuntu-specific package management and system operations
#

# Source common OS functions
LOCAL_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the main common library first (for logging functions)
source "${LOCAL_SCRIPT_DIR}/../lib/common.sh"

# Source OS-specific common functions
source "${LOCAL_SCRIPT_DIR}/common.sh"

#=============================================================================
# Package Management
#=============================================================================

os_pkg_update() {
    wait_for_lock
    DEBIAN_FRONTEND=noninteractive apt-get update -qq
}

os_pkg_install() {
    wait_for_lock
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@"
}

os_pkg_remove() {
    wait_for_lock
    DEBIAN_FRONTEND=noninteractive apt-get remove -y -qq "$@"
}

os_pkg_installed() {
    dpkg -l "$1" 2>/dev/null | grep -q "^ii"
}

#=============================================================================
# Service Management
#=============================================================================

os_service_start() {
    systemctl start "$1"
}

os_service_stop() {
    systemctl stop "$1"
}

os_service_restart() {
    systemctl restart "$1"
}

os_service_enable() {
    systemctl enable "$1"
}

os_service_disable() {
    systemctl disable "$1"
}

#=============================================================================
# Firewall Management (UFW)
#=============================================================================

os_firewall_open_port() {
    local port="$1"
    local proto="${2:-tcp}"

    if ! command_exists ufw; then
        pkg_install ufw
    fi

    ufw allow "${port}/${proto}"
}

os_firewall_close_port() {
    local port="$1"
    local proto="${2:-tcp}"

    ufw delete allow "${port}/${proto}"
}

os_firewall_enable() {
    if ! command_exists ufw; then
        pkg_install ufw
    fi

    # Allow SSH before enabling
    ufw allow 22/tcp
    echo "y" | ufw enable
}

os_firewall_disable() {
    ufw disable
}

#=============================================================================
# System Configuration
#=============================================================================

os_configure_ntp() {
    # Install and configure chrony
    pkg_install chrony

    # Configure multiple NTP sources
    cat > /etc/chrony/chrony.conf <<EOF
# Multiple NTP sources for reliability
server 0.ubuntu.pool.ntp.org iburst
server 1.ubuntu.pool.ntp.org iburst
server 2.ubuntu.pool.ntp.org iburst
server 3.ubuntu.pool.ntp.org iburst

# Allow large clock adjustments
makestep 1.0 3

# Enable kernel synchronization
rtcsync

# Log directory
logdir /var/log/chrony
EOF

    # Enable and start chrony service
    systemctl enable chrony
    systemctl start chrony
}

#=============================================================================
# Ubuntu-Specific Operations
#=============================================================================

os_setup_repositories() {
    # Ensure universe and multiverse are enabled
    if ! grep -q "universe multiverse" /etc/apt/sources.list; then
        sed -i 's/main$/main universe multiverse restricted/g' /etc/apt/sources.list
        pkg_update
    fi
    
    # Add additional repositories if needed
    # For example, you could add PPAs here
}
