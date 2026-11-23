#!/bin/bash
#
# WebOps Monitoring Addon
# Installs and configures comprehensive monitoring stack
#
# This addon supports:
# - Prometheus metrics collection
# - Grafana visualization
# - Node Exporter for system metrics
# - AlertManager for notifications
# - Custom dashboards for WebOps
#

set -euo pipefail

# Addon metadata
# Only set readonly variables if they're not already set
if [[ -z "${ADDON_NAME:-}" ]]; then
    readonly ADDON_NAME="monitoring"
fi
if [[ -z "${ADDON_VERSION:-}" ]]; then
    readonly ADDON_VERSION="1.0.0"
fi
if [[ -z "${ADDON_DESCRIPTION:-}" ]]; then
    readonly ADDON_DESCRIPTION="WebOps Monitoring Stack (Prometheus + Grafana)"
fi

# Source libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
source "${SCRIPT_DIR}/../lib/os.sh"
source "${SCRIPT_DIR}/../lib/state.sh"

# Load configuration before defining fallback defaults.
load_config

# Configuration
# Only set readonly variables if they're not already set
if [[ -z "${PROMETHEUS_VERSION:-}" ]]; then
    readonly PROMETHEUS_VERSION="2.45.0"
fi
if [[ -z "${GRAFANA_VERSION:-}" ]]; then
    readonly GRAFANA_VERSION="10.0.0"
fi
if [[ -z "${NODE_EXPORTER_VERSION:-}" ]]; then
    readonly NODE_EXPORTER_VERSION="1.6.0"
fi
if [[ -z "${ALERTMANAGER_VERSION:-}" ]]; then
    readonly ALERTMANAGER_VERSION="0.25.0"
fi

# Directories
# Only set readonly variables if they're not already set
if [[ -z "${PROMETHEUS_USER:-}" ]]; then
    readonly PROMETHEUS_USER="prometheus"
fi
if [[ -z "${GRAFANA_USER:-}" ]]; then
    readonly GRAFANA_USER="grafana"
fi
if [[ -z "${MONITORING_DIR:-}" ]]; then
    readonly MONITORING_DIR="/opt/monitoring"
fi
if [[ -z "${PROMETHEUS_DATA_DIR:-}" ]]; then
    readonly PROMETHEUS_DATA_DIR="/var/lib/prometheus"
fi
if [[ -z "${GRAFANA_DATA_DIR:-}" ]]; then
    readonly GRAFANA_DATA_DIR="/var/lib/grafana"
fi
if [[ -z "${ALERTMANAGER_DATA_DIR:-}" ]]; then
    readonly ALERTMANAGER_DATA_DIR="/var/lib/alertmanager"
fi

# True only when WebOps installed Grafana for the first time in this run.
GRAFANA_FRESH_PACKAGE="${GRAFANA_FRESH_PACKAGE:-false}"

# Ports
# Only set readonly variables if they're not already set
if [[ -z "${PROMETHEUS_PORT:-}" ]]; then
    readonly PROMETHEUS_PORT="9090"
fi
if [[ -z "${GRAFANA_PORT:-}" ]]; then
    readonly GRAFANA_PORT="3000"
fi
if [[ -z "${NODE_EXPORTER_PORT:-}" ]]; then
    readonly NODE_EXPORTER_PORT="9100"
fi
if [[ -z "${ALERTMANAGER_PORT:-}" ]]; then
    readonly ALERTMANAGER_PORT="9093"
fi

#=============================================================================
# Monitoring Installation
#=============================================================================

