/**
 * WebOps Dynamic Theme Loader
 * Dynamically loads CSS theme variables from theme files
 * Handles system preference detection, localStorage persistence, and fallback behavior
 */

class WebOpsDynamicThemeLoader {
    constructor() {
        this.availableThemes = ['dark', 'light', 'forest', 'high-contrast', 'custom'];
        this.currentTheme = this.detectInitialTheme();
        this.themeLinks = new Map();
        this.isLoading = false;
        this.loadCallbacks = [];
        
        // Initialize the theme loader
        this.init();
    }

    /**
     * Initialize the theme loader
     */
    async init() {
        // Create theme link elements for each available theme
        this.createThemeLinks();
        
        // Load the initial theme
        await this.loadTheme(this.currentTheme);
        
        // Listen for system preference changes
        this.setupSystemPreferenceListener();
        
        // Apply theme to document
        this.applyThemeToDocument(this.currentTheme);
    }

    /**
     * Detect initial theme based on user preference or system settings
     */
    detectInitialTheme() {
        // Check localStorage first
        const storedTheme = localStorage.getItem('webops-theme');
        if (storedTheme && this.availableThemes.includes(storedTheme)) {
            return storedTheme;
        }

        // Check system preference
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
            return 'light';
        }
        
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }

        // Default to dark theme
        return 'dark';
    }

    /**
     * Create link elements for each theme file
     */
    createThemeLinks() {
        this.availableThemes.forEach(theme => {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.type = 'text/css';
            link.href = `/static/css/themes/${theme}.css`;
            link.disabled = true;
            link.setAttribute('data-theme', theme);
            link.setAttribute('data-theme-type', 'dynamic');
            
            // Add error handling
            link.onerror = () => {
                console.warn(`Failed to load theme file: ${theme}.css`);
                this.handleThemeLoadError(theme);
            };
            
            // Add load success handler
            link.onload = () => {
                console.log(`Successfully loaded theme file: ${theme}.css`);
            };
            
            document.head.appendChild(link);
            this.themeLinks.set(theme, link);
        });
    }

    /**
     * Load a specific theme
     */
    async loadTheme(themeName) {
        if (!this.availableThemes.includes(themeName)) {
            console.warn(`Unknown theme: ${themeName}, falling back to dark`);
            themeName = 'dark';
        }

        if (this.isLoading) {
            console.warn('Theme loading already in progress');
            return;
        }

        this.isLoading = true;
        
        try {
            const themeLink = this.themeLinks.get(themeName);
            if (!themeLink) {
                throw new Error(`Theme link not found for: ${themeName}`);
            }

            // Disable all theme links first
            this.disableAllThemes();
            
            // Enable the selected theme
            themeLink.disabled = false;
            
            // Wait for the theme to be applied
            await this.waitForThemeApplication(themeLink);
            
            // Store the preference
            this.storeThemePreference(themeName);
            
            // Update current theme
            this.currentTheme = themeName;
            
            // Notify callbacks
            this.notifyThemeChange(themeName);
            
            console.log(`Theme loaded successfully: ${themeName}`);
            
        } catch (error) {
            console.error(`Failed to load theme: ${themeName}`, error);
            this.handleThemeLoadError(themeName);
        } finally {
            this.isLoading = false;
        }
    }

    /**
     * Disable all theme stylesheets
     */
    disableAllThemes() {
        this.themeLinks.forEach(link => {
            link.disabled = true;
        });
    }

    /**
     * Wait for theme stylesheet to be applied
     */
    async waitForThemeApplication(linkElement) {
        return new Promise((resolve) => {
            // If already loaded, resolve immediately
            if (linkElement.sheet) {
                resolve();
                return;
            }
            
            // Wait for load event
            if (linkElement.onload) {
                const originalOnload = linkElement.onload;
                linkElement.onload = () => {
                    originalOnload();
                    resolve();
                };
            } else {
                linkElement.onload = resolve;
            }
            
            // Timeout fallback
            setTimeout(resolve, 100);
        });
    }

    /**
     * Apply theme to document element
     */
    applyThemeToDocument(themeName) {
        // Set data-theme attribute on document element
        document.documentElement.setAttribute('data-theme', themeName);
        
        // Add theme transition class for smooth transitions
        document.documentElement.classList.add('theme-transitioning');
        
        // Remove transition class after animation completes
        setTimeout(() => {
            document.documentElement.classList.remove('theme-transitioning');
        }, 300);
    }

    /**
     * Handle theme loading errors with fallback
     */
    handleThemeLoadError(failedTheme) {
        console.warn(`Theme file not found or failed to load: ${failedTheme}.css`);
        
        // Fallback to default dark theme
        const fallbackTheme = 'dark';
        const fallbackLink = this.themeLinks.get(fallbackTheme);
        
        if (fallbackLink && !fallbackLink.disabled) {
            console.log(`Falling back to default theme: ${fallbackTheme}`);
            this.loadTheme(fallbackTheme);
        } else {
            // If even fallback fails, use basic CSS variables
            this.applyBasicTheme(fallbackTheme);
        }
    }

    /**
     * Apply basic theme as ultimate fallback
     */
    applyBasicTheme(themeName) {
        const basicThemes = {
            dark: {
                '--webops-color-bg-primary': '#0a0e0d',
                '--webops-color-bg-secondary': '#111816',
                '--webops-color-text-primary': '#e8f5f0',
                '--webops-color-primary': '#00ff88'
            },
            light: {
                '--webops-color-bg-primary': '#ffffff',
                '--webops-color-bg-secondary': '#f8fafb',
                '--webops-color-text-primary': '#1a1a1a',
                '--webops-color-primary': '#00aa88'
            }
        };
        
        const theme = basicThemes[themeName] || basicThemes.dark;
        
        Object.entries(theme).forEach(([property, value]) => {
            document.documentElement.style.setProperty(property, value);
        });
        
        document.documentElement.setAttribute('data-theme', themeName);
        console.log(`Applied basic fallback theme: ${themeName}`);
    }

    /**
     * Store theme preference in localStorage
     */
    storeThemePreference(themeName) {
        try {
            localStorage.setItem('webops-theme', themeName);
            
            // Also store timestamp for future enhancements
            localStorage.setItem('webops-theme-timestamp', Date.now().toString());
        } catch (error) {
            console.warn('Failed to store theme preference:', error);
        }
    }

    /**
     * Switch to a different theme
     */
    async switchTheme(newTheme) {
        if (newTheme === this.currentTheme) {
            return; // No change needed
        }

        // Validate theme
        if (!this.availableThemes.includes(newTheme)) {
            console.warn(`Invalid theme: ${newTheme}`);
            return;
        }

        // Load the new theme
        await this.loadTheme(newTheme);
        
        // Apply to document
        this.applyThemeToDocument(newTheme);
    }

    /**
     * Setup system preference change listener
     */
    setupSystemPreferenceListener() {
        if (!window.matchMedia) return;

        const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
        const lightModeQuery = window.matchMedia('(prefers-color-scheme: light)');

        const handleSystemChange = () => {
            // Only auto-switch if user hasn't manually selected a theme
            const hasUserPreference = localStorage.getItem('webops-theme');
            if (!hasUserPreference) {
                const systemTheme = this.detectInitialTheme();
                if (systemTheme !== this.currentTheme) {
                    this.switchTheme(systemTheme);
                }
            }
        };

        // Add listeners for system preference changes
        darkModeQuery.addEventListener('change', handleSystemChange);
        lightModeQuery.addEventListener('change', handleSystemChange);
    }

    /**
     * Add callback for theme changes
     */
    onThemeChange(callback) {
        this.loadCallbacks.push(callback);
    }

    /**
     * Notify all callbacks of theme change
     */
    notifyThemeChange(themeName) {
        this.loadCallbacks.forEach(callback => {
            try {
                callback(themeName, this.currentTheme);
            } catch (error) {
                console.error('Theme change callback error:', error);
            }
        });
    }

    /**
     * Get current theme information
     */
    getCurrentTheme() {
        return {
            name: this.currentTheme,
            isSystemPreference: !localStorage.getItem('webops-theme'),
            availableThemes: [...this.availableThemes]
        };
    }

    /**
     * Reset to system preference
     */
    async resetToSystemPreference() {
        localStorage.removeItem('webops-theme');
        localStorage.removeItem('webops-theme-timestamp');
        
        const systemTheme = this.detectInitialTheme();
        await this.switchTheme(systemTheme);
    }

    /**
     * Check if a theme file exists
     */
    async themeExists(themeName) {
        try {
            const response = await fetch(`/static/css/themes/${themeName}.css`, {
                method: 'HEAD'
            });
            return response.ok;
        } catch {
            return false;
        }
    }
}

// Initialize the dynamic theme loader when DOM is ready
let themeLoader = null;

document.addEventListener('DOMContentLoaded', () => {
    themeLoader = new WebOpsDynamicThemeLoader();
    
    // Make theme loader available globally for other components
    window.WebOpsThemeLoader = themeLoader;
    
    console.log('WebOps Dynamic Theme Loader initialized');
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebOpsDynamicThemeLoader;
}