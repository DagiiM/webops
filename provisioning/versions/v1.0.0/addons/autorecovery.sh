#!/bin/bash
#
# WebOps Auto-Recovery Addon
# Implements automatic service recovery and health monitoring
#
# This addon provides:
# - Service health monitoring
# - Automatic restart on failure
# - Circuit breaker pattern for repeated failures
# - Health check endpoints
# - Recovery notifications
#

set -euo pipefail

# Source common functions
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../lib/state.sh"

# Addon configuration
ADDON_NAME="autorecovery"
ADDON_VERSION="1.0.0"
SERVICE_NAME="webops-autorecovery"

# Configuration defaults
DEFAULT_CHECK_INTERVAL=30
DEFAULT_MAX_RETRIES=3
DEFAULT_RETRY_DELAY=60
DEFAULT_CIRCUIT_BREAKER_THRESHOLD=5
DEFAULT_CIRCUIT_BREAKER_TIMEOUT=300

# Paths
AUTORECOVERY_DIR="/opt/webops/autorecovery"
CONFIG_DIR="${AUTORECOVERY_DIR}/config"
LOG_DIR="${AUTORECOVERY_DIR}/logs"
AUTORECOVERY_STATE_DIR="${AUTORECOVERY_DIR}/state"
BIN_DIR="${AUTORECOVERY_DIR}/bin"

#=============================================================================
# Addon Metadata
#=============================================================================

addon_metadata() {
    cat <<EOF
{
  "name": "${ADDON_NAME}",
  "version": "${ADDON_VERSION}",
  "description": "Automatic service recovery and health monitoring",
  "depends": ["systemd"],
  "provides": ["service-monitoring", "auto-recovery"],
  "config_schema": {
    "check_interval": {
      "type": "integer",
      "default": ${DEFAULT_CHECK_INTERVAL},
      "description": "Health check interval in seconds"
    },
    "max_retries": {
      "type": "integer", 
      "default": ${DEFAULT_MAX_RETRIES},
      "description": "Maximum restart attempts before circuit breaker"
    },
    "retry_delay": {
      "type": "integer",
      "default": ${DEFAULT_RETRY_DELAY},
      "description": "Delay between restart attempts in seconds"
    },
    "circuit_breaker_threshold": {
      "type": "integer",
      "default": ${DEFAULT_CIRCUIT_BREAKER_THRESHOLD},
      "description": "Failure count to trigger circuit breaker"
    },
    "circuit_breaker_timeout": {
      "type": "integer",
      "default": ${DEFAULT_CIRCUIT_BREAKER_TIMEOUT},
      "description": "Circuit breaker timeout in seconds"
    }
  }
}
EOF
}

addon_sla() {
    cat <<EOF
{
    "availability_target": 99.95,
    "performance_targets": {
        "response_time": 50,
        "cpu_usage": 10.0,
        "memory_usage": 50.0,
        "disk_io": 20.0,
        "network_throughput": 100.0
    },
    "recovery_objectives": {
        "rto": 60,
        "rpo": 300,
        "backup_frequency": 86400,
        "test_frequency": 604800
    },
    "support_level": "critical",
    "monitoring_requirements": {
        "health_check_interval": 30,
        "metrics_retention": 2592000,
        "alert_thresholds": {
            "service_failure_count": 3,
            "circuit_breaker_trips": 1,
            "recovery_failure_rate": 10
        }
    }
}
EOF
}

addon_security() {
    cat <<EOF
{
    "privilege_level": "system",
    "data_access": ["service_status", "system_logs", "configuration"],
    "network_access": ["localhost", "127.0.0.1", "::1"],
    "authentication": {
        "method": "system",
        "encryption": "none",
        "certificate_validation": false
    },
    "authorization": {
        "role_based_access": true,
        "least_privilege": true,
        "privilege_separation": true
    },
    "encryption": {
        "data_at_rest": false,
        "data_in_transit": false,
        "backup_encryption": false
    },
    "audit": {
        "service_management_logging": true,
        "health_check_logging": true,
        "recovery_action_logging": true,
        "configuration_changes": true,
        "access_failures": true
    },
    "vulnerability_management": {
        "security_updates": true,
        "vulnerability_scanning": false,
        "penetration_testing": false
    },
    "compliance": {
        "data_classification": "internal",
        "retention_policy": true,
        "gdpr_compliance": false
    }
}
EOF
}