install_monitoring_packages() {
    log_step "Installing monitoring packages..."

    # Never stop existing administrator-owned monitoring services during a
    # first WebOps installation. Existing WebOps monitoring can be restarted
    # when its recorded component ownership is established.
    if is_component_installed "$ADDON_NAME"; then
        systemctl stop prometheus node-exporter alertmanager grafana-server 2>/dev/null || true
    else
        log_info "No existing WebOps monitoring ownership; preserving shared services"
    fi
    
    # Install required packages
    pkg_install wget curl tar jq
    
    # Create monitoring directory
    ensure_directory "$MONITORING_DIR" "root:root" "755"
    
    # Download and install Prometheus
    log_info "Installing Prometheus v${PROMETHEUS_VERSION}..."
    cd /tmp
    wget -q "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz"
    tar xzf "prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz"
    cd "prometheus-${PROMETHEUS_VERSION}.linux-amd64"
    
    # Install Prometheus binaries
    cp prometheus promtool /usr/local/bin/
    chmod +x /usr/local/bin/prometheus /usr/local/bin/promtool
    
    # Create Prometheus directories
    ensure_directory "$PROMETHEUS_DATA_DIR" "$PROMETHEUS_USER:$PROMETHEUS_USER" "755"
    ensure_directory "$MONITORING_DIR/prometheus" "$PROMETHEUS_USER:$PROMETHEUS_USER" "755"
    
    # Copy Prometheus configuration templates
    cp -r consoles console_libraries "$MONITORING_DIR/prometheus/"
    
    # Clean up
    cd /tmp
    rm -rf "prometheus-${PROMETHEUS_VERSION}.linux-amd64"*
    
    # Download and install Node Exporter
    log_info "Installing Node Exporter v${NODE_EXPORTER_VERSION}..."
    wget -q "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz"
    tar xzf "node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz"
    cd "node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64"
    
    # Install Node Exporter binary
    cp node_exporter /usr/local/bin/
    chmod +x /usr/local/bin/node_exporter
    
    # Clean up
    cd /tmp
    rm -rf "node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64"*
    
    # Download and install AlertManager
    log_info "Installing AlertManager v${ALERTMANAGER_VERSION}..."
    wget -q "https://github.com/prometheus/alertmanager/releases/download/v${ALERTMANAGER_VERSION}/alertmanager-${ALERTMANAGER_VERSION}.linux-amd64.tar.gz"
    tar xzf "alertmanager-${ALERTMANAGER_VERSION}.linux-amd64.tar.gz"
    cd "alertmanager-${ALERTMANAGER_VERSION}.linux-amd64"
    
    # Install AlertManager binaries
    cp alertmanager amtool /usr/local/bin/
    chmod +x /usr/local/bin/alertmanager /usr/local/bin/amtool
    
    # Create AlertManager directories
    ensure_directory "$ALERTMANAGER_DATA_DIR" "$PROMETHEUS_USER:$PROMETHEUS_USER" "755"
    ensure_directory "$MONITORING_DIR/alertmanager" "$PROMETHEUS_USER:$PROMETHEUS_USER" "755"
    
    # Clean up
    cd /tmp
    rm -rf "alertmanager-${ALERTMANAGER_VERSION}.linux-amd64"*
    
    # Install Grafana without trusting a remote APT key system-wide.
    # Reusing a previously installed Grafana never rewrites its repository.
    log_info "Checking Grafana package..."
    if command -v grafana-server >/dev/null 2>&1; then
        log_info "Existing Grafana installation detected; preserving package"
    else
        GRAFANA_FRESH_PACKAGE=true
        case "$OS_ID" in
            ubuntu|debian)
                pkg_install ca-certificates gnupg
                install -d -m 755 /etc/apt/keyrings
                if [[ ! -s /etc/apt/keyrings/grafana.asc ]]; then
                    local key_tmp
                    key_tmp="$(mktemp /etc/apt/keyrings/.grafana-key.XXXXXX)"
                    if ! curl --fail --location --silent --show-error --retry 3 \
                        --max-time 60 https://apt.grafana.com/gpg-full.key -o "$key_tmp"; then
                        rm -f "$key_tmp"
                        log_error "Could not download the Grafana signing key"
                        return 1
                    fi
                    chmod 644 "$key_tmp"
                    mv "$key_tmp" /etc/apt/keyrings/grafana.asc
                fi
                local apt_repo
                apt_repo="deb [signed-by=/etc/apt/keyrings/grafana.asc] https://apt.grafana.com stable main"
                if [[ -s /etc/apt/sources.list.d/grafana.list ]] &&
                   ! grep -Fxq "$apt_repo" /etc/apt/sources.list.d/grafana.list; then
                    # The older WebOps installer used the legacy unsigned line.
                    # Back it up; refuse any other administrator-managed source.
                    if grep -Fxq 'deb https://apt.grafana.com stable main' /etc/apt/sources.list.d/grafana.list &&
                       [[ "$(wc -l </etc/apt/sources.list.d/grafana.list)" -eq 1 ]]; then
                        cp -p /etc/apt/sources.list.d/grafana.list \
                            /etc/apt/sources.list.d/grafana.list.webops-legacy-backup
                    else
                        log_error "Existing Grafana APT source differs from the WebOps-managed repository"
                        log_error "Refusing to overwrite administrator-managed APT sources"
                        return 1
                    fi
                fi
                printf '%s\n' "$apt_repo" > /etc/apt/sources.list.d/grafana.list
                apt-get update
                pkg_install grafana
                ;;
            rocky|almalinux)
                if [[ ! -e /etc/yum.repos.d/grafana.repo ]]; then
                    cat > /etc/yum.repos.d/grafana.repo <<'EOF'
[grafana]
name=grafana
baseurl=https://rpm.grafana.com
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://rpm.grafana.com/gpg.key
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
EOF
                fi
                pkg_install grafana
                ;;
            *)
                log_error "Grafana package installation unsupported on $OS_ID"
                return 1
                ;;
        esac
    fi

    # Create Grafana directories
    ensure_directory "$GRAFANA_DATA_DIR" "$GRAFANA_USER:$GRAFANA_USER" "755"
    
    # Verify installations
    if command -v prometheus &>/dev/null; then
        log_success "Prometheus installed ✓"
    else
        log_error "Prometheus installation failed"
        return 1
    fi
    
    if command -v node_exporter &>/dev/null; then
        log_success "Node Exporter installed ✓"
    else
        log_error "Node Exporter installation failed"
        return 1
    fi
    
    if command -v alertmanager &>/dev/null; then
        log_success "AlertManager installed ✓"
    else
        log_error "AlertManager installation failed"
        return 1
    fi
    
    if command -v grafana-server &>/dev/null; then
        log_success "Grafana installed ✓"
    else
        log_error "Grafana installation failed"
        return 1
    fi
}

setup_monitoring_users() {
    log_step "Setting up monitoring users..."
    
    # Create Prometheus user
    if ! id "$PROMETHEUS_USER" &>/dev/null; then
        useradd -r -s /bin/false -d "$PROMETHEUS_DATA_DIR" "$PROMETHEUS_USER"
        log_info "Created Prometheus user: $PROMETHEUS_USER"
    else
        log_info "Prometheus user $PROMETHEUS_USER already exists"
    fi
    
    # Create Grafana user
    if ! id "$GRAFANA_USER" &>/dev/null; then
        useradd -r -s /bin/false -d "$GRAFANA_DATA_DIR" "$GRAFANA_USER"
        log_info "Created Grafana user: $GRAFANA_USER"
    else
        log_info "Grafana user $GRAFANA_USER already exists"
    fi

    # Ensure required directories exist before ownership adjustments.
    ensure_directory "$MONITORING_DIR" "root:root" "755"
    ensure_directory "$MONITORING_DIR/prometheus" "$PROMETHEUS_USER:$PROMETHEUS_USER" "755"
    ensure_directory "$PROMETHEUS_DATA_DIR" "$PROMETHEUS_USER:$PROMETHEUS_USER" "755"
    ensure_directory "$MONITORING_DIR/alertmanager" "$PROMETHEUS_USER:$PROMETHEUS_USER" "755"
    ensure_directory "$ALERTMANAGER_DATA_DIR" "$PROMETHEUS_USER:$PROMETHEUS_USER" "755"
    ensure_directory "$GRAFANA_DATA_DIR" "$GRAFANA_USER:$GRAFANA_USER" "755"

    log_success "Monitoring users setup completed ✓"
}

