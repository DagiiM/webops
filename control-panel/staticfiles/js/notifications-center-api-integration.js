/**
 * WebOps Notifications Center - API Integration
 *
 * This script modifies the NotificationsCenter class to use the backend API
 * instead of localStorage for persistent notification storage.
 */

'use strict';

(function() {
    // Wait for NotificationsCenter to be available
    if (typeof NotificationsCenter === 'undefined') {
        console.error('NotificationsCenter not found. Make sure notifications-center.js is loaded first.');
        return;
    }

    // Store original methods
    const originalInit = NotificationsCenter.prototype.init;
    const originalAddNotification = NotificationsCenter.prototype.addNotification;
    const originalMarkAsRead = NotificationsCenter.prototype.markAsRead;
    const originalMarkAllAsRead = NotificationsCenter.prototype.markAllAsRead;
    const originalClearAll = NotificationsCenter.prototype.clearAll;

    /**
     * Override init method to load from API instead of localStorage
     */
    NotificationsCenter.prototype.init = function() {
        // Create notifications center DOM elements
        this.createNotificationsCenter();

        // Create toggle button
        this.createToggleButton();

        // Load notifications from API
        this.loadNotificationsFromAPI();

        // Start polling for new notifications
        this.startPolling();

        console.log('WebOps Notifications Center initialized with API integration');
    };

    /**
     * Load notifications from API
     */
    NotificationsCenter.prototype.loadNotificationsFromAPI = async function() {
        try {
            if (!window.WebOpsNotificationsAPI) {
                console.error('NotificationsAPI not available');
                return;
            }

            const response = await window.WebOpsNotificationsAPI.getNotifications({
                limit: 50
            });

            if (response.success) {
                // Convert API response to notifications format
                this.notifications = response.notifications.map(n => ({
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

                // Update UI
                this.updateUI();
            }
        } catch (error) {
            console.error('Failed to load notifications from API:', error);
        }
    };

    /**
     * Override markAsRead to use API
     */
    NotificationsCenter.prototype.markAsRead = async function(id) {
        try {
            const notification = this.notifications.find(n => n.id === id);
            if (notification && !notification.read) {
                // Call API
                const response = await window.WebOpsNotificationsAPI.markAsRead(id);

                if (response.success) {
                    // Update local state
                    notification.read = true;
                    notification.read_at = new Date();
                    this.updateUI();
                }
            }
        } catch (error) {
            console.error('Failed to mark notification as read:', error);
        }
    };

    /**
     * Override markAllAsRead to use API
     */
    NotificationsCenter.prototype.markAllAsRead = async function() {
        try {
            // Call API
            const response = await window.WebOpsNotificationsAPI.markAllAsRead();

            if (response.success) {
                // Update local state
                this.notifications.forEach(notification => {
                    notification.read = true;
                    notification.read_at = new Date();
                });
                this.updateUI();
            }
        } catch (error) {
            console.error('Failed to mark all as read:', error);
        }
    };

    /**
     * Override clearAll to use API
     */
    NotificationsCenter.prototype.clearAll = async function() {
        try {
            // Call API
            const response = await window.WebOpsNotificationsAPI.clearAll();

            if (response.success) {
                // Clear local state
                this.notifications = [];
                this.updateUI();
            }
        } catch (error) {
            console.error('Failed to clear notifications:', error);
        }
    };

    /**
     * Delete a single notification
     */
    NotificationsCenter.prototype.deleteNotification = async function(id) {
        try {
            const response = await window.WebOpsNotificationsAPI.deleteNotification(id);

            if (response.success) {
                // Remove from local state
                const index = this.notifications.findIndex(n => n.id === id);
                if (index !== -1) {
                    this.notifications.splice(index, 1);
                    this.updateUI();
                }
            }
        } catch (error) {
            console.error('Failed to delete notification:', error);
        }
    };

    /**
     * Start polling for new notifications
     */
    NotificationsCenter.prototype.startPolling = function() {
        // Poll every 30 seconds
        this.pollingInterval = setInterval(() => {
            this.checkForNewNotifications();
        }, 30000);

        console.log('Started polling for notifications (30s interval)');
    };

    /**
     * Stop polling for new notifications
     */
    NotificationsCenter.prototype.stopPolling = function() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
            console.log('Stopped polling for notifications');
        }
    };

    /**
     * Check for new notifications
     */
    NotificationsCenter.prototype.checkForNewNotifications = async function() {
        try {
            if (!window.WebOpsNotificationsAPI) {
                return;
            }

            // Get current notification count
            const currentIds = new Set(this.notifications.map(n => n.id));

            // Fetch latest notifications
            const response = await window.WebOpsNotificationsAPI.getNotifications({
                limit: 10
            });

            if (response.success) {
                // Find new notifications
                const newNotifications = response.notifications.filter(n => !currentIds.has(n.id));

                if (newNotifications.length > 0) {
                    // Add new notifications to the beginning
                    for (const n of newNotifications.reverse()) {
                        this.notifications.unshift({
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
                        });

                        // Show toast for new notification
                        if (window.WebOpsToast && !this.isOpen) {
                            window.WebOpsToast.show({
                                title: n.title,
                                message: n.message,
                                type: n.type,
                                duration: 5000,
                                onClick: () => this.open()
                            });
                        }
                    }

                    // Update UI
                    this.updateUI();

                    // Play notification sound (optional)
                    this.playNotificationSound();
                }
            }
        } catch (error) {
            console.error('Failed to check for new notifications:', error);
        }
    };

    /**
     * Play notification sound (optional)
     */
    NotificationsCenter.prototype.playNotificationSound = function() {
        // Optional: Play a subtle notification sound
        // You can add an audio element or use Web Audio API
        try {
            const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBJWP3/LJciQGJXXH8N6RQAoSXbTp66lVFApGnt/xs2wgA5SK3fLKcSUFJHXG8N2RQAoSXbTo66lVEwlFnN/xsm4gA5WI3fLKcSUEJHXG8NyRPwoSXbPo66hVEwlFnN/xsm4fA5WI3/LJcSUEJHTG8NyRPwoSXbPo66hVEglEnN/xsW4fA5WH3/LJcSUEI3TG8NyQPwoSXbPo66hUEglEnN/xsm4fA5SI3/LJcSUEJHTG8NuQPwoRXbPn66hVEwlEnN/xsW4gA5WI3vLJcSYEJHTG79uQPwoRXbPn66hVEglEnN/xsW4gA5WH3vLJcSYEI3PG79uPPwoRXbPn66hVEglFnN/xsW4gA5WH3vLJcSYEI3PG79uPPwoRXbPn66hVEglFnN/xsG4gA5WH3vLKcSYEI3PG79qPPwoRXbPn66hUEglFnN/xsG4gA5WH3vLKcSYEI3TG79qPPwoRXbPn66hUEwlEnN/xsG4gA5WH3vLKcSYEI3TG79qPPgoRXbPn66hUEwlEnN/xsG4gA5WH3/LKcSYEJHXG8NqPPgoRXbPo66hUEwlEnN/xsm4gA5WH3/LKcSYEJHXG8NqPPgoSXbPo66hUEwlEnN/xsm4gA5WH3/LKcSYEJHXG8NqQPgoSXbPo66hUEglFnN/xsm4gA5WH3/LKcSYEJHXG8NqQPgoSXbPo66hUEglFnN/xsm4gA5WH3/LKcSYEJHXG8NqQPgoSXbPo66hUEglFnN/xsm4gA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4gA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4hA5WH3/LKcSYEJHXG8NqQPgoRXbPo66hUEglFnN/xsm4h');
            audio.volume = 0.3;
            audio.play().catch(() => {
                // Ignore errors (browser may block autoplay)
            });
        } catch (error) {
            // Silently fail - not critical
        }
    };

    /**
     * Override save/load methods to do nothing (we use API now)
     */
    NotificationsCenter.prototype.saveNotifications = function() {
        // No-op - notifications are saved to backend automatically
    };

    NotificationsCenter.prototype.loadNotifications = function() {
        // No-op - use loadNotificationsFromAPI instead
    };

    /**
     * Remove sample notifications initialization
     */
    NotificationsCenter.prototype.initializeSampleNotifications = function() {
        // No-op - we load real notifications from API
    };

    console.log('NotificationsCenter API integration loaded');
})();
