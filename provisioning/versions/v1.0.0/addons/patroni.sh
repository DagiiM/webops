#!/bin/bash
#
# WebOps Patroni Addon
# Installs and configures Patroni for PostgreSQL high availability
#
# This addon supports:
# - PostgreSQL HA cluster with automatic failover
# - etcd-based distributed consensus
# - TLS encryption for replication
# - Automated backup and recovery
# - Connection pooling via PgBouncer
#

set -euo pipefail

# Addon metadata
# Only set readonly variables if they're not already set
if [[ -z "${ADDON_NAME:-}" ]]; then
    readonly ADDON_NAME="patroni"
fi
if [[ -z "${ADDON_VERSION:-}" ]]; then
    readonly ADDON_VERSION="3.0.2"
fi
if [[ -z "${ADDON_DESCRIPTION:-}" ]]; then
    readonly ADDON_DESCRIPTION="Patroni PostgreSQL High Availability Cluster"
fi

# Source libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
source "${SCRIPT_DIR}/../lib/os.sh"
source "${SCRIPT_DIR}/../lib/state.sh"
source "${SCRIPT_DIR}/../lib/addon-contract.sh"

# Configuration
# Only set readonly variables if they're not already set
if [[ -z "${PATRONI_VERSION:-}" ]]; then
    readonly PATRONI_VERSION="3.0.2"
fi
if [[ -z "${PATRONI_USER:-}" ]]; then
    readonly PATRONI_USER="patroni"
fi
if [[ -z "${PATRONI_CONFIG_DIR:-}" ]]; then
    readonly PATRONI_CONFIG_DIR="/etc/patroni"
fi
if [[ -z "${PATRONI_LOG_DIR:-}" ]]; then
    readonly PATRONI_LOG_DIR="/var/log/patroni"
fi
if [[ -z "${PATRONI_RUN_DIR:-}" ]]; then
    readonly PATRONI_RUN_DIR="/var/run/patroni"
fi
if [[ -z "${PATRONI_DATA_DIR:-}" ]]; then
    readonly PATRONI_DATA_DIR="/var/lib/postgresql/data"
fi
if [[ -z "${PGBOUNCER_USER:-}" ]]; then
    readonly PGBOUNCER_USER="pgbouncer"
fi
if [[ -z "${PGBOUNCER_CONFIG_DIR:-}" ]]; then
    readonly PGBOUNCER_CONFIG_DIR="/etc/pgbouncer"
fi

# Load configuration
load_config

# Cluster configuration
# Only set readonly variables if they're not already set
if [[ -z "${PATRONI_CLUSTER_NAME:-}" ]]; then
    readonly PATRONI_CLUSTER_NAME="webops-pg-cluster"
fi
if [[ -z "${PATRONI_NAMESPACE:-}" ]]; then
    readonly PATRONI_NAMESPACE="/service/"
fi
if [[ -z "${PATRONI_RESTAPI_PORT:-}" ]]; then
    readonly PATRONI_RESTAPI_PORT="8008"
fi
if [[ -z "${PATRONI_POSTGRESQL_PORT:-}" ]]; then
    readonly PATRONI_POSTGRESQL_PORT="5432"
fi
if [[ -z "${PGBOUNCER_PORT:-}" ]]; then
    readonly PGBOUNCER_PORT="6432"
fi

#=============================================================================
# Addon Contract Functions
#=============================================================================

addon_metadata() {
    cat <<EOF
{
    "name": "$ADDON_NAME",
    "version": "$ADDON_VERSION",
    "description": "$ADDON_DESCRIPTION",
    "category": "database",
    "depends": ["etcd", "postgresql"],
    "provides": ["postgresql-ha", "patroni", "pgbouncer"],
    "conflicts": [],
    "system_requirements": {
        "min_memory_mb": 2048,
        "min_disk_gb": 10,
        "min_cpu_cores": 2,
        "required_ports": [5432, 6432, 8008]
    },
    "maintainer": "WebOps Team",
    "license": "MIT",
    "documentation_url": "https://webops.dev/docs/addons/patroni",
    "support_url": "https://webops.dev/support",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-10-29T09:35:00Z"
}
EOF
}

addon_sla() {
    cat <<EOF
{
    "availability_target": "99.95%",
    "performance_targets": {
        "max_response_time_ms": 100,
        "max_failover_time_s": 30,
        "min_throughput_ops_per_sec": 1000
    },
    "recovery_objectives": {
        "rpo": "0",
        "rto": "30s"
    },
    "monitoring_requirements": {
        "metrics": ["patroni_status", "postgresql_connections", "replication_lag"],
        "alerting": ["cluster_failure", "replication_lag", "node_down"],
        "health_checks": ["patroni_api", "postgresql_connection"]
    },
    "maintenance_windows": {
        "planned_maintenance": "4_hours_monthly",
        "emergency_maintenance": "24x7",
        "notification_requirements": ["24_hours_advance", "stakeholder_approval"]
    }
}
EOF
}

