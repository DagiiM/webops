/**
 * WebOps User Settings Page - Ultra Sleek Interactions
 * Handles form interactions, toggle switches, and dynamic behaviors
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeUserSettings();
});

function initializeUserSettings() {
    // Initialize toggle switches
    initializeToggleSwitches();
    
    // Initialize form navigation
    initializeFormNavigation();
    
    // Initialize theme switching
    initializeThemeSwitching();
    
    // Initialize form validation
    initializeFormValidation();
    
    // Initialize save functionality
    initializeSaveFunctionality();
    
    // Initialize all settings forms
    initializeSettingsForms();
}

/**
 * Initialize toggle switches with enhanced interactions
 */
function initializeToggleSwitches() {
    const toggleContainers = document.querySelectorAll('.webops-toggle');
    
    toggleContainers.forEach(container => {
        const input = container.querySelector('input[type="checkbox"], input[type="radio"]');
        const slider = container.querySelector('.webops-toggle__slider');
        const label = container.querySelector('.webops-toggle__label');
        
        if (!input || !slider) return;
        
        // Handle click events
        container.addEventListener('click', function(e) {
            if (e.target.tagName !== 'INPUT') {
                e.preventDefault();
                
                if (input.type === 'radio') {
                    // For radio buttons, just check the clicked one
                    input.checked = true;
                } else {
                    // For checkboxes, toggle the state
                    input.checked = !input.checked;
                }
                
                // Trigger change event
                input.dispatchEvent(new Event('change', { bubbles: true }));
                
                // Add visual feedback
                addToggleFeedback(container);
            }
        });
        
        // Handle keyboard navigation
        container.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                container.click();
            }
        });
        
        // Handle change events
        input.addEventListener('change', function() {
            updateToggleState(container, input.checked);
            
            // Trigger custom event for other components
            const customEvent = new CustomEvent('toggleChanged', {
                detail: {
                    container: container,
                    input: input,
                    checked: input.checked,
                    value: input.value
                }
            });
            document.dispatchEvent(customEvent);
        });
        
        // Initialize state
        updateToggleState(container, input.checked);
    });
}

/**
 * Update toggle visual state
 */
function updateToggleState(container, isChecked) {
    const slider = container.querySelector('.webops-toggle__slider');
    const label = container.querySelector('.webops-toggle__label');
    
    if (!slider) return;
    
    if (isChecked) {
        slider.style.background = 'var(--webops-color-primary-alpha-20)';
        slider.style.borderColor = 'var(--webops-color-primary)';
        
        const before = slider.querySelector('::before');
        if (before) {
            slider.style.setProperty('--slider-transform', 'translateX(24px)');
        }
    } else {
        slider.style.background = 'var(--webops-color-neutral-alpha-20)';
        slider.style.borderColor = 'var(--webops-color-neutral-alpha-30)';
        
        const before = slider.querySelector('::before');
        if (before) {
            slider.style.setProperty('--slider-transform', 'translateX(0)');
        }
    }
    
    // Update label styling
    if (label && isChecked) {
        label.style.color = 'var(--webops-color-primary)';
        label.style.fontWeight = 'var(--webops-font-weight-semibold)';
    } else if (label) {
        label.style.color = 'var(--webops-color-text-primary)';
        label.style.fontWeight = 'var(--webops-font-weight-medium)';
    }
}

/**
 * Add visual feedback to toggle interactions
 */
function addToggleFeedback(container) {
    container.style.transform = 'scale(0.98)';
    setTimeout(() => {
        container.style.transform = 'scale(1)';
    }, 150);
}

/**
 * Initialize form navigation between sections
 */
function initializeFormNavigation() {
    const navLinks = document.querySelectorAll('.webops-settings-nav__item');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href') || this.getAttribute('data-section');
            if (!targetId) return;
            
            // Update active state
            navLinks.forEach(l => l.classList.remove('active'));
            this.classList.add('active');
            
            // Show target section
            showSection(targetId);
            
            // Update URL without page reload
            history.pushState(null, null, targetId);
        });
    });
    
    // Handle initial section based on URL hash
    const initialHash = window.location.hash;
    if (initialHash) {
        const targetLink = document.querySelector(`[href="${initialHash}"]`);
        if (targetLink) {
            targetLink.click();
        }
    }
}

/**
 * Show specific section
 */
