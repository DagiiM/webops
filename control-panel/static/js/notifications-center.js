/**
 * WebOps Notifications Center
 * A dedicated area for viewing and managing notifications
 */

'use strict';

class NotificationsCenter {
    constructor() {
        this.container = null;
        this.overlay = null;
        this.toggleButton = null;
        this.notifications = [];
        this.activeTab = 'all';
        this.isOpen = false;
        this.maxNotifications = 50;
        this.notificationId = 0;
        this.init();
    }

    init() {
        // Create notifications center DOM elements
        this.createNotificationsCenter();
        
        // Create toggle button
        this.createToggleButton();
        
        // Load notifications from localStorage
        this.loadNotifications();
        
        // Initialize with sample notifications for testing
        this.initializeSampleNotifications();
        
        console.log('WebOps Notifications Center initialized');
    }

    createNotificationsCenter() {
        // Create overlay
        this.overlay = document.createElement('div');
        this.overlay.className = 'webops-notifications-center__overlay';
        this.overlay.addEventListener('click', () => this.close());
        document.body.appendChild(this.overlay);

        // Create notifications center container
        this.container = document.createElement('div');
        this.container.className = 'webops-notifications-center';
        this.container.innerHTML = `
            <div class="webops-notifications-center__header">
                <h2 class="webops-notifications-center__title">
                    <span class="material-icons">notifications</span>
                    Notifications
                    <span class="webops-notifications-center__badge" id="notificationCount">0</span>
                </h2>
                <button class="webops-notifications-center__close" id="closeNotificationsCenter" aria-label="Close notifications">
                    <span class="material-icons">close</span>
                </button>
            </div>
            
            <div class="webops-notifications-center__tabs">
                <button class="webops-notifications-center__tab webops-notifications-center__tab--active" data-tab="all">
                    All
                    <span class="webops-notifications-center__tab-count" id="allCount">0</span>
                </button>
                <button class="webops-notifications-center__tab" data-tab="unread">
                    Unread
                    <span class="webops-notifications-center__tab-count" id="unreadCount">0</span>
                </button>
                <button class="webops-notifications-center__tab" data-tab="success">
                    Success
                </button>
                <button class="webops-notifications-center__tab" data-tab="error">
                    Error
                </button>
            </div>
            
            <div class="webops-notifications-center__content" id="notificationsContent">
                <div class="webops-notifications-center__empty">
                    <div class="webops-notifications-center__empty-icon">
                        <span class="material-icons">notifications_off</span>
                    </div>
                    <div class="webops-notifications-center__empty-title">No notifications</div>
                    <div class="webops-notifications-center__empty-message">You're all caught up! New notifications will appear here.</div>
                </div>
            </div>
            
            <div class="webops-notifications-center__footer">
                <button class="webops-notifications-center__mark-all-read" id="markAllRead">Mark all as read</button>
                <button class="webops-notifications-center__clear-all" id="clearAll">Clear all</button>
            </div>
        `;
        
        document.body.appendChild(this.container);
        
        // Set up event listeners
        this.setupEventListeners();
    }

    createToggleButton() {
        // Check if toggle button already exists
        this.toggleButton = document.getElementById('notificationsToggle');
        
        if (!this.toggleButton) {
            // Find a suitable place to add the toggle button (e.g., in the header)
            const header = document.querySelector('.webops-header__actions') || 
                          document.querySelector('.webops-header') ||
                          document.querySelector('header');
            
            if (header) {
                this.toggleButton = document.createElement('button');
                this.toggleButton.id = 'notificationsToggle';
                this.toggleButton.className = 'webops-notifications-center__toggle';
                this.toggleButton.setAttribute('aria-label', 'View notifications');
                this.toggleButton.innerHTML = `
                    <span class="material-icons">notifications</span>
                    <span class="webops-notifications-center__toggle-badge" id="toggleBadge">0</span>
                `;
                
                header.appendChild(this.toggleButton);
                this.toggleButton.addEventListener('click', () => this.toggle());
            }
        }
    }