configure_prometheus() {
    log_step "Configuring Prometheus..."
    
    # Create Prometheus configuration
    cat > "$MONITORING_DIR/prometheus/prometheus.yml" <<EOF
# WebOps Prometheus Configuration
# Generated by WebOps addons/monitoring.sh

global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'webops'
    replica: 'prometheus-1'

# AlertManager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - localhost:$ALERTMANAGER_PORT

# Load rules
rule_files:
  - "$MONITORING_DIR/prometheus/rules/*.yml"

# Scrape configurations
scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:$PROMETHEUS_PORT']
    scrape_interval: 5s
    metrics_path: /metrics

  # Node Exporter - system metrics
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:$NODE_EXPORTER_PORT']
    scrape_interval: 10s

  # WebOps Control Panel
  - job_name: 'webops-control-panel'
    static_configs:
      - targets: ['localhost:8009']
    metrics_path: /metrics
    scrape_interval: 15s

  # PostgreSQL (if installed)
  - job_name: 'postgresql'
    static_configs:
      - targets: ['localhost:9187']
    scrape_interval: 15s

  # etcd (if installed)
  - job_name: 'etcd'
    static_configs:
      - targets: ['localhost:2379']
    metrics_path: /metrics
    scrape_interval: 15s

  # Patroni (if installed)
  - job_name: 'patroni'
    static_configs:
      - targets: ['localhost:8008']
    metrics_path: /metrics
    scrape_interval: 15s

  # Nginx (if installed)
  - job_name: 'nginx'
    static_configs:
      - targets: ['localhost:9113']
    scrape_interval: 15s

  # Redis (if installed)
  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']
    scrape_interval: 15s

# Remote write configuration (optional)
# remote_write:
#   - url: "http://remote-storage:9090/api/v1/write"
EOF
    
    # Create rules directory
    ensure_directory "$MONITORING_DIR/prometheus/rules" "$PROMETHEUS_USER:$PROMETHEUS_USER" "755"
    
    # Create alerting rules
    cat > "$MONITORING_DIR/prometheus/rules/webops.yml" <<'EOF'
# WebOps Alerting Rules
# Generated by WebOps addons/monitoring.sh

groups:
  - name: webops.rules
    rules:
      # System alerts
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage on {{ $labels.instance }}"
          description: "CPU usage is above 80% for more than 5 minutes"

      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage on {{ $labels.instance }}"
          description: "Memory usage is above 85% for more than 5 minutes"

      - alert: DiskSpaceLow
        expr: (1 - (node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes{fstype!="tmpfs"})) * 100 > 90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Low disk space on {{ $labels.instance }}"
          description: "Disk usage is above 90% on {{ $labels.mountpoint }}"

      # Service alerts
      - alert: PrometheusDown
        expr: up{job="prometheus"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Prometheus is down"
          description: "Prometheus has been down for more than 1 minute"

      - alert: GrafanaDown
        expr: up{job="grafana"} == 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Grafana is down"
          description: "Grafana has been down for more than 1 minute"

      - alert: NodeExporterDown
        expr: up{job="node-exporter"} == 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Node Exporter is down"
          description: "Node Exporter has been down for more than 1 minute"

      # WebOps specific alerts
      - alert: WebOpsControlPanelDown
        expr: up{job="webops-control-panel"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "WebOps Control Panel is down"
          description: "WebOps Control Panel has been down for more than 2 minutes"

      - alert: PostgreSQLDown
        expr: up{job="postgresql"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL is down"
          description: "PostgreSQL has been down for more than 1 minute"

      - alert: etcdDown
        expr: up{job="etcd"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "etcd is down"
          description: "etcd has been down for more than 1 minute"
EOF
    
    # Set ownership and permissions
    chown -R "$PROMETHEUS_USER:$PROMETHEUS_USER" "$MONITORING_DIR/prometheus"
    chmod 640 "$MONITORING_DIR/prometheus/prometheus.yml"
    find "$MONITORING_DIR/prometheus/rules" -maxdepth 1 -type f -name "*.yml" -exec chmod 640 {} +
    
    log_success "Prometheus configured ✓"
}

configure_alertmanager() {
    log_step "Configuring AlertManager..."
    
    # Create AlertManager configuration
    cat > "$MONITORING_DIR/alertmanager/alertmanager.yml" <<EOF
# WebOps AlertManager Configuration
# Generated by WebOps addons/monitoring.sh

global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@webops.local'
  smtp_require_tls: false

# Route configuration
route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'webops-notifications'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
      group_wait: 5s
      repeat_interval: 30m
    - match:
        severity: warning
      receiver: 'warning-alerts'
      group_wait: 10s
      repeat_interval: 1h

# Receivers
receivers:
  - name: 'webops-notifications'
    email_configs:
      - to: 'admin@webops.local'

  - name: 'critical-alerts'
    email_configs:
      - to: 'admin@webops.local'

  - name: 'warning-alerts'
    email_configs:
      - to: 'admin@webops.local'

# Inhibit rules
inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
EOF
    
    # Set ownership and permissions
    chown -R "$PROMETHEUS_USER:$PROMETHEUS_USER" "$MONITORING_DIR/alertmanager"
    chmod 640 "$MONITORING_DIR/alertmanager/alertmanager.yml"
    
    log_success "AlertManager configured ✓"
}

configure_grafana() {
    log_step "Configuring Grafana..."
    
    # Never regenerate Grafana admin credentials on retry or replace
    # configuration owned by another administrator/application.
    local grafana_ini="/etc/grafana/grafana.ini"
    local managed_grafana_config=false
    if [[ -s "$grafana_ini" ]] &&
       grep -Fqx '# WebOps Grafana Configuration' "$grafana_ini"; then
        managed_grafana_config=true
        log_info "Existing WebOps Grafana config detected; preserving credentials"
    elif [[ -s "$grafana_ini" && "$GRAFANA_FRESH_PACKAGE" != "true" ]]; then
        log_warn "Preserving pre-existing Grafana configuration and credentials"
        log_warn "Verify its configured port matches WebOps GRAFANA_PORT=$GRAFANA_PORT"
    else
        if [[ -e "$grafana_ini" ]]; then
            local grafana_backup="${grafana_ini}.webops-package-original"
            if [[ ! -e "$grafana_backup" ]]; then
                cp -p "$grafana_ini" "$grafana_backup"
            fi
        fi
        # Only the freshly installed Grafana package receives WebOps defaults.
        # Keep the config readable by the grafana service group, not world.
        umask 027
        cat > "$grafana_ini" <<EOF
# WebOps Grafana Configuration
# Generated by WebOps addons/monitoring.sh

[server]
protocol = http
http_addr = 0.0.0.0
http_port = $GRAFANA_PORT
domain = localhost
root_url = http://localhost:$GRAFANA_PORT/

[database]
type = sqlite3
path = $GRAFANA_DATA_DIR/grafana.db

[security]
admin_user = admin
admin_password = $(openssl rand -base64 16)
secret_key = $(openssl rand -hex 32)

[users]
allow_sign_up = false
auto_assign_org_role = Viewer

[auth.anonymous]
enabled = false

[smtp]
enabled = false

[log]
mode = file
level = info
file = $GRAFANA_DATA_DIR/grafana.log

[paths]
data = $GRAFANA_DATA_DIR
logs = $GRAFANA_DATA_DIR/logs
plugins = $GRAFANA_DATA_DIR/plugins
provisioning = /etc/grafana/provisioning

[api]
enable_api = true
EOF
        chown "root:$GRAFANA_USER" "$grafana_ini"
        chmod 640 "$grafana_ini"
        managed_grafana_config=true
    fi

    # Create provisioning directories
    ensure_directory "/etc/grafana/provisioning/datasources" "root:root" "755"
    ensure_directory "/etc/grafana/provisioning/dashboards" "root:root" "755"
    
    # Do not overwrite another application's Grafana datasource.
    if [[ ! -e /etc/grafana/provisioning/datasources/prometheus.yml ]] ||
       grep -Fqx '# WebOps Grafana Datasources' /etc/grafana/provisioning/datasources/prometheus.yml; then
        cat > /etc/grafana/provisioning/datasources/prometheus.yml <<EOF
# WebOps Grafana Datasources
# Generated by WebOps addons/monitoring.sh

apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://localhost:$PROMETHEUS_PORT
    isDefault: true
    editable: true
EOF
    else
        log_warn "Existing Prometheus datasource is not WebOps-managed; preserving it"
    fi

    # Keep a user-edited dashboard provisioning file intact.
    if [[ ! -e /etc/grafana/provisioning/dashboards/webops.yml ]] ||
       grep -Fqx '# WebOps Grafana Dashboards' /etc/grafana/provisioning/dashboards/webops.yml; then
        cat > /etc/grafana/provisioning/dashboards/webops.yml <<EOF
# WebOps Grafana Dashboards
# Generated by WebOps addons/monitoring.sh

apiVersion: 1

providers:
  - name: 'webops-dashboards'
    orgId: 1
    folder: 'WebOps'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
EOF
    else
        log_warn "Existing dashboards provisioning file is not WebOps-managed; preserving it"
    fi

    # Create dashboards directory
    ensure_directory "/var/lib/grafana/dashboards/webops" "$GRAFANA_USER:$GRAFANA_USER" "755"
    
    # A user-customized overview dashboard must never be overwritten on retry.
    if [[ ! -e /var/lib/grafana/dashboards/webops/overview.json ]]; then
        cat > /var/lib/grafana/dashboards/webops/overview.json <<EOF
{
  "dashboard": {
    "id": null,
    "title": "WebOps Overview",
    "tags": ["webops"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "System CPU Usage",
        "type": "stat",
        "targets": [
          {
            "expr": "100 - (avg by(instance) (irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
            "legendFormat": "{{instance}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "thresholds": {
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 70},
                {"color": "red", "value": 90}
              ]
            }
          }
        },
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
      },
      {
        "id": 2,
        "title": "System Memory Usage",
        "type": "stat",
        "targets": [
          {
            "expr": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
            "legendFormat": "{{instance}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "thresholds": {
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 75},
                {"color": "red", "value": 90}
              ]
            }
          }
        },
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
      },
      {
        "id": 3,
        "title": "Disk Usage",
        "type": "stat",
        "targets": [
          {
            "expr": "(1 - (node_filesystem_avail_bytes{fstype!=\"tmpfs\"} / node_filesystem_size_bytes{fstype!=\"tmpfs\"})) * 100",
            "legendFormat": "{{instance}}: {{mountpoint}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "thresholds": {
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 80},
                {"color": "red", "value": 95}
              ]
            }
          }
        },
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 8}
      },
      {
        "id": 4,
        "title": "Service Status",
        "type": "table",
        "targets": [
          {
            "expr": "up",
            "legendFormat": "{{job}} - {{instance}}"
          }
        ],
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 16}
      }
    ],
    "time": {"from": "now-1h", "to": "now"},
    "refresh": "5s"
  }
}
EOF
    else
        log_info "Existing WebOps dashboard preserved"
    fi

    # Limit permission changes to the WebOps-owned data directory.
    # Do not alter administrator-managed Grafana configuration permissions.
    chown -R "$GRAFANA_USER:$GRAFANA_USER" "$GRAFANA_DATA_DIR"
    if [[ "$managed_grafana_config" == "true" ]]; then
        chown "root:$GRAFANA_USER" "$grafana_ini"
        chmod 640 "$grafana_ini"
    fi
    
    log_success "Grafana configured ✓"
}

