# Addon Enable/Disable System

## Overview

WebOps now has a comprehensive addon enable/disable system that ensures disabled addons:
- ✅ Don't load their hooks during startup
- ✅ Don't appear in the UI (deployment forms, etc.)
- ✅ Don't consume system resources
- ✅ Can be easily toggled on/off without code changes

## How It Works

### 1. **Database-Driven Control**

Each addon has an `enabled` field in the database:

```python
class Addon(BaseModel):
    name = models.CharField(max_length=200, unique=True)
    enabled = models.BooleanField(default=True)  # ← Controls addon state
    # ... other fields
```

### 2. **Loader Respects Enabled State**

The addon loader (`apps/addons/loader.py`) checks the `enabled` field before registering hooks:

```python
def register_discovered_addons(registry, addons_path):
    for addon in addons:
        # Sync DB record first
        sync_addon_record(meta, addon['manifest_path'])

        # Check if enabled
        addon_record = Addon.objects.get(name=name)
        if not addon_record.enabled:
            logger.info(f"Skipping disabled addon '{name}'")
            continue  # ← Skip hook registration

        # Register hooks (only for enabled addons)
        register_hooks(...)
```

**Result:** Disabled addons' hooks are never registered, so they never execute.

### 3. **Template Context Processor**

A context processor (`apps/addons/context_processors.py`) makes enabled addons available in all templates:

```python
def enabled_addons(request):
    return {
        'enabled_addon_names': {'docker', 'monitoring', ...},  # Set of enabled addon names
        'addon_capabilities': {'container_management', ...},   # All capabilities
        'enabled_addons': {...},                               # Full addon info
    }
```

**Result:** Templates can conditionally show features based on enabled addons.

### 4. **Conditional UI Rendering**

Templates check if an addon is enabled before showing its features:

```django
{% if 'docker' in enabled_addon_names %}
    <!-- Docker options section -->
    <div class="webops-card">
        <h4>Docker Containerization</h4>
        <!-- Docker configuration fields -->
    </div>
{% endif %}
```

**Result:** Disabled addons don't appear in the UI at all.

## Managing Addons

### Method 1: Management Command (Recommended)

```bash
# List all addons
python manage.py addon list

# Enable an addon
python manage.py addon enable docker

# Disable an addon
python manage.py addon disable docker

# Show detailed info about an addon
python manage.py addon info docker

# Reload addons (re-discover and re-register)
python manage.py addon reload
```

#### Example Output:

```
$ python manage.py addon list

WebOps Addons:
================================================================================

docker (v1.0.0)
  Status: ✓ ENABLED
  Description: Docker containerization support for deployments
  Author: WebOps Team
  Capabilities: container_management, dockerfile_generation, docker_build
  Metrics: 15 success, 2 failures (88.2% success rate)

monitoring (v1.0.0)
  Status: ✗ DISABLED
  Description: Advanced monitoring and alerting
  Author: WebOps Team

================================================================================
Total: 2 addons (1 enabled, 1 disabled)
```

### Method 2: Django Admin

1. **Access admin panel:** `/admin/addons/addon/`
2. **View addon list:** See all addons with their status, metrics, and capabilities
3. **Enable/Disable individual addon:**
   - Click on addon name
   - Toggle "Enabled" checkbox
   - Save
4. **Bulk actions:**
   - Select multiple addons
   - Choose "Enable selected addons" or "Disable selected addons"
   - Apply

**Features:**
- Color-coded status (✓ Enabled in green, ✗ Disabled in red)
- Success rate with color indicators
- Capabilities display
- Metrics tracking (success/failure counts)
- Read-only fields (name, version, manifest path, etc.)
- Cannot add/delete addons manually (managed by discovery)

### Method 3: Python Shell

```python
python manage.py shell
```

```python
from apps.addons.models import Addon

# Disable an addon
docker = Addon.objects.get(name='docker')
docker.enabled = False
docker.save()

# Enable an addon
docker.enabled = True
docker.save()

# Disable all addons
Addon.objects.all().update(enabled=False)

# Enable specific addons
Addon.objects.filter(name__in=['docker', 'monitoring']).update(enabled=True)
```

### Method 4: Direct Database (Not Recommended)