function showSection(sectionId) {
    // Handle empty hash or invalid selectors
    if (!sectionId || sectionId === '#' || sectionId === '') {
        return;
    }
    
    // Remove hash if present
    if (sectionId.startsWith('#')) {
        sectionId = sectionId.substring(1);
    }
    
    const sections = document.querySelectorAll('.webops-settings-section');
    sections.forEach(section => {
        section.style.display = 'none';
        section.classList.remove('active');
    });
    
    // Try to find section by ID first
    let targetSection = document.getElementById(sectionId);
    
    // If not found by ID, try by data-section attribute
    if (!targetSection) {
        targetSection = document.querySelector(`[data-section="${sectionId}"]`);
    }
    
    if (targetSection) {
        targetSection.style.display = 'block';
        setTimeout(() => {
            targetSection.classList.add('active');
        }, 50);
        
        // Scroll to top of section
        targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

/**
 * Initialize theme switching functionality
 */
function initializeThemeSwitching() {
    const themeInputs = document.querySelectorAll('input[name="theme"]');
    
    themeInputs.forEach(input => {
        input.addEventListener('change', function() {
            if (this.checked) {
                applyTheme(this.value);
                saveThemePreference(this.value);
            }
        });
    });
    
    // Load saved theme preference
    const savedTheme = localStorage.getItem('webops-theme') || 'system';
    const savedInput = document.querySelector(`input[name="theme"][value="${savedTheme}"]`);
    if (savedInput) {
        savedInput.checked = true;
        applyTheme(savedTheme);
    }
}

/**
 * Apply theme to the page
 */
function applyTheme(theme) {
    const root = document.documentElement;
    
    // Remove existing theme classes
    root.removeAttribute('data-theme');
    
    // Apply new theme
    if (theme !== 'system') {
        root.setAttribute('data-theme', theme);
    }
    
    // Update theme toggle icon
    updateThemeIcon(theme);
}

/**
 * Update theme toggle icon
 */
function updateThemeIcon(theme) {
    const themeIcon = document.querySelector('.webops-theme-toggle__icon');
    if (!themeIcon) return;
    
    // Remove all icon classes
    themeIcon.classList.remove('webops-theme-toggle__icon--light', 'webops-theme-toggle__icon--dark', 'webops-theme-toggle__icon--custom');
    
    // Add appropriate icon class
    themeIcon.classList.add(`webops-theme-toggle__icon--${theme}`);
}

/**
 * Save theme preference
 */
function saveThemePreference(theme) {
    localStorage.setItem('webops-theme', theme);
    
    // Show save notification
    showNotification('Theme preference saved', 'success');
}

/**
 * Initialize form validation
 */
function initializeFormValidation() {
    const form = document.querySelector('.webops-settings-form');
    if (!form) return;
    
    const inputs = form.querySelectorAll('.webops-form-control');
    
    inputs.forEach(input => {
        // Add validation on blur
        input.addEventListener('blur', function() {
            validateField(this);
        });
        
        // Clear validation on focus
        input.addEventListener('focus', function() {
            clearFieldValidation(this);
        });
        
        // Real-time validation for certain fields
        if (input.type === 'email') {
            input.addEventListener('input', function() {
                if (this.value.length > 0) {
                    validateField(this);
                }
            });
        }
    });
}

/**
 * Validate individual field
 */
function validateField(field) {
    const value = field.value.trim();
    let isValid = true;
    let errorMessage = '';
    
    // Required field validation
    if (field.hasAttribute('required') && value === '') {
        isValid = false;
        errorMessage = 'This field is required';
    }
    
    // Email validation
    if (field.type === 'email' && value !== '') {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
            isValid = false;
            errorMessage = 'Please enter a valid email address';
        }
    }
    
    // Name validation
    if (field.id === 'first_name' || field.id === 'last_name') {
        if (value !== '' && value.length < 2) {
            isValid = false;
            errorMessage = 'Name must be at least 2 characters long';
        }
    }
    
    updateFieldValidation(field, isValid, errorMessage);
    return isValid;
}

/**
 * Update field validation display
 */
function updateFieldValidation(field, isValid, errorMessage) {
    const formGroup = field.closest('.webops-form-group');
    if (!formGroup) return;
    
    // Remove existing validation states
    field.classList.remove('webops-form-control--error', 'webops-form-control--success');
    
    // Remove existing error message
    const existingError = formGroup.querySelector('.webops-field-error');
    if (existingError) {
        existingError.remove();
    }
    
    if (isValid) {
        field.classList.add('webops-form-control--success');
    } else {
        field.classList.add('webops-form-control--error');
        
        // Add error message
        const errorElement = document.createElement('div');
        errorElement.className = 'webops-field-error';
        errorElement.textContent = errorMessage;
        formGroup.appendChild(errorElement);
    }
}

/**
 * Clear field validation
 */
function clearFieldValidation(field) {
    const formGroup = field.closest('.webops-form-group');
    if (!formGroup) return;
    
    field.classList.remove('webops-form-control--error', 'webops-form-control--success');
    
    const existingError = formGroup.querySelector('.webops-field-error');
    if (existingError) {
        existingError.remove();
    }
}

/**
 * Initialize save functionality
 */
function initializeSaveFunctionality() {
    const saveButton = document.querySelector('.webops-form-actions .webops-btn--primary');
    const cancelButton = document.querySelector('.webops-form-actions .webops-btn--secondary');
    const form = document.querySelector('.webops-settings-form');
    
    if (!saveButton || !form) return;
    
    saveButton.addEventListener('click', function(e) {
        e.preventDefault();
        saveSettings(form);
    });
    
    // Handle form submission
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        saveSettings(form);
    });
    
    if (cancelButton) {
        cancelButton.addEventListener('click', function(e) {
            e.preventDefault();
            resetForm(form);
        });
    }
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + S to save
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            saveSettings(form);
        }
        
        // Escape to cancel
        if (e.key === 'Escape') {
            resetForm(form);
        }
    });
}

