# KVM Virtual Machine Addon for WebOps

Enable KVM/QEMU virtual machine deployments on bare metal servers. This addon allows WebOps to function as a compute reselling platform, where users can subdivide bare metal resources and deploy isolated VMs.

## Features

- **Full VM Lifecycle Management**: Deploy, start, stop, restart, and delete VMs
- **Resource Management**: CPU, RAM, and disk allocation with overcommit support
- **NAT Networking**: Port forwarding for SSH and other services
- **Cloud-Init Integration**: Automated VM provisioning with SSH keys and custom configuration
- **Usage Metering**: Hourly tracking for billing and analytics
- **Resource Quotas**: Per-user limits on VMs and resources
- **Snapshots**: VM backup and restore capabilities
- **Multi-Template Support**: Ubuntu, Debian, CentOS, Rocky Linux, etc.
- **Admin Dashboard**: Django admin interface for managing VMs, plans, and nodes

## Architecture

### Components

1. **LibvirtManager** (`libvirt_manager.py`): Low-level libvirt operations
2. **KVMDeploymentService** (`deployment_service.py`): High-level VM lifecycle
3. **CloudInitGenerator** (`cloud_init.py`): VM provisioning configuration
4. **NetworkManager** (`networking.py`): NAT and port forwarding
5. **ResourceManager** (`resource_manager.py`): Resource allocation
6. **Hooks** (`hooks.py`): Integration with WebOps addon system
7. **Celery Tasks** (`tasks.py`): Background jobs for monitoring and metering

### Database Models

- **ComputeNode**: Physical bare metal servers
- **VMPlan**: Pre-defined resource plans (micro, small, medium, large)
- **OSTemplate**: Operating system images (qcow2 format)
- **VMDeployment**: VM instance records
- **VMSnapshot**: VM backups
- **VMUsageRecord**: Hourly usage for billing
- **VMQuota**: Per-user resource limits

## Installation

### Prerequisites

**System Requirements:**
- Ubuntu 22.04 LTS or Debian 12 (bare metal)
- KVM-capable CPU (Intel VT-x or AMD-V)
- Minimum 16GB RAM, 500GB disk
- Root or sudo access

**Software Dependencies:**
```bash
sudo apt update
sudo apt install -y \
    qemu-kvm \
    libvirt-daemon-system \
    libvirt-clients \
    virtinst \
    bridge-utils \
    genisoimage \
    libguestfs-tools \
    python3-libvirt
```

**Verify KVM Support:**
```bash
# Check CPU virtualization
egrep -c '(vmx|svm)' /proc/cpuinfo  # Should be > 0

# Check KVM module
lsmod | grep kvm

# Test libvirt
sudo virsh list --all
```

### WebOps Integration

1. **Install Python dependencies:**
```bash
cd /path/to/webops
pip install -r addons/kvm/requirements.txt
```

2. **Update Django settings** (`control-panel/config/settings.py`):
```python
# Add to INSTALLED_APPS (if using Django app integration)
INSTALLED_APPS += [
    'addons.kvm',
]

# KVM addon settings
KVM_STORAGE_PATH = '/var/lib/webops/vms'
KVM_TEMPLATE_PATH = '/var/lib/webops/templates'
```

3. **Run migrations:**
```bash
cd control-panel
python manage.py makemigrations
python manage.py migrate
```

4. **Initialize addon:**
```bash
python manage.py init_kvm --create-defaults
```

5. **Register hooks** (in `control-panel/config/__init__.py` or startup):
```python
from addons.kvm.hooks import register_hooks
register_hooks()
```

6. **Setup Celery tasks** (in `control-panel/config/celery.py`):
```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'record-vm-usage': {
        'task': 'addons.kvm.tasks.record_vm_usage',
        'schedule': crontab(minute=0),  # Every hour
    },
    'update-vm-states': {
        'task': 'addons.kvm.tasks.update_vm_states',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}
```

## Configuration

### 1. Add Compute Node

Register your bare metal server:

```bash
python manage.py add_compute_node localhost \
    --vcpus 16 \
    --memory-mb 32768 \
    --disk-gb 500 \
    --cpu-overcommit 2.0 \
    --memory-overcommit 1.0
```

Or via Django admin at `/admin/kvm/computenode/add/`.

### 2. Create VM Plans

Plans are pre-defined resource tiers (created automatically with `--create-defaults`):

| Plan   | vCPUs | RAM   | Disk  | Price/hour |
|--------|-------|-------|-------|------------|
| Micro  | 1     | 1GB   | 20GB  | $0.0050    |
| Small  | 2     | 2GB   | 40GB  | $0.0100    |
| Medium | 4     | 4GB   | 80GB  | $0.0200    |
| Large  | 8     | 8GB   | 160GB | $0.0400    |

Edit via admin: `/admin/kvm/vmplan/`

### 3. Create OS Templates

Download cloud images:

```bash
cd /var/lib/webops/templates

# Ubuntu 22.04 LTS
wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img
mv jammy-server-cloudimg-amd64.img ubuntu-22.04.qcow2

# Debian 12
wget https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2
```

Register via Django admin (`/admin/kvm/ostemplate/add/`):
- **Name**: `ubuntu-22.04`
- **Display Name**: Ubuntu 22.04 LTS
- **OS Family**: ubuntu
- **OS Version**: 22.04
- **Image Path**: `/var/lib/webops/templates/ubuntu-22.04.qcow2`
- **Supports Cloud-Init**: Yes

### 4. Configure User Quotas

Set limits per user via admin (`/admin/kvm/vmquota/`):
- Max VMs: 5
- Max vCPUs: 16
- Max Memory: 32GB
- Max Disk: 500GB

