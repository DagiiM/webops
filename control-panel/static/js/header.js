/**
 * WebOps Header Component JavaScript
 * Handles theme switcher, user menu, and settings interactions
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeThemeSwitcher();
    initializeUserMenu();
    initializeSettingsButton();
});

/**
 * Initialize theme switcher functionality
 */
function initializeThemeSwitcher() {
    const themeToggle = document.getElementById('themeToggle');
    const themeDropdown = document.getElementById('themeDropdown');
    const themeOptions = document.querySelectorAll('.webops-theme-option');
    
    if (!themeToggle || !themeDropdown) return;
    
    // Initialize with current theme
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    updateThemeIcon(currentTheme);
    
    // Toggle dropdown
    themeToggle.addEventListener('click', function(e) {
        e.stopPropagation();
        const isOpen = themeToggle.getAttribute('aria-expanded') === 'true';
        
        if (isOpen) {
            closeThemeDropdown();
        } else {
            openThemeDropdown();
        }
    });
    
    // Handle theme selection
    themeOptions.forEach(option => {
        option.addEventListener('click', function() {
            const theme = this.getAttribute('data-theme');
            selectTheme(theme);
            closeThemeDropdown();
        });
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!themeToggle.contains(e.target) && !themeDropdown.contains(e.target)) {
            closeThemeDropdown();
        }
    });
    
    // Keyboard navigation
    themeToggle.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            themeToggle.click();
        }
    });
    
    function openThemeDropdown() {
        themeToggle.setAttribute('aria-expanded', 'true');
        themeDropdown.classList.add('webops-theme-dropdown--open');
        themeDropdown.querySelector('.webops-theme-option').focus();
    }
    
    function closeThemeDropdown() {
        themeToggle.setAttribute('aria-expanded', 'false');
        themeDropdown.classList.remove('webops-theme-dropdown--open');
    }
    
    function selectTheme(theme) {
        // Update active state
        themeOptions.forEach(option => {
            option.classList.remove('webops-theme-option--active');
        });
        
        const selectedOption = document.querySelector(`[data-theme="${theme}"]`);
        if (selectedOption) {
            selectedOption.classList.add('webops-theme-option--active');
            
            // Update toggle label
            const label = themeToggle.querySelector('.webops-theme-toggle__label');
            if (label) {
                label.textContent = selectedOption.querySelector('.webops-theme-option__label').textContent;
            }
            
            // Update icon visibility
            updateThemeIcon(theme);
        }
        
        // Apply theme (integrate with existing theme system)
        applyTheme(theme);
    }
    
    function updateThemeIcon(theme) {
        // Hide all theme icons
        const allIcons = themeToggle.querySelectorAll('.webops-theme-toggle__icon');
        allIcons.forEach(icon => {
            icon.style.display = 'none';
        });
        
        // Show the appropriate icon for the current theme
        const currentIcon = themeToggle.querySelector(`.webops-theme-toggle__icon--${theme}`);
        if (currentIcon) {
            currentIcon.style.display = 'block';
        }
    }
    
    function applyTheme(theme) {
        // This should integrate with your existing theme system
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('webops-theme', theme);
        
        // Dispatch custom event for other components
        window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
    }
}

/**
 * Initialize user menu functionality
 */
function initializeUserMenu() {
    const userMenuTrigger = document.getElementById('userMenuTrigger');
    const userDropdown = document.getElementById('userDropdown');
    
    if (!userMenuTrigger || !userDropdown) return;
    
    // Toggle dropdown
    userMenuTrigger.addEventListener('click', function(e) {
        e.stopPropagation();
        const isOpen = userMenuTrigger.getAttribute('aria-expanded') === 'true';
        
        if (isOpen) {
            closeUserDropdown();
        } else {
            openUserDropdown();
        }
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!userMenuTrigger.contains(e.target) && !userDropdown.contains(e.target)) {
            closeUserDropdown();
        }
    });
    
    // Keyboard navigation
    userMenuTrigger.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            userMenuTrigger.click();
        }
    });
    
    function openUserDropdown() {
        userMenuTrigger.setAttribute('aria-expanded', 'true');
        userDropdown.classList.add('webops-user-menu__dropdown--open');
        userDropdown.querySelector('.webops-user-menu__item').focus();
    }
    
    function closeUserDropdown() {
        userMenuTrigger.setAttribute('aria-expanded', 'false');
        userDropdown.classList.remove('webops-user-menu__dropdown--open');
    }
}

/**
 * Initialize settings button functionality
 */
function initializeSettingsButton() {
    const settingsButton = document.getElementById('settingsButton');
    const userSettingsButton = document.getElementById('userSettingsButton');
    
    if (settingsButton) {
        settingsButton.addEventListener('click', function() {
            // Handle settings button click
            console.log('Settings button clicked');
            // You can implement settings modal or navigation here
        });
    }
    
    if (userSettingsButton) {
        userSettingsButton.addEventListener('click', function() {
            // Handle user settings button click
            console.log('User settings button clicked');
            // You can implement user settings modal or navigation here
        });
    }
}

/**
 * Utility function to handle escape key for closing dropdowns
 */
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        // Close all open dropdowns
        const themeDropdown = document.getElementById('themeDropdown');
        const userDropdown = document.getElementById('userDropdown');
        const themeToggle = document.getElementById('themeToggle');
        const userMenuTrigger = document.getElementById('userMenuTrigger');
        
        if (themeDropdown && themeDropdown.classList.contains('webops-theme-dropdown--open')) {
            themeToggle.setAttribute('aria-expanded', 'false');
            themeDropdown.classList.remove('webops-theme-dropdown--open');
        }
        
        if (userDropdown && userDropdown.classList.contains('webops-user-menu__dropdown--open')) {
            userMenuTrigger.setAttribute('aria-expanded', 'false');
            userDropdown.classList.remove('webops-user-menu__dropdown--open');
        }
    }
});