```sql
-- Disable an addon
UPDATE addons SET enabled = false WHERE name = 'docker';

-- Enable an addon
UPDATE addons SET enabled = true WHERE name = 'docker';
```

## Important Notes

### 🔴 Restart Required

**Changes to addon enabled/disabled state require a WebOps restart to take effect.**

This is because hooks are registered during application startup in `AddonsConfig.ready()`.

```bash
# Development
# Stop current runserver (Ctrl+C), then:
python manage.py runserver

# Production
sudo systemctl restart webops-control-panel
```

### Why Restart is Needed

1. **Hooks are registered at startup:** The `register_discovered_addons()` function runs once during Django app initialization
2. **Hook registry is static:** Once hooks are registered, they remain in memory until the process restarts
3. **No dynamic unloading:** Python doesn't support truly unloading modules dynamically

**Future Enhancement:** Could implement a reload mechanism that clears and re-registers hooks without restart (but restart is safer).

## Use Cases

### Scenario 1: Disabling Docker Addon

**When:** Docker not installed on server, or not using containerization

```bash
# Disable Docker addon
python manage.py addon disable docker

# Restart WebOps
sudo systemctl restart webops-control-panel
```

**Result:**
- Docker options disappear from deployment form
- Docker hooks don't execute during deployments
- No Docker-related errors or overhead

### Scenario 2: Temporary Troubleshooting

**When:** An addon is causing issues and needs to be temporarily disabled

```bash
# Disable problematic addon
python manage.py addon disable problematic-addon

# Restart to apply changes
sudo systemctl restart webops-control-panel

# ... troubleshoot ...

# Re-enable when fixed
python manage.py addon enable problematic-addon
sudo systemctl restart webops-control-panel
```

### Scenario 3: Feature Flags

**When:** Gradually rolling out new features

```bash
# Initially disable new addon
python manage.py addon disable new-feature

# ... addon discovered and synced, but disabled ...

# When ready to activate
python manage.py addon enable new-feature
sudo systemctl restart webops-control-panel
```

### Scenario 4: Environment-Specific Addons

**When:** Different addons for dev vs. production

```bash
# Development: Enable debug addons
python manage.py addon enable dev-tools
python manage.py addon enable profiling

# Production: Disable debug addons
python manage.py addon disable dev-tools
python manage.py addon disable profiling
python manage.py addon enable monitoring
python manage.py addon enable alerting
```

## Implementation Details

### Files Modified/Created

1. **`apps/addons/loader.py`** - Added enabled check before hook registration
2. **`apps/addons/context_processors.py`** - NEW - Template context for enabled addons
3. **`apps/addons/management/commands/addon.py`** - NEW - Management command
4. **`apps/addons/admin.py`** - Enhanced with enable/disable actions
5. **`config/settings.py`** - Added context processor to TEMPLATES
6. **`templates/deployments/create.html`** - Conditional Docker section rendering

### Context Processor Registration

In `config/settings.py`:

```python
TEMPLATES = [
    {
        'OPTIONS': {
            'context_processors': [
                # ... existing processors ...
                'apps.addons.context_processors.enabled_addons',  # ← Added
            ],
        },
    },
]
```

### Template Variables Available

After adding the context processor, these variables are available in ALL templates:

```python
# In any template:
{{ enabled_addon_names }}      # Set of enabled addon names
{{ addon_capabilities }}        # Set of all capabilities from enabled addons
{{ enabled_addons }}            # Dict of addon details

# Usage examples:
{% if 'docker' in enabled_addon_names %}
    <!-- Show Docker features -->
{% endif %}

{% if 'container_management' in addon_capabilities %}
    <!-- Show container management UI -->
{% endif %}

{{ enabled_addons.docker.version }}  # Access specific addon info
```

## Testing the System

### 1. Verify Addon Discovery

```bash
python manage.py addon list
```

Should show Docker addon as enabled by default.

### 2. Test Disabling Docker

```bash
# Disable Docker
python manage.py addon disable docker

# Restart WebOps
python manage.py runserver  # or sudo systemctl restart webops-control-panel
```

