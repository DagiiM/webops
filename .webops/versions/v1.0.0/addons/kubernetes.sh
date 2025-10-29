#!/bin/bash
#
# WebOps Kubernetes Addon
# Installs and configures Kubernetes cluster
#
# This addon supports:
# - Single-node Kubernetes setup
# - Container runtime (containerd)
# - kubelet, kubeadm, kubectl
# - CNI plugin (Flannel)
# - Basic cluster networking
#

set -euo pipefail

# Addon metadata
if [[ -z "${ADDON_NAME:-}" ]]; then
    readonly ADDON_NAME="kubernetes"
fi
if [[ -z "${ADDON_VERSION:-}" ]]; then
    readonly ADDON_VERSION="1.28.0"
fi
if [[ -z "${ADDON_DESCRIPTION:-}" ]]; then
    readonly ADDON_DESCRIPTION="Kubernetes Container Orchestration"
fi

# Source libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
source "${SCRIPT_DIR}/../lib/os.sh"
source "${SCRIPT_DIR}/../lib/state.sh"
source "${SCRIPT_DIR}/../lib/addon-contract.sh"

# Configuration
if [[ -z "${KUBERNETES_VERSION:-}" ]]; then
    readonly KUBERNETES_VERSION="${KUBERNETES_VERSION:-1.28.0}"
fi
if [[ -z "${CONTAINERD_VERSION:-}" ]]; then
    readonly CONTAINERD_VERSION="${CONTAINERD_VERSION:-1.7.0}"
fi
if [[ -z "${POD_NETWORK_CIDR:-}" ]]; then
    readonly POD_NETWORK_CIDR="${POD_NETWORK_CIDR:-10.244.0.0/16}"
fi
if [[ -z "${SERVICE_SUBNET:-}" ]]; then
    readonly SERVICE_SUBNET="${SERVICE_SUBNET:-10.96.0.0/12}"
fi

# Load configuration
load_config

#=============================================================================
# Addon Contract Functions
#=============================================================================

addon_metadata() {
    cat <<EOF
{
    "name": "$ADDON_NAME",
    "version": "$ADDON_VERSION",
    "description": "$ADDON_DESCRIPTION",
    "category": "orchestration",
    "depends": ["containerd"],
    "provides": ["kubernetes", "kubectl", "kubeadm", "kubelet"],
    "conflicts": ["docker"],
    "system_requirements": {
        "min_memory_mb": 4096,
        "min_disk_gb": 20,
        "min_cpu_cores": 2,
        "required_ports": [6443, 10250, 10251, 10252, "30000-32767"]
    },
    "maintainer": "WebOps Team",
    "license": "Apache-2.0",
    "documentation_url": "https://webops.dev/docs/addons/kubernetes",
    "support_url": "https://webops.dev/support",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-10-29T09:42:00Z"
}
EOF
}

addon_sla() {
    cat <<EOF
{
    "availability_target": "99.9",
    "performance_targets": {
        "api_response_time_ms": "200",
        "pod_startup_time_seconds": "30",
        "node_ready_time_seconds": "60"
    },
    "recovery_objectives": {
        "rto": "30",
        "rpo": "15",
        "backup_frequency": "daily",
        "backup_retention_days": "30"
    },
    "monitoring_requirements": {
        "metrics_collection_interval": "30",
        "health_check_interval": "10",
        "alert_response_time": "300"
    },
    "scalability_targets": {
        "max_nodes_per_cluster": "100",
        "max_pods_per_node": "110",
        "max_services_per_cluster": "1000"
    },
    "maintenance_requirements": {
        "scheduled_maintenance_window": "monthly",
        "maintenance_notification_hours": "48",
        "emergency_maintenance": "true"
    },
    "security_requirements": {
        "encryption_at_rest": "true",
        "encryption_in_transit": "true",
        "authentication_method": "certificate",
        "access_control": "rbac"
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
        "NET_ADMIN",
        "DAC_OVERRIDE",
        "SETUID",
        "SETGID"
    ],
    "system_user": "root",
    "data_access": {
        "type": "cluster",
        "locations": [
            "/etc/kubernetes",
            "/var/lib/kubelet",
            "/var/lib/etcd",
            "/var/lib/containerd"
        ],
        "encryption": true,
        "backup_retention_days": 30
    },
    "network_access": {
        "required_ports": [6443, 10250, 10251, 10252, "30000-32767"],
        "protocols": ["https", "http"],
        "encryption_required": true
    },
    "authentication": {
        "method": "certificate",
        "certificate_locations": [
            "/etc/kubernetes/pki/ca.crt",
            "/etc/kubernetes/pki/apiserver.crt",
            "/etc/kubernetes/pki/apiserver.key"
        ],
        "ca_certificate": "/etc/kubernetes/pki/ca.crt"
    },
    "audit_logging": {
        "enabled": true,
        "log_level": "info",
        "log_retention_days": 90,
        "audit_events": [
            "pod_creation",
            "service_creation",
            "rbac_changes",
            "node_operations",
            "api_access"
        ]
    },
    "vulnerability_scanning": {
        "enabled": true,
        "scan_frequency": "weekly",
        "auto_patch_security": true
    },
    "compliance": {
        "standards": ["SOC2", "GDPR", "PCI-DSS"],
        "data_classification": "confidential",
        "pii_handling": false
    }
}
EOF
}

