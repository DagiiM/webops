#!/bin/bash
#
# WebOps Base System Setup
# HA-ready OS hardening and base configuration
#
# This script implements the base system hardening as described in the
# WebOps upgrade guide, providing a secure foundation for all addons.
#

set -euo pipefail

# Source libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
source "${SCRIPT_DIR}/../lib/os.sh"
source "${SCRIPT_DIR}/../lib/state.sh"

# Load configuration before finalizing defaults
load_config

# Configuration
if [[ -z "${WEBOPS_USER:-}" ]]; then
    readonly WEBOPS_USER="webops"
fi
if [[ -z "${TIMEZONE:-}" ]]; then
    readonly TIMEZONE="UTC"
fi
if [[ -z "${ENABLE_FIREWALL:-}" ]]; then
    readonly ENABLE_FIREWALL="true"
fi

# SSH Hardening Configuration
if [[ -z "${ENABLE_SSH_HARDENING:-}" ]]; then
    readonly ENABLE_SSH_HARDENING="false"
fi
if [[ -z "${PERMIT_ROOT_LOGIN:-}" ]]; then
    readonly PERMIT_ROOT_LOGIN="yes"
fi
if [[ -z "${SSH_PASSWORD_AUTH:-}" ]]; then
    readonly SSH_PASSWORD_AUTH="yes"
fi
if [[ -z "${SSH_MAX_AUTH_TRIES:-}" ]]; then
    readonly SSH_MAX_AUTH_TRIES="3"
fi

#=============================================================================
# System User and Security Setup
#=============================================================================

setup_webops_user() {
    log_step "Creating WebOps system user..."
    
    # Create system user with minimal privileges
    if ! id "$WEBOPS_USER" &>/dev/null; then
        useradd -r -m -s /bin/bash "$WEBOPS_USER"
        log_info "Created system user: $WEBOPS_USER"
    else
        log_info "System user $WEBOPS_USER already exists"
    fi
    
    # Create necessary directories
    ensure_directory "/home/$WEBOPS_USER/.ssh" "$WEBOPS_USER:$WEBOPS_USER" "700"
    
    # Add to appropriate groups
    usermod -a -G www-data "$WEBOPS_USER" 2>/dev/null || true
    usermod -a -G sudo "$WEBOPS_USER" 2>/dev/null || true
    
    log_success "WebOps user configured ✓"
}

configure_ssh_hardening() {
    if [[ "$ENABLE_SSH_HARDENING" != "true" ]]; then
        log_info "Preserving existing SSH settings; hardening is opt-in"
        return 0
    fi
    # An existing config.env is not proof that the administrator consented.
    if ! [[ -v SSH_ACCESS_CHANGE_CONFIRMED && "$SSH_ACCESS_CHANGE_CONFIRMED" == "true" ]]; then
        log_error "Refusing SSH changes without SSH_ACCESS_CHANGE_CONFIRMED=true"
        return 1
    fi
    case "$PERMIT_ROOT_LOGIN:$SSH_PASSWORD_AUTH" in
        yes:yes|prohibit-password:no) ;;
        *) log_error "Unsupported SSH policy; only explicitly reviewed easy/key-only profiles are allowed"; return 1 ;;
    esac
    if [[ ! "$SSH_MAX_AUTH_TRIES" =~ ^[0-9]+$ ]] ||
       (( SSH_MAX_AUTH_TRIES < 3 || SSH_MAX_AUTH_TRIES > 20 )); then
        log_error "SSH_MAX_AUTH_TRIES must be between 3 and 20"
        return 1
    fi
    if [[ "$SSH_PASSWORD_AUTH" == "no" ]]; then
        # This checks only that a root key is installed. Operators must also
        # prove a separate key-only session works BEFORE enabling this mode.
        if [[ ! -f /root/.ssh/authorized_keys || -L /root/.ssh/authorized_keys ]] ||
           ! grep -Eq '^[[:space:]]*(ssh-ed25519|ecdsa-sha2-|sk-ssh-ed25519|sk-ecdsa-sha2-|ssh-rsa)[[:space:]]+[A-Za-z0-9+/=]+' /root/.ssh/authorized_keys; then
            log_error "No root authorized key; refusing to disable password login"
            return 1
        fi
    fi
    local sshd_config="/etc/ssh/sshd_config"
    local sshd_dropin_dir="/etc/ssh/sshd_config.d"
    local sshd_dropin="$sshd_dropin_dir/99-webops.conf"
    local old_exists=false backup="" candidate="" effective=""
    if [[ ! -f "$sshd_config" || -L "$sshd_config" ||
          ! -d "$sshd_dropin_dir" || -L "$sshd_dropin_dir" || -L "$sshd_dropin" ]]; then
        log_error "Unsafe SSH configuration paths; refusing changes"
        return 1
    fi
    # Never truncate sshd_config (it can contain critical provider settings).
    if ! grep -Eq '^[[:space:]]*Include[[:space:]]+/etc/ssh/sshd_config.d/\*\.conf([[:space:]]|$)' "$sshd_config"; then
        log_error "SSH config has no standard drop-in Include; review manually"
        return 1
    fi
    if ! command -v sshd >/dev/null 2>&1 || ! sshd -t -f "$sshd_config"; then
        log_error "Cannot validate the existing SSH service; refusing changes"
        return 1
    fi
    candidate="$(mktemp "$sshd_dropin_dir/.webops-ssh.XXXXXXXX")" || return 1
    chmod 0600 "$candidate"
    cat > "$candidate" <<EOF
