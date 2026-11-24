/* Moved from templates/core/google_oauth_config.html (ui-skill rule 17: no inline <script>). */
document.addEventListener('DOMContentLoaded', function() {
    // Auto-generate redirect URI based on current domain
    const redirectUriField = document.getElementById('id_google_oauth_redirect_uri');
    if (redirectUriField && !redirectUriField.value) {
        const currentOrigin = window.location.origin;
        redirectUriField.value = currentOrigin + webopsPage().urlCallback;
    }

    // Client-side validation
    const clientIdField = document.getElementById('id_google_oauth_client_id');
    const clientSecretField = document.getElementById('id_google_oauth_client_secret');

    // Real-time validation for Client ID
    if (clientIdField) {
        clientIdField.addEventListener('blur', function() {
            const value = this.value.trim();
            const errorContainer = this.parentNode.querySelector('.client-error') || 
                                 document.createElement('div');
            errorContainer.className = 'client-error';
            errorContainer.style.color = 'var(--error-color)';
            errorContainer.style.fontSize = '0.875rem';
            errorContainer.style.marginTop = '0.25rem';

            if (value && !value.endsWith('.apps.googleusercontent.com')) {
                errorContainer.textContent = 'Client ID must end with .apps.googleusercontent.com';
                if (!this.parentNode.querySelector('.client-error')) {
                    this.parentNode.appendChild(errorContainer);
                }
                this.style.borderColor = 'var(--error-color)';
            } else if (value && value.length < 50) {
                errorContainer.textContent = 'Client ID appears to be too short';
                if (!this.parentNode.querySelector('.client-error')) {
                    this.parentNode.appendChild(errorContainer);
                }
                this.style.borderColor = 'var(--error-color)';
            } else {
                const existingError = this.parentNode.querySelector('.client-error');
                if (existingError) {
                    existingError.remove();
                }
                this.style.borderColor = 'var(--border-color)';
            }
        });
    }

    // Real-time validation for Client Secret
    if (clientSecretField) {
        clientSecretField.addEventListener('blur', function() {
            const value = this.value.trim();
            const errorContainer = this.parentNode.querySelector('.secret-error') || 
                                 document.createElement('div');
            errorContainer.className = 'secret-error';
            errorContainer.style.color = 'var(--error-color)';
            errorContainer.style.fontSize = '0.875rem';
            errorContainer.style.marginTop = '0.25rem';

            if (value && value.length < 20) {
                errorContainer.textContent = 'Client Secret appears to be too short';
                if (!this.parentNode.querySelector('.secret-error')) {
                    this.parentNode.appendChild(errorContainer);
                }
                this.style.borderColor = 'var(--error-color)';
            } else if (value && ['your_client_secret', 'client_secret', 'secret'].includes(value.toLowerCase())) {
                errorContainer.textContent = 'Please enter a valid Client Secret';
                if (!this.parentNode.querySelector('.secret-error')) {
                    this.parentNode.appendChild(errorContainer);
                }
                this.style.borderColor = 'var(--error-color)';
            } else {
                const existingError = this.parentNode.querySelector('.secret-error');
                if (existingError) {
                    existingError.remove();
                }
                this.style.borderColor = 'var(--border-color)';
            }
        });
    }

    // Real-time validation for Redirect URI
    if (redirectUriField) {
        redirectUriField.addEventListener('blur', function() {
            const value = this.value.trim();
            const errorContainer = this.parentNode.querySelector('.uri-error') || 
                                 document.createElement('div');
            errorContainer.className = 'uri-error';
            errorContainer.style.color = 'var(--error-color)';
            errorContainer.style.fontSize = '0.875rem';
            errorContainer.style.marginTop = '0.25rem';

            if (value && !value.startsWith('http://') && !value.startsWith('https://')) {
                errorContainer.textContent = 'Redirect URI must start with http:// or https://';
                if (!this.parentNode.querySelector('.uri-error')) {
                    this.parentNode.appendChild(errorContainer);
                }
                this.style.borderColor = 'var(--error-color)';
            } else if (value && !value.includes('/auth/google/callback/')) {
                errorContainer.textContent = 'Redirect URI must contain the callback path: /auth/google/callback/';
                if (!this.parentNode.querySelector('.uri-error')) {
                    this.parentNode.appendChild(errorContainer);
                }
                this.style.borderColor = 'var(--error-color)';
            } else {
                const existingError = this.parentNode.querySelector('.uri-error');
                if (existingError) {
                    existingError.remove();
                }
                this.style.borderColor = 'var(--border-color)';
            }
        });
    }

    // Form submission validation
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const clientId = clientIdField ? clientIdField.value.trim() : '';
            const clientSecret = clientSecretField ? clientSecretField.value.trim() : '';

            // Check if both are provided or both are empty
            if ((clientId && !clientSecret) || (!clientId && clientSecret)) {
                e.preventDefault();
                alert('Both Client ID and Client Secret must be provided together.');
                return false;
            }

            // Check for validation errors
            const errors = document.querySelectorAll('.client-error, .secret-error, .uri-error');
            if (errors.length > 0) {
                e.preventDefault();
                alert('Please fix the validation errors before submitting.');
                return false;
            }
        });
    }

    // Show/hide help text on focus
    const inputs = document.querySelectorAll('.webops-input');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            const helpText = this.parentNode.querySelector('.help-text');
            if (helpText) {
                helpText.style.opacity = '1';
            }
        });

        input.addEventListener('blur', function() {
            const helpText = this.parentNode.querySelector('.help-text');
            if (helpText) {
                helpText.style.opacity = '0.7';
            }
        });
    });

    // Enhanced form behavior
    updateFormBehavior();

    // Add test connection button event listener
    const testBtn = document.getElementById('test-connection-btn');
    if (testBtn) {
        testBtn.addEventListener('click', testConnection);
    }
});

