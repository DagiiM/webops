/**
 * WebOps Notifications WebSocket Integration
 *
 * Integrates the WebSocket client with the NotificationsCenter for real-time updates.
 * Replaces polling with WebSocket push notifications.
 */

'use strict';

(function() {
    // Wait for dependencies to be available
    if (typeof NotificationsCenter === 'undefined') {
        console.error('NotificationsCenter not found. Make sure notifications-center.js is loaded first.');
        return;
    }

    if (typeof WebOpsNotificationsWS === 'undefined') {
        console.error('WebOpsNotificationsWS not found. Make sure notifications-websocket.js is loaded first.');
        return;
    }

    // Store reference to original methods
    const originalInit = NotificationsCenter.prototype.init;
    const originalStartPolling = NotificationsCenter.prototype.startPolling;
    const originalStopPolling = NotificationsCenter.prototype.stopPolling;
    const originalMarkAsRead = NotificationsCenter.prototype.markAsRead;
    const originalMarkAllAsRead = NotificationsCenter.prototype.markAllAsRead;

    /**
     * Override init to set up WebSocket integration
     */
    NotificationsCenter.prototype.init = function() {
        // Call original init
        originalInit.call(this);

        // Set up WebSocket handlers
        this.setupWebSocketHandlers();

        console.log('NotificationsCenter initialized with WebSocket integration');
    };

    /**
     * Set up WebSocket event handlers
     */
    NotificationsCenter.prototype.setupWebSocketHandlers = function() {
        const self = this;

        // Handle incoming WebSocket messages
        window.WebOpsNotificationsWS.onMessage((data) => {
            self.handleWebSocketMessage(data);
        });

        // Handle connection events
        window.WebOpsNotificationsWS.onConnect(() => {
            console.log('WebSocket connected - real-time notifications enabled');

            // Request initial unread count
            window.WebOpsNotificationsWS.getUnreadCount();
        });

        // Handle disconnection events
        window.WebOpsNotificationsWS.onDisconnect(() => {
            console.log('WebSocket disconnected - falling back to polling');

            // Fall back to polling if WebSocket disconnects
            if (!self.pollingInterval) {
                self.startPolling();
            }
        });
    };

    /**
     * Handle WebSocket messages
     * @param {Object} data - Message data from WebSocket
     */
    NotificationsCenter.prototype.handleWebSocketMessage = function(data) {
        switch (data.type) {
            case 'new_notification':
                this.handleNewNotification(data.notification);
                break;

            case 'notification_updated':
                this.handleNotificationUpdated(data.notification_id, data.updates);
                break;

            case 'notification_deleted':
                this.handleNotificationDeleted(data.notification_id);
                break;

            case 'notifications_list':
                this.handleNotificationsList(data.notifications);
                break;

            case 'unread_count':
                this.handleUnreadCount(data.count);
                break;

            case 'marked_read':
                this.handleMarkedRead(data.notification_id, data.unread_count);
                break;

            case 'all_marked_read':
                this.handleAllMarkedRead(data.count, data.unread_count);
                break;

            case 'error':
                console.error('WebSocket error:', data.message);
                break;

            default:
                console.warn('Unknown WebSocket message type:', data.type);
        }
    };

    /**
     * Handle new notification from WebSocket
     * @param {Object} notification - Notification data
     */
    NotificationsCenter.prototype.handleNewNotification = function(notification) {
        console.log('New notification received via WebSocket:', notification.title);

        // Convert to internal format
        const internalNotification = {
            id: notification.id,
            title: notification.title,
            message: notification.message,
            type: notification.type,
            read: notification.read,
            timestamp: new Date(notification.timestamp),
            actions: notification.action_url ? [{
                id: 'view',
                text: notification.action_text || 'View',
                handler: () => {
                    if (notification.action_url) {
                        window.location.href = notification.action_url;
                    }
                }
            }] : [],
            metadata: notification.metadata,
            read_at: notification.read_at ? new Date(notification.read_at) : null,
        };

        // Add to notifications array at the beginning
        this.notifications.unshift(internalNotification);

        // Update UI
        this.updateUI();

        // Show toast notification if center is closed
        if (window.WebOpsToast && !this.isOpen) {
            window.WebOpsToast.show({
                title: notification.title,
                message: notification.message,
                type: notification.type,
                duration: 5000,
                onClick: () => this.open()
            });
        }

        // Play notification sound
        this.playNotificationSound();
    };

    /**
     * Handle notification updated from WebSocket
     * @param {number} notificationId - ID of updated notification
     * @param {Object} updates - Updated fields
     */
    NotificationsCenter.prototype.handleNotificationUpdated = function(notificationId, updates) {
        const notification = this.notifications.find(n => n.id === notificationId);
        if (notification) {
            Object.assign(notification, updates);
            this.updateUI();
        }
    };

    /**
     * Handle notification deleted from WebSocket
     * @param {number} notificationId - ID of deleted notification
     */
    NotificationsCenter.prototype.handleNotificationDeleted = function(notificationId) {
        const index = this.notifications.findIndex(n => n.id === notificationId);
        if (index !== -1) {
            this.notifications.splice(index, 1);
            this.updateUI();
        }
    };

    /**
     * Handle notifications list from WebSocket
     * @param {Array} notifications - Array of notifications
     */
    NotificationsCenter.prototype.handleNotificationsList = function(notifications) {
        this.notifications = notifications.map(n => ({
            id: n.id,
            title: n.title,
            message: n.message,
            type: n.type,
            read: n.read,
            timestamp: new Date(n.timestamp),
            actions: n.action_url ? [{
                id: 'view',
                text: n.action_text || 'View',
                handler: () => {
                    if (n.action_url) {
                        window.location.href = n.action_url;
                    }
                }
            }] : [],
            metadata: n.metadata,
            read_at: n.read_at ? new Date(n.read_at) : null,
        }));

        this.updateUI();
    };

    /**
     * Handle unread count from WebSocket
     * @param {number} count - Unread count
     */
    NotificationsCenter.prototype.handleUnreadCount = function(count) {
        // Update badge
        const badge = this.toggleButton.querySelector('.notification-badge');
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'flex' : 'none';
        }
    };

    /**
     * Handle marked read confirmation from WebSocket
     * @param {number} notificationId - ID of marked notification
     * @param {number} unreadCount - New unread count
     */
    NotificationsCenter.prototype.handleMarkedRead = function(notificationId, unreadCount) {
        const notification = this.notifications.find(n => n.id === notificationId);
        if (notification) {
            notification.read = true;
            notification.read_at = new Date();
            this.updateUI();
        }

        this.handleUnreadCount(unreadCount);
    };

    /**
     * Handle all marked read confirmation from WebSocket
     * @param {number} count - Number of notifications marked
     * @param {number} unreadCount - New unread count (should be 0)
     */
    NotificationsCenter.prototype.handleAllMarkedRead = function(count, unreadCount) {
        this.notifications.forEach(notification => {
            notification.read = true;
            notification.read_at = new Date();
        });

        this.updateUI();
        this.handleUnreadCount(unreadCount);
    };

    /**
     * Override startPolling to disable it when WebSocket is connected
     */
    NotificationsCenter.prototype.startPolling = function() {
        // Only start polling if WebSocket is not connected
        if (!window.WebOpsNotificationsWS.isConnected) {
            console.log('WebSocket not connected, starting polling fallback');
            if (originalStartPolling) {
                originalStartPolling.call(this);
            }
        } else {
            console.log('WebSocket connected, polling not needed');
        }
    };

    /**
     * Override stopPolling to ensure it's stopped
     */
    NotificationsCenter.prototype.stopPolling = function() {
        if (originalStopPolling) {
            originalStopPolling.call(this);
        }
    };

    /**
     * Override markAsRead to use WebSocket when available
     */
    NotificationsCenter.prototype.markAsRead = async function(id) {
        const notification = this.notifications.find(n => n.id === id);
        if (!notification || notification.read) {
            return;
        }

        // Try WebSocket first
        if (window.WebOpsNotificationsWS.isConnected) {
            window.WebOpsNotificationsWS.markAsRead(id);
            // WebSocket response will update the UI
        } else {
            // Fall back to API
            if (originalMarkAsRead) {
                await originalMarkAsRead.call(this, id);
            }
        }
    };

    /**
     * Override markAllAsRead to use WebSocket when available
     */
    NotificationsCenter.prototype.markAllAsRead = async function() {
        // Try WebSocket first
        if (window.WebOpsNotificationsWS.isConnected) {
            window.WebOpsNotificationsWS.markAllAsRead();
            // WebSocket response will update the UI
        } else {
            // Fall back to API
            if (originalMarkAllAsRead) {
                await originalMarkAllAsRead.call(this);
            }
        }
    };

    console.log('NotificationsCenter WebSocket integration loaded');
})();
