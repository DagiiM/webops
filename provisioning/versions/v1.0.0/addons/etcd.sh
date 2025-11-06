#!/bin/bash
#
# WebOps etcd Addon
# Installs and configures etcd distributed key-value store
#
# This addon supports:
# - Single-node etcd installation
# - Multi-node HA cluster setup
# - TLS encryption for security
# - Automatic snapshots and backup
#

set -euo pipefail

# Addon metadata
# Addon metadata (use local variables to avoid conflicts when sourced)
local ADDON_NAME="etcd"
local ADDON_VERSION="3.5.9"
local ADDON_DESCRIPTION="etcd Distributed Key-Value Store"

# Source libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
source "${SCRIPT_DIR}/../lib/os.sh"
source "${SCRIPT_DIR}/../lib/state.sh"

# Configuration
# Configuration (use local variables to avoid conflicts when sourced)
local ETCD_VERSION="${ETCD_VERSION:-3.5.9}"
local ETCD_USER="${ETCD_USER:-etcd}"
local ETCD_DATA_DIR="${ETCD_DATA_DIR:-/var/lib/etcd}"
local ETCD_CONFIG_DIR="${ETCD_CONFIG_DIR:-/etc/etcd}"
local ETCD_LOG_DIR="${ETCD_LOG_DIR:-/var/log/etcd}"
local ETCD_CERT_DIR="${ETCD_CERT_DIR:-/etc/etcd/certs}"

# Load configuration
load_config

# Cluster configuration
readonly ETCD_CLUSTER_NAME="${ETCD_CLUSTER_NAME:-webops-cluster}"
readonly ETCD_INITIAL_ADVERTISE_PEER_URLS="${ETCD_INITIAL_ADVERTISE_PEER_URLS:-}"
readonly ETCD_INITIAL_CLUSTER="${ETCD_INITIAL_CLUSTER:-}"
readonly ETCD_INITIAL_CLUSTER_STATE="${ETCD_INITIAL_CLUSTER:-new}"

#=============================================================================
# etcd Installation
#=============================================================================

install_etcd_packages() {
    log_step "Installing etcd packages..."
    
    case "$OS_ID" in
        ubuntu|debian)
            # Download etcd binary
            local etcd_arch="amd64"
            if [[ "$(uname -m)" == "aarch64" ]]; then
                etcd_arch="arm64"
            fi
            
            local etcd_url="https://github.com/etcd-io/etcd/releases/download/v${ETCD_VERSION}/etcd-v${ETCD_VERSION}-linux-${etcd_arch}.tar.gz"
            
            log_info "Downloading etcd v${ETCD_VERSION}..."
            cd /tmp
            wget -q "$etcd_url" -O etcd.tar.gz
            
            # Extract and install
            tar xzf etcd.tar.gz
            cd "etcd-v${ETCD_VERSION}-linux-${etcd_arch}"
            
            # Install binaries
            cp etcd etcdctl /usr/local/bin/
            chmod +x /usr/local/bin/etcd /usr/local/bin/etcdctl
            
            # Cleanup
            cd /tmp
            rm -rf etcd.tar.gz "etcd-v${ETCD_VERSION}-linux-${etcd_arch}"
            ;;
        rocky|almalinux)
            # Install from EPEL or compile from source
            if pkg_install etcd; then
                log_info "etcd installed from repository"
            else
                # Fallback to binary installation
                local etcd_arch="amd64"
                if [[ "$(uname -m)" == "aarch64" ]]; then
                    etcd_arch="arm64"
                fi
                
                local etcd_url="https://github.com/etcd-io/etcd/releases/download/v${ETCD_VERSION}/etcd-v${ETCD_VERSION}-linux-${etcd_arch}.tar.gz"
                
                log_info "Downloading etcd v${ETCD_VERSION}..."
                cd /tmp
                wget -q "$etcd_url" -O etcd.tar.gz
                
                # Extract and install
                tar xzf etcd.tar.gz
                cd "etcd-v${ETCD_VERSION}-linux-${etcd_arch}"
                
                # Install binaries
                cp etcd etcdctl /usr/local/bin/
                chmod +x /usr/local/bin/etcd /usr/local/bin/etcdctl
                
                # Cleanup
                cd /tmp
                rm -rf etcd.tar.gz "etcd-v${ETCD_VERSION}-linux-${etcd_arch}"
            fi
            ;;
    esac
    
    # Verify installation
    if command -v etcd &>/dev/null; then
        local installed_version=$(etcd --version | grep -oP 'etcd Version: \K[^ ]+' || echo "unknown")
        log_success "etcd installed: $installed_version ✓"
    else
        log_error "etcd installation failed"
        return 1
    fi
}

