/**
 * Sidebar Toggle Manager
 * Handles minimize/maximize functionality for the sidebar
 */
class SidebarToggleManager {
    constructor() {
        this.sidebar = null;
        this.toggleButton = null;
        this.mainContent = null;
        this.isMinimized = false;
        this.initialized = false;
        
        // Bind methods to maintain context
        this.toggleHandler = this.toggleSidebar.bind(this);
        
        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }
    
    init() {
        this.sidebar = document.querySelector('.webops-sidebar');
        this.toggleButton = document.getElementById('btn-toggle-sidebar');
        this.mainContent = document.querySelector('.webops-main-content');
        
        if (!this.sidebar || !this.toggleButton) {
            console.warn('Sidebar toggle elements not found');
            return;
        }
        
        // Restore sidebar state from localStorage
        this.restoreState();
        
        // Setup toggle button event
        this.toggleButton.addEventListener('click', this.toggleHandler);
        
        // Update toggle button icon based on current state
        this.updateToggleIcon();
        
        this.initialized = true;
        console.log('Sidebar toggle manager initialized');
    }
    
    restoreState() {
        const savedState = localStorage.getItem('sidebar-minimized');
        this.isMinimized = savedState === 'true';
        
        if (this.isMinimized) {
            this.sidebar.classList.add('minimized');
            if (this.mainContent) {
                this.mainContent.classList.add('expanded');
            }
        }
    }
    
    toggleSidebar() {
        if (!this.sidebar || !this.toggleButton) return;
        
        this.isMinimized = !this.isMinimized;
        
        // Toggle CSS classes
        this.sidebar.classList.toggle('minimized');
        if (this.mainContent) {
            this.mainContent.classList.toggle('expanded');
        }
        
        // Save state to localStorage
        localStorage.setItem('sidebar-minimized', this.isMinimized);
        
        // Update toggle button icon
        this.updateToggleIcon();
        
        // Dispatch custom event for other components
        const event = new CustomEvent('sidebarToggle', {
            detail: { minimized: this.isMinimized }
        });
        document.dispatchEvent(event);
        
        console.log(`Sidebar ${this.isMinimized ? 'minimized' : 'maximized'}`);
    }
    
    updateToggleIcon() {
        if (!this.toggleButton) return;
        
        const icon = this.toggleButton.querySelector('.material-icons');
        if (icon) {
            // Show chevron_right when minimized (indicating it can be expanded)
            // Show chevron_left when maximized (indicating it can be minimized)
            icon.textContent = this.isMinimized ? 'chevron_right' : 'chevron_left';
        }
    }
    
    // Public methods for external use
    minimize() {
        if (!this.isMinimized) {
            this.toggleSidebar();
        }
    }
    
    maximize() {
        if (this.isMinimized) {
            this.toggleSidebar();
        }
    }
    
    getState() {
        return {
            minimized: this.isMinimized,
            initialized: this.initialized
        };
    }
}

// Initialize the sidebar toggle manager
const sidebarToggleManager = new SidebarToggleManager();

// Export for use in other modules if needed
window.SidebarToggleManager = SidebarToggleManager;
window.sidebarToggleManager = sidebarToggleManager;