create_monitoring_systemd_services() {
    log_step "Creating monitoring systemd services..."
    
    # Create Prometheus service
    cat > /etc/systemd/system/prometheus.service <<EOF
[Unit]
Description=Prometheus
Documentation=https://prometheus.io/docs/introduction/overview/
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$PROMETHEUS_USER
Group=$PROMETHEUS_USER

# ExecStart
ExecStart=/usr/local/bin/prometheus \\
    --config.file=$MONITORING_DIR/prometheus/prometheus.yml \\
    --storage.tsdb.path=$PROMETHEUS_DATA_DIR \\
    --web.console.libraries=$MONITORING_DIR/prometheus/console_libraries \\
    --web.console.templates=$MONITORING_DIR/prometheus/consoles \\
    --storage.tsdb.retention.time=30d \\
    --web.enable-lifecycle \\
    --web.enable-admin-api

# Restart policy
Restart=always
RestartSec=5s

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$PROMETHEUS_DATA_DIR $MONITORING_DIR/prometheus

[Install]
WantedBy=multi-user.target
EOF
    
    # Create Node Exporter service
    cat > /etc/systemd/system/node-exporter.service <<EOF
[Unit]
Description=Node Exporter
Documentation=https://github.com/prometheus/node_exporter
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$PROMETHEUS_USER
Group=$PROMETHEUS_USER

# ExecStart
ExecStart=/usr/local/bin/node_exporter \\
    --collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)

