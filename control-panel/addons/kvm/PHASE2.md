### Phase 2: Production Features - Implementation Complete ✓

This document describes the Phase 2 features that have been added to the KVM addon.

## New Features

### 1. noVNC Web Console ✓

**What it is:** Browser-based VNC console access for VMs.

**Components:**
- `vnc_proxy.py`: WebSocket proxy consumer that bridges browser to QEMU VNC
- `routing.py`: Django Channels WebSocket routing
- `templates/kvm/console.html`: Full-featured console UI with noVNC client

**Features:**
- Real-time console access in browser (no SSH/client required)
- Token-based authentication (15-minute expiring tokens)
- Connection status indicators
- Ctrl+Alt+Del support
- Fullscreen mode
- Security audit logging
- Auto-reconnect on disconnect

**Usage:**
```python
# Access console for a VM
url = f"/kvm/console/{deployment_id}/"

# Or generate VNC token programmatically
from addons.kvm.vnc_proxy import VNCTokenAuth
token = VNCTokenAuth.generate_token(vm_deployment, user)
```

**Setup Requirements:**
1. Install Django Channels: `pip install channels`
2. Configure ASGI in `config/asgi.py`:
```python
from channels.routing import ProtocolTypeRouter, URLRouter
from addons.kvm import routing as kvm_routing

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': URLRouter(kvm_routing.websocket_urlpatterns),
})
```

3. Update `settings.py`:
```python
INSTALLED_APPS += ['channels']
ASGI_APPLICATION = 'config.asgi.application'
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('127.0.0.1', 6379)],
        },
    },
}
```

**Security:**
- All console access logged to `SecurityAuditLog`
- Token-based authentication with expiry
- User authorization checks (owner or staff only)
- WebSocket over TLS in production

### 2. Enhanced Snapshot Management ✓

**What it is:** Full UI for creating, restoring, and deleting VM snapshots.

**Components:**
- `views.py`: API endpoints for snapshot CRUD operations
- `templates/kvm/dashboard.html`: Integrated snapshot management UI

**Features:**
- List all snapshots for a VM
- Create named snapshots with descriptions
- Restore VM to previous snapshot
- Delete old snapshots
- Snapshot metadata (size, creation date)

**API Endpoints:**
```
GET    /kvm/api/vm/{id}/snapshots/              # List snapshots
POST   /kvm/api/vm/{id}/snapshots/create/       # Create snapshot
POST   /kvm/api/vm/{id}/snapshots/{sid}/restore/ # Restore snapshot
DELETE /kvm/api/vm/{id}/snapshots/{sid}/delete/ # Delete snapshot
```

**Usage:**
```python
from addons.kvm.deployment_service import KVMDeploymentService

service = KVMDeploymentService()

# Create snapshot
service.create_snapshot(
    vm_deployment,
    name='pre-upgrade',
    description='Before system upgrade'
)

# Restore (via libvirt manager)
from addons.kvm.libvirt_manager import LibvirtManager
with LibvirtManager(vm.compute_node.libvirt_uri) as mgr:
    mgr.restore_snapshot(vm.vm_name, 'pre-upgrade')
```

### 3. VM Migration ✓

**What it is:** Move VMs between compute nodes with minimal/zero downtime.

**Components:**
- `migration.py`: `VMMigrationService` with offline and live migration support

**Migration Types:**

**Offline Migration** (VM stopped during migration):
- Stops VM on source
- Copies disk to target
- Starts VM on target
- Updates database
- Cleanup source

**Live Migration** (VM stays running):
- Requires libvirt live migration support
- Uses block migration (no shared storage needed)
- Near-zero downtime
- Network connectivity between nodes required

**Usage:**
```python
from addons.kvm.migration import VMMigrationService
from addons.kvm.models import ComputeNode

service = VMMigrationService()
target_node = ComputeNode.objects.get(hostname='node2.example.com')

# Check if migration is possible
can_migrate, reason = service.can_migrate(vm_deployment, target_node)

if can_migrate:
    # Offline migration (safer, requires downtime)
    service.migrate_vm(vm_deployment, target_node, live=False)

    # Or live migration (no downtime, more complex)
    service.migrate_vm(vm_deployment, target_node, live=True)
```

