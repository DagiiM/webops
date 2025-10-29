/**
 * WebOps Notifications API Client
 *
 * Handles all API interactions for the notifications system.
 * Provides methods to fetch, update, and manage user notifications.
 */

'use strict';

class NotificationsAPI {
    constructor() {
        this.baseUrl = '/auth/integrations/notifications/api/notifications';
        this.csrfToken = this.getCSRFToken();
    }

    /**
     * Get CSRF token from cookies
     */
    getCSRFToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    /**
     * Make an API request
     */
    async request(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken,
            },
            credentials: 'same-origin',
        };

        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers,
            },
        };

        try {
            const response = await fetch(url, mergedOptions);

            if (!response.ok) {
                throw new Error(`API request failed: ${response.status} ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API request error:', error);
            throw error;
        }
    }

    /**
     * Get user notifications
     * @param {Object} params - Query parameters
     * @param {boolean} params.unread_only - Only fetch unread notifications
     * @param {number} params.limit - Maximum number of notifications
     * @param {number} params.offset - Offset for pagination
     * @param {string} params.type - Filter by notification type
     */
    async getNotifications(params = {}) {
        const queryParams = new URLSearchParams();

        if (params.unread_only) {
            queryParams.append('unread_only', 'true');
        }
        if (params.limit) {
            queryParams.append('limit', params.limit);
        }
        if (params.offset) {
            queryParams.append('offset', params.offset);
        }
        if (params.type) {
            queryParams.append('type', params.type);
        }

        const url = `${this.baseUrl}/?${queryParams.toString()}`;
        return await this.request(url);
    }

    /**
     * Get unread notification count
     */
    async getUnreadCount() {
        const url = `${this.baseUrl}/unread-count/`;
        return await this.request(url);
    }

    /**
     * Get notification detail
     * @param {number} notificationId - Notification ID
     */
    async getNotificationDetail(notificationId) {
        const url = `${this.baseUrl}/${notificationId}/`;
        return await this.request(url);
    }

    /**
     * Mark notification as read
     * @param {number} notificationId - Notification ID
     */
    async markAsRead(notificationId) {
        const url = `${this.baseUrl}/${notificationId}/mark-read/`;
        return await this.request(url, {
            method: 'POST',
        });
    }

    /**
     * Mark all notifications as read
     */
    async markAllAsRead() {
        const url = `${this.baseUrl}/mark-all-read/`;
        return await this.request(url, {
            method: 'POST',
        });
    }

    /**
     * Delete a notification
     * @param {number} notificationId - Notification ID
     */
    async deleteNotification(notificationId) {
        const url = `${this.baseUrl}/${notificationId}/delete/`;
        return await this.request(url, {
            method: 'POST',
        });
    }

    /**
     * Clear all notifications
     */
    async clearAll() {
        const url = `${this.baseUrl}/clear-all/`;
        return await this.request(url, {
            method: 'POST',
        });
    }
}

// Create global API client instance
window.WebOpsNotificationsAPI = new NotificationsAPI();