# WebOps explicitly opted-in SSH policy; sshd_config itself is preserved.
PermitRootLogin $PERMIT_ROOT_LOGIN
PasswordAuthentication $SSH_PASSWORD_AUTH
MaxAuthTries $SSH_MAX_AUTH_TRIES
EOF
    if [[ -e "$sshd_dropin" ]]; then
        if ! grep -Fq '# WebOps explicitly opted-in SSH policy' "$sshd_dropin"; then
            log_error "Existing SSH drop-in is not WebOps-owned; refusing overwrite"
            rm -f "$candidate"
            return 1
        fi
        old_exists=true
        backup="$(mktemp "$sshd_dropin_dir/.webops-ssh-backup.XXXXXXXX")" ||
            { rm -f "$candidate"; return 1; }
        cp -p "$sshd_dropin" "$backup" ||
            { rm -f "$candidate" "$backup"; return 1; }
    fi
    mv -f "$candidate" "$sshd_dropin" || { rm -f "$candidate"; return 1; }

    # Verify effective SSH policy, not merely that sshd -t succeeds.
    local valid=true actual_root="" actual_password="" actual_tries="" actual_key=""
    if ! sshd -t -f "$sshd_config" ||
       ! effective="$(sshd -T -f "$sshd_config" -C user=root,host=localhost,addr=127.0.0.1 2>/dev/null)"; then
        valid=false
    else
        actual_root="$(awk '$1=="permitrootlogin"{print $2;exit}' <<< "$effective")"
        # OpenSSH normalizes prohibit-password to its legacy without-password alias.
        if [[ "$actual_root" == "without-password" ]]; then
            actual_root="prohibit-password"
        fi
        actual_password="$(awk '$1=="passwordauthentication"{print $2;exit}' <<< "$effective")"
        actual_tries="$(awk '$1=="maxauthtries"{print $2;exit}' <<< "$effective")"
        actual_key="$(awk '$1=="pubkeyauthentication"{print $2;exit}' <<< "$effective")"
        if [[ "$actual_root" != "$PERMIT_ROOT_LOGIN" ||
              "$actual_password" != "$SSH_PASSWORD_AUTH" ||
              "$actual_tries" != "$SSH_MAX_AUTH_TRIES" ||
              ( "$SSH_PASSWORD_AUTH" == "no" && "$actual_key" != "yes" ) ]]; then
            valid=false
        fi
    fi
    if [[ "$valid" != "true" ]]; then
        log_error "SSH policy validation failed; restoring previous drop-in"
        if [[ "$old_exists" == "true" ]]; then cp -p "$backup" "$sshd_dropin"; else rm -f "$sshd_dropin"; fi
        if [[ -n "$backup" ]]; then rm -f "$backup"; fi
        return 1
    fi
    if ! service_restart ssh; then
        log_error "SSH restart failed; restoring previous drop-in"
        if [[ "$old_exists" == "true" ]]; then cp -p "$backup" "$sshd_dropin"; else rm -f "$sshd_dropin"; fi
        service_restart ssh || log_error "SSH recovery restart failed; use provider console"
        if [[ -n "$backup" ]]; then rm -f "$backup"; fi
        return 1
    fi
    if [[ "$old_exists" == "true" ]]; then
        log_info "Previous SSH drop-in saved at $backup"
    fi
    log_success "Explicit SSH policy applied without replacing provider sshd_config"
}

