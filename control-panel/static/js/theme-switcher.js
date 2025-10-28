/**
 * WebOps Theme Switcher
 * Manages theme switching functionality with localStorage persistence
 */

class WebOpsThemeSwitcher {
    constructor() {
        this.themes = ['dark', 'light', 'forest', 'high-contrast', 'custom'];
        this.currentTheme = this.getStoredTheme() || 'dark';
        this.container = null;
        this.isInitialized = false;
        this.dynamicLoader = null;
        
        // Wait for dynamic theme loader to be available
        this.waitForDynamicLoader();
    }
    
    /**
     * Wait for dynamic theme loader to be available
     */
    waitForDynamicLoader() {
        const checkLoader = () => {
            if (window.WebOpsThemeLoader) {
                this.dynamicLoader = window.WebOpsThemeLoader;
                this.init();
            } else {
                setTimeout(checkLoader, 100);
            }
        };
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', checkLoader);
        } else {
            checkLoader();
        }
    }

    /**
     * Initialize the theme switcher
     */
    init() {
        this.applyTheme(this.currentTheme);
        this.updateSwitcherUI();
        this.bindEvents();
    }

    /**
     * Get stored theme from localStorage
     * @returns {string|null} The stored theme or null
     */
    getStoredTheme() {
        return localStorage.getItem('theme');
    }

    /**
     * Store theme in localStorage
     * @param {string} theme - Theme name to store
     */
    storeTheme(theme) {
        localStorage.setItem('theme', theme);
    }

    /**
     * Apply theme to document
     * @param {string} theme - Theme name to apply
     */
    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        this.currentTheme = theme;
        this.storeTheme(theme);
        this.updateSwitcherUI();
    }

    /**
     * Cycle to next theme
     */
    cycleTheme() {
        const currentIndex = this.themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % this.themes.length;
        const nextTheme = this.themes[nextIndex];
        
        this.currentTheme = nextTheme;
        this.storeTheme(nextTheme);
        
        // Use dynamic loader if available
        if (this.dynamicLoader) {
            this.dynamicLoader.switchTheme(nextTheme);
        } else {
            this.applyTheme(nextTheme);
        }
        
        this.updateSwitcherUI();
    }

    /**
     * Create theme switcher UI component
     */
    createThemeSwitcher() {
        const switcher = document.createElement('div');
        switcher.className = 'webops-theme-switcher';
        switcher.innerHTML = `
            <button class="webops-theme-toggle" title="Switch Theme">
                <svg class="webops-theme-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="5"/>
                    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
                </svg>
                <span class="webops-theme-label">${this.getThemeLabel(this.currentTheme)}</span>
            </button>
            <div class="webops-theme-dropdown">
                ${this.themes.map(theme => `
                    <button class="webops-theme-option ${theme === this.currentTheme ? 'active' : ''}" data-theme="${theme}">
                        <span class="webops-theme-preview webops-theme-preview-${theme}"></span>
                        ${this.getThemeLabel(theme)}
                    </button>
                `).join('')}
            </div>
        `;

        // Add to header or create floating button
        const header = document.querySelector('.webops-header') || document.querySelector('header');
        if (header) {
            header.appendChild(switcher);
        } else {
            switcher.classList.add('webops-theme-switcher-floating');
            document.body.appendChild(switcher);
        }
    }

    /**
     * Get human-readable theme label
     * @param {string} theme - Theme name
     * @returns {string} Human-readable label
     */
    getThemeLabel(theme) {
        const labels = {
            'dark': 'Dark',
            'light': 'Light',
            'custom': 'Custom',
            'high-contrast': 'High Contrast'
        };
        return labels[theme] || theme;
    }

    /**
     * Update switcher UI to reflect current theme
     */
    updateSwitcherUI() {
        const switcher = document.querySelector('.webops-theme-switcher');
        if (!switcher) return;

        // Update the toggle button label
        const label = switcher.querySelector('.webops-theme-toggle__label');
        if (label) {
            label.textContent = this.getThemeLabel(this.currentTheme);
        }

        // Update the active state of theme options
        const options = switcher.querySelectorAll('.webops-theme-option');
        options.forEach(option => {
            option.classList.toggle('active', option.dataset.theme === this.currentTheme);
        });

        // Update icon visibility based on current theme
        const icons = switcher.querySelectorAll('.webops-theme-toggle__icon');
        icons.forEach(icon => {
            const themeClass = Array.from(icon.classList).find(cls => cls.includes('--'));
            if (themeClass) {
                const theme = themeClass.split('--').pop();
                icon.style.display = theme === this.currentTheme ? 'block' : 'none';
            }
        });
    }

    /**
     * Bind event listeners
     */
    bindEvents() {
        document.addEventListener('click', (e) => {
            const switcher = document.querySelector('.webops-theme-switcher');
            if (!switcher) return;

            // Toggle dropdown
            if (e.target.closest('#themeToggle')) {
                e.preventDefault();
                const isOpen = switcher.classList.contains('open');
                
                if (isOpen) {
                    switcher.classList.remove('open');
                    document.getElementById('themeToggle').setAttribute('aria-expanded', 'false');
                } else {
                    switcher.classList.add('open');
                    document.getElementById('themeToggle').setAttribute('aria-expanded', 'true');
                }
                return;
            }

            // Select theme
            if (e.target.closest('.webops-theme-option')) {
                e.preventDefault();
                const theme = e.target.closest('.webops-theme-option').dataset.theme;
                
                // Use dynamic loader if available
                if (this.dynamicLoader) {
                    this.dynamicLoader.switchTheme(theme);
                } else {
                    this.applyTheme(theme);
                }
                
                // Close dropdown
                switcher.classList.remove('open');
                document.getElementById('themeToggle').setAttribute('aria-expanded', 'false');
                return;
            }

            // Close dropdown when clicking outside
            if (!e.target.closest('.webops-theme-switcher')) {
                switcher.classList.remove('open');
                document.getElementById('themeToggle').setAttribute('aria-expanded', 'false');
            }
        });

        // Keyboard support
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const switcher = document.querySelector('.webops-theme-switcher');
                if (switcher) {
                    switcher.classList.remove('open');
                    document.getElementById('themeToggle').setAttribute('aria-expanded', 'false');
                }
            }
        });
    }
}

// Initialize theme switcher when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new WebOpsThemeSwitcher();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebOpsThemeSwitcher;
}
