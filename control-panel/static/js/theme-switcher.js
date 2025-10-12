/**
 * WebOps Theme Switcher
 * Manages theme switching functionality with localStorage persistence
 */

class WebOpsThemeSwitcher {
    constructor() {
        this.themes = ['dark', 'light', 'custom', 'high-contrast'];
        this.currentTheme = this.getStoredTheme() || 'dark';
        this.init();
    }

    /**
     * Initialize the theme switcher
     */
    init() {
        this.applyTheme(this.currentTheme);
        this.bindEvents();
    }

    /**
     * Get stored theme from localStorage
     * @returns {string|null} The stored theme or null
     */
    getStoredTheme() {
        return localStorage.getItem('webops-theme');
    }

    /**
     * Store theme in localStorage
     * @param {string} theme - Theme name to store
     */
    storeTheme(theme) {
        localStorage.setItem('webops-theme', theme);
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
        this.applyTheme(this.themes[nextIndex]);
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

        const label = switcher.querySelector('.webops-theme-label');
        const options = switcher.querySelectorAll('.webops-theme-option');

        if (label) {
            label.textContent = this.getThemeLabel(this.currentTheme);
        }

        options.forEach(option => {
            option.classList.toggle('active', option.dataset.theme === this.currentTheme);
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
            if (e.target.closest('.webops-theme-toggle')) {
                e.preventDefault();
                switcher.classList.toggle('open');
                return;
            }

            // Select theme
            if (e.target.closest('.webops-theme-option')) {
                e.preventDefault();
                const theme = e.target.closest('.webops-theme-option').dataset.theme;
                this.applyTheme(theme);
                switcher.classList.remove('open');
                return;
            }

            // Close dropdown when clicking outside
            if (!e.target.closest('.webops-theme-switcher')) {
                switcher.classList.remove('open');
            }
        });

        // Keyboard support
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const switcher = document.querySelector('.webops-theme-switcher');
                if (switcher) {
                    switcher.classList.remove('open');
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