# Restart policy
Restart=always
RestartSec=5s

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF
    
    # Create AlertManager service
    cat > /etc/systemd/system/alertmanager.service <<EOF
[Unit]
Description=AlertManager
Documentation=https://prometheus.io/docs/alerting/alertmanager/
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$PROMETHEUS_USER
Group=$PROMETHEUS_USER

# ExecStart
ExecStart=/usr/local/bin/alertmanager \\
    --config.file=$MONITORING_DIR/alertmanager/alertmanager.yml \\
    --storage.path=$ALERTMANAGER_DATA_DIR \\
    --cluster.listen-address= \\
    --web.external-url=http://localhost:$ALERTMANAGER_PORT

# Restart policy
Restart=always
RestartSec=5s

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$ALERTMANAGER_DATA_DIR $MONITORING_DIR/alertmanager

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd and enable services
    systemctl daemon-reload
    systemctl enable prometheus node-exporter alertmanager grafana-server
    
    log_success "Monitoring systemd services created ✓"
}

grafana_health_ready() {
    local body
    # Bypass proxy environment variables, enforce short timeouts and require
    # Grafana's own database health instead of accepting any HTTP 200 response.
    body="$(curl --silent --show-error --fail --noproxy '*' \
        --connect-timeout 2 --max-time 5 \
        "http://127.0.0.1:$GRAFANA_PORT/api/health" 2>/dev/null)" || return 1
    if command -v jq >/dev/null 2>&1; then
        printf '%s\n' "$body" | jq -e '.database == "ok"' >/dev/null 2>&1
    else
        printf '%s\n' "$body" | grep -Eq '"database"[[:space:]]*:[[:space:]]*"ok"'
    fi
}

report_grafana_startup_failure() {
    local dir="${WEBOPS_MONITORING_LOG_DIR:-/var/log/webops}"
    local report=""
    log_error "Grafana is not healthy at 127.0.0.1:$GRAFANA_PORT/api/health"
    if systemctl is-failed --quiet grafana-server 2>/dev/null; then
        log_error "grafana-server.service entered FAILED state"
    elif systemctl is-active --quiet grafana-server 2>/dev/null; then
        log_error "Grafana service is active but HTTP/database health is not ready"
    else
        log_error "Grafana service is not active"
    fi

    # Capture raw journals in a root-only file, not the general install log.
    # Journals may contain private information; operators should redact first.
    if [[ ! -d "$dir" ]]; then
        install -d -m 700 "$dir" 2>/dev/null || true
    fi
    if [[ -d "$dir" ]]; then
        report="$dir/grafana-startup-$(date +%Y%m%d-%H%M%S)-$$.log"
        (
            umask 077
            {
                printf 'WebOps Grafana startup diagnostics (private)\n'
                date -u
                printf '\nGrafana systemd status:\n'
                systemctl status grafana-server --no-pager --full --lines=35 || true
                printf '\nGrafana journal (recent):\n'
                journalctl -u grafana-server -b -n 80 --no-pager || true
                printf '\nGrafana application log (recent):\n'
                if [[ -r /var/log/grafana/grafana.log ]]; then
                    tail -n 60 /var/log/grafana/grafana.log
                elif [[ -r "$GRAFANA_DATA_DIR/grafana.log" ]]; then
                    tail -n 60 "$GRAFANA_DATA_DIR/grafana.log"
                fi
                printf '\nListeners and filesystem state:\n'
                ss -lntp 2>/dev/null | grep -E ":$GRAFANA_PORT[[:space:]]" || true
                df -h "$GRAFANA_DATA_DIR" /etc/grafana 2>/dev/null || true
                stat -c '%U:%G %a %n' \
                    /etc/grafana/grafana.ini "$GRAFANA_DATA_DIR" \
                    /var/log/grafana 2>/dev/null || true
            } > "$report" 2>&1
        ) || true
        if [[ -f "$report" ]]; then
            chmod 600 "$report" 2>/dev/null || true
            log_error "Detailed Grafana diagnostics: $report"
            log_warn "Report may contain private information; redact before sharing"
        fi
    fi
    log_error "Inspect: systemctl status grafana-server --no-pager -l"
    log_error "Inspect: journalctl -u grafana-server -b -n 100 --no-pager"
}