#=============================================================================
# Standard Addon Interface Functions
#=============================================================================

install() {
    install_autorecovery
}

uninstall() {
    uninstall_autorecovery "$@"
}

status() {
    status_autorecovery
}

health_check() {
    if [[ -x "${BIN_DIR}/health-check" ]]; then
        "${BIN_DIR}/health-check" >/dev/null 2>&1
    else
        return 1
    fi
}

start() {
    systemctl start "${SERVICE_NAME}"
    log_info "Auto-Recovery service started"
}

stop() {
    systemctl stop "${SERVICE_NAME}"
    log_info "Auto-Recovery service stopped"
}

restart() {
    systemctl restart "${SERVICE_NAME}"
    log_info "Auto-Recovery service restarted"
}

configure() {
    log_info "Configuring Auto-Recovery addon..."
    # Configuration is handled during install
    return 0
}

validate() {
    log_info "Validating Auto-Recovery addon configuration..."
    
    # Check if directories exist
    if [[ ! -d "${AUTORECOVERY_DIR}" ]]; then
        log_error "Auto-Recovery directory missing"
        return 1
    fi
    
    # Check if configuration exists
    if [[ ! -f "${CONFIG_DIR}/autorecovery.conf" ]]; then
        log_error "Auto-Recovery configuration missing"
        return 1
    fi
    
    # Check if scripts are executable
    if [[ ! -x "${BIN_DIR}/autorecovery-daemon" ]]; then
        log_error "Auto-Recovery daemon script not executable"
        return 1
    fi
    
    log_info "Auto-Recovery addon validation passed"
    return 0
}

backup() {
    local backup_dir="${1:-/tmp/webops-backup-$(date +%Y%m%d_%H%M%S)}"
    
    log_info "Backing up Auto-Recovery addon..."
    
    mkdir -p "$backup_dir"
    
    # Backup configuration
    if [[ -d "${CONFIG_DIR}" ]]; then
        cp -r "${CONFIG_DIR}" "$backup_dir/"
    fi
    
    # Backup state
    if [[ -d "${AUTORECOVERY_STATE_DIR}" ]]; then
        cp -r "${AUTORECOVERY_STATE_DIR}" "$backup_dir/"
    fi
    
    # Backup logs
    if [[ -d "${LOG_DIR}" ]]; then
        cp -r "${LOG_DIR}" "$backup_dir/"
    fi
    
    log_info "Auto-Recovery addon backed up to: $backup_dir"
}

