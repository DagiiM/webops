/* Moved from templates/auth/password_reset.html (ui-skill rule 17: no inline <script>). */
(function() {
    'use strict';

    const form = document.getElementById('resetForm');
    const emailInput = document.getElementById(webopsPage().emailId);
    const submitBtn = document.getElementById('submitBtn');

    // Add placeholders and classes
    emailInput.placeholder = 'your.email@example.com';
    emailInput.className = 'auth-input';
    emailInput.type = 'email';
    emailInput.autocomplete = 'email';
    emailInput.setAttribute('aria-describedby', 'email-feedback');
    emailInput.autofocus = true;

    // Email validation
    function validateEmail() {
        const value = emailInput.value.trim();
        const feedback = document.getElementById('email-feedback');
        const icon = document.getElementById('email-icon');

        if (value === '') {
            emailInput.classList.remove('valid', 'invalid');
            icon.textContent = '';
            feedback.classList.remove('show');
            return false;
        }

        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
            emailInput.classList.remove('valid');
            emailInput.classList.add('invalid');
            icon.textContent = 'error';
            icon.classList.remove('success');
            icon.classList.add('error');
            feedback.innerHTML = '<span class="material-icons">error</span><span>Please enter a valid email address</span>';
            feedback.classList.add('show', 'error');
            feedback.classList.remove('success');
            return false;
        }

        emailInput.classList.remove('invalid');
        emailInput.classList.add('valid');
        icon.textContent = 'check_circle';
        icon.classList.remove('error');
        icon.classList.add('success');
        feedback.classList.remove('show');
        return true;
    }

    // Attach event listeners
    emailInput.addEventListener('input', validateEmail);
    emailInput.addEventListener('blur', validateEmail);

    // Form submission
    form.addEventListener('submit', function(e) {
        const emailValid = validateEmail();

        if (!emailValid) {
            e.preventDefault();
            emailInput.focus();
            return false;
        }

        // Add loading state
        submitBtn.classList.add('auth-btn-loading');
        submitBtn.textContent = 'Sending...';
    });
})();
