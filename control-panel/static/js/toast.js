/**
 * WebOps Toast Notification System
 * Modern, accessible toast notifications that integrate with existing alert classes
 */

'use strict';

class ToastManager {
    constructor() {
        this.container = null;
        this.toasts = new Map();
        this.maxToasts = 5;
        this.defaultDuration = 5000;
        this.toastId = 0;
        this.init();
    }

    init() {
        // Create toast container if it doesn't exist
        if (!document.querySelector('.webops-toast-container')) {
            this.container = document.createElement('div');
            this.container.className = 'webops-toast-container';
            this.container.setAttribute('aria-live', 'polite');
            this.container.setAttribute('aria-label', 'Notifications');
            document.body.appendChild(this.container);
        } else {
            this.container = document.querySelector('.webops-toast-container');
        }
    }

    /**
     * Show a toast notification
     * @param {Object} options - Toast options
     * @param {string} options.message - Toast message (required)
     * @param {string} options.type - Toast type: success, error, warning, info (default: info)
     * @param {string} options.title - Toast title (optional)
     * @param {number} options.duration - Duration in ms (default: 5000, 0 for sticky)
     * @param {Array} options.actions - Array of action buttons (optional)
     * @param {boolean} options.dismissible - Whether toast can be dismissed (default: true)
     * @param {Function} options.onShow - Callback when toast is shown
     * @param {Function} options.onHide - Callback when toast is hidden
     * @param {Function} options.onClick - Callback when toast is clicked
     * @returns {string} Toast ID
     */
    show(options) {
        // Validate required options
        if (!options || !options.message) {
            console.error('Toast message is required');
            return null;
        }

        // Generate unique ID
        const id = `toast-${++this.toastId}`;
        
        // Set default options
        const config = {
            type: 'info',
            duration: this.defaultDuration,
            dismissible: true,
            ...options
        };

        // Limit number of toasts
        if (this.toasts.size >= this.maxToasts) {
            const oldestToast = this.toasts.values().next().value;
            if (oldestToast) {
                this.hide(oldestToast.id);
            }
        }

        // Create toast element
        const toastElement = this.createToast(id, config);
        
        // Store toast data
        const toastData = {
            id,
            element: toastElement,
            config,
            timeout: null,
            progressInterval: null
        };
        
        this.toasts.set(id, toastData);
        
        // Add to container
        this.container.appendChild(toastElement);
        
        // Trigger animation
        requestAnimationFrame(() => {
            toastElement.classList.add('webops-toast--show');
        });
        
        // Set auto-hide timeout
        if (config.duration > 0) {
            this.setAutoHide(toastData);
        }
        
        // Call onShow callback
        if (typeof config.onShow === 'function') {
            config.onShow(id);
        }
        
        return id;
    }

    /**
     * Create toast DOM element
     * @param {string} id - Toast ID
     * @param {Object} config - Toast configuration
     * @returns {HTMLElement} Toast element
     */
    createToast(id, config) {
        const toast = document.createElement('div');
        toast.className = `webops-toast webops-toast--${config.type}`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-atomic', 'true');
        toast.setAttribute('data-toast-id', id);

        // Create icon
        const icon = document.createElement('div');
        icon.className = 'webops-toast__icon';
        icon.innerHTML = this.getIconForType(config.type);

        // Create content
        const content = document.createElement('div');
        content.className = 'webops-toast__content';

        if (config.title) {
            const title = document.createElement('div');
            title.className = 'webops-toast__title';
            title.textContent = config.title;
            content.appendChild(title);
        }

        const message = document.createElement('div');
        message.className = 'webops-toast__message';
        message.textContent = config.message;
        content.appendChild(message);

        // Create actions if provided
        if (config.actions && config.actions.length > 0) {
            const actions = document.createElement('div');
            actions.className = 'webops-toast__actions';
            
            config.actions.forEach(action => {
                const button = document.createElement('button');
                button.className = 'webops-toast__action';
                button.textContent = action.text;
                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (typeof action.handler === 'function') {
                        action.handler(id);
                    }
                });
                actions.appendChild(button);
            });
            