## Usage

### Deploy a VM

**Via API:**
```bash
curl -X POST -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-vm",
    "deployment_type": "kvm",
    "kvm_config": {
      "plan": "small",
      "template": "ubuntu-22.04",
      "ssh_keys": ["ssh-rsa AAAAB3..."]
    }
  }' \
  https://panel.example.com/api/v1/deployments/
```

**Via Django Admin:**
1. Go to `/admin/deployments/deployment/add/`
2. Set **Deployment Type**: `kvm`
3. Set **KVM Config**:
   ```json
   {
     "plan": "small",
     "template": "ubuntu-22.04",
     "ssh_keys": ["ssh-rsa AAAAB3..."]
   }
   ```
4. Save

**Programmatically:**
```python
from apps.deployments.models import Deployment
from addons.kvm.deployment_service import KVMDeploymentService
from addons.kvm.models import VMPlan, OSTemplate

deployment = Deployment.objects.create(
    user=request.user,
    name='my-vm',
    deployment_type='kvm',
    kvm_config={
        'plan': 'small',
        'template': 'ubuntu-22.04',
        'ssh_keys': ['ssh-rsa AAAAB3...'],
    }
)

service = KVMDeploymentService()
plan = VMPlan.objects.get(name='small')
template = OSTemplate.objects.get(name='ubuntu-22.04')

result = service.deploy_vm(
    deployment=deployment,
    plan=plan,
    template=template,
    ssh_keys=['ssh-rsa AAAAB3...'],
)

print(f"SSH: {result['ssh_command']}")
print(f"Password: {result['root_password']}")
```

### VM Operations

```python
from addons.kvm.models import VMDeployment
from addons.kvm.deployment_service import KVMDeploymentService

service = KVMDeploymentService()
vm = VMDeployment.objects.get(vm_name='webops-vm-123')

# Stop VM
service.stop_vm(vm)

# Start VM
service.start_vm(vm)

# Restart VM
service.restart_vm(vm)

# Create snapshot
service.create_snapshot(vm, 'backup-2024-01-01', 'Pre-update backup')

# Delete VM
service.delete_vm(vm, delete_disk=True)
```

### Access VM

After deployment:
```bash
# Via SSH (using NAT port forwarding)
ssh -p 2201 root@panel.example.com

# Or via direct IP (if using bridge networking)
ssh root@192.168.100.10
```

## Monitoring

### Health Checks

VMs are automatically health-checked every 5 minutes via Celery task. Status visible in admin dashboard.

### Usage Metering

Hourly usage records created for billing:

```python
from addons.kvm.models import VMUsageRecord
from django.db.models import Sum

# Get total cost for a VM this month
records = VMUsageRecord.objects.filter(
    vm_deployment=vm,
    timestamp__month=1,
    timestamp__year=2024,
)
total_cost = records.aggregate(Sum('cost'))['cost__sum']
```

### Resource Statistics

```python
from addons.kvm.resource_manager import ResourceManager

mgr = ResourceManager()
stats = mgr.get_cluster_stats()

print(f"vCPU utilization: {stats['vcpus']['utilization_pct']:.1f}%")
print(f"Memory utilization: {stats['memory_mb']['utilization_pct']:.1f}%")
```

## Networking

### NAT Mode (Default)

VMs get private IPs (192.168.100.0/24) with port forwarding:
- SSH ports: 2200-2299
- VNC ports: 5900-5999

Automatic iptables rules created for each VM.

### Bridge Mode (Future)

For direct public IP assignment, edit `networking.py` to use bridge interface.

## Troubleshooting

### VM won't start

```bash
# Check libvirt status
sudo systemctl status libvirtd

# Check VM logs
sudo virsh console webops-vm-123

# Check libvirt logs
sudo tail -f /var/log/libvirt/qemu/webops-vm-123.log
```

### Cloud-init not working

```bash
# SSH into VM and check cloud-init status
cloud-init status --long

# View cloud-init logs
sudo tail -f /var/log/cloud-init.log
```

### Network issues

```bash
# Check NAT network
sudo virsh net-list --all
sudo virsh net-info webops-nat

# Check iptables rules
sudo iptables -t nat -L -n -v
```

### Disk issues

```bash
# Check qcow2 image
qemu-img info /var/lib/webops/vms/vm-123/disk.qcow2

# Check backing file chain
qemu-img info --backing-chain /var/lib/webops/vms/vm-123/disk.qcow2
```

## Security

- VMs run as `libvirt-qemu` user (unprivileged)
- Disk images stored with restricted permissions
- SSH keys required (password auth optional)
- NAT provides network isolation
- Encrypted credentials in database (via WebOps encryption)

## Performance Tuning

### CPU Pinning
Edit `libvirt_manager.py` to add CPU pinning for better performance.

### Huge Pages
Enable huge pages for memory-intensive VMs:
```bash
echo 1024 | sudo tee /proc/sys/vm/nr_hugepages
```

### I/O Scheduler
Use `deadline` or `noop` for VM disks:
```bash
echo deadline | sudo tee /sys/block/sda/queue/scheduler
```

## Roadmap

**Phase 2 (Production):**
- [ ] noVNC web console
- [ ] Enhanced snapshot management
- [ ] VM migration between nodes
- [ ] Bridge networking option

**Phase 3 (Scale):**
- [ ] Multi-node clustering
- [ ] Live migration
- [ ] Custom ISO uploads
- [ ] Windows template support

## License

Same as WebOps project.

## Support

Report issues at: https://github.com/anthropics/webops/issues
