# Docker Addon Discovery Fix

## Issue

The Docker addon was not being discovered by WebOps because the addon loader expects **YAML manifest files** (`.yaml` or `.yml`), but I initially created a JSON file (`addon.json`).

## What Was Fixed

### 1. Created Proper YAML Manifest (`addon.yaml`)

The addon loader in `apps/addons/loader.py` scans the `ADDONS_PATH` directory for `.yaml` or `.yml` files. Changed from:

- ❌ `addons/docker/addon.json` (JSON format - not recognized)

To:

- ✅ `addons/docker/addon.yaml` (YAML format - properly discovered)

### 2. Updated Hook Registration Method

The YAML-based addon system uses a different hook registration approach:

**Old approach (manual registration):**
```python
from apps.addons.registry import hook_registry

@hook_registry.register('pre_deployment', priority=50)
def docker_pre_deployment(context):
    ...
```

**New approach (YAML-based):**
```yaml
# In addon.yaml
hooks:
  pre_deployment:
    - handler: addons.docker.hooks:docker_pre_deployment
      priority: 50
      timeout_ms: 10000
```

```python
# In hooks.py (no decorator needed)
def docker_pre_deployment(context: Dict[str, Any]) -> None:
    ...
```

### 3. YAML Manifest Structure

The complete `addon.yaml` file includes:

```yaml
name: docker
version: 1.0.0
description: Docker containerization support
author: WebOps Team
license: MIT
enabled: true

hooks:
  pre_deployment:
    - handler: addons.docker.hooks:docker_pre_deployment
      priority: 50
      timeout_ms: 10000
      retries: 0
      enforcement: optional

  post_deployment:
    - handler: addons.docker.hooks:docker_post_deployment
      priority: 50
      timeout_ms: 600000
      retries: 0
      enforcement: optional

  service_health_check:
    - handler: addons.docker.hooks:docker_health_check
      priority: 50
      timeout_ms: 5000
      retries: 0
      enforcement: optional

capabilities:
  - container_management
  - dockerfile_generation
  - docker_build
  - health_monitoring

settings_schema:
  default_base_image:
    type: string
    default: "python:3.11-slim"
    description: Default Docker base image
```

## How Addon Discovery Works

1. **App Startup**: Django calls `AddonsConfig.ready()` in `apps/addons/apps.py`

2. **Discovery**: `register_discovered_addons()` scans `ADDONS_PATH` for `.yaml`/`.yml` files

3. **Parsing**: Each YAML manifest is parsed to extract:
   - Metadata (name, version, description, etc.)
   - Hook definitions (event, handler, priority, timeout, etc.)

4. **Registration**: For each hook definition:
   - Handler function is resolved from the `handler` string (e.g., `addons.docker.hooks:docker_pre_deployment`)
   - Hook is registered with the global `hook_registry`
   - Addon record is created/updated in the database

5. **Execution**: When a deployment event occurs, the `AddonManager` triggers registered hooks

## Verifying the Fix

To verify the Docker addon is now discoverable:

1. **Check the addons directory structure:**
   ```bash
   ls -la control-panel/addons/docker/
   # Should show: addon.yaml, docker_service.py, hooks.py, __init__.py, README.md
   ```

2. **Restart WebOps** (to trigger addon discovery):
   ```bash
   # If using development server
   python manage.py runserver

   # If using systemd
   sudo systemctl restart webops-control-panel
   ```

3. **Check logs for addon discovery:**
   ```
   Addons discovered and hooks registered at startup.
   ```

4. **Verify in database:**
   ```bash
   python manage.py shell
   >>> from apps.addons.models import Addon
   >>> Addon.objects.filter(name='docker').exists()
   True
   >>> docker_addon = Addon.objects.get(name='docker')
   >>> print(docker_addon.name, docker_addon.version, docker_addon.enabled)
   docker 1.0.0 True
   ```

5. **Check registered hooks:**
   ```bash
   python manage.py shell
   >>> from apps.addons.registry import hook_registry
   >>> pre_hooks = hook_registry.get_hooks('pre_deployment')
   >>> [h.addon_name for h in pre_hooks if h.addon_name == 'docker']
   ['docker']
   ```

## Files Changed

### New Files:
- `addons/docker/addon.yaml` - Proper YAML manifest

### Modified Files:
- `addons/docker/hooks.py` - Removed decorator-based registration
- `addons/docker/addon.json.bak` - Backed up old JSON file

### Removed:
- Decorator imports from `hook_registry`
- Manual `@hook_registry.register()` decorators

## Summary

The Docker addon will now be:
- ✅ Automatically discovered on WebOps startup
- ✅ Registered in the database as an Addon record
- ✅ Have its hooks registered in the hook registry
- ✅ Execute during deployment workflows

The issue was simply a file format mismatch - the addon system expected YAML but we provided JSON. The fix ensures compatibility with WebOps' addon discovery system.