addon_health_check() {
    local detailed="${1:-false}"
    
    # Check if kubelet is running
    if ! systemctl is-active --quiet kubelet; then
        echo "CRITICAL: kubelet service is not running"
        return 2
    fi
    
    # Check if containerd is running
    if ! systemctl is-active --quiet containerd; then
        echo "CRITICAL: containerd service is not running"
        return 2
    fi
    
    # Check if cluster is accessible
    if ! kubectl cluster-info &>/dev/null; then
        echo "CRITICAL: Kubernetes API server is not accessible"
        return 2
    fi
    
    # Check node status
    local node_status=$(kubectl get nodes -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | tr ' ' '\n' | grep -c true || echo "0")
    local total_nodes=$(kubectl get nodes --no-headers | wc -l)
    
    if [[ $node_status -ne $total_nodes ]]; then
        echo "WARNING: Not all nodes are ready ($node_status/$total_nodes)"
        return 1
    fi
    
    # Check system pods
    local system_pods=$(kubectl get pods -n kube-system -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | tr ' ' '\n' | grep -c true || echo "0")
    local total_system_pods=$(kubectl get pods -n kube-system --no-headers | wc -l)
    
    if [[ $system_pods -lt $((total_system_pods - 2)) ]]; then
        echo "WARNING: Some system pods may not be ready ($system_pods/$total_system_pods)"
        return 1
    fi
    
    if [[ "$detailed" == "true" ]]; then
        echo "Kubernetes cluster is healthy"
        echo "Nodes ready: $node_status/$total_nodes"
        echo "System pods ready: $system_pods/$total_system_pods"
        
        # Get cluster version
        local k8s_version=$(kubectl version --short | grep 'Server Version' | awk '{print $3}')
        echo "Kubernetes version: $k8s_version"
        
        # Get pod counts by namespace
        echo "Pod counts by namespace:"
        kubectl get pods --all-namespaces --no-headers | awk '{print $1}' | sort | uniq -c
        
        # Get resource usage
        echo "Node resource usage:"
        kubectl top nodes 2>/dev/null || echo "Metrics server not available"
    fi
    
    echo "OK: Kubernetes cluster is healthy"
    return 0
}

addon_start() {
    log_info "Starting Kubernetes services..."
    
    # Start containerd
    systemctl start containerd
    
    # Wait for containerd to start
    if ! systemctl is-active --quiet containerd; then
        log_error "containerd failed to start"
        return 1
    fi
    
    # Start kubelet
    systemctl start kubelet
    
    # Wait for kubelet to start
    local max_attempts=30
    local attempt=1
    
    while (( attempt <= max_attempts )); do
        if systemctl is-active --quiet kubelet; then
            log_success "kubelet service started ✓"
            break
        fi
        
        log_info "Waiting for kubelet to start (attempt $attempt/$max_attempts)..."
        sleep 2
        ((attempt++))
        
        if (( attempt > max_attempts )); then
            log_error "kubelet failed to start"
            return 1
        fi
    done
    
    # Wait for API server to be ready
    local max_attempts=60
    local attempt=1
    
    while (( attempt <= max_attempts )); do
        if kubectl cluster-info &>/dev/null; then
            log_success "Kubernetes API server is ready ✓"
            break
        fi
        
        log_info "Waiting for API server to be ready (attempt $attempt/$max_attempts)..."
        sleep 5
        ((attempt++))
        
        if (( attempt > max_attempts )); then
            log_warn "API server may not be fully ready"
        fi
    done
    
    return 0
}

