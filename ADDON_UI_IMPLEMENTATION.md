# Addon UI Enable/Disable Implementation

## Summary

Added a comprehensive Web UI for managing addons, allowing users to enable/disable addons directly from the WebOps interface without using the command line or admin panel.

## What Was Implemented

### 1. **Enhanced Views** (`apps/addons/views.py`)

Created multiple view functions:

- **`addons_list`** - Main addons page showing all addons with stats
- **`addon_toggle`** - Toggle addon enabled/disabled (POST)
- **`addon_enable`** - Enable specific addon (POST)
- **`addon_disable`** - Disable specific addon (POST)
- **`addon_detail`** - Detailed addon information page
- **`addon_toggle_ajax`** - AJAX endpoint for instant toggle (future enhancement)

**Features:**
- Statistics calculation (enabled/disabled counts)
- Hook count per addon
- Success rate calculation
- Confirmation dialogs before enable/disable
- Restart reminders

### 2. **Updated Template** (`templates/addons/list.html`)

Enhanced the existing addons list template with:

**New Features:**
- ✅ **Enable/Disable Buttons** - Per-addon toggle controls
- ✅ **Details Button** - Link to addon detail page
- ✅ **Restart Warning** - Prominent reminder about restart requirement
- ✅ **Success Messages** - Django messages framework integration
- ✅ **Confirmation Dialogs** - JavaScript confirm before toggle
- ✅ **Visual Status** - Color-coded enabled/disabled badges
- ✅ **Metrics Display** - Success rate, total runs, last run time
- ✅ **Error Display** - Shows last error if any
- ✅ **Capabilities Tags** - Shows addon capabilities

**UI Elements:**
```html
<!-- Enable button (for disabled addons) -->
<button class="webops-addon-action-button webops-addon-action-success">
    <span class="material-icons">power_settings_new</span>
    Enable
</button>

<!-- Disable button (for enabled addons) -->
<button class="webops-addon-action-button webops-addon-action-danger">
    <span class="material-icons">power_settings_new</span>
    Disable
</button>

<!-- Details link -->
<a href="/addons/docker/" class="webops-addon-action-button webops-addon-action-secondary">
    <span class="material-icons">info</span>
    Details
</a>
```

### 3. **URL Configuration** (`apps/addons/urls.py`)

Updated URL patterns:

```python
urlpatterns = [
    path('', views.addons_list, name='addons_list'),
    path('<str:addon_name>/', views.addon_detail, name='addon_detail'),
    path('<str:addon_name>/toggle/', views.addon_toggle, name='addon_toggle'),
    path('<str:addon_name>/enable/', views.addon_enable, name='addon_enable'),
    path('<str:addon_name>/disable/', views.addon_disable, name='addon_disable'),
    path('<str:addon_name>/toggle-ajax/', views.addon_toggle_ajax, name='addon_toggle_ajax'),
]
```

### 4. **Navigation Update** (`templates/components/aside.html`)

Fixed the Addons navigation link:
- Changed from `{% url 'addons:list' %}` to `{% url 'addons:addons_list' %}`
- Link already exists in sidebar under "Management" section

## How It Works

### User Workflow:

1. **Navigate to Addons Page**
   - Click "Addons" in sidebar
   - URL: `/addons/`

2. **View Addon Status**
   - See all addons with enabled/disabled status
   - View metrics (success rate, runs, last run)
   - See capabilities and descriptions

3. **Enable/Disable Addon**
   - Click "Enable" or "Disable" button
   - Confirm in dialog popup
   - See success message
   - **Reminder: Restart required!**

4. **Restart WebOps**
   - Changes take effect after restart
   - Hooks are re-registered based on new state

### Technical Flow:

```
1. User clicks "Disable" on Docker addon
   ↓
2. Confirmation dialog appears:
   "This will disable the docker addon. A restart is required. Continue?"
   ↓
3. User confirms
   ↓
4. POST request to /addons/docker/toggle/
   ↓
5. View toggles addon.enabled = False
   ↓
6. Saves to database
   ↓
7. Redirects back to /addons/
   ↓
8. Success message displayed:
   "Addon 'docker' has been disabled. Restart WebOps for changes to take effect."
   ↓
9. User restarts WebOps
   ↓
10. Loader skips disabled addons
    ↓
11. Docker section disappears from deployment form
```

## UI Screenshots (Description)

### Addons List Page

```
┌─────────────────────────────────────────────────────────┐
│ Addons                                                   │
│ Manage and monitor your installed addons                │
├─────────────────────────────────────────────────────────┤
│ ⚠ Restart Required: Changes to addon enabled/disabled   │
│   status require a WebOps restart to take effect.       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ ┌─────────────────────────────────┐                     │
│ │ 📦 docker          v1.0.0   ✓  │                     │
│ │ by WebOps Team                  │                     │
│ │                                 │                     │
│ │ Docker containerization support │                     │
│ │                                 │                     │
│ │ Capabilities:                   │                     │
│ │ [container_management]          │                     │
│ │ [dockerfile_generation]         │                     │
│ │                                 │                     │
│ │ Hooks: 3    Success Rate: 95%  │                     │
│ │ Total: 20   Last: 2 mins ago   │                     │
│ │                                 │                     │
│ │ [Details] [Disable]             │                     │
│ └─────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

### Addon Card States

**Enabled Addon:**
- Green "✓ Enabled" badge
- Full opacity
- Red "Disable" button
- Shows hook count and metrics

**Disabled Addon:**
- Gray "✗ Disabled" badge
- Reduced opacity (70%)
- Green "Enable" button
- Hook count shows 0

## API Endpoints

### List Addons
```
GET /addons/
Returns: HTML page with all addons
```

### Toggle Addon
```
POST /addons/docker/toggle/
CSRF: Required
Returns: Redirect to /addons/ with success message
```

### Enable Addon
```
POST /addons/docker/enable/
CSRF: Required
Returns: Redirect to /addons/ with success message
```

### Disable Addon
```
POST /addons/docker/disable/
CSRF: Required
Returns: Redirect to /addons/ with success message
```

### Addon Detail
```
GET /addons/docker/
Returns: HTML page with detailed addon info
```

### AJAX Toggle (Future)
```
POST /addons/docker/toggle-ajax/
CSRF: Required
Returns: JSON response
{
    "success": true,
    "enabled": false,
    "message": "Addon 'docker' has been disabled...",
    "action": "disabled"
}
```

## CSS Classes Added

```css
/* Alert Messages */
.webops-addon-alert
.webops-addon-alert-success
.webops-addon-alert-warning
.webops-addon-alert-info

