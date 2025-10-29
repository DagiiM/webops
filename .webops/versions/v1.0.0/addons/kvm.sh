#!/bin/bash
#
# WebOps KVM Addon
# Installs and configures KVM virtualization
#
# This addon supports:
# - KVM hypervisor setup
# - libvirt management
# - bridge networking
# - storage pool configuration
# - VM lifecycle management
#

set -euo pipefail

# Addon metadata
if [[ -z "${ADDON_NAME:-}" ]]; then
    readonly ADDON_NAME="kvm"
fi
if [[ -z "${ADDON_VERSION:-}" ]]; then
    readonly ADDON_VERSION="1.0.0"
fi
if [[ -z "${ADDON_DESCRIPTION:-}" ]]; then
    readonly ADDON_DESCRIPTION="KVM Virtualization Platform"
fi

# Source libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/common.sh"
source "${SCRIPT_DIR}/../lib/os.sh"
source "${SCRIPT_DIR}/../lib/state.sh"
source "${SCRIPT_DIR}/../lib/addon-contract.sh"

# Configuration
if [[ -z "${KVM_USER:-}" ]]; then
    readonly KVM_USER="${KVM_USER:-libvirt-qemu}"
fi
if [[ -z "${LIBVIRT_GROUP:-}" ]]; then
    readonly LIBVIRT_GROUP="${LIBVIRT_GROUP:-libvirt}"
fi
if [[ -z "${BRIDGE_NAME:-}" ]]; then
    readonly BRIDGE_NAME="${BRIDGE_NAME:-virbr0}"
fi
if [[ -z "${BRIDGE_NETWORK:-}" ]]; then
    readonly BRIDGE_NETWORK="${BRIDGE_NETWORK:-192.168.122.0/24}"
fi
if [[ -z "${STORAGE_POOL:-}" ]]; then
    readonly STORAGE_POOL="${STORAGE_POOL:-default}"
fi
if [[ -z "${STORAGE_PATH:-}" ]]; then
    readonly STORAGE_PATH="${STORAGE_PATH:-/var/lib/libvirt/images}"
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
    "category": "virtualization",
    "depends": [],
    "provides": ["kvm", "libvirt", "qemu", "virt-manager"],
    "conflicts": ["docker", "lxc", "openvz"],
    "system_requirements": {
        "min_memory_mb": 4096,
        "min_disk_gb": 50,
        "min_cpu_cores": 2,
        "required_ports": [16509],
        "hardware_requirements": ["kvm_support"]
    },
    "maintainer": "WebOps Team",
    "license": "GPL-2.0",
    "documentation_url": "https://webops.dev/docs/addons/kvm",
    "support_url": "https://webops.dev/support",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-10-29T09:45:00Z"
}
EOF
}