addon_stop() {
    log_info "Stopping Kubernetes services..."
    
    # Stop kubelet
    systemctl stop kubelet || true
    
    # Stop containerd
    systemctl stop containerd || true
    
    log_success "Kubernetes services stopped ✓"
    return 0
}

addon_restart() {
    log_info "Restarting Kubernetes services..."
    
    # Restart kubelet
    systemctl restart kubelet
    
    # Wait for kubelet to start
    local max_attempts=30
    local attempt=1
    
    while (( attempt <= max_attempts )); do
        if systemctl is-active --quiet kubelet; then
            log_success "kubelet service restarted ✓"
            break
        fi
        
        log_info "Waiting for kubelet to restart (attempt $attempt/$max_attempts)..."
        sleep 2
        ((attempt++))
        
        if (( attempt > max_attempts )); then
            log_error "kubelet failed to restart"
            return 1
        fi
    done
    
    # Restart containerd
    systemctl restart containerd
    
    # Wait for API server to be ready
    local max_attempts=60
    local attempt=1
    
    while (( attempt <= max_attempts )); do
        if kubectl cluster-info &>/dev/null; then
            log_success "Kubernetes API server is ready ✓"
            break
        fi
        
        log_info "Waiting for API server to be ready (attempt $attempt/$max_attempts)..."
        sleep 5
        ((attempt++))
        
        if (( attempt > max_attempts )); then
            log_warn "API server may not be fully ready"
        fi
    done
    
    return 0
}

addon_configure() {
    local config_file="${1:-}"
    
    if [[ -n "$config_file" && -f "$config_file" ]]; then
        log_info "Applying Kubernetes configuration from $config_file..."
        
        # Apply configuration
        kubectl apply -f "$config_file"
        
        log_success "Kubernetes configuration applied ✓"
    else
        log_info "Reconfiguring Kubernetes with current settings..."
        
        # Reapply cluster configuration if needed
        if [[ ! -f /etc/kubernetes/admin.conf ]]; then
            initialize_kubernetes_cluster
        fi
        
        log_success "Kubernetes reconfigured ✓"
    fi
    
    return 0
}

addon_validate() {
    log_info "Validating Kubernetes installation..."
    
    local errors=0
    
    # Check if kubectl is installed
    if ! command -v kubectl &>/dev/null; then
        log_error "kubectl is not installed"
        ((errors++))
    fi
    
    # Check if kubeadm is installed
    if ! command -v kubeadm &>/dev/null; then
        log_error "kubeadm is not installed"
        ((errors++))
    fi
    
    # Check if kubelet is installed
    if ! command -v kubelet &>/dev/null; then
        log_error "kubelet is not installed"
        ((errors++))
    fi
    
    # Check if containerd is installed
    if ! command -v containerd &>/dev/null; then
        log_error "containerd is not installed"
        ((errors++))
    fi
    
    # Check configuration files
    if [[ ! -f /etc/containerd/config.toml ]]; then
        log_error "containerd configuration file not found"
        ((errors++))
    fi
    
    if [[ ! -f /etc/kubernetes/admin.conf ]]; then
        log_error "Kubernetes admin configuration not found"
        ((errors++))
    fi
    
    # Check systemd services
    if ! systemctl list-unit-files | grep -q "kubelet.service"; then
        log_error "kubelet systemd service not found"
        ((errors++))
    fi
    
    if ! systemctl list-unit-files | grep -q "containerd.service"; then
        log_error "containerd systemd service not found"
        ((errors++))
    fi
    
    # Validate cluster configuration
    if command -v kubeadm &>/dev/null; then
        if ! kubeadm init phase preflight --ignore-preflight-errors=all &>/dev/null; then
            log_error "Kubernetes preflight validation failed"
            ((errors++))
        fi
    fi
    
    if [[ $errors -eq 0 ]]; then
        log_success "Kubernetes validation passed ✓"
        return 0
    else
        log_error "Kubernetes validation failed with $errors errors"
        return 1
    fi
}