restore() {
    local backup_dir="$1"
    
    if [[ ! -d "$backup_dir" ]]; then
        log_error "Backup directory not found: $backup_dir"
        return 1
    fi
    
    log_info "Restoring Auto-Recovery addon from: $backup_dir"
    
    # Stop service first
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        systemctl stop "${SERVICE_NAME}"
    fi
    
    # Restore configuration
    if [[ -d "$backup_dir/config" ]]; then
        cp -r "$backup_dir/config"/* "${CONFIG_DIR}/"
    fi
    
    # Restore state
    if [[ -d "$backup_dir/state" ]]; then
        cp -r "$backup_dir/state"/* "${AUTORECOVERY_STATE_DIR}/"
    fi
    
    # Restore logs
    if [[ -d "$backup_dir/logs" ]]; then
        cp -r "$backup_dir/logs"/* "${LOG_DIR}/"
    fi
    
    # Fix ownership
    chown -R webops:webops "${AUTORECOVERY_DIR}"
    
    log_info "Auto-Recovery addon restored successfully"
}

#=============================================================================
# Installation Functions
#=============================================================================

install_autorecovery() {
    log_info "Installing WebOps Auto-Recovery addon..."
    
    # Create directories
    create_directories
    
    # Install configuration
    install_configuration
    
    # Install scripts
    install_scripts
    
    # Install systemd service
    install_systemd_service
    
    # Create monitoring configuration
    create_monitoring_config
    
    log_info "Auto-Recovery addon installed successfully"
}

create_directories() {
    log_verbose "Creating auto-recovery directories..."
    
    mkdir -p "${AUTORECOVERY_DIR}"
    mkdir -p "${CONFIG_DIR}"
    mkdir -p "${LOG_DIR}"
    mkdir -p "${AUTORECOVERY_STATE_DIR}"
    mkdir -p "${BIN_DIR}"
    
    # Set ownership
    chown -R webops:webops "${AUTORECOVERY_DIR}"
    chmod 755 "${AUTORECOVERY_DIR}"
    chmod 755 "${CONFIG_DIR}"
    chmod 755 "${LOG_DIR}"
    chmod 755 "${AUTORECOVERY_STATE_DIR}"
    chmod 755 "${BIN_DIR}"
}

install_configuration() {
    log_verbose "Installing auto-recovery configuration..."
    
    # Main configuration file
    cat > "${CONFIG_DIR}/autorecovery.conf" <<EOF
# WebOps Auto-Recovery Configuration

# Monitoring settings
CHECK_INTERVAL=${DEFAULT_CHECK_INTERVAL}
MAX_RETRIES=${DEFAULT_MAX_RETRIES}
RETRY_DELAY=${DEFAULT_RETRY_DELAY}

# Circuit breaker settings
CIRCUIT_BREAKER_THRESHOLD=${DEFAULT_CIRCUIT_BREAKER_THRESHOLD}
CIRCUIT_BREAKER_TIMEOUT=${DEFAULT_CIRCUIT_BREAKER_TIMEOUT}

# Logging
LOG_LEVEL=INFO
LOG_FILE="${LOG_DIR}/autorecovery.log"

# Notification settings
ENABLE_NOTIFICATIONS=true
NOTIFICATION_METHODS=["log", "webhook"]
WEBHOOK_URL=""
EOF

    # Service definitions
    cat > "${CONFIG_DIR}/services.yaml" <<EOF
# WebOps Services to Monitor
services:
  # Core platform services
  - name: "postgresql"
    type: "systemd"
    service: "postgresql"
    health_check:
      type: "connection"
      command: "sudo -u postgres pg_isready"
      timeout: 10
    recovery:
      action: "restart"
      max_retries: 3
      retry_delay: 30

  - name: "redis-server"
    type: "systemd"
    service: "redis-server"
    health_check:
      type: "connection"
      command: "redis-cli ping"
      timeout: 5
    recovery:
      action: "restart"
      max_retries: 3
      retry_delay: 15

  - name: "nginx"
    type: "systemd"
    service: "nginx"
    health_check:
      type: "http"
      url: "http://localhost/health"
      timeout: 5
    recovery:
      action: "restart"
      max_retries: 3
      retry_delay: 15

  # WebOps application services
  - name: "webops-web"
    type: "systemd"
    service: "webops-web"
    health_check:
      type: "http"
      url: "http://localhost:8000/health/"
      timeout: 10
    recovery:
      action: "restart"
      max_retries: 3
      retry_delay: 30

  - name: "webops-worker"
    type: "systemd"
    service: "webops-worker"
    health_check:
      type: "process"
      command: "pgrep -f 'celery.*worker'"
      timeout: 5
    recovery:
      action: "restart"
      max_retries: 3
      retry_delay: 30

  - name: "webops-beat"
    type: "systemd"
    service: "webops-beat"
    health_check:
      type: "process"
      command: "pgrep -f 'celery.*beat'"
      timeout: 5
    recovery:
      action: "restart"
      max_retries: 3
      retry_delay: 30

  # Database services (if Patroni is enabled)
  - name: "patroni"
    type: "systemd"
    service: "patroni"
    enabled: false
    health_check:
      type: "http"
      url: "http://localhost:8008/health"
      timeout: 10
    recovery:
      action: "restart"
      max_retries: 3
      retry_delay: 60

  # Monitoring services (if enabled)
  - name: "prometheus"
    type: "systemd"
    service: "prometheus"
    enabled: false
    health_check:
      type: "http"
      url: "http://localhost:9090/-/healthy"
      timeout: 10
    recovery:
      action: "restart"
      max_retries: 3
      retry_delay: 30
EOF

    chown webops:webops "${CONFIG_DIR}/autorecovery.conf"
    chown webops:webops "${CONFIG_DIR}/services.yaml"
    chmod 644 "${CONFIG_DIR}/autorecovery.conf"
    chmod 644 "${CONFIG_DIR}/services.yaml"
}

install_scripts() {
    log_verbose "Installing auto-recovery scripts..."
    
    # Main auto-recovery daemon
    cat > "${BIN_DIR}/autorecovery-daemon" <<'EOF'
#!/bin/bash
#
# WebOps Auto-Recovery Daemon
# Monitors services and performs automatic recovery
#

set -euo pipefail

# Source configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/../config"
AUTORECOVERY_STATE_DIR="${SCRIPT_DIR}/../state"
LOG_DIR="${SCRIPT_DIR}/../logs"

source "${CONFIG_DIR}/autorecovery.conf"

# Logging function
log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "${LOG_FILE}"
}

# Service health check
check_service_health() {
    local service_name="$1"
    local service_config="$2"
    
    local health_check_type=$(echo "$service_config" | yq eval '.health_check.type' -)
    local timeout=$(echo "$service_config" | yq eval '.health_check.timeout // 5' -)
    
    case "$health_check_type" in
        "connection")
            local command=$(echo "$service_config" | yq eval '.health_check.command' -)
            timeout "$timeout" bash -c "$command" >/dev/null 2>&1
            ;;
        "http")
            local url=$(echo "$service_config" | yq eval '.health_check.url' -)
            curl -f -s --max-time "$timeout" "$url" >/dev/null 2>&1
            ;;
        "process")
            local command=$(echo "$service_config" | yq eval '.health_check.command' -)
            eval "$command" >/dev/null 2>&1
            ;;
        *)
            log_message "ERROR" "Unknown health check type: $health_check_type"
            return 1
            ;;
    esac
}

# Service recovery
recover_service() {
    local service_name="$1"
    local service_config="$2"
    local retry_count="$3"
    
    local recovery_action=$(echo "$service_config" | yq eval '.recovery.action' -)
    local max_retries=$(echo "$service_config" | yq eval '.recovery.max_retries // 3' -)
    local retry_delay=$(echo "$service_config" | yq eval '.recovery.retry_delay // 30' -)
    
    if [[ $retry_count -ge $max_retries ]]; then
        log_message "ERROR" "Service $service_name exceeded max retries ($max_retries)"
        trigger_circuit_breaker "$service_name"
        return 1
    fi
    
    log_message "INFO" "Attempting to recover service $service_name (attempt $((retry_count + 1))/$max_retries)"
    
    case "$recovery_action" in
        "restart")
            local systemd_service=$(echo "$service_config" | yq eval '.service' -)
            systemctl restart "$systemd_service"
            sleep "$retry_delay"
            ;;
        "reload")
            local systemd_service=$(echo "$service_config" | yq eval '.service' -)
            systemctl reload "$systemd_service"
            sleep "$retry_delay"
            ;;
        *)
            log_message "ERROR" "Unknown recovery action: $recovery_action"
            return 1
            ;;
    esac
    
    # Verify recovery
    if check_service_health "$service_name" "$service_config"; then
        log_message "INFO" "Service $service_name recovered successfully"
        reset_failure_count "$service_name"
        return 0
    else
        log_message "WARN" "Service $service_name recovery failed"
        increment_failure_count "$service_name"
        return 1
    fi
}

# Circuit breaker functions
trigger_circuit_breaker() {
    local service_name="$1"
    local circuit_file="${AUTORECOVERY_STATE_DIR}/circuit_${service_name}"
    
    echo "$(date +%s)" > "$circuit_file"
    log_message "WARN" "Circuit breaker triggered for service $service_name"
}

is_circuit_breaker_open() {
    local service_name="$1"
    local circuit_file="${AUTORECOVERY_STATE_DIR}/circuit_${service_name}"
    
    if [[ ! -f "$circuit_file" ]]; then
        return 1
    fi
    
    local trigger_time=$(cat "$circuit_file")
    local current_time=$(date +%s)
    local elapsed=$((current_time - trigger_time))
    
    if [[ $elapsed -lt $CIRCUIT_BREAKER_TIMEOUT ]]; then
        return 0
    else
        rm -f "$circuit_file"
        return 1
    fi
}

# Failure count management
get_failure_count() {
    local service_name="$1"
    local failure_file="${AUTORECOVERY_STATE_DIR}/failures_${service_name}"
    
    if [[ -f "$failure_file" ]]; then
        cat "$failure_file"
    else
        echo "0"
    fi
}

increment_failure_count() {
    local service_name="$1"
    local failure_file="${AUTORECOVERY_STATE_DIR}/failures_${service_name}"
    local count=$(get_failure_count "$service_name")
    echo $((count + 1)) > "$failure_file"
}

reset_failure_count() {
    local service_name="$1"
    local failure_file="${AUTORECOVERY_STATE_DIR}/failures_${service_name}"
    rm -f "$failure_file"
}

# Send notification
send_notification() {
    local event="$1"
    local service="$2"
    local message="$3"
    
    if [[ "$ENABLE_NOTIFICATIONS" != "true" ]]; then
        return 0
    fi
    
    # Log notification
    log_message "NOTIFICATION" "$event: $service - $message"
    
    # Send webhook notification if configured
    if [[ -n "$WEBHOOK_URL" ]]; then
        local payload=$(cat <<EOF
{
    "event": "$event",
    "service": "$service",
    "message": "$message",
    "timestamp": "$(date -Iseconds)",
    "hostname": "$(hostname)"
}
EOF)
        curl -s -X POST -H "Content-Type: application/json" \
            -d "$payload" "$WEBHOOK_URL" >/dev/null 2>&1 || true
    fi
}

# Main monitoring loop
monitor_services() {
    log_message "INFO" "Starting service monitoring..."
    
    while true; do
        # Read service configuration
        local services=$(yq eval '.services[]' "${CONFIG_DIR}/services.yaml" -o json)
        
        echo "$services" | jq -c '.' | while read -r service_config; do
            local service_name=$(echo "$service_config" | jq -r '.name')
            local enabled=$(echo "$service_config" | jq -r '.enabled // true')
            
            # Skip disabled services
            if [[ "$enabled" != "true" ]]; then
                continue
            fi
            
            # Skip if circuit breaker is open
            if is_circuit_breaker_open "$service_name"; then
                log_message "WARN" "Circuit breaker open for $service_name, skipping"
                continue
            fi
            
            # Check service health
            if check_service_health "$service_name" "$service_config"; then
                # Service is healthy
                local failure_count=$(get_failure_count "$service_name")
                if [[ $failure_count -gt 0 ]]; then
                    log_message "INFO" "Service $service_name is now healthy"
                    send_notification "RECOVERY" "$service_name" "Service recovered after $failure_count failures"
                    reset_failure_count "$service_name"
                fi
            else
                # Service is unhealthy
                local failure_count=$(get_failure_count "$service_name")
                log_message "WARN" "Service $service_name is unhealthy (failure count: $failure_count)"
                
                # Check if we should trigger circuit breaker
                if [[ $failure_count -ge $((CIRCUIT_BREAKER_THRESHOLD - 1)) ]]; then
                    trigger_circuit_breaker "$service_name"
                    send_notification "CIRCUIT_BREAKER" "$service_name" "Circuit breaker triggered after $((failure_count + 1)) failures"
                    continue
                fi
                
                # Attempt recovery
                increment_failure_count "$service_name"
                send_notification "FAILURE" "$service_name" "Service health check failed"
                
                if ! recover_service "$service_name" "$service_config" "$failure_count"; then
                    send_notification "RECOVERY_FAILED" "$service_name" "Automatic recovery failed"
                fi
            fi
        done
        
        sleep "$CHECK_INTERVAL"
    done
}

# Signal handlers
cleanup() {
    log_message "INFO" "Shutting down auto-recovery daemon..."
    exit 0
}

trap cleanup SIGTERM SIGINT

# Start monitoring
monitor_services
EOF

    # Health check script
    cat > "${BIN_DIR}/health-check" <<'EOF'
#!/bin/bash
#
# WebOps Service Health Check
# Provides health status for all monitored services
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/../config"
AUTORECOVERY_STATE_DIR="${SCRIPT_DIR}/../state"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Service health check
check_service() {
    local service_name="$1"
    local service_config="$2"
    
    local health_check_type=$(echo "$service_config" | yq eval '.health_check.type' -)
    local timeout=$(echo "$service_config" | yq eval '.health_check.timeout // 5' -)
    
    if check_service_health "$service_name" "$service_config"; then
        echo -e "${GREEN}✓${NC} $service_name"
        return 0
    else
        echo -e "${RED}✗${NC} $service_name"
        return 1
    fi
}

# Circuit breaker status
check_circuit_breaker() {
    local service_name="$1"
    local circuit_file="${AUTORECOVERY_STATE_DIR}/circuit_${service_name}"
    
    if [[ -f "$circuit_file" ]]; then
        local trigger_time=$(cat "$circuit_file")
        local current_time=$(date +%s)
        local elapsed=$((current_time - trigger_time))
        local remaining=$((CIRCUIT_BREAKER_TIMEOUT - elapsed))
        
        if [[ $remaining -gt 0 ]]; then
            echo -e "${YELLOW}⚡${NC} $service_name (circuit breaker: ${remaining}s remaining)"
            return 2
        fi
    fi
    
    return 0
}

# Main health check
main() {
    echo "WebOps Service Health Status"
    echo "============================"
    
    local services=$(yq eval '.services[]' "${CONFIG_DIR}/services.yaml" -o json)
    local healthy_count=0
    local total_count=0
    
    echo "$services" | jq -c '.' | while read -r service_config; do
        local service_name=$(echo "$service_config" | jq -r '.name')
        local enabled=$(echo "$service_config" | jq -r '.enabled // true')
        
        if [[ "$enabled" != "true" ]]; then
            echo -e "${YELLOW}○${NC} $service_name (disabled)"
            continue
        fi
        
        total_count=$((total_count + 1))
        
        # Check circuit breaker first
        if check_circuit_breaker "$service_name"; then
            # Check service health
            if check_service "$service_name" "$service_config"; then
                healthy_count=$((healthy_count + 1))
            fi
        fi
    done
    
    echo ""
    echo "Summary: $healthy_count/$total_count services healthy"
    
    if [[ $healthy_count -eq $total_count ]]; then
        exit 0
    else
        exit 1
    fi
}

main "$@"
EOF

    # Make scripts executable
    chmod +x "${BIN_DIR}/autorecovery-daemon"
    chmod +x "${BIN_DIR}/health-check"
    
    chown -R webops:webops "${BIN_DIR}"
}

install_systemd_service() {
    log_verbose "Installing auto-recovery systemd service..."
    
    cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=WebOps Auto-Recovery Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=webops
Group=webops
ExecStart=${BIN_DIR}/autorecovery-daemon
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${AUTORECOVERY_DIR}

# Environment
Environment=CONFIG_DIR=${CONFIG_DIR}
Environment=STATE_DIR=${AUTORECOVERY_STATE_DIR}
Environment=LOG_DIR=${LOG_DIR}

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}"
}

create_monitoring_config() {
    log_verbose "Creating monitoring configuration..."
    
    # Create logrotate configuration
    cat > "/etc/logrotate.d/webops-autorecovery" <<EOF
${LOG_DIR}/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 webops webops
    postrotate
        systemctl reload ${SERVICE_NAME} || true
    endscript
}
EOF
}

#=============================================================================
# Uninstallation Functions
#=============================================================================

uninstall_autorecovery() {
    log_info "Uninstalling WebOps Auto-Recovery addon..."
    
    # Stop and disable service
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        systemctl stop "${SERVICE_NAME}"
    fi
    
    if systemctl is-enabled --quiet "${SERVICE_NAME}"; then
        systemctl disable "${SERVICE_NAME}"
    fi
    
    # Remove systemd service file
    rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload
    
    # Remove logrotate configuration
    rm -f "/etc/logrotate.d/webops-autorecovery"
    
    # Remove directories (preserve logs if requested)
    if [[ "${1:-}" != "--purge" ]]; then
        # Preserve logs and state
        if [[ -d "${LOG_DIR}" ]]; then
            mv "${LOG_DIR}" "${AUTORECOVERY_DIR}/logs.backup.$(date +%Y%m%d_%H%M%S)"
        fi
        if [[ -d "${AUTORECOVERY_STATE_DIR}" ]]; then
            mv "${AUTORECOVERY_STATE_DIR}" "${AUTORECOVERY_DIR}/state.backup.$(date +%Y%m%d_%H%M%S)"
        fi
    fi
    
    # Remove installation directory
    rm -rf "${AUTORECOVERY_DIR}"
    
    log_info "Auto-Recovery addon uninstalled successfully"
}

#=============================================================================
# Status Functions
#=============================================================================

status_autorecovery() {
    log_info "WebOps Auto-Recovery addon status:"
    
    # Service status
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        echo "✓ Auto-Recovery service is running"
    else
        echo "✗ Auto-Recovery service is not running"
    fi
    
    if systemctl is-enabled --quiet "${SERVICE_NAME}"; then
        echo "✓ Auto-Recovery service is enabled"
    else
        echo "✗ Auto-Recovery service is not enabled"
    fi
    
    # Directory status
    if [[ -d "${AUTORECOVERY_DIR}" ]]; then
        echo "✓ Auto-Recovery directory exists"
    else
        echo "✗ Auto-Recovery directory missing"
    fi
    
    # Run health check
    if [[ -x "${BIN_DIR}/health-check" ]]; then
        echo ""
        echo "Service Health Status:"
        "${BIN_DIR}/health-check" || true
    fi
}

#=============================================================================
# Main Execution
#=============================================================================

# Only execute main logic if script is called directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-install}" in
    "metadata")
        addon_metadata
        ;;
    "install")
        install_autorecovery
        ;;
    "uninstall")
        uninstall_autorecovery "${2:-}"
        ;;
    "status")
        status_autorecovery
        ;;
    "start")
        systemctl start "${SERVICE_NAME}"
        log_info "Auto-Recovery service started"
        ;;
    "stop")
        systemctl stop "${SERVICE_NAME}"
        log_info "Auto-Recovery service stopped"
        ;;
    "restart")
        systemctl restart "${SERVICE_NAME}"
        log_info "Auto-Recovery service restarted"
        ;;
    "enable")
        systemctl enable "${SERVICE_NAME}"
        log_info "Auto-Recovery service enabled"
        ;;
    "disable")
        systemctl disable "${SERVICE_NAME}"
        log_info "Auto-Recovery service disabled"
        ;;
    "health")
        if [[ -x "${BIN_DIR}/health-check" ]]; then
            "${BIN_DIR}/health-check"
        else
            log_error "Health check script not found"
            exit 1
        fi
        ;;
    *)
        echo "Usage: $0 {install|uninstall|status|start|stop|restart|enable|disable|health|metadata}"
        exit 1
        ;;
esac
fi