addon_sla() {
    cat <<EOF
{
    "availability_target": "99.8",
    "performance_targets": {
        "vm_startup_time_seconds": "30",
        "vm_migration_time_minutes": "5",
        "disk_io_iops": "1000",
        "network_throughput_mbps": "1000"
    },
    "recovery_objectives": {
        "rto": "10",
        "rpo": "15",
        "backup_frequency": "daily",
        "backup_retention_days": "30"
    },
    "monitoring_requirements": {
        "metrics_collection_interval": "60",
        "health_check_interval": "30",
        "alert_response_time": "300"
    },
    "capacity_targets": {
        "max_concurrent_vms": "20",
        "max_vcpus_per_host": "32",
        "max_memory_per_host_gb": "128",
        "max_storage_per_host_tb": "10"
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
        "type": "virtualization",
        "locations": [
            "/var/lib/libvirt",
            "/etc/libvirt",
            "$STORAGE_PATH",
            "/var/log/libvirt"
        ],
        "encryption": true,
        "backup_retention_days": 30
    },
    "network_access": {
        "required_ports": [16509],
        "protocols": ["tcp", "tls"],
        "encryption_required": true
    },
    "authentication": {
        "method": "certificate",
        "certificate_locations": [
            "/etc/pki/libvirt/servercert.pem",
            "/etc/pki/libvirt/private/serverkey.pem",
            "/etc/pki/libvirt/cacert.pem"
        ],
        "ca_certificate": "/etc/pki/libvirt/cacert.pem"
    },
    "audit_logging": {
        "enabled": true,
        "log_level": "info",
        "log_retention_days": 90,
        "audit_events": [
            "vm_creation",
            "vm_deletion",
            "vm_migration",
            "network_changes",
            "storage_operations",
            "libvirt_access"
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
    
    # Check if libvirtd is running
    if ! systemctl is-active --quiet libvirtd; then
        echo "CRITICAL: libvirtd service is not running"
        return 2
    fi
    
    # Check if KVM modules are loaded
    if ! lsmod | grep -q kvm; then
        echo "CRITICAL: KVM modules are not loaded"
        return 2
    fi
    
    # Check if libvirt is accessible
    if ! virsh uri &>/dev/null; then
        echo "CRITICAL: libvirt is not accessible"
        return 2
    fi
    
    # Check if /dev/kvm exists
    if [[ ! -e /dev/kvm ]]; then
        echo "CRITICAL: /dev/kvm device not found"
        return 2
    fi
    
    # Check if default network is active
    if ! virsh net-info default | grep -q "Active:.*yes"; then
        echo "WARNING: Default network is not active"
        return 1
    fi
    
    # Check if default storage pool is active
    if ! virsh pool-info default | grep -q "State:.*running"; then
        echo "WARNING: Default storage pool is not running"
        return 1
    fi
    
    # Check disk space for storage pool
    if [[ -d "$STORAGE_PATH" ]]; then
        local storage_usage=$(df "$STORAGE_PATH" | awk 'NR==2{print $5}' | sed 's/%//')
        if [[ $storage_usage -gt 85 ]]; then
            echo "WARNING: Storage pool directory is ${storage_usage}% full"
            return 1
        fi
    fi
    
    if [[ "$detailed" == "true" ]]; then
        echo "KVM hypervisor is healthy"
        
        # Get hypervisor info
        echo "Hypervisor information:"
        virsh nodeinfo
        
        # Get VM counts
        local running_vms=$(virsh list --state-running --name | wc -l)
        local total_vms=$(virsh list --all --name | wc -l)
        echo "VMs: $running_vms running, $total_vms total"
        
        # Get resource usage
        echo "Resource usage:"
        virsh list --all | head -10
        
        # Get network status
        echo "Network status:"
        virsh net-list --all
        
        # Get storage pool status
        echo "Storage pool status:"
        virsh pool-list --all
    fi
    
    echo "OK: KVM hypervisor is healthy"
    return 0
}

addon_start() {
    log_info "Starting KVM services..."
    
    # Load KVM modules
    modprobe kvm
    modprobe kvm_intel || modprobe kvm_amd
    
    # Start libvirtd service
    systemctl start libvirtd
    
    # Wait for libvirtd to start
    local max_attempts=10
    local attempt=1
    
    while (( attempt <= max_attempts )); do
        if systemctl is-active --quiet libvirtd; then
            log_success "libvirtd service started ✓"
            break
        fi
        
        log_info "Waiting for libvirtd to start (attempt $attempt/$max_attempts)..."
        sleep 2
        ((attempt++))
        
        if (( attempt > max_attempts )); then
            log_error "libvirtd failed to start"
            return 1
        fi
    done
    
    # Start default network
    if virsh net-list --name | grep -q default; then
        virsh net-start default 2>/dev/null || true
    fi
    
    # Start default storage pool
    if virsh pool-list --name | grep -q default; then
        virsh pool-start default 2>/dev/null || true
    fi
    
    return 0
}

addon_stop() {
    log_info "Stopping KVM services..."
    
    # Stop all running VMs
    local running_vms=$(virsh list --state-running --name)
    if [[ -n "$running_vms" ]]; then
        log_info "Stopping running VMs..."
        echo "$running_vms" | xargs -I {} virsh shutdown {}
        sleep 10
        
        # Force stop if still running
        running_vms=$(virsh list --state-running --name)
        if [[ -n "$running_vms" ]]; then
            echo "$running_vms" | xargs -I {} virsh destroy {}
        fi
    fi
    
    # Stop default network
    if virsh net-list --name | grep -q default; then
        virsh net-stop default 2>/dev/null || true
    fi
    
    # Stop default storage pool
    if virsh pool-list --name | grep -q default; then
        virsh pool-stop default 2>/dev/null || true
    fi
    
    # Stop libvirtd service
    systemctl stop libvirtd || true
    
    log_success "KVM services stopped ✓"
    return 0
}

addon_restart() {
    log_info "Restarting KVM services..."
    
    # Stop services
    addon_stop
    
    # Wait a moment
    sleep 5
    
    # Start services
    addon_start
    
    return 0
}

addon_configure() {
    local config_file="${1:-}"
    
    if [[ -n "$config_file" && -f "$config_file" ]]; then
        log_info "Applying KVM configuration from $config_file..."
        
        # Apply libvirt configuration
        if [[ "$config_file" == *.xml ]]; then
            virsh define "$config_file"
        else
            # Copy configuration files
            cp "$config_file" /etc/libvirt/libvirtd.conf
            systemctl restart libvirtd
        fi
        
        log_success "KVM configuration applied ✓"
    else
        log_info "Reconfiguring KVM with current settings..."
        
        # Reconfigure libvirt
        configure_libvirt
        
        log_success "KVM reconfigured ✓"
    fi
    
    return 0
}

addon_validate() {
    log_info "Validating KVM installation..."
    
    local errors=0
    
    # Check hardware virtualization support
    if ! grep -q -E "(vmx|svm)" /proc/cpuinfo; then
        log_error "Hardware virtualization not supported"
        ((errors++))
    fi
    
    # Check if KVM modules are loaded
    if ! lsmod | grep -q kvm; then
        log_error "KVM modules are not loaded"
        ((errors++))
    fi
    
    # Check if /dev/kvm exists
    if [[ ! -e /dev/kvm ]]; then
        log_error "/dev/kvm device not found"
        ((errors++))
    fi
    
    # Check if required packages are installed
    if ! command -v virsh &>/dev/null; then
        log_error "virsh is not installed"
        ((errors++))
    fi
    
    if ! command -v qemu-system-x86_64 &>/dev/null; then
        log_error "qemu-system-x86_64 is not installed"
        ((errors++))
    fi
    
    # Check configuration files
    if [[ ! -f /etc/libvirt/libvirtd.conf ]]; then
        log_error "libvirt configuration file not found"
        ((errors++))
    fi
    
    # Check systemd services
    if ! systemctl list-unit-files | grep -q "libvirtd.service"; then
        log_error "libvirtd systemd service not found"
        ((errors++))
    fi
    
    # Check libvirt connectivity
    if ! virsh uri &>/dev/null; then
        log_error "libvirt is not accessible"
        ((errors++))
    fi
    
    if [[ $errors -eq 0 ]]; then
        log_success "KVM validation passed ✓"
        return 0
    else
        log_error "KVM validation failed with $errors errors"
        return 1
    fi
}

addon_backup() {
    local backup_dir="${1:-${WEBOPS_ROOT:-/webops}/backups/kvm}"
    local backup_type="${2:-full}"
    
    log_info "Creating KVM backup ($backup_type)..."
    
    # Create backup directory
    mkdir -p "$backup_dir"
    
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$backup_dir/kvm-backup-$timestamp"
    
    case "$backup_type" in
        "full")
            # Backup VM configurations
            virsh dumpxml --all > "$backup_file-vms.xml"
            gzip "$backup_file-vms.xml"
            log_success "VM configurations backup completed: $(basename "$backup_file-vms.xml.gz")"
            
            # Backup network configurations
            virsh net-dumpxml --all > "$backup_file-networks.xml"
            gzip "$backup_file-networks.xml"
            log_success "Network configurations backup completed: $(basename "$backup_file-networks.xml.gz")"
            
            # Backup storage pool configurations
            virsh pool-dumpxml --all > "$backup_file-pools.xml"
            gzip "$backup_file-pools.xml"
            log_success "Storage pool configurations backup completed: $(basename "$backup_file-pools.xml.gz")"
            ;;
        "config")
            # Backup configuration files
            tar -czf "$backup_file-config.tar.gz" \
                /etc/libvirt \
                /etc/qemu \
                /var/log/libvirt
            log_success "Configuration backup completed: $(basename "$backup_file-config.tar.gz")"
            ;;
        "storage")
            # Backup storage pool data
            if [[ -d "$STORAGE_PATH" ]]; then
                tar -czf "$backup_file-storage.tar.gz" -C "$(dirname "$STORAGE_PATH")" "$(basename "$STORAGE_PATH")"
                log_success "Storage backup completed: $(basename "$backup_file-storage.tar.gz")"
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
    
    log_info "Restoring KVM from backup: $(basename "$backup_file")"
    
    case "$backup_file" in
        *-vms.xml.gz)
            # Restore VM configurations
            gunzip -c "$backup_file" | virsh define -
            log_success "VM configurations restored ✓"
            ;;
        *-networks.xml.gz)
            # Restore network configurations
            gunzip -c "$backup_file" | virsh net-define -
            log_success "Network configurations restored ✓"
            ;;
        *-pools.xml.gz)
            # Restore storage pool configurations
            gunzip -c "$backup_file" | virsh pool-define -
            log_success "Storage pool configurations restored ✓"
            ;;
        *-config.tar.gz)
            # Restore configuration
            tar -xzf "$backup_file" -C /
            systemctl restart libvirtd
            log_success "Configuration restored ✓"
            ;;
        *-storage.tar.gz)
            # Restore storage data
            tar -xzf "$backup_file" -C /
            log_success "Storage data restored ✓"
            ;;
        *)
            log_error "Unknown backup format: $backup_file"
            return 1
            ;;
    esac
    
    return 0
}