addon_backup() {
    local backup_dir="${1:-${WEBOPS_ROOT:-/webops}/backups/kubernetes}"
    local backup_type="${2:-full}"
    
    log_info "Creating Kubernetes backup ($backup_type)..."
    
    # Create backup directory
    mkdir -p "$backup_dir"
    
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$backup_dir/kubernetes-backup-$timestamp"
    
    case "$backup_type" in
        "full")
            # Backup etcd data
            if command -v etcdctl &>/dev/null && [[ -d /var/lib/etcd ]]; then
                ETCDCTL_API=3 etcdctl snapshot save "$backup_file-etcd.db" \
                    --endpoints=https://127.0.0.1:2379 \
                    --cacert=/etc/kubernetes/pki/etcd/ca.crt \
                    --cert=/etc/kubernetes/pki/etcd/server.crt \
                    --key=/etc/kubernetes/pki/etcd/server.key
                log_success "etcd backup completed: $(basename "$backup_file-etcd.db")"
            fi
            
            # Backup cluster resources
            kubectl get all --all-namespaces -o yaml > "$backup_file-resources.yaml"
            gzip "$backup_file-resources.yaml"
            log_success "Cluster resources backup completed: $(basename "$backup_file-resources.yaml.gz")"
            ;;
        "config")
            # Backup configuration files
            tar -czf "$backup_file-config.tar.gz" \
                /etc/kubernetes \
                /etc/containerd \
                /var/lib/kubelet \
                $HOME/.kube/config
            log_success "Configuration backup completed: $(basename "$backup_file-config.tar.gz")"
            ;;
        "etcd")
            # Backup etcd only
            if command -v etcdctl &>/dev/null && [[ -d /var/lib/etcd ]]; then
                ETCDCTL_API=3 etcdctl snapshot save "$backup_file-etcd.db" \
                    --endpoints=https://127.0.0.1:2379 \
                    --cacert=/etc/kubernetes/pki/etcd/ca.crt \
                    --cert=/etc/kubernetes/pki/etcd/server.crt \
                    --key=/etc/kubernetes/pki/etcd/server.key
                log_success "etcd backup completed: $(basename "$backup_file-etcd.db")"
            fi
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
    
    log_info "Restoring Kubernetes from backup: $(basename "$backup_file")"
    
    # Stop services
    addon_stop
    
    case "$backup_file" in
        *-etcd.db)
            # Restore etcd data
            if command -v etcdctl &>/dev/null; then
                # Move current etcd data
                mv /var/lib/etcd /var/lib/etcd.backup.$(date +%Y%m%d_%H%M%S)
                mkdir -p /var/lib/etcd
                
                # Restore etcd snapshot
                ETCDCTL_API=3 etcdctl snapshot restore "$backup_file" \
                    --data-dir /var/lib/etcd \
                    --endpoints=https://127.0.0.1:2379 \
                    --cacert=/etc/kubernetes/pki/etcd/ca.crt \
                    --cert=/etc/kubernetes/pki/etcd/server.crt \
                    --key=/etc/kubernetes/pki/etcd/server.key
                
                # Fix permissions
                chown -R etcd:etcd /var/lib/etcd
                
                log_success "etcd data restored ✓"
            fi
            ;;
        *-config.tar.gz)
            # Restore configuration
            tar -xzf "$backup_file" -C /
            systemctl daemon-reload
            log_success "Configuration restored ✓"
            ;;
        *-resources.yaml.gz)
            # Restore cluster resources
            gunzip -c "$backup_file" | kubectl apply -f -
            log_success "Cluster resources restored ✓"
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
# Kubernetes Installation
#=============================================================================

install_kubernetes_packages() {
    log_step "Installing Kubernetes packages..."
    
    # Disable swap
    swapoff -a
    sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
    
    # Install required packages
    pkg_install apt-transport-https ca-certificates curl gnupg
    
    # Add Kubernetes apt repository
    case "$OS_ID" in
        ubuntu|debian)
            # Add Kubernetes GPG key
            curl -fsSL https://pkgs.k8s.io/core:/stable:/v${KUBERNETES_VERSION%.*}/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
            
            # Add Kubernetes repository
            echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v${KUBERNETES_VERSION%.*}/deb/ /" > /etc/apt/sources.list.d/kubernetes.list
            
            # Update package list
            apt-get update
            
            # Install Kubernetes packages
            apt-get install -y kubelet="${KUBERNETES_VERSION}-1.1" kubeadm="${KUBERNETES_VERSION}-1.1" kubectl="${KUBERNETES_VERSION}-1.1"
            
            # Hold packages to prevent upgrades
            apt-mark hold kubelet kubeadm kubectl
            ;;
        rocky|almalinux)
            # Add Kubernetes YUM repository
            cat > /etc/yum.repos.d/kubernetes.repo <<EOF
