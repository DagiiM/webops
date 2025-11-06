/**
 * WebOps AI Chat Interface
 * Comprehensive chat functionality with API and WebSocket integration
 */

class WebOpsChatInterface {
    constructor() {
        this.messages = [];
        this.isConnected = false;
        this.websocket = null;
        this.retryCount = 0;
        this.maxRetries = 3;
        this.retryDelay = 1000;
        this.apiBaseUrl = window.location.origin;
        this.isTyping = false;
        this.messageIdCounter = 0;
        
        this.init();
    }

    /**
     * Initialize the chat interface
     */
    init() {
        this.bindEvents();
        this.initializeWebSocket();
        this.loadChatHistory();
        this.focusInput();
        this.setupAccessibility();
    }

    /**
     * Bind all event listeners
     */
    bindEvents() {
        const chatInput = document.getElementById('chatInput');
        const sendButton = document.getElementById('sendButton');
        const attachButton = document.getElementById('attachButton');
        const quickActions = document.getElementById('quickActions');
        const sidebarClose = document.getElementById('sidebarClose');
        
        // Input events
        chatInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
        chatInput.addEventListener('input', (e) => this.handleInput(e));
        chatInput.addEventListener('paste', (e) => this.handlePaste(e));
        
        // Button events
        sendButton.addEventListener('click', () => this.sendMessage());
        attachButton.addEventListener('click', () => this.handleFileAttach());
        sidebarClose.addEventListener('click', () => this.toggleSidebar());
        
        // Quick actions
        quickActions.addEventListener('click', (e) => {
            if (e.target.classList.contains('webops-chat-quick-action')) {
                this.handleQuickAction(e.target.dataset.action);
            }
        });
        
        // Auto-resize textarea
        this.autoResizeTextarea(chatInput);
    }