/**
 * Save settings with enhanced feedback
 */
function saveSettings(form) {
    // Validate all fields first
    const inputs = form.querySelectorAll('.webops-form-control');
    let isFormValid = true;
    
    inputs.forEach(input => {
        if (!validateField(input)) {
            isFormValid = false;
        }
    });
    
    if (!isFormValid) {
        showNotification('Please fix the errors in the form', 'error');
        return;
    }
    
    // Show loading state
    const saveButton = form.querySelector('.webops-form-actions .webops-btn--primary');
    const originalText = saveButton.textContent;
    
    saveButton.disabled = true;
    saveButton.classList.add('webops-btn-loading');
    saveButton.innerHTML = '<span class="webops-btn-spinner"></span> Saving...';
    
    // Submit the form using fetch API
    fetch(form.action || window.location.href, {
        method: 'POST',
        body: new FormData(form),
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json'
        },
        credentials: 'same-origin'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        // Reset button state
        saveButton.disabled = false;
        saveButton.classList.remove('webops-btn-loading');
        saveButton.textContent = originalText;
        
        if (data.success) {
            // Show success notification
            showNotification(data.message || 'Settings saved successfully!', 'success');
            
            // Add success animation to form
            form.classList.add('webops-form--saved');
            setTimeout(() => {
                form.classList.remove('webops-form--saved');
            }, 2000);
            
            // Save to localStorage for backup
            const formData = new FormData(form);
            const settingsData = {};
            
            for (let [key, value] of formData.entries()) {
                settingsData[key] = value;
            }
            
            // Add checkbox values
            const checkboxes = form.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(checkbox => {
                settingsData[checkbox.name] = checkbox.checked;
            });
            
            localStorage.setItem('webops-user-settings', JSON.stringify(settingsData));
        } else {
            // Show error message from server
            showNotification(data.message || 'Failed to save settings', 'error');
            
            // Handle form errors if provided
            if (data.errors) {
                Object.keys(data.errors).forEach(fieldName => {
                    const field = form.querySelector(`[name="${fieldName}"]`);
                    if (field) {
                        updateFieldValidation(field, false, data.errors[fieldName][0]);
                    }
                });
            }
        }
    })
    .catch(error => {
        // Reset button state
        saveButton.disabled = false;
        saveButton.classList.remove('webops-btn-loading');
        saveButton.textContent = originalText;
        
        // Show error notification
        showNotification(`Error: ${error.message}`, 'error');
        console.error('Save settings error:', error);
    });
}

/**
 * Reset form to original state
 */
