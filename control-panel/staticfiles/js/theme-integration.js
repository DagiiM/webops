/**
 * WebOps Theme Integration
 * Integrates the existing theme switcher UI with the dynamic theme loader
 */

class WebOpsThemeIntegration {
    constructor() {
        this.themeLoader = null;
        this.originalSwitcher = null;
        this.isInitialized = false;
        
        this.init();
    }
    
    /**
     * Initialize the theme integration
     */
    async init() {
        // Wait for both the dynamic loader and original switcher to be available
        await this.waitForDependencies();
        
        // Integrate the systems
        this.integrateSystems();
        
        // Setup theme change listener
        this.setupThemeChangeListener();
        
        this.isInitialized = true;
        console.log('WebOps Theme Integration initialized');
    }
    
    /**
     * Wait for both dynamic loader and original switcher
     */
    async waitForDependencies() {
        return new Promise((resolve) => {
            const checkDependencies = () => {
                if (window.WebOpsThemeLoader && window.WebOpsThemeSwitcher) {
                    this.themeLoader = window.WebOpsThemeLoader;
                    this.originalSwitcher = window.WebOpsThemeSwitcher;
                    resolve();
                } else {
                    setTimeout(checkDependencies, 100);
                }
            };
            
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', checkDependencies);
            } else {
                checkDependencies();
            }
        });
    }
    
    /**
     * Integrate the dynamic loader with the original switcher
     */
    integrateSystems() {
        if (!this.originalSwitcher || !this.themeLoader) {
            console.warn('Cannot integrate: missing dependencies');
            return;
        }
        
        // Override the original switcher's theme methods to use dynamic loader
        const originalCycleTheme = this.originalSwitcher.cycleTheme.bind(this.originalSwitcher);
        const originalApplyTheme = this.originalSwitcher.applyTheme.bind(this.originalSwitcher);
        
        // Override cycleTheme
        this.originalSwitcher.cycleTheme = () => {
            const currentIndex = this.originalSwitcher.themes.indexOf(this.originalSwitcher.currentTheme);
            const nextIndex = (currentIndex + 1) % this.originalSwitcher.themes.length;
            const nextTheme = this.originalSwitcher.themes[nextIndex];
            
            // Use dynamic loader instead
            this.themeLoader.switchTheme(nextTheme);
            
            // Update original switcher's state
            this.originalSwitcher.currentTheme = nextTheme;
            this.originalSwitcher.storeTheme(nextTheme);
            this.originalSwitcher.updateSwitcherUI();
        };
        
        // Override theme selection from dropdown
        this.overrideDropdownHandlers();
        
        // Sync initial theme
        this.syncInitialTheme();
    }
    
    /**
     * Override dropdown theme selection handlers
     */
    overrideDropdownHandlers() {
        // Find all theme options in the dropdown
        const themeOptions = document.querySelectorAll('.webops-theme-option');
        
        themeOptions.forEach(option => {
            const theme = option.dataset.theme;
            
            // Remove existing click handlers and add new ones
            option.replaceWith(option.cloneNode(true));
            
            const newOption = document.querySelector(`[data-theme="${theme}"].webops-theme-option`);
            if (newOption) {
                newOption.addEventListener('click', (e) => {
                    e.preventDefault();
                    
                    // Use dynamic loader
                    this.themeLoader.switchTheme(theme);
                    
                    // Update original switcher state
                    this.originalSwitcher.currentTheme = theme;
                    this.originalSwitcher.storeTheme(theme);
                    this.originalSwitcher.updateSwitcherUI();
                    
                    // Close dropdown
                    const switcher = document.querySelector('.webops-theme-switcher');
                    if (switcher) {
                        switcher.classList.remove('open');
                    }
                });
            }
        });
    }
    
    /**
     * Sync initial theme between systems
     */
    syncInitialTheme() {
        const currentThemeInfo = this.themeLoader.getCurrentTheme();
        
        // Update original switcher to match dynamic loader
        if (currentThemeInfo.name !== this.originalSwitcher.currentTheme) {
            this.originalSwitcher.currentTheme = currentThemeInfo.name;
            this.originalSwitcher.updateSwitcherUI();
        }
    }
    
    /**
     * Setup theme change listener
     */
    setupThemeChangeListener() {
        this.themeLoader.onThemeChange((newTheme, oldTheme) => {
            console.log(`Theme changed from ${oldTheme} to ${newTheme}`);
            
            // Ensure original switcher stays in sync
            if (this.originalSwitcher.currentTheme !== newTheme) {
                this.originalSwitcher.currentTheme = newTheme;
                this.originalSwitcher.storeTheme(newTheme);
                this.originalSwitcher.updateSwitcherUI();
            }
            
            // Show notification
            if (window.WebOps && window.WebOps.Toast) {
                window.WebOps.Toast.success(`Theme switched to ${newTheme}`);
            }
        });
    }
    
    /**
     * Get the integrated theme system info
     */
    getThemeInfo() {
        if (!this.isInitialized) {
            return { error: 'Integration not initialized' };
        }
        
        return {
            currentTheme: this.themeLoader.getCurrentTheme(),
            availableThemes: this.originalSwitcher.themes,
            isDynamicLoaderActive: true,
            isOriginalSwitcherActive: true
        };
    }
}

// Initialize the theme integration when DOM is ready
let themeIntegration = null;

document.addEventListener('DOMContentLoaded', () => {
    themeIntegration = new WebOpsThemeIntegration();
    
    // Make integration available globally
    window.WebOpsThemeIntegration = themeIntegration;
    
    console.log('WebOps Theme Integration ready');
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebOpsThemeIntegration;
}