#=============================================================================
# KVM Installation
#=============================================================================

check_kvm_support() {
    log_step "Checking KVM hardware support..."
    
    # Check for KVM support
    if ! grep -q -E "(vmx|svm)" /proc/cpuinfo; then
        log_error "KVM hardware virtualization not supported"
        return 1
    fi
    
    # Check if KVM modules are loaded
    if ! lsmod | grep -q kvm; then
        log_info "Loading KVM modules..."
        modprobe kvm
        modprobe kvm_intel || modprobe kvm_amd
    fi
    
    # Check if /dev/kvm exists
    if [[ ! -e /dev/kvm ]]; then
        log_error "/dev/kvm device not found"
        return 1
    fi
    
    log_success "KVM hardware support confirmed ✓"
}

install_kvm_packages() {
    log_step "Installing KVM packages..."
    
    case "$OS_ID" in
        ubuntu|debian)
            # Install KVM and related packages
            apt-get install -y qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils virtinst virt-manager virt-viewer
            ;;
        rocky|almalinux)
            # Install KVM and related packages
            yum groupinstall -y "Virtualization Host"
            yum install -y qemu-kvm libvirt-daemon libvirt-client bridge-utils virt-install virt-manager virt-viewer
            ;;
    esac
    
    # Verify installation
    if command -v virsh &>/dev/null; then
        log_success "KVM packages installed ✓"
    else
        log_error "KVM installation failed"
        return 1
    fi
}