diagnose_monitoring_readonly() {
    log_step "Checking monitoring service status without modifying configuration"
    local service failures=0
    for service in prometheus node-exporter alertmanager grafana-server; do
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            log_success "$service is active"
        else
            log_warn "$service is not active"
            failures=$((failures + 1))
        fi
    done
    if grafana_health_ready; then
        log_success "Grafana HTTP/database health is good"
    else
        log_error "Grafana HTTP/database health failed on port $GRAFANA_PORT"
        failures=$((failures + 1))
    fi
    if ((failures > 0)); then
        log_error "$failures monitoring checks did not pass"
        return 1
    fi
}

repair_grafana_only() {
    log_step "Safely repairing Grafana service readiness (no package reinstall)"
    if grafana_health_ready; then
        log_success "Grafana already healthy; no changes necessary"
        return 0
    fi
    if ! command -v systemctl >/dev/null 2>&1; then
        log_error "systemctl unavailable; cannot start Grafana in this environment"
        return 1
    fi
    if ! systemctl start grafana-server; then
        log_error "grafana-server could not be started"
        report_grafana_startup_failure
        return 1
    fi
    local max_attempts="${MONITORING_GRAFANA_MAX_ATTEMPTS:-40}"
    local poll_seconds="${MONITORING_GRAFANA_POLL_SECONDS:-3}"
    if ! [[ "$max_attempts" =~ ^[0-9]+$ ]] ||
       ((max_attempts < 1 || max_attempts > 60)) ||
       ! [[ "$poll_seconds" =~ ^[0-9]+$ ]] ||
       ((poll_seconds > 10)); then
        log_error "Invalid Grafana readiness retry settings"
        return 1
    fi
    local attempt
    for ((attempt=1; attempt<=max_attempts; attempt++)); do
        if grafana_health_ready; then
            log_success "Grafana recovered; no other services or data were changed"
            return 0
        fi
        if systemctl is-failed --quiet grafana-server 2>/dev/null; then
            break
        fi
        if ((attempt < max_attempts)); then
            sleep "$poll_seconds"
        fi
    done
    report_grafana_startup_failure
    return 1
}

setup_monitoring_services() {
    log_step "Starting monitoring services..."

    local service
    for service in node-exporter alertmanager prometheus grafana-server; do
        if ! systemctl start "$service"; then
            log_error "Could not start systemd service: $service"
            if [[ "$service" == "grafana-server" ]]; then
                report_grafana_startup_failure
            else
                systemctl status "$service" --no-pager --lines=25 || true
            fi
            return 1
        fi
    done

    local attempt
    for ((attempt=1; attempt<=10; attempt++)); do
        if curl --silent --fail --noproxy '*' --connect-timeout 2 --max-time 4 \
            "http://127.0.0.1:$PROMETHEUS_PORT/-/healthy" >/dev/null 2>&1; then
            log_success "Prometheus is running ✓"
            break
        fi
        if ((attempt == 10)); then
            log_error "Prometheus did not become healthy after 10 attempts"
            return 1
        fi
        sleep 2
    done

    # Grafana database migrations can require more than the old 20-second window.
    local max_attempts="${MONITORING_GRAFANA_MAX_ATTEMPTS:-40}"
    local poll_seconds="${MONITORING_GRAFANA_POLL_SECONDS:-3}"
    if ! [[ "$max_attempts" =~ ^[0-9]+$ ]] ||
       ((max_attempts < 1 || max_attempts > 60)); then
        log_error "MONITORING_GRAFANA_MAX_ATTEMPTS must be 1-60"
        return 1
    fi
    if ! [[ "$poll_seconds" =~ ^[0-9]+$ ]] ||
       ((poll_seconds > 10)); then
        log_error "MONITORING_GRAFANA_POLL_SECONDS must be 0-10"
        return 1
    fi

    for ((attempt=1; attempt<=max_attempts; attempt++)); do
        if grafana_health_ready; then
            log_success "Grafana HTTP and database health verified ✓"
            log_success "All monitoring services started ✓"
            return 0
        fi
        if systemctl is-failed --quiet grafana-server 2>/dev/null; then
            log_error "Grafana entered failed state during startup"
            report_grafana_startup_failure
            return 1
        fi
        log_info "Waiting for Grafana readiness ($attempt/$max_attempts)..."
        if ((attempt < max_attempts)); then
            sleep "$poll_seconds"
        fi
    done

    log_error "Grafana did not become healthy after $max_attempts checks"
    report_grafana_startup_failure
    return 1
}

#=============================================================================
# Health Checks
#=============================================================================

