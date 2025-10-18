# WebOps Toast Notification System

## Overview

The WebOps Toast Notification System provides a modern, accessible way to display notifications to users. It integrates seamlessly with the existing alert system and provides both programmatic and automatic conversion of traditional alerts to toast notifications.

## Features

- Modern, sleek design with animations
- Multiple toast types: success, error, warning, info
- Auto-dismiss with progress indicator
- Manual dismiss option
- Sticky toasts (no auto-dismiss)
- Custom titles and messages
- Action buttons
- Click handlers
- Automatic conversion of existing `webops-alert` elements
- Django messages integration
- Responsive design
- Accessibility support (ARIA attributes)
- Reduced motion support
- High contrast mode support

## Usage

### Basic Usage

```javascript
// Show a success toast
window.WebOps.Toast.success('Operation completed successfully!');

// Show an error toast
window.WebOps.Toast.error('An error occurred while processing your request.');

// Show a warning toast
window.WebOps.Toast.warning('Please review your input before proceeding.');

// Show an info toast
window.WebOps.Toast.info('Here is some useful information for you.');
```

### Advanced Usage

```javascript
// Show a toast with custom options
const toastId = window.WebOpsToast.show({
    title: 'Custom Title',
    message: 'This is a custom toast with advanced options.',
    type: 'info',
    duration: 8000, // 8 seconds
    dismissible: true,
    onClick: (id) => {
        console.log('Toast clicked:', id);
    },
    onShow: (id) => {
        console.log('Toast shown:', id);
    },
    onHide: (id) => {
        console.log('Toast hidden:', id);
    }
});

// Show a sticky toast (no auto-dismiss)
window.WebOpsToast.show({
    title: 'Action Required',
    message: 'This toast will not auto-dismiss.',
    type: 'warning',
    duration: 0 // 0 means sticky
});

// Show a toast with action buttons
window.WebOpsToast.show({
    title: 'Confirm Action',
    message: 'Do you want to proceed?',
    type: 'info',
    duration: 0, // Sticky until action is taken
    actions: [
        {
            text: 'Accept',
            handler: (id) => {
                window.WebOpsToast.hide(id);
                window.WebOpsToast.success('Action accepted!');
            }
        },
        {
            text: 'Decline',
            handler: (id) => {
                window.WebOpsToast.hide(id);
                window.WebOpsToast.warning('Action declined.');
            }
        }
    ]
});
```

### Manual Control

```javascript
// Hide a specific toast
window.WebOps.Toast.hide(toastId);

// Hide all toasts
window.WebOps.Toast.hideAll();
```

## Integration with Existing Alerts

The toast system automatically detects and converts existing `webops-alert` elements to toast notifications. This means you don't need to change your existing alert code - the conversion happens automatically.

### Alert Classes Supported

- `webops-alert-success` → Success toast
- `webops-alert-error` → Error toast
- `webops-alert-danger` → Error toast
- `webops-alert-warning` → Warning toast
- `webops-alert-info` → Info toast

### Django Messages Integration

Django messages are automatically converted to toasts. The system detects the message type and creates the appropriate toast:

```python
# In your Django views
from django.contrib import messages

messages.success(request, 'Operation completed successfully!')
messages.error(request, 'An error occurred!')
messages.warning(request, 'Please review your input.')
messages.info(request, 'Here is some information.')
```

## Testing

To test the toast system, visit the test page at `/auth/test/toast/` (requires login). This page provides:

- Basic toast examples
- Advanced toast features
- Alert to toast conversion examples
- Django messages integration test

## CSS Customization

The toast system uses CSS variables that can be customized in your theme:

```css
:root {
    /* Toast container positioning */
    --webops-toast-container-top: 20px;
    --webops-toast-container-right: 20px;
    
    /* Toast colors are inherited from theme variables */
    --webops-color-success: #00ff88;
    --webops-color-error: #ff4757;
    --webops-color-warning: #ffb800;
    --webops-color-info: #00aaff;
}
```

## Accessibility

The toast system includes several accessibility features:

- `aria-live` region for screen readers
- `role="alert"` for important notifications
- `aria-atomic="true"` for complete message reading
- Keyboard navigation support
- High contrast mode support
- Reduced motion support

## Browser Support

The toast system supports all modern browsers:
- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+

## API Reference

### ToastManager Methods

#### show(options)
Show a toast notification with the specified options.

**Parameters:**
- `options.message` (string, required) - Toast message
- `options.type` (string) - Toast type: 'success', 'error', 'warning', 'info' (default: 'info')
- `options.title` (string) - Toast title (optional)
- `options.duration` (number) - Duration in ms (default: 5000, 0 for sticky)
- `options.dismissible` (boolean) - Whether toast can be dismissed (default: true)
- `options.actions` (array) - Array of action buttons (optional)
- `options.onShow` (function) - Callback when toast is shown
- `options.onHide` (function) - Callback when toast is hidden
- `options.onClick` (function) - Callback when toast is clicked

**Returns:** String - Toast ID

#### success(message, options)
Show a success toast.

#### error(message, options)
Show an error toast.

#### warning(message, options)
Show a warning toast.

#### info(message, options)
Show an info toast.

#### hide(id)
Hide a specific toast by ID.

#### hideAll()
Hide all active toasts.

## Troubleshooting

### Toasts not appearing
1. Check that the JavaScript files are loaded correctly
2. Ensure the CSS file is included
3. Check browser console for errors

### Alerts not converting to toasts
1. Make sure the alert elements have the correct `webops-alert` classes
2. Check that the toast system has initialized (check console for initialization message)

### Django messages not converting
1. Ensure messages are being added correctly in your views
2. Check that the base template includes the toast system files
3. Verify the messages container in the base template