configure_libvirt() {
    log_step "Configuring libvirt..."
    
    # Enable and start libvirtd service
    systemctl enable libvirtd
    systemctl start libvirtd
    
    # Add current user to libvirt group
    usermod -a -G "$LIBVIRT_GROUP" "$(whoami)"
    if id "webops" &>/dev/null; then
        usermod -a -G "$LIBVIRT_GROUP" "webops"
    fi
    
    # Configure libvirt to listen on TCP (optional, for remote management)
    cat > /etc/libvirt/libvirtd.conf <<EOF
# WebOps libvirt Configuration
# Generated by WebOps addons/kvm.sh

# Listen for TCP connections
listen_tcp = 1
listen_tls = 0

# Authentication
auth_tcp = "none"

# Access control
unix_sock_group = "$LIBVIRT_GROUP"
unix_sock_rw_perms = "0770"

# Logging
log_level = 3
log_outputs = "3:syslog:libvirtd"
EOF
    
    # Configure libvirt to allow TCP connections
    cat > /etc/default/libvirtd <<EOF
# WebOps libvirtd defaults
# Generated by WebOps addons/kvm.sh

libvirtd_opts="-l"
EOF
    
    # Restart libvirtd to apply configuration
    systemctl restart libvirtd
    
    # Wait for libvirtd to start
    local max_attempts=10
    local attempt=1
    
    while (( attempt <= max_attempts )); do
        if virsh uri &>/dev/null; then
            log_success "libvirt configured and running ✓"
            break
        fi
        
        log_info "Waiting for libvirtd to start (attempt $attempt/$max_attempts)..."
        sleep 2
        ((attempt++))
        
        if (( attempt > max_attempts )); then
            log_error "libvirtd failed to start"
            return 1
        fi
    done
}