            content.appendChild(actions);
        }

        // Create close button if dismissible
        if (config.dismissible) {
            const closeBtn = document.createElement('button');
            closeBtn.className = 'webops-toast__close';
            closeBtn.setAttribute('aria-label', 'Close notification');
            closeBtn.innerHTML = '&times;';
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.hide(id);
            });
            toast.appendChild(closeBtn);
        }

        // Create progress bar if duration is set
        if (config.duration > 0) {
            const progress = document.createElement('div');
            progress.className = 'webops-toast__progress';
            progress.style.width = '100%';
            toast.appendChild(progress);
        }

        // Add click handler
        if (typeof config.onClick === 'function') {
            toast.addEventListener('click', () => {
                config.onClick(id);
            });
            toast.style.cursor = 'pointer';
        }

        // Assemble toast
        toast.appendChild(icon);
        toast.appendChild(content);

        return toast;
    }

    /**
     * Get icon HTML for toast type
     * @param {string} type - Toast type
     * @returns {string} Icon HTML
     */
    getIconForType(type) {
        const icons = {
            success: '<span class="material-icons">check_circle</span>',
            error: '<span class="material-icons">error</span>',
            warning: '<span class="material-icons">warning</span>',
            info: '<span class="material-icons">info</span>'
        };
        return icons[type] || icons.info;
    }

    /**
     * Set auto-hide timeout and progress bar animation
     * @param {Object} toastData - Toast data object
     */
    setAutoHide(toastData) {
        const { id, element, config } = toastData;
        const progressBar = element.querySelector('.webops-toast__progress');
        
        if (progressBar) {
            // Animate progress bar
            const startTime = Date.now();
            const duration = config.duration;
            
            toastData.progressInterval = setInterval(() => {
                const elapsed = Date.now() - startTime;
                const remaining = Math.max(0, duration - elapsed);
                const percentage = (remaining / duration) * 100;
                
                progressBar.style.width = `${percentage}%`;
                
                if (remaining <= 0) {
                    clearInterval(toastData.progressInterval);
                }
            }, 50);
        }
        
        // Set timeout to hide toast
        toastData.timeout = setTimeout(() => {
            this.hide(id);
        }, config.duration);
    }

    /**
     * Hide a toast notification
     * @param {string} id - Toast ID
     */
    hide(id) {
        const toastData = this.toasts.get(id);
        if (!toastData) return;

        const { element, config, timeout, progressInterval } = toastData;

        // Clear timeout and interval
        if (timeout) clearTimeout(timeout);
        if (progressInterval) clearInterval(progressInterval);

        // Add hide animation
        element.classList.add('webops-toast--hide');

        // Remove after animation
        setTimeout(() => {
            if (element.parentNode) {
                element.parentNode.removeChild(element);
            }
            this.toasts.delete(id);
            
            // Call onHide callback
            if (typeof config.onHide === 'function') {
                config.onHide(id);
            }
        }, 300); // Match animation duration
    }

    /**
     * Hide all toast notifications
     */
    hideAll() {
        this.toasts.forEach((toastData) => {
            this.hide(toastData.id);
        });
    }

    /**
     * Show success toast
     * @param {string} message - Message
     * @param {Object} options - Additional options
     * @returns {string} Toast ID
     */
    success(message, options = {}) {
        return this.show({ ...options, message, type: 'success' });
    }

    /**
     * Show error toast
     * @param {string} message - Message
     * @param {Object} options - Additional options
     * @returns {string} Toast ID
     */
    error(message, options = {}) {
        return this.show({ ...options, message, type: 'error' });
    }

    /**
     * Show warning toast
     * @param {string} message - Message
     * @param {Object} options - Additional options
     * @returns {string} Toast ID
     */
    warning(message, options = {}) {
        return this.show({ ...options, message, type: 'warning' });
    }

    /**
     * Show info toast
     * @param {string} message - Message
     * @param {Object} options - Additional options
     * @returns {string} Toast ID
     */
    info(message, options = {}) {
        return this.show({ ...options, message, type: 'info' });
    }

    /**
     * Convert existing webops-alert and auth-alert elements to toasts
     * This integrates with the existing alert system
     */
    convertAlertsToToasts() {
        const alerts = document.querySelectorAll('.webops-alert, .auth-alert');
        alerts.forEach(alert => {
            // Skip if already converted
            if (alert.getAttribute('data-converted-to-toast')) return;

            // Extract alert information
            const message = alert.textContent.trim();
            const type = this.extractAlertType(alert);

            // Create toast
            this.show({
                message,
                type,
                duration: 8000 // Longer duration for converted alerts
            });

            // Mark as converted and hide original
            alert.setAttribute('data-converted-to-toast', 'true');
            alert.style.display = 'none';
        });
    }

    /**
     * Extract alert type from element classes
     * @param {HTMLElement} alert - Alert element
     * @returns {string} Alert type
     */
    extractAlertType(alert) {
        const classes = alert.className.split(' ');
        
        for (const cls of classes) {
            if (cls.includes('success')) return 'success';
            if (cls.includes('error') || cls.includes('danger')) return 'error';
            if (cls.includes('warning')) return 'warning';
            if (cls.includes('info')) return 'info';
        }
        
        return 'info'; // Default
    }

    /**
     * Monitor for new alerts and convert them to toasts
     */
    monitorAlerts() {
        // Create a MutationObserver to watch for new alerts
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        // Check if the added node is an alert or contains alerts
                        if (node.classList && (node.classList.contains('webops-alert') || node.classList.contains('auth-alert'))) {
                            this.convertAlertsToToasts();
                        } else if (node.querySelectorAll) {
                            const alerts = node.querySelectorAll('.webops-alert, .auth-alert');
                            if (alerts.length > 0) {
                                this.convertAlertsToToasts();
                            }
                        }
                    }
                });
            });
        });

        // Start observing the document body
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        // Store observer for cleanup
        this.alertObserver = observer;
    }

    /**
     * Initialize the toast system and start monitoring alerts
     */
    initialize() {
        // Convert existing alerts
        this.convertAlertsToToasts();
        
        // Start monitoring for new alerts
        this.monitorAlerts();
        
        console.log('WebOps Toast Manager initialized');
    }

    /**
     * Cleanup resources
     */
    destroy() {
        // Hide all toasts
        this.hideAll();
        
        // Stop monitoring alerts
        if (this.alertObserver) {
            this.alertObserver.disconnect();
        }
        
        // Remove container
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
        
        // Clear references
        this.container = null;
        this.toasts.clear();
    }
}

// Initialize toast manager when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Create global toast manager instance
    window.WebOpsToast = new ToastManager();
    
    // Initialize the system
    window.WebOpsToast.initialize();
    
    // Add to global WebOps object if it exists
    if (window.WebOps) {
        window.WebOps.ToastManager = window.WebOpsToast;
        
        // Update the existing Toast methods to use the new system
        window.WebOps.Toast = {
            success: (message, options) => window.WebOpsToast.success(message, options),
            error: (message, options) => window.WebOpsToast.error(message, options),
            warning: (message, options) => window.WebOpsToast.warning(message, options),
            info: (message, options) => window.WebOpsToast.info(message, options),
            show: (message, type, duration) => window.WebOpsToast.show({ message, type, duration }),
            hide: (id) => window.WebOpsToast.hide(id),
            hideAll: () => window.WebOpsToast.hideAll()
        };
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ToastManager;
}