configure_sudo_access() {
    log_step "Configuring limited sudo access..."
    
    local sudoers_file="/etc/sudoers.d/webops"
    
    cat > "$sudoers_file" <<EOF
# WebOps Sudo Configuration
# Generated by WebOps setup/base.sh

Defaults:$WEBOPS_USER !requiretty
Defaults:$WEBOPS_USER !lecture

# Allow system management commands
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/systemctl *, /usr/bin/systemctl *
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/service, /usr/sbin/service
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/kill, /usr/bin/kill

# Allow package management
$WEBOPS_USER ALL=(root) NOPASSWD: /usr/bin/apt-get, /usr/bin/apt, /usr/bin/dnf, /usr/bin/yum
$WEBOPS_USER ALL=(root) NOPASSWD: /usr/bin/dpkg, /usr/bin/rpm

# Allow network management
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/ip, /sbin/ip, /usr/sbin/ip
$WEBOPS_USER ALL=(root) NOPASSWD: /sbin/iptables, /sbin/ip6tables
$WEBOPS_USER ALL=(root) NOPASSWD: /usr/sbin/ufw, /usr/bin/firewall-cmd

# Allow certificate management
$WEBOPS_USER ALL=(root) NOPASSWD: /usr/bin/certbot, /usr/local/bin/certbot

# Allow file system operations in webops directories
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/mount, /bin/umount
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/chown, /bin/chmod
$WEBOPS_USER ALL=(root) NOPASSWD: /bin/mkdir, /bin/rm, /bin/ln

# Allow process management for webops services
$WEBOPS_USER ALL=(root) NOPASSWD: /usr/bin/nice, /usr/bin/renice
EOF
    
    # Set correct permissions
    chmod 0440 "$sudoers_file"
    
    # Validate sudoers syntax
    if visudo -c -f "$sudoers_file" >/dev/null 2>&1; then
        log_success "Sudo access configured ✓"
    else
        log_error "Invalid sudoers configuration"
        rm -f "$sudoers_file"
        return 1
    fi
}

#=============================================================================
# System Configuration
#=============================================================================