    /**
     * Handle keyboard events
     */
    handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendMessage();
        }
    }

    /**
     * Handle input changes
     */
    handleInput(e) {
        const textarea = e.target;
        const sendButton = document.getElementById('sendButton');
        
        // Auto-resize
        this.autoResizeTextarea(textarea);
        
        // Enable/disable send button
        const hasText = textarea.value.trim().length > 0;
        sendButton.disabled = !hasText || !this.isConnected;
        
        // Send typing indicator if needed
        if (hasText && !this.isTyping && this.isConnected) {
            this.sendTypingIndicator();
        }
    }

    /**
     * Auto-resize textarea
     */
    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        const newHeight = Math.min(textarea.scrollHeight, 120);
        textarea.style.height = newHeight + 'px';
    }

    /**
     * Send a chat message
     */
    async sendMessage() {
        const chatInput = document.getElementById('chatInput');
        const messageText = chatInput.value.trim();
        
        if (!messageText || !this.isConnected) return;
        
        // Clear input
        chatInput.value = '';
        document.getElementById('sendButton').disabled = true;
        this.autoResizeTextarea(chatInput);
        
        // Add user message to UI
        const userMessage = this.addMessage('user', messageText);
        
        // Send to API
        try {
            await this.sendToAPI({
                type: 'chat_message',
                content: messageText,
                messageId: userMessage.id,
                timestamp: new Date().toISOString()
            });
            
            // Show typing indicator
            this.showTypingIndicator();
            
        } catch (error) {
            this.addSystemMessage('Failed to send message. Please check your connection.', 'error');
            console.error('Send message error:', error);
        }
    }

    /**
     * Add a message to the chat
     */
    addMessage(type, content, options = {}) {
        const messageId = ++this.messageIdCounter;
        const timestamp = new Date();
        const messageElement = this.createMessageElement({
            id: messageId,
            type,
            content,
            timestamp,
            ...options
        });
        
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.appendChild(messageElement);
        this.scrollToBottom();
        
        // Store in memory
        const message = { id: messageId, type, content, timestamp, ...options };
        this.messages.push(message);
        
        return message;
    }

    /**
     * Create a message DOM element
     */
    createMessageElement(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `webops-chat-message webops-chat-message--${message.type}`;
        messageDiv.dataset.messageId = message.id;
        
        const avatarIcon = this.getAvatarIcon(message.type);
        const senderName = this.getSenderName(message.type);
        
        messageDiv.innerHTML = `
            <div class="webops-chat-message__wrapper">
                <div class="webops-chat-message__avatar">
                    <span class="material-icons">${avatarIcon}</span>
                </div>
                <div class="webops-chat-message__content">
                    <div class="webops-chat-message__header">
                        <span class="webops-chat-message__sender">${senderName}</span>
                        <span class="webops-chat-message__timestamp">${this.formatTime(message.timestamp)}</span>
                    </div>
                    <div class="webops-chat-message__text">${this.formatMessageContent(message.content, message.type)}</div>
                    ${this.createMessageActions(message)}
                </div>
            </div>
        `;
        
        return messageDiv;
    }

    /**
     * Get avatar icon based on message type
     */
    getAvatarIcon(type) {
        const icons = {
            user: 'person',
            assistant: 'smart_toy',
            system: 'info',
            error: 'error',
            success: 'check_circle'
        };
        return icons[type] || 'info';
    }

    /**
     * Get sender name based on message type
     */
    getSenderName(type) {
        const names = {
            user: 'You',
            assistant: 'AI Assistant',
            system: 'System',
            error: 'System',
            success: 'System'
        };
        return names[type] || 'Unknown';
    }

    /**
     * Format message content
     */
    formatMessageContent(content, type) {
        if (type === 'user') {
            return this.escapeHtml(content).replace(/\n/g, '<br>');
        }
        
        // Format AI/system responses
        return this.formatCodeBlocks(this.escapeHtml(content).replace(/\n/g, '<br>'));
    }

    /**
     * Format code blocks in messages
     */
    formatCodeBlocks(content) {
        // Inline code
        content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // Code blocks
        content = content.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
        
        // Lists
        content = content.replace(/^• (.+)$/gm, '<li>$1</li>');
        content = content.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
        
        // Links
        content = content.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        
        return content;
    }

    /**
     * Create message actions (copy, retry, etc.)
     */
    createMessageActions(message) {
        if (message.type === 'assistant' || message.type === 'system') {
            return `
                <div class="webops-chat-message__actions">
                    <button class="webops-chat-input__button webops-chat-input__button--attach" 
                            onclick="webopsChat.copyMessage('${message.id}')" 
                            title="Copy message"
                            aria-label="Copy message">
                        <span class="material-icons">content_copy</span>
                    </button>
                    <button class="webops-chat-input__button webops-chat-input__button--attach" 
                            onclick="webopsChat.retryMessage('${message.id}')" 
                            title="Retry"
                            aria-label="Retry message">
                        <span class="material-icons">refresh</span>
                    </button>
                </div>
            `;
        }
        return '';
    }

    /**
     * Show typing indicator
     */
    showTypingIndicator() {
        const typingIndicator = document.getElementById('typingIndicator');
        typingIndicator.style.display = 'flex';
        this.isTyping = true;
        this.scrollToBottom();
    }

    /**
     * Hide typing indicator
     */
    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typingIndicator');
        typingIndicator.style.display = 'none';
        this.isTyping = false;
    }

    /**
     * Add system message
     */
    addSystemMessage(content, type = 'system') {
        return this.addMessage(type, content);
    }

    /**
     * API Communication
     */
    async sendToAPI(data) {
        const token = this.getAuthToken();
        const response = await fetch(`${this.apiBaseUrl}/api/agents/chat/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': token ? `Bearer ${token}` : '',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            throw new Error(`API request failed: ${response.status}`);
        }
        
        return await response.json();
    }

    /**
     * Get authentication token
     */
    getAuthToken() {
        // Try to get token from various sources
        return localStorage.getItem('auth_token') || 
               sessionStorage.getItem('auth_token') ||
               this.getCookie('auth_token');
    }

    /**
     * Get CSRF token
     */
    getCsrfToken() {
        return this.getCookie('csrftoken') || 
               document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
               '';
    }

    /**
     * Get cookie value
     */
    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return '';
    }

    /**
     * WebSocket Communication
     */
    initializeWebSocket() {
        const wsUrl = this.getWebSocketUrl();
        
        try {
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                this.handleWebSocketOpen();
            };
            
            this.websocket.onmessage = (event) => {
                this.handleWebSocketMessage(event);
            };
            
            this.websocket.onclose = (event) => {
                this.handleWebSocketClose(event);
            };
            
            this.websocket.onerror = (error) => {
                this.handleWebSocketError(error);
            };
            
        } catch (error) {
            console.error('WebSocket initialization failed:', error);
            this.updateConnectionStatus('disconnected');
        }
    }

    /**
     * Get WebSocket URL
     */
    getWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const token = this.getAuthToken();
        return `${protocol}//${host}/ws/agents/chat/?token=${token}`;
    }

    /**
     * Handle WebSocket open
     */
    handleWebSocketOpen() {
        this.isConnected = true;
        this.retryCount = 0;
        this.updateConnectionStatus('connected');
        this.hideTypingIndicator();
        
        // Send initial message
        this.sendWebSocketMessage({
            type: 'hello',
            client: 'webops-chat',
            timestamp: new Date().toISOString()
        });
    }

    /**
     * Handle WebSocket messages
     */
    handleWebSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);
            
            switch (data.type) {
                case 'chat_response':
                    this.handleChatResponse(data);
                    break;
                case 'typing_start':
                    this.showTypingIndicator();
                    break;
                case 'typing_stop':
                    this.hideTypingIndicator();
                    break;
                case 'system_notification':
                    this.handleSystemNotification(data);
                    break;
                case 'error':
                    this.handleWebSocketError(data);
                    break;
                default:
                    console.log('Unknown WebSocket message type:', data.type);
            }
        } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
        }
    }

    /**
     * Handle chat response from WebSocket
     */
    handleChatResponse(data) {
        this.hideTypingIndicator();
        
        if (data.content) {
            this.addMessage('assistant', data.content, {
                originalMessageId: data.originalMessageId,
                actions: data.actions || []
            });
        }
        
        if (data.suggestions) {
            this.showSuggestions(data.suggestions);
        }
    }

    /**
     * Handle system notifications
     */
    handleSystemNotification(data) {
        this.addSystemMessage(data.content, data.level || 'info');
    }

    /**
     * Handle WebSocket close
     */
    handleWebSocketClose(event) {
        this.isConnected = false;
        this.updateConnectionStatus('disconnected');
        this.hideTypingIndicator();
        
        // Attempt reconnection
        if (this.retryCount < this.maxRetries) {
            setTimeout(() => {
                this.retryCount++;
                this.initializeWebSocket();
            }, this.retryDelay * Math.pow(2, this.retryCount));
        }
    }

    /**
     * Handle WebSocket errors
     */
    handleWebSocketError(error) {
        console.error('WebSocket error:', error);
        this.updateConnectionStatus('error');
    }

    /**
     * Send WebSocket message
     */
    sendWebSocketMessage(data) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify(data));
        }
    }

    /**
     * Send typing indicator
     */
    sendTypingIndicator() {
        this.sendWebSocketMessage({
            type: 'typing',
            timestamp: new Date().toISOString()
        });
    }

    /**
     * Update connection status
     */
    updateConnectionStatus(status) {
        const indicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('connectionStatus');
        
        indicator.className = `webops-chat-status-indicator ${status}`;
        
        const statusMessages = {
            connected: 'Connected',
            connecting: 'Connecting...',
            disconnected: 'Disconnected',
            error: 'Connection Error'
        };
        
        statusText.textContent = statusMessages[status] || 'Unknown';
    }

    /**
     * Quick Actions Handler
     */
    async handleQuickAction(action) {
        const actionMessages = {
            'deploy-app': 'I want to deploy a new application. Can you help me with that?',
            'check-health': 'Please check the system health and status.',
            'list-deployments': 'Show me all current deployments.',
            'security-audit': 'Perform a security audit of the system.'
        };
        
        const message = actionMessages[action];
        if (message) {
            const chatInput = document.getElementById('chatInput');
            chatInput.value = message;
            this.handleInput({ target: chatInput });
            this.sendMessage();
        }
    }

    /**
     * Handle file attachment
     */
    handleFileAttach() {
        const input = document.createElement('input');
        input.type = 'file';
        input.multiple = true;
        input.accept = '.txt,.log,.json,.md,.py,.js,.html,.css';
        
        input.onchange = (e) => {
            const files = Array.from(e.target.files);
            if (files.length > 0) {
                this.processAttachments(files);
            }
        };
        
        input.click();
    }

    /**
     * Process file attachments
     */
    async processAttachments(files) {
        for (const file of files) {
            try {
                const content = await this.readFileContent(file);
                this.addMessage('user', `📎 Attached: ${file.name}\n\`\`\`\n${content}\n\`\`\``);
            } catch (error) {
                this.addSystemMessage(`Failed to read file: ${file.name}`, 'error');
            }
        }
    }

    /**
     * Read file content
     */
    readFileContent(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(reader.error);
            reader.readAsText(file);
        });
    }

    /**
     * Show suggestions
     */
    showSuggestions(suggestions) {
        const quickActions = document.getElementById('quickActions');
        // Update quick actions with suggestions
        console.log('Suggestions received:', suggestions);
    }

    /**
     * Utility Functions
     */
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    formatTime(timestamp) {
        return new Date(timestamp).toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
    
    scrollToBottom() {
        const messagesContainer = document.getElementById('chatMessages');
        setTimeout(() => {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }, 100);
    }
    
    focusInput() {
        document.getElementById('chatInput').focus();
    }

    /**
     * Copy message to clipboard
     */
    copyMessage(messageId) {
        const message = this.messages.find(m => m.id == messageId);
        if (message) {
            navigator.clipboard.writeText(message.content).then(() => {
                this.showToast('Message copied to clipboard');
            });
        }
    }

    /**
     * Retry message
     */
    retryMessage(messageId) {
        const message = this.messages.find(m => m.id == messageId);
        if (message && message.type === 'user') {
            const chatInput = document.getElementById('chatInput');
            chatInput.value = message.content;
            this.handleInput({ target: chatInput });
            this.sendMessage();
        }
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `webops-toast webops-toast--${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--webops-color-surface);
            border: 1px solid var(--webops-color-primary-alpha-20);
            border-radius: var(--webops-radius-md);
            padding: var(--webops-space-2) var(--webops-space-3);
            color: var(--webops-color-text-primary);
            z-index: 10000;
            animation: webopsToastSlideIn 0.3s ease-out;
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'webopsToastSlideOut 0.3s ease-out';
            setTimeout(() => document.body.removeChild(toast), 300);
        }, 3000);
    }

    /**
     * Toggle sidebar
     */
    toggleSidebar() {
        const sidebar = document.getElementById('chatSidebar');
        sidebar.classList.toggle('open');
    }

    /**
     * Load chat history from storage
     */
    loadChatHistory() {
        try {
            const history = localStorage.getItem('webops-chat-history');
            if (history) {
                const messages = JSON.parse(history);
                // Load recent messages (last 50)
                messages.slice(-50).forEach(msg => {
                    if (msg.type !== 'system') { // Don't reload system welcome messages
                        this.addMessage(msg.type, msg.content, {
                            timestamp: new Date(msg.timestamp)
                        });
                    }
                });
            }
        } catch (error) {
            console.error('Failed to load chat history:', error);
        }
    }

    /**
     * Save chat history
     */
    saveChatHistory() {
        try {
            const recentMessages = this.messages.slice(-100); // Keep last 100 messages
            localStorage.setItem('webops-chat-history', JSON.stringify(recentMessages));
        } catch (error) {
            console.error('Failed to save chat history:', error);
        }
    }

    /**
     * Accessibility setup
     */
    setupAccessibility() {
        // Add ARIA labels and roles
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.setAttribute('role', 'log');
        messagesContainer.setAttribute('aria-live', 'polite');
        messagesContainer.setAttribute('aria-label', 'Chat messages');
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.altKey && e.key === 'h') {
                this.toggleSidebar();
            }
        });
        
        // Focus management
        this.setupFocusManagement();
    }

    /**
     * Setup focus management for accessibility
     */
    setupFocusManagement() {
        const chatInput = document.getElementById('chatInput');
        let lastFocusedElement = null;
        
        chatInput.addEventListener('focus', () => {
            lastFocusedElement = document.activeElement;
        });
        
        // Trap focus in modal when needed
        document.addEventListener('focus', (e) => {
            if (document.querySelector('.webops-chat-sidebar.open')) {
                const sidebar = document.getElementById('chatSidebar');
                if (!sidebar.contains(e.target)) {
                    e.stopPropagation();
                    sidebar.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')?.focus();
                }
            }
        });
    }

    /**
     * Cleanup when page unloads
     */
    destroy() {
        if (this.websocket) {
            this.websocket.close();
        }
        this.saveChatHistory();
    }
}

// Global instances and functions
let webopsChat;

// Initialize chat when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    webopsChat = new WebOpsChatInterface();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (webopsChat) {
        webopsChat.destroy();
    }
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebOpsChatInterface;
}