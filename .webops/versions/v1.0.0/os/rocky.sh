#!/bin/bash
#
# WebOps Rocky Linux Handler
# Rocky Linux / RHEL-based specific package management and system operations
#

# Source common OS functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

#=============================================================================
# Package Management
#=============================================================================

os_pkg_update() {
    dnf check-update -y || true
}

os_pkg_install() {
    dnf install -y "$@"
}

os_pkg_remove() {
    dnf remove -y "$@"
}

os_pkg_installed() {
    rpm -q "$1" &>/dev/null
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
# Firewall Management (firewalld)
#=============================================================================

os_firewall_open_port() {
    local port="$1"
    local proto="${2:-tcp}"

    if ! systemctl is-active --quiet firewalld; then
        systemctl start firewalld
    fi

    firewall-cmd --permanent --add-port="${port}/${proto}"
    firewall-cmd --reload
}

os_firewall_close_port() {
    local port="$1"
    local proto="${2:-tcp}"

    firewall-cmd --permanent --remove-port="${port}/${proto}"
    firewall-cmd --reload
}

os_firewall_enable() {
    systemctl enable firewalld
    systemctl start firewalld

    # Allow SSH
    firewall-cmd --permanent --add-service=ssh
    firewall-cmd --reload
}

os_firewall_disable() {
    systemctl stop firewalld
    systemctl disable firewalld
}

#=============================================================================
# System Configuration
#=============================================================================

os_configure_ntp() {
    # Install and configure chrony
    pkg_install chrony

    # Configure multiple NTP sources
    cat > /etc/chrony.conf <<EOF
# Multiple NTP sources for reliability
server 0.rocky.pool.ntp.org iburst
server 1.rocky.pool.ntp.org iburst
server 2.rocky.pool.ntp.org iburst
server 3.rocky.pool.ntp.org iburst

# Allow large clock adjustments
makestep 1.0 3

# Enable kernel synchronization
rtcsync

# Log directory
logdir /var/log/chrony
EOF

    systemctl restart chronyd
    systemctl enable chronyd
}

os_configure_sysctl() {
    # Kernel tuning for database workloads
    cat > /etc/sysctl.d/99-webops.conf <<EOF
# Network tuning
net.ipv4.tcp_keepalive_time = 60
net.ipv4.tcp_keepalive_intvl = 10
net.ipv4.tcp_keepalive_probes = 6

# VM tuning for database workloads
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
vm.swappiness = 10

# Shared memory (for PostgreSQL)
kernel.shmmax = 17179869184
kernel.shmall = 4194304
EOF

    sysctl -p /etc/sysctl.d/99-webops.conf
}

#=============================================================================
# RHEL-Specific Operations
#=============================================================================

os_setup_repositories() {
    # Enable EPEL repository
    pkg_install epel-release
    pkg_update
}

os_disable_selinux() {
    # Disable SELinux (optional, for compatibility)
    setenforce 0 || true
    sed -i 's/^SELINUX=enforcing/SELINUX=permissive/' /etc/selinux/config
}