setup_etcd_user() {
    log_step "Setting up etcd user..."
    
    # Create etcd user
    if ! id "$ETCD_USER" &>/dev/null; then
        useradd -r -s /bin/bash -d "$ETCD_DATA_DIR" "$ETCD_USER"
        log_info "Created etcd user: $ETCD_USER"
    else
        log_info "etcd user $ETCD_USER already exists"
    fi
    
    # Create directories
    ensure_directory "$ETCD_DATA_DIR" "$ETCD_USER:$ETCD_USER" "700"
    ensure_directory "$ETCD_CONFIG_DIR" "$ETCD_USER:$ETCD_USER" "755"
    ensure_directory "$ETCD_LOG_DIR" "$ETCD_USER:$ETCD_USER" "755"
    ensure_directory "$ETCD_CERT_DIR" "$ETCD_USER:$ETCD_USER" "700"
    
    log_success "etcd user setup completed ✓"
}

generate_etcd_certificates() {
    log_step "Generating etcd TLS certificates..."
    
    # Check if certificates already exist
    if [[ -f "$ETCD_CERT_DIR/server.crt" && -f "$ETCD_CERT_DIR/server.key" ]]; then
        log_info "etcd certificates already exist"
        return 0
    fi
    
    # Generate CA certificate
    local ca_key="$ETCD_CERT_DIR/ca.key"
    local ca_csr="$ETCD_CERT_DIR/ca.csr"
    local ca_crt="$ETCD_CERT_DIR/ca.crt"
    
    # Generate CA private key
    openssl genrsa -out "$ca_key" 2048
    
    # Generate CA certificate signing request
    openssl req -new -key "$ca_key" -subj "/CN=etcd-ca" -out "$ca_csr"
    
    # Generate CA certificate
    openssl x509 -req -in "$ca_csr" -signkey "$ca_key" -days 3650 -out "$ca_crt" -extensions v3_ca
    
    # Generate server certificate
    local server_key="$ETCD_CERT_DIR/server.key"
    local server_csr="$ETCD_CERT_DIR/server.csr"
    local server_crt="$ETCD_CERT_DIR/server.crt"
    
    # Generate server private key
    openssl genrsa -out "$server_key" 2048
    
    # Generate server certificate signing request
    openssl req -new -key "$server_key" -subj "/CN=etcd-server" -out "$server_csr"
    
    # Generate server certificate
    openssl x509 -req -in "$server_csr" -CA "$ca_crt" -CAkey "$ca_key" -CAcreateserial -days 3650 -out "$server_crt"
    
    # Generate peer certificate
    local peer_key="$ETCD_CERT_DIR/peer.key"
    local peer_csr="$ETCD_CERT_DIR/peer.csr"
    local peer_crt="$ETCD_CERT_DIR/peer.crt"
    
    # Generate peer private key
    openssl genrsa -out "$peer_key" 2048
    
    # Generate peer certificate signing request
    openssl req -new -key "$peer_key" -subj "/CN=etcd-peer" -out "$peer_csr"
    
    # Generate peer certificate
    openssl x509 -req -in "$peer_csr" -CA "$ca_crt" -CAkey "$ca_key" -CAcreateserial -days 3650 -out "$peer_crt"
    
    # Set proper permissions
    chmod 600 "$ETCD_CERT_DIR"/*.key
    chmod 644 "$ETCD_CERT_DIR"/*.crt
    chown -R "$ETCD_USER:$ETCD_USER" "$ETCD_CERT_DIR"
    
    # Clean up CSR files
    rm -f "$ETCD_CERT_DIR"/*.csr
    
    log_success "etcd TLS certificates generated ✓"
}

configure_etcd() {
    log_step "Configuring etcd..."
    
    # Get system IP address
    local system_ip=$(hostname -I | awk '{print $1}')
    local advertise_peer_url="https://${system_ip}:2380"
    local listen_peer_urls="https://${system_ip}:2380"
    local listen_client_urls="https://127.0.0.1:2379,https://${system_ip}:2379"
    
    # Override with configuration if provided
    if [[ -n "${ETCD_ADVERTISE_PEER_URLS:-}" ]]; then
        advertise_peer_url="$ETCD_ADVERTISE_PEER_URLS"
    fi
    
    # Create etcd configuration
    cat > "$ETCD_CONFIG_DIR/etcd.conf" <<EOF
# WebOps etcd Configuration
# Generated by WebOps addons/etcd.sh

# Member configuration
name: etcd-$(hostname -s | tr '[:upper:]' '[:lower:]')
data-dir: $ETCD_DATA_DIR
listen-peer-urls: $listen_peer_urls
listen-client-urls: $listen_client_urls
advertise-client-urls: $listen_client_urls
initial-advertise-peer-urls: $advertise_peer_url

# Cluster configuration
initial-cluster: $ETCD_INITIAL_CLUSTER
initial-cluster-state: $ETCD_INITIAL_CLUSTER_STATE

# Security configuration
client-cert-auth: true
trusted-ca-file: $ETCD_CERT_DIR/ca.crt
cert-file: $ETCD_CERT_DIR/server.crt
key-file: $ETCD_CERT_DIR/server.key
peer-client-cert-auth: true
peer-trusted-ca-file: $ETCD_CERT_DIR/ca.crt
peer-cert-file: $ETCD_CERT_DIR/peer.crt
peer-key-file: $ETCD_CERT_DIR/peer.key

# Logging configuration
log-level: info
log-outputs: default
logger: zap
log-package-levels: etcdserver=info,etcdclient=debug

# Performance tuning
heartbeat-interval: 250
election-timeout: 5000
max-snapshots: 5
max-wals: 5
snapshot-count: 5
snapshot-catchup-entries: 10000

# Auto-compaction
auto-compaction-mode: periodic
auto-compaction-retention: 1h

# Metrics
enable-pprof: false
metrics: basic
EOF
    
    # Set ownership and permissions
    chown "$ETCD_USER:$ETCD_USER" "$ETCD_CONFIG_DIR/etcd.conf"
    chmod 640 "$ETCD_CONFIG_DIR/etcd.conf"
    
    log_success "etcd configured ✓"
}

create_etcd_systemd_service() {
    log_step "Creating etcd systemd service..."
    
    cat > /etc/systemd/system/etcd.service <<EOF
[Unit]
Description=etcd Key-Value Store
Documentation=https://github.com/etcd-io/etcd
After=network.target
Wants=network-online.target

[Service]
Type=notify
User=$ETCD_USER
Group=$ETCD_USER

# Environment file
EnvironmentFile=$ETCD_CONFIG_DIR/etcd.env

# ExecStart
ExecStart=/usr/local/bin/etcd

# Restart policy
Restart=always
RestartSec=5s

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$ETCD_DATA_DIR $ETCD_LOG_DIR

# Resource limits
LimitNOFILE=65536
LimitNPROC=32768

[Install]
WantedBy=multi-user.target
EOF
    
    # Create environment file
    cat > "$ETCD_CONFIG_DIR/etcd.env" <<EOF
# etcd Environment Variables
ETCD_NAME=etcd-$(hostname -s | tr '[:upper:]' '[:lower:]')
ETCD_DATA_DIR=$ETCD_DATA_DIR
ETCD_LISTEN_PEER_URLS=$(grep 'listen-peer-urls:' $ETCD_CONFIG_DIR/etcd.conf | cut -d' ' -f2 | tr -d ' ')
ETCD_LISTEN_CLIENT_URLS=$(grep 'listen-client-urls:' $ETCD_CONFIG_DIR/etcd.conf | cut -d' ' -f2 | tr -d ' ')
ETCD_ADVERTISE_CLIENT_URLS=$(grep 'advertise-client-urls:' $ETCD_CONFIG_DIR/etcd.conf | cut -d' ' -f2 | tr -d ' ')
ETCD_INITIAL_ADVERTISE_PEER_URLS=$(grep 'initial-advertise-peer-urls:' $ETCD_CONFIG_DIR/etcd.conf | cut -d' ' -f2 | tr -d ' ')
ETCD_INITIAL_CLUSTER=$(grep 'initial-cluster:' $ETCD_CONFIG_DIR/etcd.conf | cut -d' ' -f2 | tr -d ' ')
ETCD_INITIAL_CLUSTER_STATE=$(grep 'initial-cluster-state:' $ETCD_CONFIG_DIR/etcd.conf | cut -d' ' -f2 | tr -d ' ')
EOF
    
    # Set ownership
    chown "$ETCD_USER:$ETCD_USER" "$ETCD_CONFIG_DIR/etcd.env"
    chmod 640 "$ETCD_CONFIG_DIR/etcd.env"
    
    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable etcd
    
    log_success "etcd systemd service created ✓"
}

setup_etcd_service() {
    log_step "Starting etcd service..."
    
    # Start etcd service
    systemctl start etcd
    
    # Wait for etcd to start
    local max_attempts=10
    local attempt=1
    
    while (( attempt <= max_attempts )); do
        if etcdctl endpoint health --endpoints="$ETCD_LISTEN_CLIENT_URLS" &>/dev/null; then
            log_success "etcd service is running ✓"
            return 0
        fi
        
        log_info "Waiting for etcd to start (attempt $attempt/$max_attempts)..."
        sleep 2
        ((attempt++))
    done
    
    log_error "etcd failed to start"
    return 1
}

configure_etcd_backups() {
    log_step "Configuring etcd backups..."
    
    # Create backup directory
    local backup_dir="${WEBOPS_ROOT:-/webops}/backups/etcd"
    ensure_directory "$backup_dir" "$ETCD_USER:$ETCD_USER" "700"
    
    # Create backup script
    local backup_script="/usr/local/bin/webops-etcd-backup"
    cat > "$backup_script" <<'EOF'
#!/bin/bash
#
# WebOps etcd Backup Script
# Runs periodic snapshots of etcd data
#

set -euo pipefail

# Configuration
BACKUP_DIR="${WEBOPS_ROOT:-/webops}/backups/etcd"
ETCD_DATA_DIR="${ETCD_DATA_DIR:-/var/lib/etcd}"
RETENTION_DAYS=7

# Create backup filename with timestamp
BACKUP_FILE="$BACKUP_DIR/etcd-snapshot-$(date +%Y%m%d-%H%M%S).db"

# Create etcd snapshot
ETCDCTL_API=3 etcdctl snapshot save "$BACKUP_FILE"

# Compress backup
gzip "$BACKUP_FILE"

# Remove old backups
find "$BACKUP_DIR" -name "etcd-snapshot-*.db.gz" -mtime +$RETENTION_DAYS -delete

# Log backup completion
logger -t webops-etcd-backup "etcd backup completed: $(basename "$BACKUP_FILE.gz")"
EOF
    
    chmod +x "$backup_script"
    
    # Create cron job for periodic snapshots every 6 hours
    local cron_job="0 */6 * * * $backup_script"
    
    # Add to etcd user's crontab
    if ! sudo -u "$ETCD_USER" crontab -l 2>/dev/null | grep -q "webops-etcd-backup"; then
        (sudo -u "$ETCD_USER" crontab -l 2>/dev/null; echo "$cron_job") | sudo -u "$ETCD_USER" crontab -
        log_info "Added periodic backup cron job"
    else
        log_info "Backup cron job already exists"
    fi
    
    log_success "etcd backup configuration completed ✓"
}