[kubernetes]
name=Kubernetes
baseurl=https://pkgs.k8s.io/core:/stable:/v${KUBERNETES_VERSION%.*}/rpm/
enabled=1
gpgcheck=1
gpgkey=https://pkgs.k8s.io/core:/stable:/v${KUBERNETES_VERSION%.*}/rpm/repodata/repomd.xml.key
exclude=kubelet kubeadm kubectl cri-tools kubernetes-cni
EOF
            
            # Install Kubernetes packages
            yum install -y kubelet-${KUBERNETES_VERSION} kubeadm-${KUBERNETES_VERSION} kubectl-${KUBERNETES_VERSION} --disableexcludes=kubernetes
            
            # Enable kubelet service
            systemctl enable --now kubelet
            ;;
    esac
    
    # Verify installation
    if command -v kubeadm &>/dev/null; then
        local installed_version=$(kubeadm version | grep -oP 'GitVersion:"v\K[^"]+' || echo "unknown")
        log_success "Kubernetes installed: $installed_version ✓"
    else
        log_error "Kubernetes installation failed"
        return 1
    fi
}

install_containerd() {
    log_step "Installing containerd..."
    
    # Install containerd
    case "$OS_ID" in
        ubuntu|debian)
            apt-get install -y containerd.io
            ;;
        rocky|almalinux)
            yum install -y containerd.io
            ;;
    esac
    
    # Create containerd configuration directory
    ensure_directory "/etc/containerd" "root:root" "755"
    
    # Generate default containerd configuration
    containerd config default > /etc/containerd/config.toml
    
    # Update containerd configuration to use systemd cgroup
    sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
    
    # Enable and restart containerd
    systemctl enable containerd
    systemctl restart containerd
    
    # Verify containerd is running
    if systemctl is-active --quiet containerd; then
        log_success "containerd is running ✓"
    else
        log_error "containerd failed to start"
        return 1
    fi
}

configure_kernel_modules() {
    log_step "Configuring kernel modules..."
    
    # Load required kernel modules
    cat > /etc/modules-load.d/k8s.conf <<EOF
overlay
br_netfilter
EOF
    
    # Load modules immediately
    modprobe overlay
    modprobe br_netfilter
    
    # Configure sysctl settings
    cat > /etc/sysctl.d/k8s.conf <<EOF
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
    
    # Apply sysctl settings
    sysctl --system
    
    log_success "Kernel modules configured ✓"
}

initialize_kubernetes_cluster() {
    log_step "Initializing Kubernetes cluster..."
    
    # Get system IP address
    local system_ip=$(hostname -I | awk '{print $1}')
    
    # Initialize Kubernetes cluster
    kubeadm init \
        --pod-network-cidr="$POD_NETWORK_CIDR" \
        --service-cidr="$SERVICE_SUBNET" \
        --apiserver-advertise-address="$system_ip" \
        --ignore-preflight-errors=all
    
    # Configure kubectl for regular user
    ensure_directory "$HOME/.kube" "root:root" "700"
    cp -i /etc/kubernetes/admin.conf "$HOME/.kube/config"
    chown "$(id -u):$(id -g)" "$HOME/.kube/config"
    
    # Configure kubectl for webops user if exists
    if id "webops" &>/dev/null; then
        ensure_directory "/home/webops/.kube" "webops:webops" "700"
        cp -i /etc/kubernetes/admin.conf "/home/webops/.kube/config"
        chown webops:webops "/home/webops/.kube/config"
    fi
    
    log_success "Kubernetes cluster initialized ✓"
}