addon_security() {
    cat <<EOF
{
    "privilege_level": "high",
    "required_capabilities": [
        "SYS_ADMIN",
        "DAC_OVERRIDE",
        "SETUID",
        "SETGID"
    ],
    "system_user": "$PATRONI_USER",
    "data_access": {
        "type": "database",
        "locations": [
            "$PATRONI_DATA_DIR",
            "$PATRONI_CONFIG_DIR",
            "$PATRONI_LOG_DIR"
        ],
        "encryption": true,
        "backup_retention_days": 30
    },
    "network_access": {
        "required_ports": [5432, 6432, 8008],
        "protocols": ["postgresql", "https"],
        "encryption_required": true
    },
    "authentication": {
        "method": "certificate",
        "certificate_locations": [
            "$PATRONI_CONFIG_DIR/certs/server.crt",
            "$PATRONI_CONFIG_DIR/certs/server.key"
        ],
        "ca_certificate": "$PATRONI_CONFIG_DIR/certs/ca.crt"
    },
    "audit_logging": {
        "enabled": true,
        "log_level": "info",
        "log_retention_days": 90,
        "audit_events": [
            "login",
            "privilege_escalation",
            "data_access",
            "configuration_change"
        ]
    },
    "vulnerability_scanning": {
        "enabled": true,
        "scan_frequency": "weekly",
        "auto_patch_security": true
    },
    "compliance": {
        "standards": ["SOC2", "GDPR", "HIPAA"],
        "data_classification": "confidential",
        "pii_handling": true
    }
}
EOF
}