// Test connection functionality
function testConnection() {
    const testBtn = document.getElementById('test-connection-btn');
    const originalText = testBtn.innerHTML;

    // Show loading state
    testBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
    testBtn.disabled = true;

    // Create form data for test
    const formData = new FormData();
    formData.append('action', 'test_connection');
    formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

    fetch(window.location.href, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        // Reset button
        testBtn.innerHTML = originalText;
        testBtn.disabled = false;

        // Update status display
        const statusBox = document.querySelector('.webops-oauth-config__status-box');
        const statusDetails = statusBox.querySelector('.webops-oauth-config__status-details');

        if (data.success) {
            statusBox.className = 'webops-oauth-config__status-box webops-oauth-config__status-box--success';
            statusDetails.innerHTML = `
                <p><strong>✓ Connection successful!</strong></p>
                <p>OAuth configuration is working properly.</p>
                <p><small>Last tested: ${new Date().toLocaleString()}</small></p>
            `;
        } else {
            statusBox.className = 'webops-oauth-config__status-box webops-oauth-config__status-box--warning';
            statusDetails.innerHTML = `
                <p><strong>⚠ Connection failed</strong></p>
                <p>${webopsEscape(data.error || 'Unable to connect to Google OAuth service.')}</p>
                <p><small>Please check your credentials and try again.</small></p>
            `;
        }
    })
    .catch(error => {
        // Reset button
        testBtn.innerHTML = originalText;
        testBtn.disabled = false;

        // Show error
        const statusBox = document.querySelector('.webops-oauth-config__status-box');
        const statusDetails = statusBox.querySelector('.webops-oauth-config__status-details');
        statusBox.className = 'webops-oauth-config__status-box webops-oauth-config__status-box--warning';
        statusDetails.innerHTML = `
            <p><strong>⚠ Test failed</strong></p>
            <p>Network error occurred while testing connection.</p>
            <p><small>Please try again later.</small></p>
        `;
    });
}

// Enhanced form behavior
function updateFormBehavior() {
    const isConfigured = document.body.dataset.oauthConfigured === 'true';
    const form = document.querySelector('form');
    const submitBtn = document.querySelector('button[type="submit"]');

    if (isConfigured) {
        // Change submit button text for updates
        if (submitBtn && submitBtn.textContent.includes('Save')) {
            submitBtn.innerHTML = '<i class="fas fa-save"></i> Update Configuration';
        }

        // Add confirmation for updates
        form.addEventListener('submit', function(e) {
            if (!confirm('Are you sure you want to update the OAuth configuration? This may affect existing integrations.')) {
                e.preventDefault();
            }
        });
    }
}
