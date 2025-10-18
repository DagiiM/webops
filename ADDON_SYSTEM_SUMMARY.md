# WebOps Addon Enable/Disable System - Summary

## What Was Implemented

A complete addon enable/disable system that ensures disabled addons are truly inactive across the entire WebOps system.

## Key Features

### 1. **Database-Driven Control**
- Each addon has an `enabled` field (Boolean)
- Default: `True` (enabled)
- Persists across restarts

### 2. **Smart Loader**
- Checks `enabled` field before registering hooks
- Skips disabled addons completely
- Logs skipped addons for visibility

### 3. **Template Context**
- All templates have access to enabled addon info
- Variables: `enabled_addon_names`, `addon_capabilities`, `enabled_addons`
- UI elements conditionally render based on addon state

### 4. **Management Command**
```bash
python manage.py addon list              # List all addons
python manage.py addon enable docker     # Enable addon
python manage.py addon disable docker    # Disable addon
python manage.py addon info docker       # Detailed info
python manage.py addon reload            # Reload all addons
```

### 5. **Admin Interface**
- View all addons with status, metrics, capabilities
- Toggle enabled/disabled via checkbox
- Bulk actions: enable/disable multiple addons
- Color-coded status indicators
- Cannot add/delete addons (discovery-managed)

### 6. **Conditional UI**
```django
{% if 'docker' in enabled_addon_names %}
    <!-- Docker options section -->
{% endif %}
```

Docker section only shows when addon is enabled!

## Files Created/Modified

### New Files:
1. `apps/addons/context_processors.py` - Template context for enabled addons
2. `apps/addons/management/__init__.py` - Management module
3. `apps/addons/management/commands/__init__.py` - Commands module
4. `apps/addons/management/commands/addon.py` - Addon management command
5. `ADDON_ENABLE_DISABLE_SYSTEM.md` - Complete documentation

### Modified Files:
1. `apps/addons/loader.py` - Check enabled field, skip disabled addons
2. `apps/addons/admin.py` - Enhanced admin with actions and metrics
3. `config/settings.py` - Added context processor
4. `templates/deployments/create.html` - Conditional Docker section

## How It Works

### Startup Flow:

```
1. Django starts
   ↓
2. AddonsConfig.ready() runs
   ↓
3. discover_addons() finds all addon.yaml files
   ↓
4. sync_addon_record() creates/updates DB records
   ↓
5. For each addon:
   - Check: is addon.enabled == True?
   - YES → Register hooks
   - NO  → Skip (log message)
   ↓
6. Only enabled addon hooks are registered
```

### Request Flow:

```
1. User views deployment form
   ↓
2. Context processor runs
   ↓
3. enabled_addons() checks database
   ↓
4. Returns {enabled_addon_names: {'docker', ...}}
   ↓
5. Template renders:
   {% if 'docker' in enabled_addon_names %}
       <!-- Show Docker section -->
   {% endif %}
   ↓
6. Docker section shows/hides based on addon state
```

## Usage Examples

### Disable Docker Addon

```bash
# 1. Disable
python manage.py addon disable docker
# Output: ✓ Addon "docker" has been disabled.
#         ⚠ You must restart WebOps for changes to take effect

# 2. Restart
sudo systemctl restart webops-control-panel
# OR (development):
# Ctrl+C, then: python manage.py runserver

# 3. Verify
python manage.py addon list
# Output: docker (v1.0.0)
#           Status: ✗ DISABLED
```

**Result:**
- Docker section disappears from deployment form
- Docker hooks don't execute
- No Docker-related overhead

### Enable Docker Addon

```bash
# 1. Enable
python manage.py addon enable docker

# 2. Restart
sudo systemctl restart webops-control-panel

# 3. Verify
python manage.py addon list
# Output: docker (v1.0.0)
#           Status: ✓ ENABLED
```

**Result:**
- Docker section appears in deployment form
- Docker hooks execute during deployments
- Can create Docker deployments

## Important: Restart Required! ⚠️

**Changes to addon enabled/disabled state ALWAYS require a restart.**

Why?
- Hooks are registered during startup in `AddonsConfig.ready()`
- Hook registry is static (not dynamically reloadable)
- Ensures consistent state between database and runtime

## Testing Checklist

- [ ] List addons: `python manage.py addon list`
- [ ] Disable Docker: `python manage.py addon disable docker`
- [ ] Restart WebOps
- [ ] Verify Docker section gone from deployment form
- [ ] Enable Docker: `python manage.py addon enable docker`
- [ ] Restart WebOps
- [ ] Verify Docker section appears in deployment form
- [ ] Check admin: `/admin/addons/addon/`
- [ ] Test bulk enable/disable in admin

## Context Variables Available in Templates

After implementation, all templates have access to:

```python
# Set of enabled addon names
enabled_addon_names = {'docker', 'monitoring', ...}

# Set of all capabilities from enabled addons
addon_capabilities = {'container_management', 'dockerfile_generation', ...}

# Full addon details
enabled_addons = {
    'docker': {
        'enabled': True,
        'version': '1.0.0',
        'capabilities': ['container_management', ...]
    },
    ...
}
```

Usage:
```django
{% if 'docker' in enabled_addon_names %}
    <!-- Docker-specific UI -->
{% endif %}

{% if 'container_management' in addon_capabilities %}
    <!-- Container management features -->
{% endif %}

Version: {{ enabled_addons.docker.version }}
```

## Benefits

1. **True Deactivation**: Disabled addons don't load hooks, don't show in UI, zero overhead
2. **Easy Management**: Simple CLI commands or admin interface
3. **Visibility**: Clear status, metrics, and capabilities in admin
4. **Safety**: Requires restart to prevent inconsistent state
5. **Flexibility**: Multiple ways to manage (CLI, admin, code, database)
6. **Performance**: No performance impact from disabled addons

## Admin Features

- **List View:**
  - Name, Version, Status (color-coded)
  - Capabilities
  - Success Rate (with color indicators)
  - Last Run timestamp
  - Created date

- **Detail View:**
  - All metadata (read-only)
  - Enabled toggle (only editable field)
  - Metrics (success/failure counts, duration)
  - Last error (if any)
  - Capabilities and settings schema

- **Actions:**
  - Enable selected addons (bulk)
  - Disable selected addons (bulk)
  - Shows restart reminder after action

- **Permissions:**
  - Cannot add addons manually
  - Cannot delete addons
  - Can only toggle enabled status

## Documentation

- **`ADDON_ENABLE_DISABLE_SYSTEM.md`** - Complete guide with use cases, troubleshooting
- **`ADDON_DISCOVERY_FIX.md`** - How addon discovery works (YAML manifests)
- **`DOCKER_ADDON_QUICKSTART.md`** - Quick start for Docker addon
- **`DOCKER_ADDON_SUMMARY.md`** - Docker addon implementation details

## Next Steps

1. **Restart WebOps** to ensure context processor is loaded
2. **Test addon management**:
   ```bash
   python manage.py addon list
   python manage.py addon info docker
   ```
3. **Test in UI**: Create deployment, verify Docker section shows/hides
4. **Test in Admin**: `/admin/addons/addon/` - enable/disable Docker
5. **Create more addons** following the same pattern!

## Summary

The enable/disable system provides complete control over addon activation:
- ✅ Disabled addons = no hooks registered
- ✅ Disabled addons = no UI elements
- ✅ Disabled addons = zero overhead
- ✅ Easy management via CLI or admin
- ✅ All changes require restart (consistent state)

**Disabled addons are truly inactive across the entire system!**
