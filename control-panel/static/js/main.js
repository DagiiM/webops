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
    static activeCount = 0; // reference count for concurrent operations

    static show(message = 'Loading') {
        const loader = document.getElementById('webopsLoader');
        const text = loader?.querySelector('.webops-loader-text');

        // Increment active operations
        this.activeCount = Math.max(0, this.activeCount) + 1;

        if (loader) {
            if (text) text.textContent = message;
            loader.classList.add('active');
            loader.setAttribute('aria-hidden', 'false');
            document.body.setAttribute('aria-busy', 'true');

            // Auto-hide after max duration to prevent stuck loaders
            if (this.timeout) clearTimeout(this.timeout);
            this.timeout = setTimeout(() => {
                this.forceHide();
                console.warn('Loader auto-hidden after timeout');
            }, this.maxDuration);
        }
    }

    static hide() {
        // Decrement active operations and only hide when it reaches zero
        this.activeCount = Math.max(0, this.activeCount - 1);

        if (this.activeCount > 0) return;

        const loader = document.getElementById('webopsLoader');
        if (loader) {
            loader.classList.remove('active');
            loader.setAttribute('aria-hidden', 'true');
            document.body.removeAttribute('aria-busy');
        }

        // Clear timeout
        if (this.timeout) {
            clearTimeout(this.timeout);
            this.timeout = null;
        }
    }

    static forceHide() {
        // Immediately reset and hide, useful for timeouts or hard resets
        this.activeCount = 0;
        const loader = document.getElementById('webopsLoader');
        if (loader) {
            loader.classList.remove('active');
            loader.setAttribute('aria-hidden', 'true');
            document.body.removeAttribute('aria-busy');
        }
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
        // Use the new toast system if available
        if (window.WebOpsToast) {
            return window.WebOpsToast.show({ message, type, duration });
        }
        
        // Fallback to the old implementation for backward compatibility
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

    static success(msg, options = {}) {
        if (window.WebOpsToast) {
            return window.WebOpsToast.success(msg, options);
        }
        return this.show(msg, 'success');
    }
    
    static error(msg, options = {}) {
        if (window.WebOpsToast) {
            return window.WebOpsToast.error(msg, options);
        }
        return this.show(msg, 'error');
    }
    
    static warning(msg, options = {}) {
        if (window.WebOpsToast) {
            return window.WebOpsToast.warning(msg, options);
        }
        return this.show(msg, 'warning');
    }
    
    static info(msg, options = {}) {
        if (window.WebOpsToast) {
            return window.WebOpsToast.info(msg, options);
        }
        return this.show(msg, 'info');
    }
    
    static hide(id) {
        if (window.WebOpsToast) {
            return window.WebOpsToast.hide(id);
        }
    }
    
    static hideAll() {
        if (window.WebOpsToast) {
            return window.WebOpsToast.hideAll();
        }
    }
}

class APIClient {
    constructor(baseURL = '/api') {
        this.baseURL = baseURL;
    }

    async request(endpoint, options = {}) {
        const url = this.baseURL + endpoint;
        const token = document.querySelector('meta[name="csrf-token"]')?.content || '';

        const { showLoader: showGlobalLoader = true } = options;
        // Remove our custom flag from fetch options
        const fetchOptions = { ...options };
        delete fetchOptions.showLoader;

        try {
            if (showGlobalLoader && window.WebOps?.Loader) {
                window.WebOps.Loader.show('Loading');
            }

            const response = await fetch(url, {
                ...fetchOptions,
                headers: {
                    'X-CSRFToken': token,
                    'Content-Type': 'application/json',
                    ...fetchOptions.headers,
                },
            });

            if (!response.ok) throw new Error('HTTP ' + response.status);
            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                return await response.json();
            }
            // Fallback to text for non-JSON responses
            return await response.text();
        } catch (error) {
            Toast.error(error.message);
            throw error;
        } finally {
            if (showGlobalLoader && window.WebOps?.Loader) {
                window.WebOps.Loader.hide();
            }
        }
    }

    get(endpoint, options = {}) { return this.request(endpoint, options); }
    post(endpoint, data, options = {}) { return this.request(endpoint, { method: 'POST', body: JSON.stringify(data), ...options }); }
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
    this.sidebar = document.querySelector('.webops-sidebar');
    this.toggle = document.querySelector('.webops-sidebar-toggle');
    this.overlay = document.querySelector('.webops-sidebar-overlay');

    if (!this.sidebar || !this.toggle || !this.overlay) {
        console.warn('Sidebar elements not found');
        return;
    }

    // Initialize sidebar state based on current visibility
    this.isOpen = this.sidebar.classList.contains('active');
    
    this.bindEvents();
    this.handleResize();
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

    // Global navigation loader hooks
    document.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (!link) return;
        if (e.defaultPrevented) return;

        const href = link.getAttribute('href');
        if (!href || href.startsWith('#')) return;
        if (/^(mailto:|tel:|javascript:)/i.test(href)) return;
        if (link.hasAttribute('download') || link.target) return;

        // Same-origin navigation and not just a hash change
        try {
            const dest = new URL(href, document.baseURI);
            const current = new URL(window.location.href);
            const isSameOrigin = dest.origin === current.origin;
            const onlyHashChange = isSameOrigin && dest.pathname === current.pathname && dest.search === current.search && dest.hash && dest.hash !== current.hash;
            if (!isSameOrigin || onlyHashChange) return;
        } catch (err) {
            // If URL parsing fails, be conservative and do nothing
            return;
        }

        // Don't show loader if explicitly disabled
        if (link.dataset.noLoader !== undefined) return;

        Loader.show('Navigating...');
        // Safety timeout: hide if navigation is intercepted (SPA behavior)
        setTimeout(() => {
            if (document.visibilityState === 'visible') {
                Loader.hide();
            }
        }, 2000);
    });

    document.addEventListener('submit', (e) => {
        const form = e.target;
        if (form && form.dataset && form.dataset.noLoader !== undefined) return;
        Loader.show('Submitting...');
        // Safety timeout: hide if submission is intercepted by JS and the page doesn't navigate
        setTimeout(() => {
            if (document.visibilityState === 'visible') {
                Loader.hide();
            }
        }, 2000);
    });

    window.addEventListener('beforeunload', () => {
        Loader.show('Loading page...');
    });
});

