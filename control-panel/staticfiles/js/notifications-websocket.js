/**
 * WebOps Notifications WebSocket Client
 *
 * Provides real-time notification delivery via WebSocket connection.
 * Automatically handles reconnection and integrates with NotificationsCenter.
 */

'use strict';

class NotificationsWebSocket {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.maxReconnectDelay = 30000; // Max 30 seconds
        this.isConnected = false;
        this.messageHandlers = [];
        this.connectionHandlers = [];
        this.disconnectionHandlers = [];
        this.shouldReconnect = true;
    }

    /**
     * Connect to the WebSocket server
     */
    connect() {
        if (this.socket && this.isConnected) {
            console.log('WebSocket already connected');
            return;
        }

        // Determine WebSocket protocol (ws:// or wss://)
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/notifications/`;

        console.log(`Connecting to WebSocket: ${wsUrl}`);

        try {
            this.socket = new WebSocket(wsUrl);

            this.socket.onopen = (event) => {
                console.log('WebSocket connected successfully');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.reconnectDelay = 1000;

                // Notify connection handlers
                this.connectionHandlers.forEach(handler => {
                    try {
                        handler(event);
                    } catch (error) {
                        console.error('Error in connection handler:', error);
                    }
                });
            };

            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };

            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            this.socket.onclose = (event) => {
                console.log('WebSocket disconnected', event.code, event.reason);
                this.isConnected = false;

                // Notify disconnection handlers
                this.disconnectionHandlers.forEach(handler => {
                    try {
                        handler(event);
                    } catch (error) {
                        console.error('Error in disconnection handler:', error);
                    }
                });

                // Attempt to reconnect if appropriate
                if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.scheduleReconnect();
                }
            };
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
        }
    }

    /**
     * Schedule a reconnection attempt with exponential backoff
     */
    scheduleReconnect() {
        this.reconnectAttempts++;

        console.log(`Scheduling reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${this.reconnectDelay}ms`);

        setTimeout(() => {
            console.log('Attempting to reconnect...');
            this.connect();
        }, this.reconnectDelay);

        // Exponential backoff
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
    }

    /**
     * Disconnect from the WebSocket server
     */
    disconnect() {
        this.shouldReconnect = false;

        if (this.socket) {
            console.log('Disconnecting WebSocket');
            this.socket.close();
            this.socket = null;
        }

        this.isConnected = false;
    }

    /**
     * Send a message to the WebSocket server
     * @param {Object} message - Message object to send
     */
    send(message) {
        if (!this.isConnected || !this.socket) {
            console.error('Cannot send message: WebSocket not connected');
            return false;
        }

        try {
            this.socket.send(JSON.stringify(message));
            return true;
        } catch (error) {
            console.error('Error sending WebSocket message:', error);
            return false;
        }
    }

    /**
     * Handle incoming WebSocket messages
     * @param {Object} data - Parsed message data
     */
    handleMessage(data) {
        console.log('WebSocket message received:', data.type);

        // Notify all message handlers
        this.messageHandlers.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error('Error in message handler:', error);
            }
        });
    }

    /**
     * Register a message handler
     * @param {Function} handler - Function to call when a message is received
     */
    onMessage(handler) {
        this.messageHandlers.push(handler);
    }

    /**
     * Register a connection handler
     * @param {Function} handler - Function to call when connected
     */
    onConnect(handler) {
        this.connectionHandlers.push(handler);
    }

    /**
     * Register a disconnection handler
     * @param {Function} handler - Function to call when disconnected
     */
    onDisconnect(handler) {
        this.disconnectionHandlers.push(handler);
    }

    /**
     * Send command to get notifications
     * @param {Object} options - Query options (limit, offset, unread_only, type)
     */
    getNotifications(options = {}) {
        return this.send({
            command: 'get_notifications',
            limit: options.limit || 50,
            offset: options.offset || 0,
            unread_only: options.unread_only || false,
            type: options.type || null
        });
    }

    /**
     * Send command to mark notification as read
     * @param {number} notificationId - ID of notification to mark as read
     */
    markAsRead(notificationId) {
        return this.send({
            command: 'mark_read',
            notification_id: notificationId
        });
    }

    /**
     * Send command to mark all notifications as read
     */
    markAllAsRead() {
        return this.send({
            command: 'mark_all_read'
        });
    }

    /**
     * Send command to get unread count
     */
    getUnreadCount() {
        return this.send({
            command: 'get_unread_count'
        });
    }
}

// Create global instance
window.WebOpsNotificationsWS = new NotificationsWebSocket();

// Auto-connect when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.WebOpsNotificationsWS.connect();
    });
} else {
    // DOM already loaded
    window.WebOpsNotificationsWS.connect();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    window.WebOpsNotificationsWS.disconnect();
});

console.log('NotificationsWebSocket module loaded');