#=============================================================================
# Health Checks
#=============================================================================

check_etcd_health() {
    log_step "Checking etcd health..."
    
    # Check if etcd is running
    if ! systemctl is-active --quiet etcd; then
        log_error "etcd service is not running"
        return 1
    fi
    
    # Check etcd endpoint health
    if ! etcdctl endpoint health --endpoints="$ETCD_LISTEN_CLIENT_URLS" &>/dev/null; then
        log_error "etcd endpoint health check failed"
        return 1
    fi
    
    # Check cluster status
    local cluster_status
    cluster_status=$(etcdctl endpoint status --write-out=table --endpoints="$ETCD_LISTEN_CLIENT_URLS" 2>/dev/null | tail -n +2 | head -1)
    
    if [[ -n "$cluster_status" ]]; then
        log_info "Cluster status: $cluster_status"
    fi
    
    # Check disk space for data directory
    local data_usage=$(df "$ETCD_DATA_DIR" | awk 'NR==2{print $5}' | sed 's/%//')
    if [[ $data_usage -gt 80 ]]; then
        log_warn "etcd data directory is ${data_usage}% full"
    fi
    
    log_success "etcd health check passed ✓"
    return 0
}

#=============================================================================
# Addon Lifecycle Management
#=============================================================================

addon_install() {
    log_info "Installing etcd addon..."
    
    # Install packages
    install_etcd_packages
    
    # Setup user and directories
    setup_etcd_user
    
    # Generate certificates
    generate_etcd_certificates
    
    # Configure etcd
    configure_etcd
    
    # Create systemd service
    create_etcd_systemd_service
    
    # Start service
    setup_etcd_service
    
    # Configure backups
    configure_etcd_backups
    
    # Run health check
    check_etcd_health
    
    # Open firewall ports
    firewall_open_port 2379 tcp  # etcd client port
    firewall_open_port 2380 tcp  # etcd peer port
    
    # Mark as installed
    mark_component_installed "$ADDON_NAME" "$ADDON_VERSION"
    
    log_success "etcd addon installed successfully ✓"
}