setup_bridge_network() {
    log_step "Setting up bridge network..."
    
    # Create default network if it doesn't exist
    if ! virsh net-list --name | grep -q default; then
        log_info "Creating default libvirt network..."
        
        # Create default network XML
        cat > /tmp/default-network.xml <<EOF
<network>
  <name>default</name>
  <forward mode='nat'/>
  <bridge name='$BRIDGE_NAME' stp='on' delay='0'/>
  <ip address='192.168.122.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.122.2' end='192.168.122.254'/>
    </dhcp>
  </ip>
</network>
EOF
        
        # Define and start the network
        virsh net-define /tmp/default-network.xml
        virsh net-autostart default
        virsh net-start default
        
        # Clean up
        rm -f /tmp/default-network.xml
        
        log_success "Default bridge network created ✓"
    else
        log_info "Default network already exists"
        # Ensure it's started and autostarted
        virsh net-start default 2>/dev/null || true
        virsh net-autostart default
    fi
}

setup_storage_pool() {
    log_step "Setting up storage pool..."
    
    # Create storage directory
    ensure_directory "$STORAGE_PATH" "root:root" "755"
    
    # Create default storage pool if it doesn't exist
    if ! virsh pool-list --name | grep -q "$STORAGE_POOL"; then
        log_info "Creating default storage pool..."
        
        # Create storage pool XML
        cat > /tmp/default-pool.xml <<EOF
<pool type='dir'>
  <name>$STORAGE_POOL</name>
  <target>
    <path>$STORAGE_PATH</path>
    <permissions>
      <mode>0755</mode>
      <owner>-1</owner>
      <group>-1</group>
    </permissions>
  </target>
</pool>
EOF
        
        # Define and start the storage pool
        virsh pool-define /tmp/default-pool.xml
        virsh pool-autostart "$STORAGE_POOL"
        virsh pool-build "$STORAGE_POOL"
        virsh pool-start "$STORAGE_POOL"
        
        # Clean up
        rm -f /tmp/default-pool.xml
        
        log_success "Default storage pool created ✓"
    else
        log_info "Storage pool '$STORAGE_POOL' already exists"
        # Ensure it's started and autostarted
        virsh pool-start "$STORAGE_POOL" 2>/dev/null || true
        virsh pool-autostart "$STORAGE_POOL"
    fi
}

create_kvm_scripts() {
    log_step "Creating KVM helper scripts..."
    
    # VM status script
    cat > /usr/local/bin/webops-kvm-status <<'EOF'
#!/bin/bash
#
# WebOps KVM Status Script
# Shows VM status and information
#

set -euo pipefail

echo "=== KVM Hypervisor Status ==="
virsh nodeinfo
echo ""

echo "=== Active VMs ==="
virsh list --all
echo ""

echo "=== Networks ==="
virsh net-list --all
echo ""

echo "=== Storage Pools ==="
virsh pool-list --all
echo ""

echo "=== Interface Statistics ==="
virsh iface-list --all
echo ""
EOF
    
    # VM create script
    cat > /usr/local/bin/webops-kvm-create <<'EOF'
#!/bin/bash
#
# WebOps KVM VM Creation Script
# Simplified VM creation helper
#

set -euo pipefail

# Default values
NAME=""
MEMORY="2048"
VCPUS="2"
DISK_SIZE="20"
OS_VARIANT="ubuntu20.04"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --name)
            NAME="$2"
            shift 2
            ;;
        --memory)
            MEMORY="$2"
            shift 2
            ;;
        --vcpus)
            VCPUS="$2"
            shift 2
            ;;
        --disk-size)
            DISK_SIZE="$2"
            shift 2
            ;;
        --os-variant)
            OS_VARIANT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 --name <name> [--memory <MB>] [--vcpus <count>] [--disk-size <GB>] [--os-variant <variant>]"
            echo "Example: $0 --name test-vm --memory 4096 --vcpus 4 --disk-size 40 --os-variant ubuntu22.04"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$NAME" ]]; then
    echo "Error: --name is required"
    exit 1