configure_system_settings() {
    log_step "Configuring system settings..."
    
    # Set timezone
    if command -v timedatectl &>/dev/null; then
        timedatectl set-timezone "$TIMEZONE"
    else
        echo "$TIMEZONE" > /etc/timezone
        dpkg-reconfigure -f noninteractive tzdata 2>/dev/null || true
    fi
    
    # Configure kernel parameters
    cat > /etc/sysctl.d/99-webops-base.conf <<'EOF'
# WebOps Base Kernel Configuration
# Generated by WebOps setup/base.sh

# Network security
net.ipv4.ip_forward = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.secure_redirects = 0
net.ipv4.conf.default.secure_redirects = 0
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.default.log_martians = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1
net.ipv4.tcp_syncookies = 1

# Connection tracking (may not be available in all kernels)
#net.netfilter.nf_conntrack_max = 1048576
#net.netfilter.nf_conntrack_tcp_timeout_established = 7200

# File system security
fs.protected_regular = 1
fs.protected_fifos = 1
fs.suid_dumpable = 0

# Core dumps
kernel.core_pattern = |/bin/false
kernel.kptr_restrict = 2

# Randomize memory addresses
kernel.randomize_va_space = 2

# Restrict dmesg
kernel.dmesg_restrict = 1

# Performance tuning for workloads
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.ipv4.tcp_congestion_control = bbr
EOF
    
    # Apply sysctl settings (ignore errors for optional modules)
    sysctl -p /etc/sysctl.d/99-webops-base.conf 2>/dev/null || true
    
    # Try to load connection tracking modules if available
    modprobe nf_conntrack 2>/dev/null || true
    modprobe xt_conntrack 2>/dev/null || true
    
    # Apply connection tracking settings if modules are loaded
    if [[ -f /proc/sys/net/netfilter/nf_conntrack_max ]]; then
        echo "net.netfilter.nf_conntrack_max = 1048576" >> /etc/sysctl.d/99-webops-base.conf
        echo "net.netfilter.nf_conntrack_tcp_timeout_established = 7200" >> /etc/sysctl.d/99-webops-base.conf
        sysctl -w net.netfilter.nf_conntrack_max=1048576 2>/dev/null || true
        sysctl -w net.netfilter.nf_conntrack_tcp_timeout_established=7200 2>/dev/null || true
    fi
    
    log_success "System settings configured ✓"
}

configure_limits() {
    log_step "Configuring system limits..."
    
    cat > /etc/security/limits.d/99-webops.conf <<'EOF'
# WebOps System Limits
# Generated by WebOps setup/base.sh

# Increase file descriptor limits
* soft nofile 65536
* hard nofile 65536
root soft nofile 65536
root hard nofile 65536

# Increase process limits
* soft nproc 32768
* hard nproc 32768
root soft nproc 32768
root hard nproc 32768

# Memory limits for webops user
webops soft memlock unlimited
webops hard memlock unlimited
webops soft stack 8192
webops hard stack 8192
EOF
    
    log_success "System limits configured ✓"
}

setup_time_sync() {
    log_step "Setting up time synchronization..."
    
    # Install and configure chrony for reliable time sync
    pkg_install chrony
    
    # Configure chrony with multiple NTP sources
    case "$OS_ID" in
        ubuntu)
            cat > /etc/chrony/chrony.conf <<EOF
# WebOps NTP Configuration
# Multiple NTP sources for reliability

pool 0.ubuntu.pool.ntp.org iburst maxsources 4
pool 1.ubuntu.pool.ntp.org iburst maxsources 4
pool 2.ubuntu.pool.ntp.org iburst maxsources 4
pool 3.ubuntu.pool.ntp.org iburst maxsources 4

# Allow large clock adjustments
makestep 1.0 3

# Enable kernel synchronization
rtcsync

# Log directory
logdir /var/log/chrony

# Security
bindcmdaddress 127.0.0.1
EOF
            ;;
        debian)
            cat > /etc/chrony/chrony.conf <<EOF
# WebOps NTP Configuration
# Multiple NTP sources for reliability

pool 0.debian.pool.ntp.org iburst maxsources 4
pool 1.debian.pool.ntp.org iburst maxsources 4
pool 2.debian.pool.ntp.org iburst maxsources 4
pool 3.debian.pool.ntp.org iburst maxsources 4

# Allow large clock adjustments
makestep 1.0 3

# Enable kernel synchronization
rtcsync

# Log directory
logdir /var/log/chrony

# Security
bindcmdaddress 127.0.0.1
EOF
            ;;
        rocky|almalinux)
            cat > /etc/chrony.conf <<EOF
# WebOps NTP Configuration
# Multiple NTP sources for reliability

pool 0.rocky.pool.ntp.org iburst maxsources 4
pool 1.rocky.pool.ntp.org iburst maxsources 4
pool 2.rocky.pool.ntp.org iburst maxsources 4
pool 3.rocky.pool.ntp.org iburst maxsources 4

# Allow large clock adjustments
makestep 1.0 3

