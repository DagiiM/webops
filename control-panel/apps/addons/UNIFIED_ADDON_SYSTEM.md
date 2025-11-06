# Unified Addon System

The WebOps Unified Addon System provides a consistent interface for managing both API-level (Python/Django) and system-level (Bash) addons through a single registry and management system.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Addon Types](#addon-types)
4. [System Addon Contract](#system-addon-contract)
5. [Usage](#usage)
6. [API Reference](#api-reference)
7. [Best Practices](#best-practices)

## Overview

### Why Unified Addons?

Previously, WebOps had two separate addon systems:
- **API-level addons** (Python/Django) - Docker, KVM application layer
- **System-level addons** (Bash) - PostgreSQL, Kubernetes, etcd, monitoring

The unified system bridges these layers, providing:
- ✅ Single interface for all addons
- ✅ Centralized management through Django admin and API
- ✅ Async operations via Celery for long-running tasks
- ✅ Database state tracking with audit trail
- ✅ Health monitoring and metrics collection
- ✅ Dependency management and conflict detection

### Key Features

- **Auto-discovery**: Automatically finds and registers addons
- **Async execution**: Long-running operations run in background via Celery
- **State management**: Database tracks installation status, health, and history
- **Audit trail**: All operations logged with execution details
- **Health monitoring**: Periodic health checks with alerting
- **Configuration management**: Centralized config with versioning

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Django Control Panel                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Unified Addon Registry                       │   │
│  │  - Auto-discovery                                    │   │
│  │  - Unified interface                                 │   │
│  │  - Dependency resolution                             │   │
│  └──────────┬───────────────────────────┬───────────────┘   │
│             │                            │                    │
│  ┌──────────▼──────────┐    ┌───────────▼───────────┐       │
│  │   Application        │    │   System Addon        │       │
│  │   Addons             │    │   Wrapper             │       │
│  │   (Python)           │    │   (Bash Bridge)       │       │
│  └─────────────────────┘    └──────────┬────────────┘       │
│                                         │                     │
└─────────────────────────────────────────┼─────────────────────┘
                                          │
            ┌─────────────────────────────▼─────────────────┐
            │         System Addons (.sh scripts)           │
            ├───────────────────────────────────────────────┤
            │ • postgresql.sh  • kubernetes.sh              │
            │ • etcd.sh        • monitoring.sh              │
            │ • patroni.sh     • kvm.sh                     │
            │ • autorecovery.sh                             │
            └───────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  Database State Management                   │
├─────────────────────────────────────────────────────────────┤
│ • SystemAddon - addon records and state                     │
│ • AddonExecution - operation audit trail                    │
│ • Addon - application addon metadata                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     Celery Task Queue                        │
├─────────────────────────────────────────────────────────────┤
│ • install_system_addon - async installation                 │
│ • uninstall_system_addon - async uninstallation             │
│ • configure_system_addon - async configuration              │
│ • health_check_system_addons - periodic health checks       │
│ • sync_system_addon_status - status synchronization         │
└─────────────────────────────────────────────────────────────┘
```

## Addon Types

### 1. System Addons (Bash)

**Location**: `provisioning/versions/v1.0.0/addons/*.sh`

**Purpose**: Infrastructure provisioning and system-level configuration

**Examples**:
- PostgreSQL database setup
- Kubernetes cluster installation
- Monitoring stack (Prometheus + Grafana)
- High availability (etcd, Patroni)

**Characteristics**:
- Written in Bash
- Run with elevated privileges via sudo
- Handle OS package installation
- Configure system services
- Manage infrastructure

### 2. Application Addons (Python)

**Location**: `control-panel/addons/*/`

**Purpose**: Application-level features within Django

**Examples**:
- Docker containerization
- KVM virtual machine management (API layer)

**Characteristics**:
- Written in Python/Django
- Integrate with hook registry
- Provide UI and API
- Manage application deployments

## System Addon Contract

All bash-based system addons **MUST** implement these functions:

### Required Functions

#### 1. `addon_metadata()`

Returns JSON with addon information:

```bash
addon_metadata() {
    cat <<'EOF'
{
  "name": "postgresql",
  "display_name": "PostgreSQL Database",
  "version": "14.0.0",
  "description": "PostgreSQL relational database server",
  "category": "database",
  "maintainer": "WebOps Team",
  "depends": [],
  "provides": ["postgresql"],
  "conflicts": ["mysql"]
}
EOF
}
```

#### 2. `addon_validate()`

Pre-flight validation checks:

```bash
addon_validate() {
    local errors=()
    local warnings=()

    # Check prerequisites
    if ! command -v systemctl &>/dev/null; then
        errors+=("systemd is required")
    fi

    # Build JSON response
    cat <<EOF
{
  "valid": true,
  "errors": [],
  "warnings": []
}
EOF
}
```

#### 3. `addon_install()`

Install the addon:

```bash
addon_install() {
    # Read config from stdin (JSON)
    local config=$(cat)

    # Installation logic
    log_step "Installing PostgreSQL..."
    pkg_install postgresql-14

    # Return success
    return 0
}
```

#### 4. `addon_uninstall()`

Uninstall the addon:

```bash
addon_uninstall() {
    local keep_data="${1:-true}"

    # Uninstallation logic
    systemctl stop postgresql
    pkg_remove postgresql-14

    if [[ "$keep_data" == "false" ]]; then
        rm -rf /var/lib/postgresql
    fi

    return 0
}
```

#### 5. `addon_status()`

Get current status:

```bash
addon_status() {
    local status="not_installed"
    local health="unknown"

    if systemctl is-active --quiet postgresql; then
        status="installed"
        health="healthy"
    fi

    cat <<EOF
{
  "status": "$status",
  "health": "$health",
  "version": "14.0",
  "message": "",
  "details": {}
}
EOF
}
```

#### 6. `addon_configure()`

Apply configuration:

```bash
addon_configure() {
    # Read config from stdin (JSON)
    local config=$(cat)

    # Parse and apply
    local port=$(echo "$config" | jq -r '.port // 5432')

    # Update configuration
    # Restart service
    systemctl restart postgresql

    return 0
}
```

### Optional Functions

- `addon_health_check()` - Detailed health check
- `addon_metrics()` - Return metrics
- `addon_backup()` - Create backup
- `addon_restore()` - Restore from backup

### Status Values

**Installation Status**:
- `not_installed` - Addon not yet installed
- `installing` - Installation in progress
- `installed` - Successfully installed
- `configuring` - Configuration in progress
- `failed` - Installation/operation failed
- `uninstalling` - Uninstallation in progress
- `degraded` - Installed but unhealthy

**Health Status**:
- `healthy` - Operating normally
- `unhealthy` - Not functioning
- `degraded` - Partially functional
- `unknown` - Unable to determine

## Usage

### Discovery

Discover all system addons:

```bash
cd control-panel
python manage.py discover_addons
```

With status sync and health check:

```bash
python manage.py discover_addons --sync-status --health-check
```

### Python API

```python
from apps.addons.unified_registry import get_addon_registry

# Get registry
registry = get_addon_registry()

# Discover addons
count = registry.discover_system_addons()

# List all addons
addons = registry.list()

# Get specific addon
postgres = registry.get('postgresql')

# Install addon (async)
task_id = registry.install('postgresql', config={'port': 5433}, user_id=1)

# Configure addon
task_id = registry.configure('postgresql', config={'max_connections': 200})

# Uninstall addon
task_id = registry.uninstall('postgresql', keep_data=True)

# Health check all addons
result = registry.health_check_all()
```

### Celery Tasks

```python
from apps.addons.tasks import (
    install_system_addon,
    uninstall_system_addon,
    configure_system_addon,
    health_check_system_addons,
    sync_system_addon_status
)

# Install addon asynchronously
task = install_system_addon.delay(
    addon_id=1,
    config={'port': 5432},
    user_id=1
)

# Check task status
from celery.result import AsyncResult
result = AsyncResult(task.id)
print(result.status)
print(result.result)
```

### Django Admin

1. Navigate to `/admin/addons/systemaddon/`
2. View all discovered addons
3. Click addon to view details
4. Use actions:
   - "Sync status from system" - Sync status from bash scripts
   - "Run health checks" - Perform health checks

### Database Queries

```python
from apps.addons.models import SystemAddon, AddonExecution

# Get installed addons
installed = SystemAddon.objects.filter(status='installed')

# Get healthy addons
healthy = SystemAddon.objects.filter(health='healthy')

# Get addon by name
postgres = SystemAddon.objects.get(name='postgresql')

# Get execution history
executions = postgres.executions.all().order_by('-started_at')

# Get failed executions
failures = AddonExecution.objects.filter(status='failed')
```

## API Reference

### BaseAddon Interface

All addons implement this interface:

```python
class BaseAddon(ABC):
    @property
    def metadata(self) -> AddonMetadata
    @property
    def addon_type(self) -> AddonType

    def validate(self) -> ValidationResult
    def install(self, config: Optional[Dict] = None) -> Dict
    def uninstall(self, keep_data: bool = True) -> Dict
    def configure(self, config: Dict) -> Dict
    def get_status(self) -> AddonStatusInfo
    def get_config(self) -> Dict
    def health_check(self) -> AddonHealth
    def register_hooks(self) -> None
    def get_metrics(self) -> Dict
```

### SystemAddonWrapper

Wraps bash addons to implement BaseAddon:

```python
wrapper = SystemAddonWrapper(
    script_path=Path('/path/to/addon.sh'),
    db_instance=system_addon_instance
)

# All BaseAddon methods available
metadata = wrapper.metadata
status = wrapper.get_status()
result = wrapper.install(config={'port': 5432})
```

### AddonRegistry

Central registry for all addons:

```python
registry = get_addon_registry()

# Discovery
count = registry.discover_all()
count = registry.discover_system_addons()
count = registry.discover_application_addons()

# Retrieval
addon = registry.get('postgresql')
all_addons = registry.list()
system_addons = registry.list_system_addons()
db_addons = registry.get_by_category('database')

# Operations (async via Celery)
task_id = registry.install('postgresql', config={}, user_id=1)
task_id = registry.uninstall('postgresql', keep_data=True)
task_id = registry.configure('postgresql', config={})
result = registry.health_check_all()
```

## Best Practices

### 1. Addon Development

**System Addons**:
- Start with the template: `provisioning/versions/v1.0.0/addons/addon-template.sh`
- Implement all required functions
- Use JSON for all output
- Handle errors gracefully
- Log operations using `log_*` functions
- Make operations idempotent (safe to run multiple times)

**Application Addons**:
- Implement BaseAddon interface
- Use dependency injection
- Write comprehensive tests
- Document configuration options

### 2. Configuration Management

- Store configuration in Django database
- Generate config files for bash addons
- Version configurations
- Validate before applying
- Backup before changes

### 3. Error Handling

- Always return appropriate exit codes
- Provide detailed error messages
- Log errors for debugging
- Update database state on failures
- Support retry logic

### 4. Security

- Run bash addons with least privilege
- Validate all inputs
- Sanitize configuration values
- Use encrypted storage for secrets
- Audit all operations

### 5. Testing

- Test discovery process
- Test all addon operations
- Mock bash script execution
- Test failure scenarios
- Verify database state updates

### 6. Monitoring

- Enable periodic health checks
- Set up alerting for failures
- Monitor execution times
- Track success rates
- Review audit logs

## Example: Creating a New System Addon

### Step 1: Create the Bash Script

```bash
cp provisioning/versions/v1.0.0/addons/addon-template.sh \
   provisioning/versions/v1.0.0/addons/redis.sh
```

### Step 2: Implement Required Functions

```bash
#!/bin/bash
set -euo pipefail

addon_metadata() {
    cat <<'EOF'
{
  "name": "redis",
  "display_name": "Redis Cache",
  "version": "7.0.0",
  "description": "In-memory data structure store",
  "category": "cache",
  "provides": ["redis"],
  "conflicts": ["memcached"]
}
EOF
}

addon_install() {
    pkg_install redis-server
    systemctl enable --now redis-server
    return 0
}

# ... implement other functions
```

### Step 3: Discover and Test

```bash
cd control-panel
python manage.py discover_addons
```

### Step 4: Install via API

```python
from apps.addons.unified_registry import get_unified_registry

registry = get_unified_registry()
task_id = registry.install('redis', user_id=1)
```

### Step 5: Monitor

Check Django admin at `/admin/addons/systemaddon/` to view status.

## Troubleshooting

### Addon Not Discovered

1. Check script is executable: `chmod +x addon.sh`
2. Verify script path is correct
3. Check `addon_metadata()` returns valid JSON
4. Run discovery command with verbose output

### Installation Fails

1. Check execution logs in Django admin
2. Review stdout/stderr in AddonExecution record
3. Test bash function directly: `bash addon.sh install`
4. Verify prerequisites are met

### Health Check Issues

1. Ensure `addon_status()` is implemented
2. Check systemd service status
3. Review health check task logs
4. Manually run: `bash addon.sh status`

### Database State Out of Sync

1. Run status sync: `python manage.py discover_addons --sync-status`
2. Check for stuck "installing" status
3. Review Celery task status
4. Manually update database if needed

## Migration Guide

### From Legacy System to Unified

1. **Backup existing data**
2. **Run migrations**: `python manage.py migrate`
3. **Discover addons**: `python manage.py discover_addons`
4. **Sync status**: `python manage.py discover_addons --sync-status`
5. **Verify in admin**: Check `/admin/addons/systemaddon/`
6. **Update code**: Use new unified registry API

### Backward Compatibility

- Existing hook registry still works for application addons
- Legacy `Addon` model preserved
- New system addons use `SystemAddon` model
- Both systems can coexist during migration

## Future Enhancements

- [ ] Web UI for addon management
- [ ] API endpoints for programmatic access
- [ ] Addon marketplace/repository
- [ ] Automatic updates and versioning
- [ ] Enhanced dependency resolution
- [ ] Rollback support
- [ ] Addon templates/scaffolding
- [ ] Integration tests framework

## Contributing

When contributing new addons:

1. Follow the addon contract
2. Write comprehensive documentation
3. Include tests
4. Update this documentation
5. Submit PR with example usage

## Support

- Documentation: `/control-panel/apps/addons/UNIFIED_ADDON_SYSTEM.md`
- Template: `provisioning/versions/v1.0.0/addons/addon-template.sh`
- Issues: https://github.com/anthropics/webops/issues