// Service Management Functions
async function restartAllServices() {
    // Get all failed services by checking for restart buttons that are visible
    const failedServices = document.querySelectorAll('[id$="-restart-btn"]:not([style*="display: none"])');
    const serviceNames = Array.from(failedServices).map(btn => {
        const match = btn.id.match(/^(.+)-restart-btn$/);
        return match ? match[1] : null;
    }).filter(name => name);
    
    if (serviceNames.length === 0) {
        if (window.WebOps && window.WebOps.Toast) {
            window.WebOps.Toast.info('No failed services to restart');
        }
        return;
    }
    
    // Show loading state
    const restartBtn = event.target.closest('button');
    const originalText = restartBtn.innerHTML;
    restartBtn.innerHTML = '<span class="material-icons" style="animation: spin 1s linear infinite;">autorenew</span> Restarting All...';
    restartBtn.disabled = true;
    
    const results = [];
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    
    // Restart services sequentially with delays to avoid rate limiting
    for (let i = 0; i < serviceNames.length; i++) {
        const serviceName = serviceNames[i];
        
        try {
            // Add delay between requests (1 second between each service)
            if (i > 0) {
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
            
            // Use the correct URL pattern for core services restart
            const response = await fetch(`/deployments/core-services/restart/${serviceName}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });
            
            let data;
            try {
                data = await response.json();
            } catch (e) {
                data = { success: false, message: 'Invalid response from server' };
            }
            
            if (response.status === 429) {
                results.push({ 
                    service: serviceName, 
                    success: false, 
                    message: 'Rate limit exceeded. Please wait a moment and try again.' 
                });
            } else if (response.ok && data.success) {
                results.push({ 
                    service: serviceName, 
                    success: true, 
                    message: data.message || 'Service restarted successfully' 
                });
            } else {
                results.push({ 
                    service: serviceName, 
                    success: false, 
                    message: data.message || `Failed to restart ${serviceName}` 
                });
            }
            
        } catch (error) {
            results.push({ 
                service: serviceName, 
                success: false, 
                message: error.message || 'Network error occurred' 
            });
        }
    }
    
    // Show results summary
    const successful = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success).length;
    const rateLimited = results.filter(r => r.message.includes('Rate limit')).length;
    
    if (successful > 0) {
        if (window.WebOps && window.WebOps.Toast) {
            window.WebOps.Toast.success(`Successfully restarted ${successful} service(s)`);
        }
    }
    
    if (rateLimited > 0) {
        if (window.WebOps && window.WebOps.Toast) {
            window.WebOps.Toast.warning(`${rateLimited} service(s) hit rate limits. Please wait and try again.`);
        }
    }
    
    if (failed > rateLimited && failed > 0) {
        if (window.WebOps && window.WebOps.Toast) {
            window.WebOps.Toast.error(`Failed to restart ${failed - rateLimited} service(s)`);
        }
    }
    
    // Reset button state
    restartBtn.innerHTML = originalText;
    restartBtn.disabled = false;
    
    // Refresh status after all restarts
    setTimeout(() => {
        if (typeof refreshServiceStatus === 'function') {
            refreshServiceStatus();
        } else {
            // Fallback: reload the page if refresh function not available
            window.location.reload();
        }
    }, 2000);
}

function refreshServiceStatus() {
    // Fallback function if not defined in template
    window.location.reload();
}

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
