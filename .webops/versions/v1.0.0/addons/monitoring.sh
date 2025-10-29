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

# Load configuration
load_config

#=============================================================================
# Monitoring Installation
#=============================================================================

install_monitoring_packages() {
    log_step "Installing monitoring packages..."
    
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
    
    # Install Grafana
    log_info "Installing Grafana..."
    case "$OS_ID" in
        ubuntu|debian)
            # Add Grafana APT repository
            wget -q -O - https://apt.grafana.com/gpg.key | apt-key add -
            echo "deb https://apt.grafana.com stable main" > /etc/apt/sources.list.d/grafana.list
            apt-get update
            pkg_install grafana
            ;;
        rocky|almalinux)
            # Add Grafana YUM repository
            cat > /etc/yum.repos.d/grafana.repo <<EOF
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
            pkg_install grafana
            ;;
    esac
    
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
    
    # Set ownership
    chown -R "$PROMETHEUS_USER:$PROMETHEUS_USER" "$MONITORING_DIR/prometheus" "$PROMETHEUS_DATA_DIR"
    chown -R "$GRAFANA_USER:$GRAFANA_USER" "$GRAFANA_DATA_DIR"
    chown -R "$PROMETHEUS_USER:$PROMETHEUS_USER" "$MONITORING_DIR/alertmanager" "$ALERTMANAGER_DATA_DIR"
    
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
    cat > "$MONITORING_DIR/prometheus/rules/webops.yml" <<EOF
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
    chmod 640 "$MONITORING_DIR/prometheus/rules/*.yml"
    
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
        subject: '[WebOps] {{ .GroupLabels.alertname }}'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          Labels: {{ range .Labels.SortedPairs }}{{ .Name }}={{ .Value }} {{ end }}
          {{ end }}

  - name: 'critical-alerts'
    email_configs:
      - to: 'admin@webops.local'
        subject: '[CRITICAL] WebOps Alert: {{ .GroupLabels.alertname }}'
        body: |
          CRITICAL ALERT:
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          Labels: {{ range .Labels.SortedPairs }}{{ .Name }}={{ .Value }} {{ end }}
          {{ end }}

  - name: 'warning-alerts'
    email_configs:
      - to: 'admin@webops.local'
        subject: '[WARNING] WebOps Alert: {{ .GroupLabels.alertname }}'
        body: |
          WARNING ALERT:
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          Labels: {{ range .Labels.SortedPairs }}{{ .Name }}={{ .Value }} {{ end }}
          {{ end }}

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
    
    # Create Grafana configuration
    cat > /etc/grafana/grafana.ini <<EOF
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
    
    # Create provisioning directories
    ensure_directory "/etc/grafana/provisioning/datasources" "root:root" "755"
    ensure_directory "/etc/grafana/provisioning/dashboards" "root:root" "755"
    
    # Create Prometheus datasource
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
    
    # Create dashboard provisioning
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
    
    # Create dashboards directory
    ensure_directory "/var/lib/grafana/dashboards/webops" "$GRAFANA_USER:$GRAFANA_USER" "755"
    
    # Create WebOps dashboard
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
    
    # Set ownership and permissions
    chown -R "$GRAFANA_USER:$GRAFANA_USER" "$GRAFANA_DATA_DIR"
    chmod 640 /etc/grafana/grafana.ini
    
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

setup_monitoring_services() {
    log_step "Starting monitoring services..."
    
    # Start Node Exporter first
    systemctl start node-exporter
    
    # Start AlertManager
    systemctl start alertmanager
    
    # Start Prometheus
    systemctl start prometheus
    
    # Start Grafana
    systemctl start grafana-server
    
    # Wait for services to start
    local max_attempts=10
    local attempt=1
    
    # Check Prometheus
    while (( attempt <= max_attempts )); do
        if curl -f -s "http://localhost:$PROMETHEUS_PORT/-/healthy" >/dev/null; then
            log_success "Prometheus is running ✓"
            break
        fi
        
        log_info "Waiting for Prometheus to start (attempt $attempt/$max_attempts)..."
        sleep 2
        ((attempt++))
        
        if (( attempt > max_attempts )); then
            log_error "Prometheus failed to start"
            return 1
        fi
    done
    
    # Check Grafana
    attempt=1
    while (( attempt <= max_attempts )); do
        if curl -f -s "http://localhost:$GRAFANA_PORT/api/health" >/dev/null; then
            log_success "Grafana is running ✓"
            break
        fi
        
        log_info "Waiting for Grafana to start (attempt $attempt/$max_attempts)..."
        sleep 2
        ((attempt++))
        
        if (( attempt > max_attempts )); then
            log_error "Grafana failed to start"
            return 1
        fi
    done
    
    log_success "All monitoring services started ✓"
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
    
    if ! curl -f -s "http://localhost:$GRAFANA_PORT/api/health" >/dev/null; then
        log_error "Grafana health check failed"
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
    
    # Install packages
    install_monitoring_packages
    
    # Setup users and directories
    setup_monitoring_users
    
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
        *)
            log_error "Unknown action: $action"
            echo "Usage: $0 {install|uninstall [--purge]|status|version|health}"
            exit 1
            ;;
    esac
fi