fi

echo "Creating VM: $NAME"
echo "Memory: ${MEMORY}MB"
echo "vCPUs: $VCPUS"
echo "Disk: ${DISK_SIZE}GB"
echo "OS Variant: $OS_VARIANT"

# Create VM
virt-install \
    --name "$NAME" \
    --memory "$MEMORY" \
    --vcpus "$VCPUS" \
    --disk "size=${DISK_SIZE},format=qcow2" \
    --os-variant "$OS_VARIANT" \
    --network network=default \
    --graphics spice \
    --noautoconsole

echo "VM '$NAME' created successfully"
echo "Use 'virsh console $NAME' to access the console"
EOF
    
    # VM management script
    cat > /usr/local/bin/webops-kvm-manage <<'EOF'
#!/bin/bash
#
# WebOps KVM VM Management Script
# Simple VM management interface
#

set -euo pipefail

show_help() {
    echo "WebOps KVM VM Management"
    echo "Usage: $0 <command> <vm-name>"
    echo ""
    echo "Commands:"
    echo "  list          List all VMs"
    echo "  start <name>  Start a VM"
    echo "  stop <name>   Stop a VM"
    echo "  restart <name> Restart a VM"
    echo "  delete <name> Delete a VM"
    echo "  console <name> Connect to VM console"
    echo "  info <name>   Show VM information"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 start my-vm"
    echo "  $0 console my-vm"
}

# Check if command is provided
if [[ $# -lt 1 ]]; then
    show_help
    exit 1
fi

COMMAND="$1"
VM_NAME="${2:-}"

case "$COMMAND" in
    list)
        echo "=== Virtual Machines ==="
        virsh list --all
        ;;
    start)
        if [[ -z "$VM_NAME" ]]; then
            echo "Error: VM name is required"
            exit 1
        fi
        virsh start "$VM_NAME"
        echo "VM '$VM_NAME' started"
        ;;
    stop)
        if [[ -z "$VM_NAME" ]]; then
            echo "Error: VM name is required"
            exit 1
        fi
        virsh shutdown "$VM_NAME"
        echo "VM '$VM_NAME' shutdown initiated"
        ;;
    restart)
        if [[ -z "$VM_NAME" ]]; then
            echo "Error: VM name is required"
            exit 1
        fi
        virsh reboot "$VM_NAME"
        echo "VM '$VM_NAME' restart initiated"
        ;;
    delete)
        if [[ -z "$VM_NAME" ]]; then
            echo "Error: VM name is required"
            exit 1
        fi
        read -p "Are you sure you want to delete VM '$VM_NAME'? (yes/no): " confirm
        if [[ "$confirm" == "yes" ]]; then
            virsh undefine "$VM_NAME" --remove-all-storage
            echo "VM '$VM_NAME' deleted"
        else
            echo "Operation cancelled"
        fi
        ;;
    console)
        if [[ -z "$VM_NAME" ]]; then
            echo "Error: VM name is required"
            exit 1
        fi
        virsh console "$VM_NAME"
        ;;
    info)
        if [[ -z "$VM_NAME" ]]; then
            echo "Error: VM name is required"
            exit 1
        fi
        virsh dominfo "$VM_NAME"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac
EOF
    
    # Make scripts executable
    chmod +x /usr/local/bin/webops-kvm-*
    
    log_success "KVM helper scripts created ✓"
}

