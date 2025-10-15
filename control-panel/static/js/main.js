/**
 * WebOps Control Panel - Premium JavaScript
 * Pure vanilla ES6+ - zero frameworks
 */

'use strict';

class GraphBackground {
    constructor() {
        this.nodes = [];
        this.nodeCount = 20;
        this.init();
    }

    init() {
        const bg = document.querySelector('.app-background');
        if (!bg) return;

        const container = document.createElement('div');
        container.className = 'graph-nodes';
        bg.appendChild(container);

        for (let i = 0; i < this.nodeCount; i++) {
            const node = document.createElement('div');
            node.className = 'graph-node';
            node.style.left = Math.random() * 100 + '%';
            node.style.top = Math.random() * 100 + '%';
            node.style.animationDelay = Math.random() * 20 + 's';
            container.appendChild(node);
        }
    }
}

class Loader {
    static timeout = null;
    static maxDuration = 30000; // 30 seconds max

    static show(message = 'Loading') {
        const loader = document.getElementById('webopsLoader');
        const text = loader?.querySelector('.webops-loader-text');

        if (loader) {
            if (text) text.textContent = message;
            loader.classList.add('active');

            // Auto-hide after max duration to prevent stuck loaders
            if (this.timeout) clearTimeout(this.timeout);
            this.timeout = setTimeout(() => {
                this.hide();
                console.warn('Loader auto-hidden after timeout');
            }, this.maxDuration);
        }
    }

    static hide() {
        const loader = document.getElementById('webopsLoader');
        if (loader) {
            loader.classList.remove('active');
        }

        // Clear timeout
        if (this.timeout) {
            clearTimeout(this.timeout);
            this.timeout = null;
        }
    }

    static async wrap(promise, message = 'Loading') {
        this.show(message);
        try {
            const result = await promise;
            return result;
        } finally {
            this.hide();
        }
    }
}

class Toast {
    static show(message, type = 'info', duration = 5000) {
        const toast = document.createElement('div');
        toast.className = 'toast toast-' + type;
        toast.textContent = message;
        toast.style.cssText = 'position:fixed;top:24px;right:24px;background:rgba(20,26,23,0.95);backdrop-filter:blur(20px);border:1px solid var(--color-' + (type === 'error' ? 'error' : 'success') + ');border-radius:8px;padding:16px 24px;color:var(--webops-color-text-primary);box-shadow:0 8px 32px rgba(0,0,0,0.5);z-index:9999;opacity:0;transform:translateX(400px);transition:all 0.3s';
        document.body.appendChild(toast);
        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(0)';
        });
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(400px)';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    static success(msg) { this.show(msg, 'success'); }
    static error(msg) { this.show(msg, 'error'); }
}

class APIClient {
    constructor(baseURL = '/api') {
        this.baseURL = baseURL;
    }

    async request(endpoint, options = {}) {
        const url = this.baseURL + endpoint;
        const token = document.querySelector('meta[name="csrf-token"]')?.content || '';

        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    'X-CSRFToken': token,
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
            });

            if (!response.ok) throw new Error('HTTP ' + response.status);
            return await response.json();
        } catch (error) {
            Toast.error(error.message);
            throw error;
        }
    }

    get(endpoint) { return this.request(endpoint); }
    post(endpoint, data) { return this.request(endpoint, { method: 'POST', body: JSON.stringify(data) }); }
}

// Global error handlers for "no broken windows" philosophy
class ErrorBoundary {
    static init() {
        // Handle uncaught JavaScript errors
        window.addEventListener('error', (event) => {
            console.error('Uncaught error:', event.error);
            ErrorBoundary.handleError(event.error || new Error(event.message));
            event.preventDefault();
        });

        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled promise rejection:', event.reason);
            ErrorBoundary.handleError(event.reason);
            event.preventDefault();
        });
    }

    static handleError(error) {
        const message = error.message || 'An unexpected error occurred';

        // Show user-friendly error toast
        if (window.WebOps && window.WebOps.Toast) {
            window.WebOps.Toast.error('Something went wrong. Please try again.');
        }

        // Log to server (optional - could add endpoint)
        ErrorBoundary.logErrorToServer(error);
    }

    static logErrorToServer(error) {
        // Optional: Send error to server for logging
        const errorData = {
            message: error.message,
            stack: error.stack,
            url: window.location.href,
            userAgent: navigator.userAgent,
            timestamp: new Date().toISOString()
        };

        // Could implement server-side error logging endpoint
        // fetch('/api/errors/log/', {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify(errorData)
        // }).catch(() => {}); // Silent fail
    }
}


class SidebarManager {
    constructor() {
        this.sidebar = null;
        this.toggle = null;
        this.overlay = null;
        this.isOpen = false;
        this.initialized = false;
        
        // Bind methods to maintain context
        this.toggleHandler = this.toggleSidebar.bind(this);
        this.overlayHandler = this.closeSidebar.bind(this);
        this.keydownHandler = this.handleKeydown.bind(this);
        this.resizeHandler = this.handleResize.bind(this);
        this.navLinkHandler = this.handleNavLinkClick.bind(this);
        
        // Use DOMContentLoaded or defer init if DOM might not be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    init() {
        if (this.initialized) {
            return;
        }

        this.sidebar = document.querySelector('.webops-sidebar');
        this.toggle = document.querySelector('.webops-sidebar-toggle');
        this.overlay = document.querySelector('.webops-sidebar-overlay');

        if (!this.sidebar || !this.toggle) {
            console.warn('Sidebar or toggle elements not found');
            return;
        }

        // Create overlay if it doesn't exist
        if (!this.overlay) {
            this.createOverlay();
        }

        // Initialize state from DOM and sync overlay
        this.isOpen = this.sidebar.classList.contains('active');
        if (this.isOpen && this.overlay) {
            this.overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
            if (this.toggle && this.toggle.hasAttribute('aria-expanded')) {
                this.toggle.setAttribute('aria-expanded', 'true');
            }
        }

        this.bindEvents();
        this.handleResize();
        this.initialized = true;
    }