**Requirements:**
- SSH connectivity between nodes
- rsync installed (for offline migration)
- Compatible libvirt versions (for live migration)
- Sufficient resources on target node

### 4. Bridge Networking ✓

**What it is:** Alternative to NAT networking - VMs get direct network access.

**Components:**
- `bridge_networking.py`: `BridgeNetworkManager` for Linux bridge setup

**Features:**
- Create Linux bridges attached to physical NICs
- Configure bridge via netplan (Ubuntu) or ifcfg (CentOS)
- Static IP assignment via libvirt DHCP
- Integration with libvirt networking

**Usage:**
```python
from addons.kvm.bridge_networking import BridgeNetworkManager

mgr = BridgeNetworkManager(bridge_name='br0')

# Create bridge on physical interface
mgr.create_bridge(
    physical_interface='eth0',
    bridge_ip='192.168.1.10',
    netmask='255.255.255.0',
)

# Create libvirt bridge network
mgr.create_libvirt_bridge_network(
    network_name='webops-bridge',
    subnet='192.168.1.0/24',
)

# Assign static IP to VM
mgr.assign_static_ip(
    mac_address='52:54:00:12:34:56',
    ip_address='192.168.1.100',
)
```

**Persistent Configuration:**
```python
# Configure bridge to persist across reboots (Ubuntu netplan)
mgr.configure_persistent_bridge(
    physical_interface='eth0',
    bridge_ip='192.168.1.10',
    netmask='255.255.255.0',
    gateway='192.168.1.1',
)
```

**When to use:**
- Have a subnet of public IPs
- Need direct network access for VMs
- Don't want NAT port forwarding complexity
- Running on bare metal with multiple IPs

### 5. VM Resize/Upgrade ✓

**What it is:** Change VM resources without redeployment.

**Components:**
- `resize.py`: `VMResizeService` for hot/cold resource changes

**Supported Resizes:**
- **vCPU**: Hot-plug (if supported) or requires restart
- **Memory**: Hot-plug (if supported) or requires restart
- **Disk**: Requires VM stop (cannot shrink, only grow)

**Usage:**
```python
from addons.kvm.resize import VMResizeService
from addons.kvm.models import VMPlan

service = VMResizeService()
new_plan = VMPlan.objects.get(name='large')

# Check if downsize (not recommended)
can_downsize, msg = service.can_downsize(vm.vm_plan, new_plan)

# Estimate downtime
estimate = service.estimate_downtime(vm, new_plan, resize_disk=True)
print(f"Estimated downtime: {estimate['downtime_seconds']} seconds")
print(f"Notes: {estimate['notes']}")

# Perform resize
service.resize_vm(
    vm_deployment,
    new_plan,
    resize_disk=True,  # Also resize disk (requires stop)
)
```

**Important Notes:**
- Disk can only grow, never shrink (data loss risk)
- Guest OS may need manual filesystem resize after disk grow
- Hot-plug success depends on guest OS and libvirt version
- Downsizing resources is generally not recommended

### 6. User-Facing VM Dashboard ✓

**What it is:** Comprehensive UI for users to manage their VMs.

**Components:**
- `templates/kvm/dashboard.html`: Full-featured dashboard
- `views.py`: Dashboard view and API endpoints
- `urls.py`: URL routing for dashboard and API

**Features:**
- Grid view of all user VMs
- Real-time state indicators (running, stopped, paused)
- Quick actions (Start, Stop, Restart)
- Console access button
- Snapshot management (expandable section)
- SSH command display
- Auto-refresh VM states (every 30 seconds)
- Resource display (vCPU, RAM, disk, IP)

**Access:**
```
/kvm/dashboard/
```

**API Endpoints:**
```
POST   /kvm/api/vm/{id}/start/    # Start VM
POST   /kvm/api/vm/{id}/stop/     # Stop VM
POST   /kvm/api/vm/{id}/restart/  # Restart VM
GET    /kvm/api/vm/{id}/state/    # Get state
```