    setupEventListeners() {
        // Close button
        const closeButton = document.getElementById('closeNotificationsCenter');
        if (closeButton) {
            closeButton.addEventListener('click', () => this.close());
        }
        
        // Tab buttons
        const tabButtons = this.container.querySelectorAll('.webops-notifications-center__tab');
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tab = button.getAttribute('data-tab');
                this.switchTab(tab);
            });
        });
        
        // Mark all as read
        const markAllReadButton = document.getElementById('markAllRead');
        if (markAllReadButton) {
            markAllReadButton.addEventListener('click', () => this.markAllAsRead());
        }
        
        // Clear all
        const clearAllButton = document.getElementById('clearAll');
        if (clearAllButton) {
            clearAllButton.addEventListener('click', () => this.clearAll());
        }
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });
    }

    /**
     * Add a new notification
     * @param {Object} options - Notification options
     * @param {string} options.title - Notification title
     * @param {string} options.message - Notification message
     * @param {string} options.type - Notification type: success, error, warning, info
     * @param {boolean} options.read - Whether notification is read (default: false)
     * @param {Date} options.timestamp - Notification timestamp (default: now)
     * @param {Object} options.actions - Notification actions (optional)
     * @returns {string} Notification ID
     */
    addNotification(options) {
        // Generate unique ID
        const id = `notification-${++this.notificationId}`;
        
        // Set default options
        const notification = {
            id,
            title: options.title || 'Notification',
            message: options.message || '',
            type: options.type || 'info',
            read: options.read || false,
            timestamp: options.timestamp || new Date(),
            actions: options.actions || []
        };
        
        // Add to notifications array
        this.notifications.unshift(notification);
        
        // Limit number of notifications
        if (this.notifications.length > this.maxNotifications) {
            this.notifications = this.notifications.slice(0, this.maxNotifications);
        }
        
        // Save to localStorage
        this.saveNotifications();
        
        // Update UI
        this.updateUI();
        
        // Show toast if not already open
        if (!this.isOpen) {
            if (window.WebOpsToast) {
                window.WebOpsToast.show({
                    title: notification.title,
                    message: notification.message,
                    type: notification.type,
                    duration: 5000,
                    onClick: () => this.open()
                });
            }
        }
        
        return id;
    }

    /**
     * Remove a notification
     * @param {string} id - Notification ID
     */
    removeNotification(id) {
        const index = this.notifications.findIndex(n => n.id === id);
        if (index !== -1) {
            this.notifications.splice(index, 1);
            this.saveNotifications();
            this.updateUI();
        }
    }

    /**
     * Mark a notification as read
     * @param {string} id - Notification ID
     */
    markAsRead(id) {
        const notification = this.notifications.find(n => n.id === id);
        if (notification && !notification.read) {
            notification.read = true;
            this.saveNotifications();
            this.updateUI();
        }
    }

    /**
     * Mark all notifications as read
     */
    markAllAsRead() {
        this.notifications.forEach(notification => {
            notification.read = true;
        });
        this.saveNotifications();
        this.updateUI();
    }

    /**
     * Clear all notifications
     */
    clearAll() {
        this.notifications = [];
        this.saveNotifications();
        this.updateUI();
    }

    /**
     * Switch to a different tab
     * @param {string} tab - Tab name
     */
    switchTab(tab) {
        this.activeTab = tab;
        
        // Update tab buttons
        const tabButtons = this.container.querySelectorAll('.webops-notifications-center__tab');
        tabButtons.forEach(button => {
            if (button.getAttribute('data-tab') === tab) {
                button.classList.add('webops-notifications-center__tab--active');
            } else {
                button.classList.remove('webops-notifications-center__tab--active');
            }
        });
        
        // Update content
        this.renderNotifications();
    }

    /**
     * Open the notifications center
     */
    open() {
        this.isOpen = true;
        this.container.classList.add('webops-notifications-center--open');
        this.overlay.classList.add('webops-notifications-center__overlay--active');
        
        // Mark all as read when opened
        this.markAllAsRead();
    }

    /**
     * Close the notifications center
     */
    close() {
        this.isOpen = false;
        this.container.classList.remove('webops-notifications-center--open');
        this.overlay.classList.remove('webops-notifications-center__overlay--active');
    }

    /**
     * Toggle the notifications center
     */
    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    /**
     * Update the UI
     */
    updateUI() {
        // Update counts
        this.updateCounts();
        
        // Render notifications
        this.renderNotifications();
    }

    /**
     * Update notification counts
     */
    updateCounts() {
        const totalCount = this.notifications.length;
        const unreadCount = this.notifications.filter(n => !n.read).length;
        const successCount = this.notifications.filter(n => n.type === 'success').length;
        const errorCount = this.notifications.filter(n => n.type === 'error').length;
        
        // Update header badge
        const notificationCount = document.getElementById('notificationCount');
        if (notificationCount) {
            notificationCount.textContent = totalCount;
        }
        
        // Update toggle badge
        const toggleBadge = document.getElementById('toggleBadge');
        if (toggleBadge) {
            toggleBadge.textContent = unreadCount;
            toggleBadge.style.display = unreadCount > 0 ? 'block' : 'none';
        }
        
        // Update tab counts
        const allCount = document.getElementById('allCount');
        if (allCount) {
            allCount.textContent = totalCount;
        }
        
        const unreadCountElement = document.getElementById('unreadCount');
        if (unreadCountElement) {
            unreadCountElement.textContent = unreadCount;
            unreadCountElement.style.display = unreadCount > 0 ? 'block' : 'none';
        }
    }

    /**
     * Render notifications
     */
    renderNotifications() {
        const content = document.getElementById('notificationsContent');
        if (!content) return;
        
        // Filter notifications based on active tab
        let filteredNotifications = this.notifications;
        
        if (this.activeTab === 'unread') {
            filteredNotifications = this.notifications.filter(n => !n.read);
        } else if (this.activeTab === 'success') {
            filteredNotifications = this.notifications.filter(n => n.type === 'success');
        } else if (this.activeTab === 'error') {
            filteredNotifications = this.notifications.filter(n => n.type === 'error');
        }
        
        // Clear content
        content.innerHTML = '';
        
        // Show empty state if no notifications
        if (filteredNotifications.length === 0) {
            content.innerHTML = `
                <div class="webops-notifications-center__empty">
                    <div class="webops-notifications-center__empty-icon">
                        <span class="material-icons">notifications_off</span>
                    </div>
                    <div class="webops-notifications-center__empty-title">No notifications</div>
                    <div class="webops-notifications-center__empty-message">
                        ${this.activeTab === 'unread' ? 'No unread notifications' : 
                          this.activeTab === 'success' ? 'No success notifications' :
                          this.activeTab === 'error' ? 'No error notifications' :
                          'You\'re all caught up! New notifications will appear here.'}
                    </div>
                </div>
            `;
            return;
        }
        
        // Create notifications list
        const list = document.createElement('div');
        list.className = 'webops-notifications-center__list';
        
        filteredNotifications.forEach(notification => {
            const item = this.createNotificationItem(notification);
            list.appendChild(item);
        });
        
        content.appendChild(list);
    }

    /**
     * Create a notification item element
     * @param {Object} notification - Notification object
     * @returns {HTMLElement} Notification item element
     */
    createNotificationItem(notification) {
        const item = document.createElement('div');
        item.className = `webops-notifications-center__item ${!notification.read ? 'webops-notifications-center__item--unread' : ''}`;
        
        // Format timestamp
        const timeAgo = this.formatTimeAgo(notification.timestamp);
        
        // Create icon
        const iconClass = `webops-notifications-center__item-icon--${notification.type}`;
        const iconHtml = `<span class="material-icons">${this.getIconForType(notification.type)}</span>`;
        
        // Create actions HTML
        let actionsHtml = '';
        if (notification.actions && notification.actions.length > 0) {
            actionsHtml = '<div class="webops-notifications-center__item-actions">';
            notification.actions.forEach(action => {
                actionsHtml += `<button class="webops-notifications-center__item-action" data-action="${action.id}">${action.text}</button>`;
            });
            actionsHtml += '</div>';
            
            // Add event listeners for actions
            setTimeout(() => {
                const actionButtons = item.querySelectorAll('.webops-notifications-center__item-action');
                actionButtons.forEach(button => {
                    button.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const actionId = button.getAttribute('data-action');
                        const action = notification.actions.find(a => a.id === actionId);
                        if (action && typeof action.handler === 'function') {
                            action.handler(notification.id);
                        }
                    });
                });
            }, 0);
        }
        
        item.innerHTML = `
            <div class="webops-notifications-center__item-header">
                <div class="webops-notifications-center__item-icon ${iconClass}">
                    ${iconHtml}
                </div>
                <div class="webops-notifications-center__item-content">
                    <div class="webops-notifications-center__item-title">${notification.title}</div>
                    <div class="webops-notifications-center__item-message">${notification.message}</div>
                </div>
                <div class="webops-notifications-center__item-time">${timeAgo}</div>
            </div>
            ${actionsHtml}
        `;
        
        // Add click event to mark as read
        if (!notification.read) {
            item.addEventListener('click', () => {
                this.markAsRead(notification.id);
            });
        }
        
        return item;
    }

    /**
     * Get icon HTML for notification type
     * @param {string} type - Notification type
     * @returns {string} Icon name
     */
    getIconForType(type) {
        const icons = {
            success: 'check_circle',
            error: 'error',
            warning: 'warning',
            info: 'info'
        };
        return icons[type] || 'info';
    }

    /**
     * Format timestamp as time ago
     * @param {Date} timestamp - Timestamp
     * @returns {string} Formatted time ago
     */
    formatTimeAgo(timestamp) {
        const now = new Date();
        const diff = now - timestamp;
        
        // Less than a minute
        if (diff < 60000) {
            return 'Just now';
        }
        
        // Less than an hour
        if (diff < 3600000) {
            const minutes = Math.floor(diff / 60000);
            return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
        }
        
        // Less than a day
        if (diff < 86400000) {
            const hours = Math.floor(diff / 3600000);
            return `${hours} hour${hours > 1 ? 's' : ''} ago`;
        }
        
        // Less than a week
        if (diff < 604800000) {
            const days = Math.floor(diff / 86400000);
            return `${days} day${days > 1 ? 's' : ''} ago`;
        }
        
        // More than a week, show date
        return timestamp.toLocaleDateString();
    }

    /**
     * Save notifications to localStorage
     */
    saveNotifications() {
        try {
            // Convert dates to strings for JSON serialization
            const notificationsToSave = this.notifications.map(n => ({
                ...n,
                timestamp: n.timestamp.toISOString()
            }));
            
            localStorage.setItem('webopsNotifications', JSON.stringify(notificationsToSave));
        } catch (e) {
            console.error('Failed to save notifications to localStorage:', e);
        }
    }

    /**
     * Load notifications from localStorage
     */
    loadNotifications() {
        try {
            const saved = localStorage.getItem('webopsNotifications');
            if (saved) {
                const parsed = JSON.parse(saved);
                
                // Convert string dates back to Date objects
                this.notifications = parsed.map(n => ({
                    ...n,
                    timestamp: new Date(n.timestamp)
                }));
                
                // Update UI
                this.updateUI();
            }
        } catch (e) {
            console.error('Failed to load notifications from localStorage:', e);
        }
    }

    /**
     * Initialize with sample notifications for testing
     */
    initializeSampleNotifications() {
        // Only add sample notifications if there are no existing ones
        if (this.notifications.length === 0) {
            this.addNotification({
                title: 'Welcome to WebOps',
                message: 'Your control panel is ready to use. Check out the features available.',
                type: 'info',
                read: true,
                timestamp: new Date(Date.now() - 86400000) // 1 day ago
            });
            
            this.addNotification({
                title: 'System Update',
                message: 'WebOps has been updated to the latest version with new features and improvements.',
                type: 'success',
                read: true,
                timestamp: new Date(Date.now() - 3600000) // 1 hour ago
            });
            
            this.addNotification({
                title: 'Deployment Complete',
                message: 'Your application has been successfully deployed to the production server.',
                type: 'success',
                read: false,
                timestamp: new Date(Date.now() - 1800000), // 30 minutes ago
                actions: [
                    {
                        id: 'view',
                        text: 'View',
                        handler: (id) => {
                            if (window.WebOpsToast) {
                                window.WebOpsToast.info('Viewing deployment details...');
                            }
                        }
                    }
                ]
            });
        }
    }

    /**
     * Cleanup resources
     */
    destroy() {
        // Remove DOM elements
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
        
        if (this.overlay && this.overlay.parentNode) {
            this.overlay.parentNode.removeChild(this.overlay);
        }
        
        // Clear references
        this.container = null;
        this.overlay = null;
        this.toggleButton = null;
        this.notifications = [];
    }
}

// Initialize notifications center when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Create global notifications center instance
    window.WebOpsNotificationsCenter = new NotificationsCenter();
    
    // Add to global WebOps object if it exists
    if (window.WebOps) {
        window.WebOps.NotificationsCenter = window.WebOpsNotificationsCenter;
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NotificationsCenter;
}