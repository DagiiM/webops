# WebOps Notifications Center

## Overview

The WebOps Notifications Center provides a dedicated area for viewing and managing notifications. It offers a persistent notification history, filtering options, and interactive actions. The center integrates seamlessly with the toast notification system and adheres to the WebOps Design System.

## Features

- Modern, sleek design with animations
- Persistent notification history stored in localStorage
- Multiple notification types: success, error, warning, info
- Tab-based filtering (All, Unread, Success, Error)
- Individual notification actions
- Mark all as read functionality
- Clear all notifications option
- Time-based notification grouping
- Responsive design
- Accessibility support (ARIA attributes)
- Reduced motion support
- High contrast mode support

## Usage

### Basic Usage

```javascript
// Add a new notification
const notificationId = window.WebOpsNotificationsCenter.addNotification({
    title: 'Deployment Complete',
    message: 'Your application has been successfully deployed.',
    type: 'success',
    read: false
});
```

### Advanced Usage

```javascript
// Add a notification with actions
window.WebOpsNotificationsCenter.addNotification({
    title: 'Action Required',
    message: 'Please review and approve the pending changes.',
    type: 'warning',
    read: false,
    actions: [
        {
            id: 'approve',
            text: 'Approve',
            handler: (id) => {
                // Handle approval
                window.WebOpsNotificationsCenter.removeNotification(id);
                window.WebOpsToast.success('Changes approved!');
            }
        },
        {
            id: 'reject',
            text: 'Reject',
            handler: (id) => {
                // Handle rejection
                window.WebOpsNotificationsCenter.removeNotification(id);
                window.WebOpsToast.warning('Changes rejected.');
            }
        }
    ]
});
```

### Manual Control

```javascript
// Open the notifications center
window.WebOpsNotificationsCenter.open();

// Close the notifications center
window.WebOpsNotificationsCenter.close();

// Toggle the notifications center
window.WebOpsNotificationsCenter.toggle();

// Mark all notifications as read
window.WebOpsNotificationsCenter.markAllAsRead();

// Clear all notifications
window.WebOpsNotificationsCenter.clearAll();

// Remove a specific notification
window.WebOpsNotificationsCenter.removeNotification(notificationId);

// Mark a specific notification as read
window.WebOpsNotificationsCenter.markAsRead(notificationId);
```

## API Reference

### NotificationsCenter Methods

#### addNotification(options)
Add a new notification to the center.

**Parameters:**
- `options.title` (string, required) - Notification title
- `options.message` (string, required) - Notification message
- `options.type` (string) - Notification type: 'success', 'error', 'warning', 'info' (default: 'info')
- `options.read` (boolean) - Whether notification is read (default: false)
- `options.timestamp` (Date) - Notification timestamp (default: now)
- `options.actions` (array) - Array of action buttons (optional)

**Returns:** String - Notification ID

#### removeNotification(id)
Remove a specific notification by ID.

#### markAsRead(id)
Mark a specific notification as read.

#### markAllAsRead()
Mark all notifications as read.

#### clearAll()
Remove all notifications.

#### open()
Open the notifications center.

#### close()
Close the notifications center.

#### toggle()
Toggle the notifications center visibility.

## Integration with Toast System

The notifications center integrates seamlessly with the toast system:

1. When a new notification is added, a toast is shown (if the center is closed)
2. Clicking the toast opens the notifications center
3. Notifications persist even after toasts are dismissed
4. The notification count badge updates automatically

## CSS Customization

The notifications center uses CSS variables that can be customized in your theme:

```css
:root {
    /* Notifications center positioning */
    --webops-notifications-center-width: 420px;
    
    /* Notification colors are inherited from theme variables */
    --webops-color-success: #00ff88;
    --webops-color-error: #ff4757;
    --webops-color-warning: #ffb800;
    --webops-color-info: #00aaff;
}
```

## Storage

Notifications are automatically saved to localStorage and persist across page refreshes. The storage format is:

```javascript
{
    id: "notification-1",
    title: "Notification Title",
    message: "Notification message",
    type: "info",
    read: false,
    timestamp: "2025-01-01T12:00:00.000Z",
    actions: [
        {
            id: "action1",
            text: "Action 1",
            handler: function() { /* ... */ }
        }
    ]
}
```

## Accessibility

The notifications center includes several accessibility features:

- `aria-label` attributes for screen readers
- Keyboard navigation support (Escape to close)
- Focus management
- High contrast mode support
- Reduced motion support

## Browser Support

The notifications center supports all modern browsers:
- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+

## Testing

To test the notifications center, visit the test page at `/auth/test/toast/` (requires login). This page provides:

- Basic notification examples
- Advanced notification features
- Notifications center controls
- Integration with toast system

## Troubleshooting

### Notifications not appearing
1. Check that the JavaScript files are loaded correctly
2. Ensure the CSS file is included
3. Check browser console for errors
4. Verify localStorage is available and not full

### Notifications not persisting
1. Check if localStorage is available
2. Verify browser privacy settings
3. Check for quota exceeded errors in console

### Toggle button not appearing
1. Ensure the header element exists in the page
2. Check that the notifications center JavaScript has loaded
3. Verify the button is not hidden by CSS