install_cni_plugin() {
    log_step "Installing CNI plugin (Flannel)..."
    
    # Wait for API server to be ready
    local max_attempts=30
    local attempt=1
    
    while (( attempt <= max_attempts )); do
        if kubectl cluster-info &>/dev/null; then
            break
        fi
        
        log_info "Waiting for Kubernetes API server (attempt $attempt/$max_attempts)..."
        sleep 2
        ((attempt++))
    done
    
    # Install Flannel CNI
    kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml
    
    # Wait for Flannel pods to be ready
    local max_attempts=30
    local attempt=1
    
    while (( attempt <= max_attempts )); do
        local ready_pods=$(kubectl get pods -n kube-flannel -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | tr ' ' '\n' | grep -c true || echo "0")
        local total_pods=$(kubectl get pods -n kube-flannel --no-headers | wc -l)
        
        if [[ $ready_pods -eq $total_pods && $total_pods -gt 0 ]]; then
            log_success "Flannel CNI is ready ✓"
            break
        fi
        
        log_info "Waiting for Flannel pods to be ready (attempt $attempt/$max_attempts)..."
        sleep 5
        ((attempt++))
        
        if (( attempt > max_attempts )); then
            log_warn "Flannel CNI may not be fully ready"
        fi
    done
}

untaint_master_node() {
    log_step "Removing taint from master node..."
    
    # Allow pods to be scheduled on master node (single-node setup)
    kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true
    kubectl taint nodes --all node-role.kubernetes.io/master- || true
    
    log_success "Master node untainted ✓"
}

create_kubernetes_scripts() {
    log_step "Creating Kubernetes helper scripts..."
    
    # Cluster status script
    cat > /usr/local/bin/webops-k8s-status <<'EOF'
#!/bin/bash
#
# WebOps Kubernetes Status Script
# Shows cluster status and information
#

set -euo pipefail

echo "=== Kubernetes Cluster Status ==="
kubectl cluster-info
echo ""

echo "=== Nodes ==="
kubectl get nodes -o wide
echo ""

echo "=== System Pods ==="
kubectl get pods -n kube-system
echo ""

echo "=== All Pods ==="
kubectl get pods --all-namespaces
echo ""

echo "=== Services ==="
kubectl get services --all-namespaces
echo ""

echo "=== Storage Classes ==="
kubectl get storageclass
echo ""
EOF
    
    # Join script generator
    cat > /usr/local/bin/webops-k8s-join <<'EOF'
#!/bin/bash
#
# WebOps Kubernetes Join Script Generator
# Generates join command for worker nodes
#

set -euo pipefail

echo "=== Kubernetes Join Command ==="
kubeadm token create --print-join-command
echo ""

echo "=== Discovery Token CA Cert Hash ==="
openssl x509 -pubkey -in /etc/kubernetes/pki/ca.crt | openssl rsa -pubin -outform der 2>/dev/null | openssl dgst -sha256 -hex | sed 's/^.* //'
EOF
    
    # Reset script
    cat > /usr/local/bin/webops-k8s-reset <<'EOF'
#!/bin/bash
#
# WebOps Kubernetes Reset Script
# Resets the Kubernetes cluster
#

set -euo pipefail

echo "WARNING: This will reset the entire Kubernetes cluster!"
read -p "Are you sure? (yes/no): " confirm

if [[ "$confirm" != "yes" ]]; then
    echo "Operation cancelled"
    exit 1
fi

echo "Resetting Kubernetes cluster..."
kubeadm reset -f

# Clean up iptables rules
iptables -F && iptables -t nat -F && iptables -t mangle -F && iptables -X

# Clean up CNI
rm -rf /etc/cni/net.d

# Clean up kubeconfig
rm -f $HOME/.kube/config
if id "webops" &>/dev/null; then
    rm -f /home/webops/.kube/config
fi

echo "Kubernetes cluster reset complete"
EOF
    
    # Make scripts executable
    chmod +x /usr/local/bin/webops-k8s-*
    
    log_success "Kubernetes helper scripts created ✓"
}

#=============================================================================
# Health Checks
#=============================================================================