addon_health_check() {
    local detailed="${1:-false}"
    
    # Check if Patroni is running
    if ! systemctl is-active --quiet patroni; then
        echo "CRITICAL: Patroni service is not running"
        return 2
    fi
    
    # Check if PgBouncer is running
    if ! systemctl is-active --quiet pgbouncer; then
        echo "CRITICAL: PgBouncer service is not running"
        return 2
    fi
    
    # Check Patroni API health
    if ! curl -f -s http://localhost:8008/health >/dev/null; then
        echo "CRITICAL: Patroni API health check failed"
        return 2
    fi
    
    # Check PostgreSQL connection
    if ! pg_isready -h localhost -p 5432 -U postgres >/dev/null 2>&1; then
        echo "CRITICAL: PostgreSQL connection check failed"
        return 2
    fi
    
    # Check PgBouncer connection
    if ! pg_isready -h localhost -p 6432 -U postgres >/dev/null 2>&1; then
        echo "WARNING: PgBouncer connection check failed"
        return 1
    fi
    
    # Get cluster status
    local cluster_state=$(curl -s http://localhost:8008/cluster | jq -r '.state' 2>/dev/null || echo "unknown")
    local role=$(curl -s http://localhost:8008/role 2>/dev/null || echo "unknown")
    
    if [[ "$cluster_state" != "running" ]]; then
        echo "WARNING: Cluster state is $cluster_state"
        return 1
    fi
    
    # Check disk space for data directory
    local data_usage=$(df "$PATRONI_DATA_DIR" | awk 'NR==2{print $5}' | sed 's/%//')
    if [[ $data_usage -gt 85 ]]; then
        echo "WARNING: Patroni data directory is ${data_usage}% full"
        return 1
    fi
    
    if [[ "$detailed" == "true" ]]; then
        echo "Patroni cluster is healthy"
        echo "Cluster state: $cluster_state"
        echo "Node role: $role"
        echo "Data directory usage: ${data_usage}%"
        
        # Get additional metrics
        local connections=$(curl -s http://localhost:8008/metrics | grep 'patroni_postgres_connections_total' | awk '{print $2}' 2>/dev/null || echo "unknown")
        echo "Active connections: $connections"
        
        local replication_lag=$(curl -s http://localhost:8008/metrics | grep 'patroni_replication_lag_seconds' | awk '{print $2}' 2>/dev/null || echo "unknown")
        echo "Replication lag: ${replication_lag}s"
    fi
    
    echo "OK: Patroni cluster is healthy (state: $cluster_state, role: $role)"
    return 0
}

addon_start() {
    log_info "Starting Patroni services..."
    
    # Start Patroni service
    systemctl start patroni
    
    # Wait for Patroni to start
    local max_attempts=30
    local attempt=1
    
    while (( attempt <= max_attempts )); do
        if curl -f -s http://localhost:8008/health >/dev/null; then
            log_success "Patroni service started ✓"
            break
        fi
        
        log_info "Waiting for Patroni to start (attempt $attempt/$max_attempts)..."
        sleep 2
        ((attempt++))
        
        if (( attempt > max_attempts )); then
            log_error "Patroni failed to start"
            return 1
        fi
    done
    
    # Start PgBouncer service
    systemctl start pgbouncer
    
    # Wait for PgBouncer to start
    if pg_isready -h localhost -p 6432 -U postgres >/dev/null 2>&1; then
        log_success "PgBouncer service started ✓"
    else
        log_error "PgBouncer failed to start"
        return 1
    fi
    
    return 0
}

addon_stop() {
    log_info "Stopping Patroni services..."
    
    # Stop PgBouncer first
    systemctl stop pgbouncer || true
    
    # Stop Patroni
    systemctl stop patroni || true
    
    log_success "Patroni services stopped ✓"
    return 0
}

addon_restart() {
    log_info "Restarting Patroni services..."
    
    # Restart Patroni
    systemctl restart patroni
    
    # Wait for Patroni to start
    local max_attempts=30
    local attempt=1
    
    while (( attempt <= max_attempts )); do
        if curl -f -s http://localhost:8008/health >/dev/null; then
            log_success "Patroni service restarted ✓"
            break
        fi
        
        log_info "Waiting for Patroni to restart (attempt $attempt/$max_attempts)..."
        sleep 2
        ((attempt++))
        
        if (( attempt > max_attempts )); then
            log_error "Patroni failed to restart"
            return 1
        fi
    done
    
    # Restart PgBouncer
    systemctl restart pgbouncer
    
    # Wait for PgBouncer to start
    if pg_isready -h localhost -p 6432 -U postgres >/dev/null 2>&1; then
        log_success "PgBouncer service restarted ✓"
    else
        log_error "PgBouncer failed to restart"
        return 1
    fi
    
    return 0
}

addon_configure() {
    local config_file="${1:-}"
    
    if [[ -n "$config_file" && -f "$config_file" ]]; then
        log_info "Applying Patroni configuration from $config_file..."
        
        # Validate configuration
        if ! python3 -c "import yaml; yaml.safe_load(open('$config_file'))" 2>/dev/null; then
            log_error "Invalid YAML configuration file: $config_file"
            return 1
        fi
        
        # Backup current configuration
        cp "$PATRONI_CONFIG_DIR/patroni.yml" "$PATRONI_CONFIG_DIR/patroni.yml.backup.$(date +%Y%m%d_%H%M%S)"
        
        # Apply new configuration
        cp "$config_file" "$PATRONI_CONFIG_DIR/patroni.yml"
        chown "$PATRONI_USER:$PATRONI_USER" "$PATRONI_CONFIG_DIR/patroni.yml"
        chmod 640 "$PATRONI_CONFIG_DIR/patroni.yml"
        
        # Restart Patroni to apply configuration
        systemctl reload patroni
        
        log_success "Patroni configuration applied ✓"
    else
        log_info "Reconfiguring Patroni with current settings..."
        configure_patroni
        systemctl reload patroni
        log_success "Patroni reconfigured ✓"
    fi
    
    return 0
}

addon_validate() {
    log_info "Validating Patroni installation..."
    
    local errors=0
    
    # Check if Patroni is installed
    if ! command -v patroni &>/dev/null; then
        log_error "Patroni is not installed"
        ((errors++))
    fi
    
    # Check if PgBouncer is installed
    if ! command -v pgbouncer &>/dev/null; then
        log_error "PgBouncer is not installed"
        ((errors++))
    fi
    
    # Check configuration files
    if [[ ! -f "$PATRONI_CONFIG_DIR/patroni.yml" ]]; then
        log_error "Patroni configuration file not found"
        ((errors++))
    fi
    
    if [[ ! -f "$PGBOUNCER_CONFIG_DIR/pgbouncer.ini" ]]; then
        log_error "PgBouncer configuration file not found"
        ((errors++))
    fi
    
    # Check certificates
    if [[ ! -f "$PATRONI_CONFIG_DIR/certs/server.crt" ]]; then
        log_error "Patroni server certificate not found"
        ((errors++))
    fi
    
    # Check systemd services
    if ! systemctl list-unit-files | grep -q "patroni.service"; then
        log_error "Patroni systemd service not found"
        ((errors++))
    fi
    
    if ! systemctl list-unit-files | grep -q "pgbouncer.service"; then
        log_error "PgBouncer systemd service not found"
        ((errors++))
    fi
    
    # Validate configuration syntax
    if command -v patroni &>/dev/null && [[ -f "$PATRONI_CONFIG_DIR/patroni.yml" ]]; then
        if ! patroni --validate-config "$PATRONI_CONFIG_DIR/patroni.yml" >/dev/null 2>&1; then
            log_error "Patroni configuration validation failed"
            ((errors++))
        fi
    fi
    
    if [[ $errors -eq 0 ]]; then
        log_success "Patroni validation passed ✓"
        return 0
    else
        log_error "Patroni validation failed with $errors errors"
        return 1
    fi
}

addon_backup() {
    local backup_dir="${1:-${WEBOPS_ROOT:-/webops}/backups/patroni}"
    local backup_type="${2:-full}"
    
    log_info "Creating Patroni backup ($backup_type)..."
    
    # Create backup directory
    mkdir -p "$backup_dir"
    
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$backup_dir/patroni-backup-$timestamp"
    
    case "$backup_type" in
        "full")
            # Logical backup
            if pg_dumpall -h localhost -p 5432 -U postgres -f "$backup_file.sql"; then
                gzip "$backup_file.sql"
                log_success "Full backup completed: $(basename "$backup_file.sql.gz")"
            else
                log_error "Full backup failed"
                return 1
            fi
            ;;
        "config")
            # Configuration backup
            tar -czf "$backup_file-config.tar.gz" \
                "$PATRONI_CONFIG_DIR" \
                "$PGBOUNCER_CONFIG_DIR" \
                /etc/systemd/system/patroni.service \
                /etc/systemd/system/pgbouncer.service
            log_success "Configuration backup completed: $(basename "$backup_file-config.tar.gz")"
            ;;
        "certificates")
            # Certificate backup
            tar -czf "$backup_file-certs.tar.gz" "$PATRONI_CONFIG_DIR/certs"
            log_success "Certificate backup completed: $(basename "$backup_file-certs.tar.gz")"
            ;;
        *)
            log_error "Unknown backup type: $backup_type"
            return 1
            ;;
    esac
    
    return 0
}