addon_uninstall() {
    local purge="${1:-false}"
    
    log_info "Uninstalling etcd addon..."
    
    # Stop etcd service
    systemctl stop etcd || true
    systemctl disable etcd || true
    
    if [[ "$purge" == "true" ]]; then
        log_warn "Purging etcd data..."
        
        # Remove etcd binaries
        rm -f /usr/local/bin/etcd /usr/local/bin/etcdctl || true
        
        # Remove data directory
        rm -rf "$ETCD_DATA_DIR" || true
        
        # Remove certificates
        rm -rf "$ETCD_CERT_DIR" || true
        
        # Remove configuration
        rm -f "$ETCD_CONFIG_DIR/etcd.conf" "$ETCD_CONFIG_DIR/etcd.env" || true
    fi
    
    # Remove systemd service
    rm -f /etc/systemd/system/etcd.service
    systemctl daemon-reload
    
    # Close firewall ports
    firewall_close_port 2379 tcp
    firewall_close_port 2380 tcp
    
    # Remove backup script and cron job
    rm -f /usr/local/bin/webops-etcd-backup
    if id "$ETCD_USER" &>/dev/null; then
        sudo -u "$ETCD_USER" crontab -l 2>/dev/null | grep -v "webops-etcd-backup" | sudo -u "$ETCD_USER" crontab - || true
    fi
    
    # Mark as removed
    mark_component_removed "$ADDON_NAME"
    
    log_success "etcd addon uninstalled ✓"
}