**Expected behavior:**
- Docker section **disappears** from deployment form
- No Docker-related errors in logs
- Existing Docker deployments still work (but can't create new ones)

### 3. Test Enabling Docker

```bash
# Enable Docker
python manage.py addon enable docker

# Restart WebOps
python manage.py runserver
```

**Expected behavior:**
- Docker section **reappears** in deployment form
- Docker hooks execute during deployments
- Can create new Docker deployments

### 4. Verify in Admin

1. Go to `/admin/addons/addon/`
2. Check Docker addon status
3. Try toggling enabled checkbox
4. Verify success message mentions restart requirement

### 5. Check Context in Templates

Create a test template:

```django
<!-- test_template.html -->
<h1>Enabled Addons Test</h1>

<h2>Addon Names:</h2>
<ul>
    {% for name in enabled_addon_names %}
        <li>{{ name }}</li>
    {% endfor %}
</ul>

<h2>Capabilities:</h2>
<ul>
    {% for cap in addon_capabilities %}
        <li>{{ cap }}</li>
    {% endfor %}
</ul>

<h2>Docker Status:</h2>
{% if 'docker' in enabled_addon_names %}
    <p style="color: green;">Docker addon is enabled</p>
{% else %}
    <p style="color: red;">Docker addon is disabled</p>
{% endif %}
```

## Troubleshooting

### Addon still appears after disabling

**Problem:** Docker section still shows in deployment form

**Solution:**
1. Verify addon is disabled: `python manage.py addon list`
2. Ensure you restarted WebOps
3. Clear browser cache (hard refresh: Ctrl+Shift+R)
4. Check logs for errors during startup

### Hooks still executing after disabling

**Problem:** Disabled addon hooks are still running

**Solution:**
1. Confirm restart happened: `ps aux | grep manage.py` or `systemctl status webops-control-panel`
2. Check for errors in startup logs
3. Verify hook registry: `python manage.py addon info docker`

### Context processor not working

**Problem:** `enabled_addon_names` not available in templates

**Solution:**
1. Verify context processor in settings:
   ```bash
   grep -A 10 "context_processors" control-panel/config/settings.py
   ```
2. Should include: `apps.addons.context_processors.enabled_addons`
3. Restart WebOps after adding

### Database vs. Memory Mismatch

**Problem:** Addon shows as disabled in database but hooks are executing

**Solution:**
- This happens when DB is updated but WebOps not restarted
- **Always restart after changing enabled status**

## Best Practices

1. **Always restart after enable/disable changes**
2. **Use management command for consistency:**
   ```bash
   python manage.py addon disable docker
   # Instead of: direct database update
   ```

3. **Document environment-specific addon states:**
   ```bash
   # production.txt
   docker: enabled
   dev-tools: disabled
   monitoring: enabled

   # development.txt
   docker: enabled
   dev-tools: enabled
   monitoring: disabled
   ```

4. **Check addon status before deployments:**
   ```bash
   python manage.py addon list
   ```

5. **Monitor addon metrics:**
   - Check success rates in admin
   - Review `last_error` field for issues
   - Use `addon info` command for detailed metrics

## Security Considerations

- Addons cannot be manually created via admin (only discovered)
- Addons cannot be deleted via admin (managed by discovery)
- Enabling/disabling requires admin access
- Hook execution is isolated with timeouts and error handling

## Performance Impact

### Enabled Addons
- Hooks execute during deployment events (minimal overhead)
- Context processor runs once per request (cached by Django)

### Disabled Addons
- **Zero overhead** - hooks not registered, not executed
- No performance impact from disabled addons

## Future Enhancements

1. **Hot Reload:** Reload addons without restarting WebOps
2. **Addon Dependencies:** Auto-enable/disable dependent addons
3. **Scheduled Enable/Disable:** Time-based addon activation
4. **Addon Permissions:** Per-user addon access control
5. **Addon Health Dashboard:** Real-time metrics and monitoring
6. **Addon Configuration UI:** Web-based settings management

## Summary

The addon enable/disable system provides:
- ✅ **Complete control** over addon activation
- ✅ **Zero overhead** for disabled addons
- ✅ **Clean UI** - disabled addons don't appear
- ✅ **Multiple management methods** (CLI, admin, code)
- ✅ **Safety** - requires restart to prevent inconsistent state
- ✅ **Visibility** - clear status and metrics

Disabled addons truly don't impact the system - they're skipped during discovery, their hooks aren't registered, and their UI elements don't render.