# Enable kernel synchronization
rtcsync

# Log directory
logdir /var/log/chrony

# Security
bindcmdaddress 127.0.0.1
EOF
            ;;
    esac
    
    # Enable and start chrony
    service_enable chrony 2>/dev/null || service_enable chronyd 2>/dev/null || true
    service_restart chrony 2>/dev/null || service_restart chronyd 2>/dev/null || true
    
    log_success "Time synchronization configured ✓"
}

configure_logging() {
    log_step "Configuring enhanced logging..."
    
    # Create WebOps log directory
    ensure_directory "/var/log/webops" "root:root" "755"
    
    # Configure journald for persistent logging
    mkdir -p /var/log/journal
    mkdir -p /etc/systemd/journald.conf.d
    cat > /etc/systemd/journald.conf.d/99-webops.conf <<'EOF'
# WebOps Journal Configuration
# Generated by WebOps setup/base.sh

[Journal]
Storage=persistent
Compress=yes
SystemMaxUse=1G
SystemMaxFileSize=100M
RuntimeMaxUse=100M
RuntimeMaxFileSize=10M
ForwardToSyslog=yes
ForwardToConsole=no
EOF
    
    # Configure logrotate for WebOps logs
    cat > /etc/logrotate.d/webops <<'EOF'
# WebOps Log Rotation
# Generated by WebOps setup/base.sh

/var/log/webops/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root adm
    postrotate
        systemctl reload rsyslog 2>/dev/null || true
    endscript
}