check_monitoring_health() {
    log_step "Checking monitoring health..."
    
    # Check if services are running
    if ! systemctl is-active --quiet prometheus; then
        log_error "Prometheus service is not running"
        return 1
    fi
    
    if ! systemctl is-active --quiet node-exporter; then
        log_error "Node Exporter service is not running"
        return 1
    fi
    
    if ! systemctl is-active --quiet alertmanager; then
        log_error "AlertManager service is not running"
        return 1
    fi
    
    if ! systemctl is-active --quiet grafana-server; then
        log_error "Grafana service is not running"
        return 1
    fi
    
    # Check service endpoints
    if ! curl -f -s "http://localhost:$PROMETHEUS_PORT/-/healthy" >/dev/null; then
        log_error "Prometheus health check failed"
        return 1
    fi
    
    if ! curl -f -s "http://localhost:$NODE_EXPORTER_PORT/metrics" >/dev/null; then
        log_error "Node Exporter health check failed"
        return 1
    fi
    
    if ! curl -f -s "http://localhost:$ALERTMANAGER_PORT/-/healthy" >/dev/null; then
        log_error "AlertManager health check failed"
        return 1
    fi
    
    if ! grafana_health_ready; then
        log_error "Grafana health check failed (HTTP endpoint or database)"
        report_grafana_startup_failure
        return 1
    fi
    
    # Check Prometheus targets
    local targets_up=$(curl -s "http://localhost:$PROMETHEUS_PORT/api/v1/targets" | jq -r '.data.activeTargets[] | select(.health=="up") | .labels.job' | wc -l)
    local targets_total=$(curl -s "http://localhost:$PROMETHEUS_PORT/api/v1/targets" | jq -r '.data.activeTargets[] | .labels.job' | wc -l)
    
    log_info "Prometheus targets: $targets_up/$targets_total up"
    
    # Check disk space for monitoring data
    local prometheus_usage=$(df "$PROMETHEUS_DATA_DIR" | awk 'NR==2{print $5}' | sed 's/%//')
    if [[ $prometheus_usage -gt 80 ]]; then
        log_warn "Prometheus data directory is ${prometheus_usage}% full"
    fi
    
    log_success "Monitoring health check passed ✓"
    return 0
}

#=============================================================================
# Addon Lifecycle Management
#=============================================================================

addon_install() {
    log_info "Installing monitoring addon..."

    # Setup users first so package install can assign ownership safely.
    setup_monitoring_users

    # Install packages
    install_monitoring_packages
    
    # Configure components
    configure_prometheus
    configure_alertmanager
    configure_grafana
    
    # Create systemd services
    create_monitoring_systemd_services
    
    # Start services
    setup_monitoring_services
    
    # Run health check
    check_monitoring_health
    
    # Open firewall ports
    firewall_open_port "$PROMETHEUS_PORT" tcp  # Prometheus
    firewall_open_port "$GRAFANA_PORT" tcp    # Grafana
    firewall_open_port "$NODE_EXPORTER_PORT" tcp  # Node Exporter
    firewall_open_port "$ALERTMANAGER_PORT" tcp   # AlertManager
    
    # Mark as installed
    mark_component_installed "$ADDON_NAME" "$ADDON_VERSION"
    
    log_success "Monitoring addon installed successfully ✓"
    log_info "Access Grafana at: http://localhost:$GRAFANA_PORT"
    log_info "Access Prometheus at: http://localhost:$PROMETHEUS_PORT"
}

addon_uninstall() {
    local purge="${1:-false}"
    
    log_info "Uninstalling monitoring addon..."
    
    # Stop services
    systemctl stop prometheus node-exporter alertmanager grafana-server || true
    systemctl disable prometheus node-exporter alertmanager grafana-server || true
    
    if [[ "$purge" == "true" ]]; then
        log_warn "Purging monitoring data..."
        
        # Remove binaries
        rm -f /usr/local/bin/prometheus /usr/local/bin/promtool
        rm -f /usr/local/bin/node_exporter
        rm -f /usr/local/bin/alertmanager /usr/local/bin/amtool
        
        # Remove data directories
        rm -rf "$PROMETHEUS_DATA_DIR" "$GRAFANA_DATA_DIR" "$ALERTMANAGER_DATA_DIR"
        
        # Remove configuration
        rm -rf "$MONITORING_DIR"
        rm -f /etc/grafana/grafana.ini
        rm -rf /etc/grafana/provisioning
    fi
    
    # Remove systemd services
    rm -f /etc/systemd/system/prometheus.service
    rm -f /etc/systemd/system/node-exporter.service
    rm -f /etc/systemd/system/alertmanager.service
    systemctl daemon-reload
    
    # Close firewall ports
    firewall_close_port "$PROMETHEUS_PORT" tcp
    firewall_close_port "$GRAFANA_PORT" tcp
    firewall_close_port "$NODE_EXPORTER_PORT" tcp
    firewall_close_port "$ALERTMANAGER_PORT" tcp
    
    # Mark as removed
    mark_component_removed "$ADDON_NAME"
    
    log_success "Monitoring addon uninstalled ✓"
}

addon_status() {
    if is_component_installed "$ADDON_NAME"; then
        echo "Monitoring addon is installed (version: $(get_component_version "$ADDON_NAME"))"
        
        if check_monitoring_health >/dev/null 2>&1; then
            echo "Status: Running and healthy"
        else
            echo "Status: Running but health check failed"
        fi
        
        return 0
    else
        echo "Monitoring addon is not installed"
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
    "category": "monitoring",
    "depends": ["base", "firewall"],
    "provides": ["monitoring", "metrics", "visualization", "alerting"],
    "conflicts": [],
    "system_requirements": {
        "min_memory_mb": 2048,
        "min_disk_gb": 20,
        "min_cpu_cores": 2,
        "required_ports": [$PROMETHEUS_PORT, $GRAFANA_PORT, $NODE_EXPORTER_PORT, $ALERTMANAGER_PORT]
    },
    "maintainer": "WebOps Team",
    "license": "Apache-2.0",
    "documentation_url": "https://webops.dev/docs/addons/monitoring",
    "support_url": "https://webops.dev/support",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-10-29T09:45:00Z"
}
EOF
}