/* Action Buttons */
.webops-addon-action-button
.webops-addon-action-secondary    /* Details button */
.webops-addon-action-success       /* Enable button */
.webops-addon-action-danger        /* Disable button */
```

## User Experience Features

### 1. **Confirmation Dialogs**
```javascript
onsubmit="return confirm('This will disable the docker addon. A restart is required. Continue?');"
```

Prevents accidental enable/disable.

### 2. **Visual Feedback**
- Success messages in green
- Warning messages in yellow/orange
- Error messages in red (if any)
- Status badges (✓ Enabled / ✗ Disabled)

### 3. **Restart Reminders**
- Persistent warning banner at top of page
- Included in every success message
- Prevents confusion about why changes don't take effect immediately

### 4. **Hover Effects**
```css
.webops-addon-action-button:hover {
    transform: translateY(-1px);
}
```

Buttons lift slightly on hover for better UX.

## Integration with Existing System

### Works With:
- ✅ **Context Processor** - UI reflects actual addon state
- ✅ **Loader** - Respects enabled field
- ✅ **Admin Panel** - Changes sync with admin
- ✅ **Management Command** - `python manage.py addon list` shows same data
- ✅ **Database** - Single source of truth

### After Enable/Disable:
1. **Before Restart:**
   - Database updated ✓
   - UI shows new status ✓
   - Old hooks still active (in memory)
   - Old UI still renders (cached context)

2. **After Restart:**
   - Hooks re-registered ✓
   - UI re-renders based on new state ✓
   - Context processor refreshed ✓
   - Everything in sync ✓

## Testing Checklist

- [ ] Navigate to `/addons/`
- [ ] See Docker addon listed with "Enabled" badge
- [ ] Click "Disable" button
- [ ] Confirm in dialog
- [ ] See success message with restart reminder
- [ ] Docker addon shows "Disabled" badge
- [ ] Click "Details" button
- [ ] See detailed addon information
- [ ] Click "Enable" button
- [ ] Confirm in dialog
- [ ] See success message
- [ ] Docker addon shows "Enabled" badge again
- [ ] Restart WebOps
- [ ] Verify deployment form shows/hides Docker section

## Files Modified

1. `apps/addons/views.py` - Added views for toggle, enable, disable, detail
2. `templates/addons/list.html` - Added enable/disable buttons and alerts
3. `apps/addons/urls.py` - Added URL patterns for new views
4. `templates/components/aside.html` - Fixed addons URL name

## Security Considerations

- ✅ **Login Required** - All views use `@login_required` decorator
- ✅ **CSRF Protection** - All POST forms include `{% csrf_token %}`
- ✅ **Confirmation Dialogs** - Prevents accidental actions
- ✅ **No Direct DB Manipulation** - Uses Django ORM
- ✅ **Message Framework** - Proper user feedback

## Future Enhancements

1. **AJAX Toggle** - Enable/disable without page reload
2. **Bulk Actions** - Enable/disable multiple addons at once
3. **Addon Settings UI** - Configure addon settings from UI
4. **Hot Reload** - Reload addons without restart (advanced)
5. **Addon Marketplace** - Browse and install new addons
6. **Dependency Management** - Auto-enable/disable dependent addons

## Usage Examples

### Enable Docker Addon via UI

1. Go to http://localhost:8000/addons/
2. Find "docker" card
3. Click green "Enable" button
4. Click "OK" in confirmation dialog
5. See message: "Addon 'docker' has been enabled. Restart WebOps for changes to take effect."
6. Restart WebOps: `sudo systemctl restart webops-control-panel`
7. Go to "New Deployment" page
8. Docker section now appears!

### Disable Docker Addon via UI

1. Go to http://localhost:8000/addons/
2. Find "docker" card
3. Click red "Disable" button
4. Click "OK" in confirmation dialog
5. See message: "Addon 'docker' has been disabled. Restart WebOps for changes to take effect."
6. Restart WebOps
7. Go to "New Deployment" page
8. Docker section is gone!

## Summary

The WebOps addon management UI provides a user-friendly way to enable/disable addons without requiring command-line access or admin panel navigation. The implementation includes:

- ✅ **Visual addon management** with status badges
- ✅ **One-click enable/disable** with confirmations
- ✅ **Clear restart reminders** to avoid confusion
- ✅ **Metrics and monitoring** for each addon
- ✅ **Detailed addon information** pages
- ✅ **Seamless integration** with existing systems

**Users can now manage addons entirely through the Web UI!** 🎉