    createOverlay() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'webops-sidebar-overlay';
        document.body.appendChild(this.overlay);
    }

    bindEvents() {
        // Toggle button click
        this.toggle.addEventListener('click', this.toggleHandler);

        // Overlay click to close
        if (this.overlay) {
            this.overlay.addEventListener('click', this.overlayHandler);
        }

        // Escape key to close
        document.addEventListener('keydown', this.keydownHandler);

        // Handle window resize
        window.addEventListener('resize', this.resizeHandler);

        // Close sidebar when clicking nav links on mobile
        if (this.sidebar) {
            const navLinks = this.sidebar.querySelectorAll('.webops-nav-item');
            navLinks.forEach(link => {
                link.addEventListener('click', this.navLinkHandler);
            });
        }
    }

    handleKeydown(e) {
        if (e.key === 'Escape' && this.isOpen) {
            this.closeSidebar();
        }
    }

    handleNavLinkClick() {
        if (window.innerWidth <= 768) {
            this.closeSidebar();
        }
    }

    toggleSidebar() {
        if (this.isOpen) {
            this.closeSidebar();
        } else {
            this.openSidebar();
        }
    }

    openSidebar() {
        if (!this.sidebar) return;
        
        this.sidebar.classList.add('active');
        if (this.overlay) {
            this.overlay.classList.add('active');
        }
        this.isOpen = true;
        document.body.style.overflow = 'hidden';
        
        // Update toggle button state if it has aria attributes
        if (this.toggle && this.toggle.hasAttribute('aria-expanded')) {
            this.toggle.setAttribute('aria-expanded', 'true');
        }
    }

    closeSidebar() {
        if (!this.sidebar) return;
        
        this.sidebar.classList.remove('active');
        if (this.overlay) {
            this.overlay.classList.remove('active');
        }
        this.isOpen = false;
        document.body.style.overflow = '';
        
        // Update toggle button state if it has aria attributes
        if (this.toggle && this.toggle.hasAttribute('aria-expanded')) {
            this.toggle.setAttribute('aria-expanded', 'false');
        }
    }

    handleResize() {
        // Auto-close sidebar on desktop resize
        if (window.innerWidth > 768 && this.isOpen) {
            this.closeSidebar();
        }
    }

    // Public methods to control sidebar externally
    open() {
        this.openSidebar();
    }

    close() {
        this.closeSidebar();
    }

    // Cleanup method to remove event listeners
    destroy() {
        if (this.toggle) {
            this.toggle.removeEventListener('click', this.toggleHandler);
        }
        if (this.overlay) {
            this.overlay.removeEventListener('click', this.overlayHandler);
        }
        
        document.removeEventListener('keydown', this.keydownHandler);
        window.removeEventListener('resize', this.resizeHandler);
        
        if (this.sidebar) {
            const navLinks = this.sidebar.querySelectorAll('.webops-nav-item');
            navLinks.forEach(link => {
                link.removeEventListener('click', this.navLinkHandler);
            });
        }
        
        // Clean up overlay if it was created by this instance
        if (this.overlay && this.overlay.parentNode) {
            this.overlay.parentNode.removeChild(this.overlay);
        }
        
        this.initialized = false;
    }
}


// Retry mechanism for failed requests
class RetryManager {
    static async withRetry(fn, maxRetries = 3, delay = 1000) {
        let lastError;

        for (let attempt = 0; attempt < maxRetries; attempt++) {
            try {
                return await fn();
            } catch (error) {
                lastError = error;

                if (attempt < maxRetries - 1) {
                    // Wait before retrying (exponential backoff)
                    await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, attempt)));
                }
            }
        }

        throw lastError;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Initialize error boundary
    ErrorBoundary.init();

    // Initialize components
    try {
        new GraphBackground();
        const sidebarManager = new SidebarManager();
        
        window.WebOps = {
            API: new APIClient(),
            Loader,
            Toast,
            ErrorBoundary,
            RetryManager,
            Sidebar: sidebarManager
        };
        console.log('%cWebOps', 'color: #00ff88; font-size: 24px; font-weight: bold;');
    } catch (error) {
        console.error('Failed to initialize WebOps:', error);
        ErrorBoundary.handleError(error);
    }

    // Loader escape key handler
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const loader = document.getElementById('webopsLoader');
            if (loader && loader.classList.contains('active')) {
                Loader.hide();
            }
        }
    });

    // Loader click-to-dismiss (click on overlay, not the loader itself)
    const loaderOverlay = document.getElementById('webopsLoader');
    if (loaderOverlay) {
        loaderOverlay.addEventListener('click', (e) => {
            if (e.target === loaderOverlay) {
                Loader.hide();
            }
        });
    }
});

// Global helper functions for convenience
function showLoader(message) {
    if (window.WebOps && window.WebOps.Loader) {
        window.WebOps.Loader.show(message);
    }
}

function hideLoader() {
    if (window.WebOps && window.WebOps.Loader) {
        window.WebOps.Loader.hide();
    }
}