addon_restore() {
    local backup_file="${1:-}"
    
    if [[ -z "$backup_file" || ! -f "$backup_file" ]]; then
        log_error "Backup file not specified or not found: $backup_file"
        return 1
    fi
    
    log_info "Restoring Patroni from backup: $(basename "$backup_file")"
    
    # Stop services
    addon_stop
    
    case "$backup_file" in
        *.sql.gz)
            # Restore logical backup
            gunzip -c "$backup_file" | psql -h localhost -p 5432 -U postgres
            log_success "Logical backup restored ✓"
            ;;
        *-config.tar.gz)
            # Restore configuration
            tar -xzf "$backup_file" -C /
            systemctl daemon-reload
            log_success "Configuration restored ✓"
            ;;
        *-certs.tar.gz)
            # Restore certificates
            tar -xzf "$backup_file" -C /
            chown -R "$PATRONI_USER:$PATRONI_USER" "$PATRONI_CONFIG_DIR/certs"
            log_success "Certificates restored ✓"
            ;;
        *)
            log_error "Unknown backup format: $backup_file"
            return 1
            ;;
    esac
    
    # Start services
    addon_start
    
    return 0
}

#=============================================================================
# Patroni Installation
#=============================================================================

install_patroni_packages() {
    log_step "Installing Patroni packages..."
    
    # Install Python and pip if not present
    pkg_install python3 python3-pip python3-venv
    
    # Create Patroni virtual environment
    if [[ ! -d "/opt/patroni" ]]; then
        python3 -m venv /opt/patroni
        log_info "Created Patroni virtual environment"
    fi
    
    # Activate virtual environment and install Patroni
    source /opt/patroni/bin/activate
    pip install --upgrade pip
    pip install "patroni[etcd]==${PATRONI_VERSION}"
    pip install python-consul python-etcd psycopg2-binary
    
    # Create symlinks for system-wide access
    ln -sf /opt/patroni/bin/patroni /usr/local/bin/patroni
    ln -sf /opt/patroni/bin/patronictl /usr/local/bin/patronictl
    
    # Install PgBouncer
    case "$OS_ID" in
        ubuntu|debian)
            pkg_install pgbouncer
            ;;
        rocky|almalinux)
            pkg_install pgbouncer || {
                # Install from EPEL if not available
                pkg_install epel-release
                pkg_install pgbouncer
            }
            ;;
    esac
    
    # Verify installation
    if command -v patroni &>/dev/null; then
        local installed_version=$(patroni --version 2>/dev/null | grep -oP 'patroni \K[^ ]+' || echo "unknown")
        log_success "Patroni installed: $installed_version ✓"
    else
        log_error "Patroni installation failed"
        return 1
    fi
    
    if command -v pgbouncer &>/dev/null; then
        local pgbouncer_version=$(pgbouncer --version | grep -oP 'PgBouncer \K[^ ]+' || echo "unknown")
        log_success "PgBouncer installed: $pgbouncer_version ✓"
    else
        log_error "PgBouncer installation failed"
        return 1
    fi
}

setup_patroni_user() {
    log_step "Setting up Patroni user..."
    
    # Create patroni user
    if ! id "$PATRONI_USER" &>/dev/null; then
        useradd -r -s /bin/bash -d "$PATRONI_DATA_DIR" "$PATRONI_USER"
        log_info "Created Patroni user: $PATRONI_USER"
    else
        log_info "Patroni user $PATRONI_USER already exists"
    fi
    
    # Create pgbouncer user
    if ! id "$PGBOUNCER_USER" &>/dev/null; then
        useradd -r -s /bin/bash "$PGBOUNCER_USER"
        log_info "Created PgBouncer user: $PGBOUNCER_USER"
    else
        log_info "PgBouncer user $PGBOUNCER_USER already exists"
    fi
    
    # Create directories
    ensure_directory "$PATRONI_CONFIG_DIR" "$PATRONI_USER:$PATRONI_USER" "755"
    ensure_directory "$PATRONI_LOG_DIR" "$PATRONI_USER:$PATRONI_USER" "755"
    ensure_directory "$PATRONI_RUN_DIR" "$PATRONI_USER:$PATRONI_USER" "755"
    ensure_directory "$PATRONI_DATA_DIR" "$PATRONI_USER:$PATRONI_USER" "700"
    ensure_directory "$PGBOUNCER_CONFIG_DIR" "$PGBOUNCER_USER:$PGBOUNCER_USER" "755"
    
    log_success "Patroni user setup completed ✓"
}