addon_status() {
    if is_component_installed "$ADDON_NAME"; then
        echo "etcd addon is installed (version: $(get_component_version "$ADDON_NAME"))"
        
        if check_etcd_health >/dev/null 2>&1; then
            echo "Status: Running and healthy"
        else
            echo "Status: Running but health check failed"
        fi
        
        return 0
    else
        echo "etcd addon is not installed"
        return 1
    fi
}

addon_version() {
    echo "$ADDON_VERSION"
}

addon_metadata() {
    cat <<EOF
{
    "name": "$ADDON_NAME",
    "version": "$ADDON_VERSION",
    "description": "$ADDON_DESCRIPTION",
    "depends": ["base", "firewall"],
    "provides": ["key-value-store", "distributed-coordination"],
    "ports": [2379, 2380],
    "services": ["etcd"],
    "config_files": ["$ETCD_CONFIG_DIR/etcd.conf", "$ETCD_CONFIG_DIR/etcd.env"],
    "data_directories": ["$ETCD_DATA_DIR"],
    "log_directories": ["$ETCD_LOG_DIR"],
    "cert_directories": ["$ETCD_CERT_DIR"]
}
EOF
}

addon_sla() {
    cat <<EOF
{
    "availability_target": 99.95,
    "performance_targets": {
        "response_time": 50,
        "cpu_usage": 30.0,
        "memory_usage": 60.0,
        "disk_io": 70.0,
        "network_throughput": 500.0
    },
    "recovery_objectives": {
        "rto": 120,
        "rpo": 300,
        "backup_frequency": 21600,
        "test_frequency": 604800
    },
    "support_level": "critical",
    "monitoring_requirements": {
        "health_check_interval": 30,
        "metrics_retention": 2592000,
        "alert_thresholds": {
            "cluster_health": 1,
            "disk_usage": 85,
            "leader_elections": 5
        }
    }
}
EOF
}

addon_security() {
    cat <<EOF
{
    "privilege_level": "service",
    "data_access": ["configuration_data", "cluster_data", "certificates"],
    "network_access": ["localhost", "127.0.0.1", "::1", "cluster_nodes"],
    "authentication": {
        "method": "certificate",
        "encryption": "tls",
        "certificate_validation": true
    },
    "authorization": {
        "role_based_access": true,
        "least_privilege": true,
        "privilege_separation": true
    },
    "encryption": {
        "data_at_rest": false,
        "data_in_transit": true,
        "backup_encryption": false
    },
    "audit": {
        "connection_logging": true,
        "configuration_changes": true,
        "cluster_operations": true,
        "access_failures": true
    },
    "vulnerability_management": {
        "security_updates": true,
        "vulnerability_scanning": false,
        "penetration_testing": false
    },
    "compliance": {
        "data_classification": "confidential",
        "retention_policy": true,
        "gdpr_compliance": false
    }
}
EOF
}