/var/log/webops/*/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    maxsize 100M
    create 0640 root adm
}
EOF
    
    # Restart journald
    systemctl restart systemd-journald
    
    log_success "Enhanced logging configured ✓"
}

#=============================================================================
# Firewall Configuration
#=============================================================================

get_ssh_listener_ports() {
    # Never enable a restrictive firewall without knowing the SSH entry ports.
    local effective="" port="" remote_ip="" remote_port="" local_ip="" connected_port=""
    if ! command -v sshd >/dev/null 2>&1 ||
       ! effective="$(sshd -T 2>/dev/null)"; then
        log_error "Cannot determine SSH listening ports; leaving firewall disabled"
        return 1
    fi
    local ports=()
    while read -r port; do
        [[ -z "$port" ]] && continue
        if [[ ! "$port" =~ ^[0-9]+$ ]] || (( port < 1 || port > 65535 )); then
            log_error "Invalid sshd listening port; refusing firewall changes"
            return 1
        fi
        ports+=("$port")
    done < <(awk '$1=="port"{print $2}' <<< "$effective")
    if [[ -v SSH_CONNECTION && -n "$SSH_CONNECTION" ]]; then
        read -r remote_ip remote_port local_ip connected_port <<< "$SSH_CONNECTION"
        if [[ ! "$connected_port" =~ ^[0-9]+$ ]] ||
           (( connected_port < 1 || connected_port > 65535 )); then
            log_error "Cannot interpret SSH_CONNECTION server port"
            return 1
        fi
        ports+=("$connected_port")
    fi
    if (( ${#ports[@]} == 0 )); then
        log_error "No SSH ports known; refusing firewall changes"
        return 1
    fi
    printf '%s\n' "${ports[@]}" | sort -n -u
}

configure_firewall() {
    if [[ "$ENABLE_FIREWALL" != "true" ]]; then
        log_info "Firewall configuration disabled"
        return 0
    fi
    
    log_step "Configuring firewall..."
    
    # Use OS-specific firewall configuration
    case "$OS_ID" in
        ubuntu|debian)
            configure_ufw
            ;;
        rocky|almalinux)
            configure_firewalld
            ;;
    esac
    
    log_success "Firewall configured ✓"
}

configure_ufw() {
    # Preserve administrator-managed rules if the firewall is already active.
    if ufw status 2>/dev/null | grep -q "^Status: active"; then
        log_warn "Existing active UFW detected; leaving firewall policy untouched"
        return 0
    fi

    local ssh_ports port
    ssh_ports="$(get_ssh_listener_ports)" || return 1
    ufw default deny incoming
    ufw default allow outgoing
    # Authorize every active or configured SSH port BEFORE enabling UFW.
    while read -r port; do
        ufw allow "$port/tcp" comment 'SSH'
    done <<< "$ssh_ports"
    ufw allow 80/tcp comment 'HTTP'
    ufw allow 443/tcp comment 'HTTPS'
    ufw --force enable
}

configure_firewalld() {
    if command -v firewall-cmd >/dev/null 2>&1 &&
       firewall-cmd --state 2>/dev/null | grep -q "^running"; then
        log_warn "Existing active firewalld detected; preserving firewall policy"
        return 0
    fi

    local ssh_ports port
    ssh_ports="$(get_ssh_listener_ports)" || return 1
    pkg_install firewalld
    if ! command -v firewall-offline-cmd >/dev/null 2>&1; then
        log_error "Cannot preauthorize SSH before starting firewalld"
        return 1
    fi
    # Starting a restrictive firewall *before* allowing SSH could lock out
    # administrators. Configure the default zone while offline instead.
    while read -r port; do
        firewall-offline-cmd --add-port="$port/tcp"
    done <<< "$ssh_ports"
    firewall-offline-cmd --add-service=http
    firewall-offline-cmd --add-service=https
    service_enable firewalld
    service_restart firewalld
    firewall-cmd --reload
}

#=============================================================================
# Package Management and Updates
#=============================================================================

update_system_packages() {
    log_step "Updating system packages..."
    
    # Update package lists
    pkg_update
    
    # Install essential packages
    local essential_packages=(
        curl
        wget
        unzip
        zip
        htop
        vim
        nano
        git
        rsync
        lsof
        strace
        tcpdump
        iotop
        ncdu
        tree
        jq
    )
    
    # Install OS-specific packages
    case "$OS_ID" in
        ubuntu|debian)
            essential_packages+=(
                apt-transport-https
                ca-certificates
                gnupg
                lsb-release
                software-properties-common
                build-essential
                python3
                python3-pip
                python3-venv
                redis-server
            )
            ;;
        rocky|almalinux)
            essential_packages+=(
                epel-release
                dnf-plugins-core
                python3
                python3-pip
                python3-devel
                gcc
                make
                autoconf
                automake
                redis
            )
            ;;
    esac
    
    # Install packages with retry
    for package in "${essential_packages[@]}"; do
        install_with_retry "$package"
    done
    
    log_success "System packages updated ✓"
}

#=============================================================================
# Redis Configuration
#=============================================================================

configure_redis() {
    log_step "Configuring Redis..."

    # Ensure Redis is installed
    if ! command -v redis-server &>/dev/null; then
        log_warn "Redis not installed, skipping configuration"
        return 0
    fi

    # Configure Redis for production use
    local redis_conf=""
    case "$OS_ID" in
        ubuntu|debian)
            redis_conf="/etc/redis/redis.conf"
            ;;
        rocky|almalinux)
            redis_conf="/etc/redis.conf"
            ;;
    esac

    if [[ -f "$redis_conf" ]]; then
        # Backup original configuration
        if [[ ! -f "$redis_conf.webops-backup" ]]; then
            cp "$redis_conf" "$redis_conf.webops-backup"
            log_info "Created Redis config backup"
        fi

        # Apply production settings
        sed -i 's/^bind .*/bind 127.0.0.1/' "$redis_conf"
        sed -i 's/^# maxmemory .*/maxmemory 256mb/' "$redis_conf"
        sed -i 's/^# maxmemory-policy .*/maxmemory-policy allkeys-lru/' "$redis_conf"

        log_info "Redis configured for localhost-only access with memory limits"
    fi

    # Enable and start Redis
    case "$OS_ID" in
        ubuntu|debian)
            service_enable redis-server
            service_start redis-server
            ;;
        rocky|almalinux)
            service_enable redis
            service_start redis
            ;;
    esac

    # Verify Redis is running
    if redis-cli ping &>/dev/null; then
        log_success "Redis configured and running ✓"
    else
        log_warn "Redis may not be responding to PING"
    fi
}