check_kubernetes_health() {
    log_step "Checking Kubernetes health..."
    
    # Check if kubelet is running
    if ! systemctl is-active --quiet kubelet; then
        log_error "kubelet service is not running"
        return 1
    fi
    
    # Check if containerd is running
    if ! systemctl is-active --quiet containerd; then
        log_error "containerd service is not running"
        return 1
    fi
    
    # Check if cluster is accessible
    if ! kubectl cluster-info &>/dev/null; then
        log_error "Kubernetes API server is not accessible"
        return 1
    fi
    
    # Check node status
    local node_status=$(kubectl get nodes -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | tr ' ' '\n' | grep -c true || echo "0")
    local total_nodes=$(kubectl get nodes --no-headers | wc -l)
    
    if [[ $node_status -ne $total_nodes ]]; then
        log_error "Not all nodes are ready ($node_status/$total_nodes)"
        return 1
    fi
    
    # Check system pods
    local system_pods=$(kubectl get pods -n kube-system -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | tr ' ' '\n' | grep -c true || echo "0")
    local total_system_pods=$(kubectl get pods -n kube-system --no-headers | wc -l)
    
    if [[ $system_pods -lt $((total_system_pods - 1)) ]]; then
        log_warn "Some system pods may not be ready ($system_pods/$total_system_pods)"
    fi
    
    log_success "Kubernetes health check passed ✓"
    return 0
}

#=============================================================================
# Addon Lifecycle Management
#=============================================================================

addon_install() {
    log_info "Installing Kubernetes addon..."
    
    # Install packages
    install_kubernetes_packages
    
    # Install containerd
    install_containerd
    
    # Configure kernel modules
    configure_kernel_modules
    
    # Initialize cluster
    initialize_kubernetes_cluster
    
    # Install CNI plugin
    install_cni_plugin
    
    # Untaint master node
    untaint_master_node
    
    # Create helper scripts
    create_kubernetes_scripts
    
    # Run health check
    check_kubernetes_health
    
    # Open firewall ports
    firewall_open_port 6443 tcp  # Kubernetes API server
    firewall_open_port 10250 tcp # Kubelet API
    firewall_open_port 10251 tcp # kube-scheduler
    firewall_open_port 10252 tcp # kube-controller-manager
    firewall_open_port 30000-32767 tcp # NodePort services
    
    # Mark as installed
    mark_component_installed "$ADDON_NAME" "$ADDON_VERSION"
    
    log_success "Kubernetes addon installed successfully ✓"
    log_info "Use 'webops-k8s-status' to check cluster status"
}

addon_uninstall() {
    local purge="${1:-false}"
    
    log_info "Uninstalling Kubernetes addon..."
    
    # Reset cluster
    if command -v kubeadm &>/dev/null; then
        kubeadm reset -f || true
    fi
    
    # Stop services
    systemctl stop kubelet containerd || true
    systemctl disable kubelet containerd || true
    
    if [[ "$purge" == "true" ]]; then
        log_warn "Purging Kubernetes data..."
        
        # Remove packages
        case "$OS_ID" in
            ubuntu|debian)
                apt-get remove --purge -y kubelet kubeadm kubectl containerd.io || true
                ;;
            rocky|almalinux)
                yum remove -y kubelet kubeadm kubectl containerd.io || true
                ;;
        esac
        
        # Remove configuration and data
        rm -rf /etc/cni/net.d
        rm -rf /etc/kubernetes
        rm -rf /var/lib/kubelet
        rm -rf /var/lib/etcd
        rm -rf /var/lib/containerd
        rm -f $HOME/.kube/config
        if id "webops" &>/dev/null; then
            rm -f /home/webops/.kube/config
        fi
    fi
    
    # Remove helper scripts
    rm -f /usr/local/bin/webops-k8s-*
    
    # Close firewall ports
    firewall_close_port 6443 tcp
    firewall_close_port 10250 tcp
    firewall_close_port 10251 tcp
    firewall_close_port 10252 tcp
    firewall_close_port 30000-32767 tcp
    
    # Mark as removed
    mark_component_removed "$ADDON_NAME"
    
    log_success "Kubernetes addon uninstalled ✓"
}

addon_status() {
    if is_component_installed "$ADDON_NAME"; then
        echo "Kubernetes addon is installed (version: $(get_component_version "$ADDON_NAME"))"
        
        if check_kubernetes_health >/dev/null 2>&1; then
            echo "Status: Running and healthy"
        else
            echo "Status: Running but health check failed"
        fi
        
        return 0
    else
        echo "Kubernetes addon is not installed"
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
            check_kubernetes_health
            ;;
        *)
            log_error "Unknown action: $action"
            echo "Usage: $0 {install|uninstall [--purge]|status|version|health}"
            exit 1
            ;;
    esac
fi