#=============================================================================
# Health Checks
#=============================================================================

check_kvm_health() {
    log_step "Checking KVM health..."
    
    # Check if libvirtd is running
    if ! systemctl is-active --quiet libvirtd; then
        log_error "libvirtd service is not running"
        return 1
    fi
    
    # Check if KVM modules are loaded
    if ! lsmod | grep -q kvm; then
        log_error "KVM modules are not loaded"
        return 1
    fi
    
    # Check if libvirt is accessible
    if ! virsh uri &>/dev/null; then
        log_error "libvirt is not accessible"
        return 1
    fi
    
    # Check if default network is active
    if ! virsh net-info default | grep -q "Active:.*yes"; then
        log_warn "Default network is not active"
    fi
    
    # Check if default storage pool is active
    if ! virsh pool-info default | grep -q "State:.*running"; then
        log_warn "Default storage pool is not running"
    fi
    
    # Check disk space for storage pool
    if [[ -d "$STORAGE_PATH" ]]; then
        local storage_usage=$(df "$STORAGE_PATH" | awk 'NR==2{print $5}' | sed 's/%//')
        if [[ $storage_usage -gt 80 ]]; then
            log_warn "Storage pool directory is ${storage_usage}% full"
        fi
    fi
    
    log_success "KVM health check passed ✓"
    return 0
}

#=============================================================================
# Addon Lifecycle Management
#=============================================================================

addon_install() {
    log_info "Installing KVM addon..."
    
    # Check hardware support
    check_kvm_support
    
    # Install packages
    install_kvm_packages
    
    # Configure libvirt
    configure_libvirt
    
    # Setup bridge network
    setup_bridge_network
    
    # Setup storage pool
    setup_storage_pool
    
    # Create helper scripts
    create_kvm_scripts
    
    # Run health check
    check_kvm_health
    
    # Open firewall ports for libvirt
    firewall_open_port 16509 tcp  # libvirt remote access
    
    # Mark as installed
    mark_component_installed "$ADDON_NAME" "$ADDON_VERSION"
    
    log_success "KVM addon installed successfully ✓"
    log_info "Use 'webops-kvm-status' to check hypervisor status"
    log_info "Use 'webops-kvm-manage' to manage VMs"
}

addon_uninstall() {
    local purge="${1:-false}"
    
    log_info "Uninstalling KVM addon..."
    
    # Stop and disable libvirtd
    systemctl stop libvirtd || true
    systemctl disable libvirtd || true
    
    if [[ "$purge" == "true" ]]; then
        log_warn "Purging KVM data..."
        
        # Remove packages
        case "$OS_ID" in
            ubuntu|debian)
                apt-get remove --purge -y qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils virtinst virt-manager virt-viewer || true
                ;;
            rocky|almalinux)
                yum remove -y qemu-kvm libvirt-daemon libvirt-client bridge-utils virt-install virt-manager virt-viewer || true
                ;;
        esac
        
        # Remove storage directory
        rm -rf "$STORAGE_PATH" || true
        
        # Remove libvirt configuration
        rm -rf /etc/libvirt
        rm -f /etc/default/libvirtd
    fi
    
    # Remove helper scripts
    rm -f /usr/local/bin/webops-kvm-*
    
    # Close firewall ports
    firewall_close_port 16509 tcp
    
    # Mark as removed
    mark_component_removed "$ADDON_NAME"
    
    log_success "KVM addon uninstalled ✓"
}

addon_status() {
    if is_component_installed "$ADDON_NAME"; then
        echo "KVM addon is installed (version: $(get_component_version "$ADDON_NAME"))"
        
        if check_kvm_health >/dev/null 2>&1; then
            echo "Status: Running and healthy"
        else
            echo "Status: Running but health check failed"
        fi
        
        return 0
    else
        echo "KVM addon is not installed"
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
            check_kvm_health
            ;;
        *)
            log_error "Unknown action: $action"
            echo "Usage: $0 {install|uninstall [--purge]|status|version|health}"
            exit 1
            ;;
    esac
fi