addon_sla() {
    cat <<EOF
{
    "availability_target": 99.9,
    "performance_targets": {
        "response_time": 200,
        "cpu_usage": 40.0,
        "memory_usage": 70.0,
        "disk_io": 60.0,
        "network_throughput": 1000.0
    },
    "recovery_objectives": {
        "rto": 300,
        "rpo": 900,
        "backup_frequency": 86400,
        "test_frequency": 604800
    },
    "support_level": "critical",
    "monitoring_requirements": {
        "health_check_interval": 60,
        "metrics_retention": 2592000,
        "alert_thresholds": {
            "prometheus_targets_down": 2,
            "disk_usage": 85,
            "memory_usage": 90,
            "cpu_usage": 95
        }
    }
}
EOF
}

addon_security() {
    cat <<EOF
{
    "privilege_level": "service",
    "data_access": ["system_metrics", "service_metrics", "configuration"],
    "network_access": ["localhost", "127.0.0.1", "::1"],
    "authentication": {
        "method": "basic",
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
        "metrics_collection_logging": true,
        "configuration_changes": true,
        "alert_notifications": true,
        "access_failures": false
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

addon_health_check() {
    check_monitoring_health
}

addon_start() {
    log_step "Starting monitoring services..."
    systemctl start node-exporter
    systemctl start alertmanager
    systemctl start prometheus
    systemctl start grafana-server
    sleep 10
    check_monitoring_health
}

addon_stop() {
    log_step "Stopping monitoring services..."
    systemctl stop grafana-server
    systemctl stop prometheus
    systemctl stop alertmanager
    systemctl stop node-exporter
}

addon_restart() {
    log_step "Restarting monitoring services..."
    systemctl restart node-exporter
    systemctl restart alertmanager
    systemctl restart prometheus
    systemctl restart grafana-server
    sleep 10
    check_monitoring_health
}

addon_configure() {
    configure_prometheus
    configure_alertmanager
    configure_grafana
}

addon_validate() {
    log_step "Validating monitoring configuration..."
    
    # Check Prometheus configuration
    if [[ ! -f "$MONITORING_DIR/prometheus/prometheus.yml" ]]; then
        log_error "Prometheus configuration file not found"
        return 1
    fi
    
    # Check Grafana configuration
    if [[ ! -f "/etc/grafana/grafana.ini" ]]; then
        log_error "Grafana configuration file not found"
        return 1
    fi
    
    # Check AlertManager configuration
    if [[ ! -f "$MONITORING_DIR/alertmanager/alertmanager.yml" ]]; then
        log_error "AlertManager configuration file not found"
        return 1
    fi
    
    # Validate Prometheus configuration syntax
    if ! /usr/local/bin/promtool check config "$MONITORING_DIR/prometheus/prometheus.yml" >/dev/null 2>&1; then
        log_error "Prometheus configuration validation failed"
        return 1
    fi
    
    # Validate AlertManager configuration syntax
    if ! /usr/local/bin/amtool config routes test "$MONITORING_DIR/alertmanager/alertmanager.yml" >/dev/null 2>&1; then
        log_error "AlertManager configuration validation failed"
        return 1
    fi
    
    log_success "Monitoring configuration validation passed ✓"
    return 0
}

addon_backup() {
    log_step "Creating monitoring backup..."
    
    local backup_dir="${WEBOPS_ROOT:-/webops}/backups/monitoring"
    local backup_file="$backup_dir/monitoring-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
    
    ensure_directory "$backup_dir" "root:root" "700"
    
    # Create backup of configurations and data
    tar czf "$backup_file" \
        "$MONITORING_DIR" \
        "$PROMETHEUS_DATA_DIR" \
        "$GRAFANA_DATA_DIR" \
        "$ALERTMANAGER_DATA_DIR" \
        /etc/grafana/ 2>/dev/null || true
    
    if [[ -f "$backup_file" ]]; then
        log_success "Monitoring backup created: $backup_file"
        return 0
    else
        log_error "Monitoring backup failed"
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
    
    log_step "Restoring monitoring from backup: $backup_file"
    
    # Stop services
    addon_stop
    
    # Extract backup
    if tar xzf "$backup_file" -C /; then
        log_success "Monitoring restore completed"
        
        # Set proper ownership
        chown -R "$PROMETHEUS_USER:$PROMETHEUS_USER" "$MONITORING_DIR" "$PROMETHEUS_DATA_DIR" "$ALERTMANAGER_DATA_DIR"
        chown -R "$GRAFANA_USER:$GRAFANA_USER" "$GRAFANA_DATA_DIR"
        
        # Start services
        addon_start
        return 0
    else
        log_error "Monitoring restore failed"
        return 1
    fi
}

#=============================================================================
# Script Execution
#=============================================================================

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
            check_monitoring_health
            ;;
        doctor)
            diagnose_monitoring_readonly
            ;;
        repair)
            repair_grafana_only
            ;;
        *)
            log_error "Unknown action: $action"
            echo "Usage: $0 {install|uninstall [--purge]|status|version|health|doctor|repair}"
            exit 1
            ;;
    esac
fi