function resetForm(form) {
    if (!form) return;
    
    // Load saved settings
    const savedSettings = localStorage.getItem('webops-user-settings');
    if (savedSettings) {
        const settings = JSON.parse(savedSettings);
        
        // Restore form values
        Object.keys(settings).forEach(key => {
            const field = form.querySelector(`[name="${key}"]`);
            if (field) {
                if (field.type === 'checkbox') {
                    field.checked = settings[key];
                } else {
                    field.value = settings[key];
                }
                
                // Trigger change event for toggles
                field.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    }
    
    // Clear all validation states
    const inputs = form.querySelectorAll('.webops-form-control');
    inputs.forEach(input => {
        clearFieldValidation(input);
    });
    
    showNotification('Form reset to last saved state', 'info');
}

/**
 * Show notification message
 */
function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.webops-notification');
    existingNotifications.forEach(notification => {
        notification.remove();
    });
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `webops-notification webops-notification--${type}`;
    notification.textContent = message;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Show with animation
    setTimeout(() => {
        notification.classList.add('webops-notification--show');
    }, 100);
    
    // Auto hide after 3 seconds
    setTimeout(() => {
        notification.classList.remove('webops-notification--show');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

/**
 * Handle browser back/forward navigation
 */
window.addEventListener('popstate', function() {
    const hash = window.location.hash;
    const targetLink = document.querySelector(`[href="${hash}"]`);
    if (targetLink) {
        targetLink.click();
    }
});

/**
 * Handle responsive sidebar toggle
 */
function initializeResponsiveSidebar() {
    const sidebarToggle = document.querySelector('.webops-sidebar-toggle');
    const sidebar = document.querySelector('.webops-settings-sidebar');
    
    if (!sidebarToggle || !sidebar) return;
    
    sidebarToggle.addEventListener('click', function() {
        sidebar.classList.toggle('webops-settings-sidebar--mobile-open');
    });
    
    // Close sidebar when clicking outside
    document.addEventListener('click', function(e) {
        if (!sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
            sidebar.classList.remove('webops-settings-sidebar--mobile-open');
        }
    });
}

/**
 * Initialize all settings forms
 */
function initializeSettingsForms() {
    const forms = document.querySelectorAll('.webops-settings-form');
    
    forms.forEach(form => {
        const saveButton = form.querySelector('.webops-form-actions .webops-btn--primary');
        const cancelButton = form.querySelector('.webops-form-actions .webops-btn--secondary');
        
        if (!saveButton) return;
        
        saveButton.addEventListener('click', function(e) {
            e.preventDefault();
            saveSettings(form);
        });
        
        // Handle form submission
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            saveSettings(form);
        });
        
        if (cancelButton) {
            cancelButton.addEventListener('click', function(e) {
                e.preventDefault();
                resetForm(form);
            });
        }
    });
}

// Initialize responsive sidebar on mobile
if (window.innerWidth <= 768) {
    initializeResponsiveSidebar();
}

// Add CSS for notifications and loading states
const additionalStyles = `
.webops-notification {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 16px 24px;
    border-radius: 8px;
    font-weight: 500;
    z-index: 10000;
    transform: translateX(100%);
    transition: all 0.3s ease;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.webops-notification--show {
    transform: translateX(0);
}

.webops-notification--success {
    background: var(--webops-color-success);
    color: white;
}

.webops-notification--error {
    background: var(--webops-color-error);
    color: white;
}

.webops-notification--info {
    background: var(--webops-color-info);
    color: white;
}

.webops-btn-loading {
    position: relative;
    color: transparent !important;
}

.webops-btn-spinner {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 16px;
    height: 16px;
    margin: -8px 0 0 -8px;
    border: 2px solid transparent;
    border-top: 2px solid currentColor;
    border-radius: 50%;
    animation: webops-spin 1s linear infinite;
}

@keyframes webops-spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

.webops-form--saved {
    animation: webops-success-pulse 2s ease-in-out;
}

@keyframes webops-success-pulse {
    0%, 100% { 
        box-shadow: var(--webops-shadow-md);
    }
    50% { 
        box-shadow: 0 0 20px var(--webops-color-success-glow);
    }
}

.webops-field-error {
    color: var(--webops-color-error);
    font-size: var(--webops-font-size-xs);
    margin-top: var(--webops-space-1);
    font-weight: var(--webops-font-weight-medium);
}

.webops-form-control--error {
    border-color: var(--webops-color-error) !important;
    box-shadow: 0 0 0 3px var(--webops-color-error-alpha-20) !important;
}

.webops-form-control--success {
    border-color: var(--webops-color-success) !important;
    box-shadow: 0 0 0 3px var(--webops-color-success-alpha-20) !important;
}

@media (max-width: 768px) {
    .webops-settings-sidebar--mobile-open {
        transform: translateX(0);
    }
}
`;

// Add styles to page
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
document.head.appendChild(styleSheet);