generate_patroni_certificates() {
    log_step "Generating Patroni TLS certificates..."
    
    local cert_dir="$PATRONI_CONFIG_DIR/certs"
    ensure_directory "$cert_dir" "$PATRONI_USER:$PATRONI_USER" "700"
    
    # Check if certificates already exist
    if [[ -f "$cert_dir/server.crt" && -f "$cert_dir/server.key" ]]; then
        log_info "Patroni certificates already exist"
        return 0
    fi
    
    # Generate CA certificate
    local ca_key="$cert_dir/ca.key"
    local ca_csr="$cert_dir/ca.csr"
    local ca_crt="$cert_dir/ca.crt"
    
    # Generate CA private key
    openssl genrsa -out "$ca_key" 2048
    
    # Generate CA certificate signing request
    openssl req -new -key "$ca_key" -subj "/CN=patroni-ca" -out "$ca_csr"
    
    # Generate CA certificate
    openssl x509 -req -in "$ca_csr" -signkey "$ca_key" -days 3650 -out "$ca_crt" -extensions v3_ca
    
    # Generate server certificate
    local server_key="$cert_dir/server.key"
    local server_csr="$cert_dir/server.csr"
    local server_crt="$cert_dir/server.crt"
    
    # Generate server private key
    openssl genrsa -out "$server_key" 2048
    
    # Generate server certificate signing request
    openssl req -new -key "$server_key" -subj "/CN=$(hostname -f)" -out "$server_csr"
    
    # Generate server certificate
    openssl x509 -req -in "$server_csr" -CA "$ca_crt" -CAkey "$ca_key" -CAcreateserial -days 3650 -out "$server_crt"
    
    # Generate replication certificate
    local replication_key="$cert_dir/replication.key"
    local replication_csr="$cert_dir/replication.csr"
    local replication_crt="$cert_dir/replication.crt"
    
    # Generate replication private key
    openssl genrsa -out "$replication_key" 2048
    
    # Generate replication certificate signing request
    openssl req -new -key "$replication_key" -subj "/CN=replication" -out "$replication_csr"
    
    # Generate replication certificate
    openssl x509 -req -in "$replication_csr" -CA "$ca_crt" -CAkey "$ca_key" -CAcreateserial -days 3650 -out "$replication_crt"
    
    # Set proper permissions
    chmod 600 "$cert_dir"/*.key
    chmod 644 "$cert_dir"/*.crt
    chown -R "$PATRONI_USER:$PATRONI_USER" "$cert_dir"
    
    # Clean up CSR files
    rm -f "$cert_dir"/*.csr
    
    log_success "Patroni TLS certificates generated ✓"
}

configure_patroni() {
    log_step "Configuring Patroni..."
    
    # Get system IP address
    local system_ip=$(hostname -I | awk '{print $1}')
    local node_name="patroni-$(hostname -s | tr '[:upper:]' '[:lower:]')"
    
    # Create Patroni configuration
    cat > "$PATRONI_CONFIG_DIR/patroni.yml" <<EOF
# WebOps Patroni Configuration
# Generated by WebOps addons/patroni.sh

restapi:
  listen: $system_ip:$PATRONI_RESTAPI_PORT
  connect_address: $system_ip:$PATRONI_RESTAPI_PORT
  auth: 'username:patroni'
  tls:
    certfile: '$PATRONI_CONFIG_DIR/certs/server.crt'
    keyfile: '$PATRONI_CONFIG_DIR/certs/server.key'
    cafile: '$PATRONI_CONFIG_DIR/certs/ca.crt'

ctl:
  insecure: false
  certfile: '$PATRONI_CONFIG_DIR/certs/server.crt'
  keyfile: '$PATRONI_CONFIG_DIR/certs/server.key'
  cafile: '$PATRONI_CONFIG_DIR/certs/ca.crt'

etcd:
  hosts: '$ETCD_INITIAL_ADVERTISE_PEER_URLS'
  tls:
    certfile: '$ETCD_CERT_DIR/server.crt'
    keyfile: '$ETCD_CERT_DIR/server.key'
    cafile: '$ETCD_CERT_DIR/ca.crt'

bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 10
    maximum_lag_on_failover: 1048576
    postgresql:
      use_pg_rewind: true
      use_slots: true
      parameters:
        max_connections: 200
        max_prepared_transactions: 200
        max_locks_per_transaction: 64
        max_wal_senders: 10
        max_replication_slots: 10
        wal_level: replica
        hot_standby: "on"
        wal_keep_segments: 64
        archive_mode: "on"
        archive_command: 'cp %p ${WEBOPS_ROOT:-/webops}/backups/postgresql/wal_archive/%f'
        shared_preload_libraries: 'pg_stat_statements,auto_explain'
        logging_collector: "on"
        log_directory: '$PATRONI_LOG_DIR'
        log_filename: 'postgresql-%Y-%m-%d_%H%M%S.log'
        log_rotation_age: '1d'
        log_rotation_size: '100MB'
        log_min_duration_statement: 1000
        log_checkpoints: "on"
        log_connections: "on"
        log_disconnections: "on"
        log_lock_waits: "on"
        log_temp_files: 0
        log_autovacuum_min_duration: 0
        log_error_verbosity: default
        log_line_prefix: '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
        track_activities: "on"
        track_counts: "on"
        track_io_timing: "on"
        track_functions: pl
        track_activity_query_size: 2048
        pg_stat_statements.track: all
        auto_explain.log_min_duration: 1000
        auto_explain.log_analyze: "on"
        auto_explain.log_verbose: "on"
        auto_explain.log_format: json
        work_mem: 16MB
        maintenance_work_mem: 128MB
        effective_cache_size: 4GB
        shared_buffers: 1GB
        checkpoint_completion_target: 0.9
        wal_buffers: 16MB
        default_statistics_target: 100
        random_page_cost: 1.1
        effective_io_concurrency: 200
        
  # Bootstrap from existing data if available
  post_bootstrap: /usr/local/bin/webops-patroni-post-bootstrap

postgresql:
  listen: $system_ip:$PATRONI_POSTGRESQL_PORT
  connect_address: $system_ip:$PATRONI_POSTGRESQL_PORT
  data_dir: $PATRONI_DATA_DIR
  bin_dir: /usr/lib/postgresql/15/bin
  config_dir: $PATRONI_CONFIG_DIR
  pgpass: /tmp/.pgpass
  authentication:
    replication:
      username: replicator
      password: '$(openssl rand -base64 32)'
    superuser:
      username: postgres
      password: '$(openssl rand -base64 32)'
    rewind:
      username: rewind_user
      password: '$(openssl rand -base64 32)'
  
  # TLS configuration
  ssl:
    enabled: true
    cert_file: '$PATRONI_CONFIG_DIR/certs/server.crt'
    key_file: '$PATRONI_CONFIG_DIR/certs/server.key'
    ca_file: '$PATRONI_CONFIG_DIR/certs/ca.crt'
    
  # Create replication user
  create_replica_methods:
    - basebackup
    - pg_basebackup
  
  basebackup:
    - max_rate: '100M'
    - checkpoint: 'fast'

tags:
  nofailover: false
  noloadbalance: false
  clonefrom: false
  nosync: false

# Watchdog configuration for automatic failover
watchdog:
  mode: automatic
  device: /dev/watchdog
  safety_margin: 5

# Health check configuration
healthcheck:
  max_retries: 3
  retry_delay: 5
  timeout: 10
  http_check: "/health"
EOF
    
    # Set ownership and permissions
    chown "$PATRONI_USER:$PATRONI_USER" "$PATRONI_CONFIG_DIR/patroni.yml"
    chmod 640 "$PATRONI_CONFIG_DIR/patroni.yml"
    
    log_success "Patroni configured ✓"
}

create_patroni_systemd_service() {
    log_step "Creating Patroni systemd service..."
    
    cat > /etc/systemd/system/patroni.service <<EOF
[Unit]
Description=Patroni - a high-availability PostgreSQL
Documentation=https://patroni.readthedocs.io/en/latest/
After=network.target etcd.service
Wants=network-online.target

[Service]
Type=notify
User=$PATRONI_USER
Group=$PATRONI_USER

# Environment
Environment=PATH=/opt/patroni/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=PATRONI_NAME=patroni-$(hostname -s | tr '[:upper:]' '[:lower:]')
Environment=PATRONI_CONFIG_FILE=$PATRONI_CONFIG_DIR/patroni.yml

# ExecStart
ExecStart=/opt/patroni/bin/patroni $PATRONI_CONFIG_FILE

# Restart policy
Restart=always
RestartSec=5s

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$PATRONI_DATA_DIR $PATRONI_LOG_DIR $PATRONI_RUN_DIR

# Resource limits
LimitNOFILE=65536
LimitNPROC=32768

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable patroni
    
    log_success "Patroni systemd service created ✓"
}

configure_pgbouncer() {
    log_step "Configuring PgBouncer..."
    
    # Create PgBouncer configuration
    cat > "$PGBOUNCER_CONFIG_DIR/pgbouncer.ini" <<EOF
# WebOps PgBouncer Configuration
# Generated by WebOps addons/patroni.sh

[databases]
# Connection to Patroni cluster
* = host=localhost port=$PATRONI_POSTGRESQL_PORT

[pgbouncer]
# Connection settings
listen_addr = 0.0.0.0
listen_port = $PGBOUNCER_PORT
unix_socket_dir = /var/run/postgresql

# Authentication
auth_type = md5
auth_file = $PGBOUNCER_CONFIG_DIR/userlist.txt

# Pooling settings
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 20
min_pool_size = 5
reserve_pool_size = 5
reserve_pool_timeout = 5
max_db_connections = 50
max_user_connections = 50

# Server settings
server_reset_query = DISCARD ALL
server_check_delay = 30
server_check_query = select 1
server_lifetime = 3600
server_idle_timeout = 600

# Logging
log_connections = 1
log_disconnections = 1
log_pooler_errors = 1
log_stats = 1
stats_period = 60
verbose = 0

# Administration
admin_users = postgres
stats_users = stats, postgres

# Security
tls_ca_file = $PATRONI_CONFIG_DIR/certs/ca.crt
tls_cert_file = $PATRONI_CONFIG_DIR/certs/server.crt
tls_key_file = $PATRONI_CONFIG_DIR/certs/server.key
tls_protocols = secure
tls_ciphers = HIGH:!aNULL:!MD5

# Performance
syslog = 0
syslog_facility = daemon
syslog_ident = pgbouncer
EOF
    
    # Create user list with generated passwords
    cat > "$PGBOUNCER_CONFIG_DIR/userlist.txt" <<EOF
"postgres" "$(openssl rand -base64 32)"
"replicator" "$(openssl rand -base64 32)"
"pgbouncer" "$(openssl rand -base64 32)"
"stats" "$(openssl rand -base64 32)"
EOF
    
    # Set ownership and permissions
    chown -R "$PGBOUNCER_USER:$PGBOUNCER_USER" "$PGBOUNCER_CONFIG_DIR"
    chmod 640 "$PGBOUNCER_CONFIG_DIR/pgbouncer.ini"
    chmod 600 "$PGBOUNCER_CONFIG_DIR/userlist.txt"
    
    log_success "PgBouncer configured ✓"
}

create_pgbouncer_systemd_service() {
    log_step "Creating PgBouncer systemd service..."
    
    cat > /etc/systemd/system/pgbouncer.service <<EOF
[Unit]
Description=PgBouncer - PostgreSQL connection pooler
Documentation=https://pgbouncer.github.io/
After=network.target patroni.service
Wants=network-online.target

[Service]
Type=notify
User=$PGBOUNCER_USER
Group=$PGBOUNCER_USER

# Environment
Environment=PGBOUNCER_CONFIG_FILE=$PGBOUNCER_CONFIG_DIR/pgbouncer.ini

# ExecStart
ExecStart=/usr/sbin/pgbouncer -d $PGBOUNCER_CONFIG_DIR/pgbouncer.ini
ExecReload=/bin/kill -HUP \$MAINPID

# Restart policy
Restart=always
RestartSec=5s

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$PGBOUNCER_CONFIG_DIR /var/run/postgresql

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable pgbouncer
    
    log_success "PgBouncer systemd service created ✓"
}

create_patroni_scripts() {
    log_step "Creating Patroni helper scripts..."
    
    # Post-bootstrap script
    cat > /usr/local/bin/webops-patroni-post-bootstrap <<'EOF'
#!/bin/bash
#
# WebOps Patroni Post-Bootstrap Script
# Runs after Patroni cluster initialization
#

set -euo pipefail

# Create additional users and databases
psql -c "CREATE USER webops WITH PASSWORD '$(openssl rand -base64 32)' SUPERUSER;"
psql -c "CREATE DATABASE webops OWNER webops;"

# Create monitoring user
psql -c "CREATE USER monitoring WITH PASSWORD '$(openssl rand -base64 32)';"
psql -c "GRANT pg_monitor TO monitoring;"

# Create backup user
psql -c "CREATE USER backup WITH PASSWORD '$(openssl rand -base64 32)';"
psql -c "GRANT CONNECT ON DATABASE postgres TO backup;"

# Enable extensions
psql -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
psql -c "CREATE EXTENSION IF NOT EXISTS auto_explain;"

# Create backup directory
mkdir -p "${WEBOPS_ROOT:-/webops}/backups/postgresql/wal_archive"
chown -R postgres:postgres "${WEBOPS_ROOT:-/webops}/backups/postgresql"

logger -t webops-patroni "Patroni post-bootstrap completed"
EOF
    
    chmod +x /usr/local/bin/webops-patroni-post-bootstrap
    
    # Health check script
    cat > /usr/local/bin/webops-patroni-health <<'EOF'
#!/bin/bash
#
# WebOps Patroni Health Check Script
# Checks Patroni cluster health
#

set -euo pipefail

# Check Patroni API
if ! curl -f -s http://localhost:8008/health >/dev/null; then
    echo "Patroni API health check failed"
    exit 1
fi

# Check PostgreSQL connection
if ! pg_isready -h localhost -p 5432 -U postgres >/dev/null 2>&1; then
    echo "PostgreSQL connection check failed"
    exit 1
fi

# Check cluster status
CLUSTER_STATE=$(curl -s http://localhost:8008/cluster | jq -r '.state' 2>/dev/null || echo "unknown")

if [[ "$CLUSTER_STATE" != "running" ]]; then
    echo "Cluster state: $CLUSTER_STATE"
    exit 1
fi

echo "Patroni cluster is healthy (state: $CLUSTER_STATE)"
EOF
    
    chmod +x /usr/local/bin/webops-patroni-health
    
    # Backup script
    cat > /usr/local/bin/webops-patroni-backup <<'EOF'
#!/bin/bash
#
# WebOps Patroni Backup Script
# Creates logical and physical backups
#

set -euo pipefail

BACKUP_DIR="${WEBOPS_ROOT:-/webops}/backups/postgresql"
RETENTION_DAYS=7

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Get primary node info
PRIMARY_NODE=$(curl -s http://localhost:8008/cluster | jq -r '.leader' 2>/dev/null || echo "")

if [[ -z "$PRIMARY_NODE" || "$PRIMARY_NODE" == "null" ]]; then
    echo "No primary node found"
    exit 1
fi

# Create logical backup
BACKUP_FILE="$BACKUP_DIR/webops-backup-$(date +%Y%m%d-%H%M%S).sql"

if pg_dumpall -h localhost -U postgres -f "$BACKUP_FILE"; then
    gzip "$BACKUP_FILE"
    echo "Logical backup completed: $(basename "$BACKUP_FILE.gz")"
else
    echo "Logical backup failed"
    exit 1
fi

# Remove old backups
find "$BACKUP_DIR" -name "webops-backup-*.sql.gz" -mtime +$RETENTION_DAYS -delete

logger -t webops-patroni-backup "Patroni backup completed"
EOF
    
    chmod +x /usr/local/bin/webops-patroni-backup
    
    log_success "Patroni helper scripts created ✓"
}

setup_patroni_services() {
    log_step "Starting Patroni services..."
    
    # Start Patroni service
    systemctl start patroni
    
    # Wait for Patroni to start
    local max_attempts=30
    local attempt=1
    
    while (( attempt <= max_attempts )); do
        if curl -f -s http://localhost:8008/health >/dev/null; then
            log_success "Patroni service is running ✓"
            break
        fi
        
        log_info "Waiting for Patroni to start (attempt $attempt/$max_attempts)..."
        sleep 2
        ((attempt++))
        
        if (( attempt > max_attempts )); then
            log_error "Patroni failed to start"
            return 1
        fi
    done
    
    # Start PgBouncer service
    systemctl start pgbouncer
    
    # Wait for PgBouncer to start
    if pg_isready -h localhost -p 6432 -U postgres >/dev/null 2>&1; then
        log_success "PgBouncer service is running ✓"
    else
        log_error "PgBouncer failed to start"
        return 1
    fi
    
    # Configure backup cron job
    local backup_cron="0 2 * * * /usr/local/bin/webops-patroni-backup"
    
    if ! crontab -l 2>/dev/null | grep -q "webops-patroni-backup"; then
        (crontab -l 2>/dev/null; echo "$backup_cron") | crontab -
        log_info "Added backup cron job"
    else
        log_info "Backup cron job already exists"
    fi
    
    log_success "Patroni services setup completed ✓"
}

#=============================================================================
# Health Checks
#=============================================================================

check_patroni_health() {
    log_step "Checking Patroni health..."
    
    # Check if Patroni is running
    if ! systemctl is-active --quiet patroni; then
        log_error "Patroni service is not running"
        return 1
    fi
    
    # Check if PgBouncer is running
    if ! systemctl is-active --quiet pgbouncer; then
        log_error "PgBouncer service is not running"
        return 1
    fi
    
    # Check Patroni API health
    if ! curl -f -s http://localhost:8008/health >/dev/null; then
        log_error "Patroni API health check failed"
        return 1
    fi
    
    # Check PostgreSQL connection
    if ! pg_isready -h localhost -p 5432 -U postgres >/dev/null 2>&1; then
        log_error "PostgreSQL connection check failed"
        return 1
    fi
    
    # Check PgBouncer connection
    if ! pg_isready -h localhost -p 6432 -U postgres >/dev/null 2>&1; then
        log_error "PgBouncer connection check failed"
        return 1
    fi
    
    # Get cluster status
    local cluster_state=$(curl -s http://localhost:8008/cluster | jq -r '.state' 2>/dev/null || echo "unknown")
    local role=$(curl -s http://localhost:8008/role 2>/dev/null || echo "unknown")
    
    log_info "Cluster state: $cluster_state"
    log_info "Node role: $role"
    
    # Check disk space for data directory
    local data_usage=$(df "$PATRONI_DATA_DIR" | awk 'NR==2{print $5}' | sed 's/%//')
    if [[ $data_usage -gt 80 ]]; then
        log_warn "Patroni data directory is ${data_usage}% full"
    fi
    
    log_success "Patroni health check passed ✓"
    return 0
}

#=============================================================================
# Addon Lifecycle Management
#=============================================================================

addon_install() {
    log_info "Installing Patroni addon..."
    
    # Check dependencies
    if ! is_component_installed "etcd"; then
        log_error "etcd addon is required but not installed"
        return 1
    fi
    
    # Install packages
    install_patroni_packages
    
    # Setup user and directories
    setup_patroni_user
    
    # Generate certificates
    generate_patroni_certificates
    
    # Configure Patroni
    configure_patroni
    
    # Create systemd services
    create_patroni_systemd_service
    create_pgbouncer_systemd_service
    
    # Configure PgBouncer
    configure_pgbouncer
    
    # Create helper scripts
    create_patroni_scripts
    
    # Start services
    setup_patroni_services
    
    # Run health check
    check_patroni_health
    
    # Open firewall ports
    firewall_open_port 5432 tcp  # PostgreSQL
    firewall_open_port 6432 tcp  # PgBouncer
    firewall_open_port 8008 tcp  # Patroni API
    
    # Mark as installed
    mark_component_installed "$ADDON_NAME" "$ADDON_VERSION"
    
    log_success "Patroni addon installed successfully ✓"
}

addon_uninstall() {
    local purge="${1:-false}"
    
    log_info "Uninstalling Patroni addon..."
    
    # Stop services
    systemctl stop patroni pgbouncer || true
    systemctl disable patroni pgbouncer || true
    
    if [[ "$purge" == "true" ]]; then
        log_warn "Purging Patroni data..."
        
        # Remove virtual environment
        rm -rf /opt/patroni || true
        
        # Remove data directory
        rm -rf "$PATRONI_DATA_DIR" || true
        
        # Remove certificates
        rm -rf "$PATRONI_CONFIG_DIR/certs" || true
        
        # Remove configuration
        rm -f "$PATRONI_CONFIG_DIR/patroni.yml" || true
        rm -f "$PGBOUNCER_CONFIG_DIR/pgbouncer.ini" || true
        rm -f "$PGBOUNCER_CONFIG_DIR/userlist.txt" || true
    fi
    
    # Remove systemd services
    rm -f /etc/systemd/system/patroni.service
    rm -f /etc/systemd/system/pgbouncer.service
    systemctl daemon-reload
    
    # Remove helper scripts
    rm -f /usr/local/bin/webops-patroni-*
    
    # Close firewall ports
    firewall_close_port 5432 tcp
    firewall_close_port 6432 tcp
    firewall_close_port 8008 tcp
    
    # Remove cron jobs
    crontab -l 2>/dev/null | grep -v "webops-patroni" | crontab - || true
    
    # Mark as removed
    mark_component_removed "$ADDON_NAME"
    
    log_success "Patroni addon uninstalled ✓"
}

addon_status() {
    if is_component_installed "$ADDON_NAME"; then
        echo "Patroni addon is installed (version: $(get_component_version "$ADDON_NAME"))"
        
        if check_patroni_health >/dev/null 2>&1; then
            echo "Status: Running and healthy"
        else
            echo "Status: Running but health check failed"
        fi
        
        return 0
    else
        echo "Patroni addon is not installed"
        return 1
    fi
}

addon_version() {
    echo "$ADDON_VERSION"
}

#=============================================================================
# Script Execution
#=============================================================================

# Handle command line arguments
action="${1:-install}"

# Only execute main logic if script is called directly (not sourced)
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    # Handle command line arguments
    action="${1:-install}"
    
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
            check_patroni_health
            ;;
        *)
            log_error "Unknown action: $action"
            echo "Usage: $0 {install|uninstall [--purge]|status|version|health}"
            exit 1
            ;;
    esac
fi