#=============================================================================
# Filesystem Optimization
#=============================================================================

optimize_filesystem() {
    log_step "Optimizing filesystem settings..."
    
    # Configure noatime for data partitions (if applicable)
    # This is typically done in /etc/fstab, but we'll provide guidance
    
    # Create /etc/fstab backup reminder
    if [[ ! -f /etc/fstab.webops-backup ]]; then
        cp /etc/fstab /etc/fstab.webops-backup
        log_info "Created /etc/fstab backup"
    fi
    
    # Add tmpfs for /tmp (if not already present)
    if ! grep -q "tmpfs /tmp" /etc/fstab; then
        echo "tmpfs /tmp tmpfs defaults,noatime,mode=1777 0 0" >> /etc/fstab
        log_info "Added tmpfs for /tmp"
    fi
    
    # Configure file descriptors limit
    echo "* soft nofile 65536" >> /etc/security/limits.conf
    echo "* hard nofile 65536" >> /etc/security/limits.conf
    
    log_success "Filesystem optimization completed ✓"
}

#=============================================================================
# Security Hardening
#=============================================================================

security_hardening() {
    log_step "Applying security hardening..."
    
    # Disable unused services
    local services_to_disable=(
        "bluetooth"
        "cups"
        "avahi-daemon"
        "whoopsie"
    )
    
    for service in "${services_to_disable[@]}"; do
        if systemctl is-enabled "$service" 2>/dev/null; then
            systemctl disable "$service" 2>/dev/null || true
            systemctl stop "$service" 2>/dev/null || true
            log_info "Disabled service: $service"
        fi
    done
    
    # Remove unnecessary packages
    local packages_to_remove=(
        "telnet"
        "rsh"
        "rlogin"
        "talk"
    )
    
    for package in "${packages_to_remove[@]}"; do
        if pkg_installed "$package"; then
            pkg_remove "$package" 2>/dev/null || true
            log_info "Removed package: $package"
        fi
    done
    
    # Configure automatic security updates (Ubuntu/Debian)
    if [[ "$OS_ID" == "ubuntu" || "$OS_ID" == "debian" ]]; then
        pkg_install unattended-upgrades
        cat > /etc/apt/apt.conf.d/50unattended-upgrades <<'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}";
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::Automatic-Reboot "false";
EOF
        
        cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
EOF
    fi
    
    log_success "Security hardening applied ✓"
}

#=============================================================================
# Main Installation Function
#=============================================================================

install_base_system() {
    log_info "Installing WebOps base system..."
    
    # Load OS handler
    load_os_handler
    
    # Setup repositories
    os_setup_repositories
    
    # Update system packages
    update_system_packages

    # Configure Redis
    configure_redis

    # Setup system user and security
    setup_webops_user
    configure_ssh_hardening
    configure_sudo_access
    
    # Configure system settings
    configure_system_settings
    configure_limits
    setup_time_sync
    configure_logging
    
    # Setup firewall
    configure_firewall
    
    # Optimize filesystem
    optimize_filesystem
    
    # Apply security hardening
    security_hardening
    
    # Mark base system as installed
    mark_component_installed "base-system" "1.0.0"
    
    log_success "Base system installation completed ✓"
}

#=============================================================================
# Script Execution
#=============================================================================

# Handle command line arguments
action="${1:-install}"

case "$action" in
    install)
        install_base_system
        ;;
    uninstall)
        log_warn "Base system uninstall not supported"
        exit 1
        ;;
    status)
        if is_component_installed "base-system"; then
            echo "Base system is installed"
            exit 0
        else
            echo "Base system is not installed"
            exit 1
        fi
        ;;
    version)
        echo "base-system 1.0.0"
        ;;
    *)
        log_error "Unknown action: $action"
        echo "Usage: $0 {install|status|version}"
        exit 1
        ;;
esac