### 7. Console Access Logging ✓

**What it is:** Security audit trail for console access.

**Implementation:**
- All console connections logged to `SecurityAuditLog`
- Tracks user, VM, action (connect/disconnect), timestamp, IP address

**Logged Events:**
- `vm_console_connect`: User opened console
- `vm_console_disconnect`: User closed console

**Query Logs:**
```python
from apps.core.models import SecurityAuditLog

# Get all console access for a VM
logs = SecurityAuditLog.objects.filter(
    action__startswith='vm_console_',
    details__deployment_id=deployment_id,
).order_by('-created_at')

# Get console access by user
user_access = SecurityAuditLog.objects.filter(
    user=user,
    action__startswith='vm_console_',
)
```

## URL Configuration

Add to main `urls.py`:

```python
urlpatterns = [
    # ... existing patterns ...
    path('kvm/', include('addons.kvm.urls')),
]
```

## Integration Checklist

- [x] Install Django Channels: `pip install channels channels-redis`
- [x] Configure ASGI application
- [x] Add KVM URLs to main URLconf
- [x] Run migrations
- [x] Ensure Redis is running (for Channels)
- [x] Update noVNC library CDN (or self-host)

## Production Deployment Notes

### WebSocket Configuration

**Nginx Configuration:**
```nginx
location /ws/ {
    proxy_pass http://localhost:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 86400;
}
```

### ASGI Server

Run with Daphne (Channels ASGI server):
```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

Or Uvicorn:
```bash
uvicorn config.asgi:application --host 0.0.0.0 --port 8000
```

### Security

1. **Use WSS (WebSocket Secure)** in production
2. **Set short token expiry** (default 15 minutes)
3. **Enable CORS properly** for WebSocket connections
4. **Rate limit** console connections per user
5. **Monitor** SecurityAuditLog for suspicious activity

## Testing

### Test Console Access

1. Deploy a VM
2. Navigate to `/kvm/dashboard/`
3. Click "Console" button
4. Click "Connect" in console view
5. Should see VM display in browser

### Test Snapshot Management

1. In dashboard, click "Snapshots" on a VM
2. Click "+ Create Snapshot"
3. Enter name and description
4. Verify snapshot appears in list
5. Test restore and delete

### Test Migration

```python
from addons.kvm.migration import VMMigrationService

service = VMMigrationService()
# Create second compute node first
service.migrate_vm(vm, target_node, live=False)
```

### Test Resize

```python
from addons.kvm.resize import VMResizeService

service = VMResizeService()
larger_plan = VMPlan.objects.get(name='medium')
service.resize_vm(vm, larger_plan, resize_disk=True)
```

## Performance Considerations

### noVNC
- noVNC uses WebSocket for VNC traffic
- Bandwidth ~1-5 Mbps per active console
- Consider compression level (default: 2)
- Quality level (default: 6, range 0-9)

### Migration
- Offline migration: Disk copy is bottleneck (rsync over SSH)
- Live migration: Network bandwidth critical
- Block migration without shared storage is slower

### Resize
- vCPU/RAM hot-plug has minimal performance impact
- Disk resize requires VM stop (plan maintenance window)

## Known Limitations

1. **noVNC**: No clipboard sync (browser security)
2. **Live Migration**: Requires compatible CPU types on nodes
3. **Bridge Networking**: Requires root access and network reconfiguration
4. **Resize**: Cannot shrink disk (only grow)

## Troubleshooting

### Console won't connect
- Check Redis is running: `redis-cli ping`
- Check WebSocket route in nginx
- Verify VNC port in database
- Check firewall rules

### Migration fails
- Verify SSH connectivity: `ssh target_node`
- Check rsync is installed
- Ensure sufficient disk space on target
- Check libvirt compatibility

### Resize doesn't apply
- Some changes require VM restart
- Check libvirt logs: `/var/log/libvirt/qemu/<vm>.log`
- Verify guest OS supports hot-plug

## Next: Phase 3

Phase 3 features (multi-node clustering, advanced monitoring, custom ISOs) are documented separately.