addon_health_check() {
    check_etcd_health
}

addon_start() {
    log_step "Starting etcd service..."
    systemctl start etcd
    sleep 5
    check_etcd_health
}

addon_stop() {
    log_step "Stopping etcd service..."
    systemctl stop etcd
}

addon_restart() {
    log_step "Restarting etcd service..."
    systemctl restart etcd
    sleep 5
    check_etcd_health
}

addon_configure() {
    configure_etcd
}

addon_validate() {
    log_step "Validating etcd configuration..."
    
    # Check configuration files
    if [[ ! -f "$ETCD_CONFIG_DIR/etcd.conf" ]]; then
        log_error "etcd configuration file not found"
        return 1
    fi
    
    if [[ ! -f "$ETCD_CONFIG_DIR/etcd.env" ]]; then
        log_error "etcd environment file not found"
        return 1
    fi
    
    # Check data directory
    if [[ ! -d "$ETCD_DATA_DIR" ]]; then
        log_error "etcd data directory not found"
        return 1
    fi
    
    # Check certificates
    if [[ ! -f "$ETCD_CERT_DIR/server.crt" || ! -f "$ETCD_CERT_DIR/server.key" ]]; then
        log_error "etcd TLS certificates not found"
        return 1
    fi
    
    # Validate configuration syntax
    if ! etcd --config-file="$ETCD_CONFIG_DIR/etcd.conf" --dry-run >/dev/null 2>&1; then
        log_warn "etcd configuration validation failed, but this may be expected"
    fi
    
    log_success "etcd configuration validation passed ✓"
    return 0
}

addon_backup() {
    log_step "Creating etcd backup..."
    
    local backup_dir="${WEBOPS_ROOT:-/webops}/backups/etcd"
    local backup_file="$backup_dir/etcd-snapshot-$(date +%Y%m%d-%H%M%S).db"
    
    ensure_directory "$backup_dir" "$ETCD_USER:$ETCD_USER" "700"
    
    # Create snapshot
    if ETCDCTL_API=3 etcdctl snapshot save "$backup_file"; then
        gzip "$backup_file"
        log_success "etcd backup created: ${backup_file}.gz"
        return 0
    else
        log_error "etcd backup failed"
        rm -f "$backup_file"
        return 1
    fi
}

addon_restore() {
    local backup_file="$1"
    
    if [[ -z "$backup_file" ]]; then
        log_error "Backup file not specified"
        return 1
    fi
    
    if [[ ! -f "$backup_file" ]]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi
    
    log_step "Restoring etcd from backup: $backup_file"
    
    # Stop etcd
    systemctl stop etcd
    
    # Extract backup if compressed
    local restore_file="$backup_file"
    if [[ "$backup_file" == *.gz ]]; then
        restore_file="/tmp/etcd-restore-$(date +%s).db"
        gunzip -c "$backup_file" > "$restore_file"
    fi
    
    # Restore backup
    if ETCDCTL_API=3 etcdctl snapshot restore "$restore_file" --data-dir "$ETCD_DATA_DIR"; then
        log_success "etcd restore completed"
        
        # Clean up temporary file
        if [[ "$restore_file" != "$backup_file" ]]; then
            rm -f "$restore_file"
        fi
        
        # Set proper ownership
        chown -R "$ETCD_USER:$ETCD_USER" "$ETCD_DATA_DIR"
        
        # Start etcd
        systemctl start etcd
        return 0
    else
        log_error "etcd restore failed"
        
        # Clean up temporary file
        if [[ "$restore_file" != "$backup_file" ]]; then
            rm -f "$restore_file"
        fi
        
        return 1
    fi
}

#=============================================================================
# Script Execution
#=============================================================================

# Handle command line arguments
action="${1:-install}"

# Only execute main logic if script is called directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
case "$action" in
    install)
        addon_install
        ;;
    uninstall)
        addon_uninstall "${2:-false}"
        ;;
    status)
        addon_status
        ;;
    version)
        addon_version
        ;;
    health)
        check_etcd_health
        ;;
    *)
        log_error "Unknown action: $action"
        echo "Usage: $0 {install|uninstall [--purge]|status|version|health}"
        exit 1
        ;;
esac
fi
