/* Moved from templates/auth/login.html (ui-skill rule 17: no inline <script>). */
(function() {
    'use strict';

    const form = document.getElementById('loginForm');
    const usernameInput = document.getElementById('id_username');
    const passwordInput = document.getElementById('id_password');
    const submitBtn = document.getElementById('submitBtn');
    const togglePassword = document.getElementById('togglePassword');

    // Password visibility toggle
    togglePassword.addEventListener('click', function() {
        const type = passwordInput.type === 'password' ? 'text' : 'password';
        passwordInput.type = type;
        const icon = this.querySelector('.material-icons');
        icon.textContent = type === 'password' ? 'visibility_off' : 'visibility';
    });

    // Real-time validation
    function validateUsername() {
        const value = usernameInput.value.trim();
        const feedback = document.getElementById('username-feedback');
        const icon = document.getElementById('username-icon');

        if (value === '') {
            usernameInput.classList.remove('valid', 'invalid');
            icon.textContent = '';
            feedback.classList.remove('show');
            return false;
        }

        if (value.length < 3) {
            usernameInput.classList.remove('valid');
            usernameInput.classList.add('invalid');
            icon.textContent = 'error';
            icon.classList.remove('success');
            icon.classList.add('error');
            feedback.innerHTML = '<span class="material-icons">error</span><span>Username must be at least 3 characters</span>';
            feedback.classList.add('show', 'error');
            feedback.classList.remove('success');
            return false;
        }

        usernameInput.classList.remove('invalid');
        usernameInput.classList.add('valid');
        icon.textContent = 'check_circle';
        icon.classList.remove('error');
        icon.classList.add('success');
        feedback.classList.remove('show');
        return true;
    }

    function validatePassword() {
        const value = passwordInput.value;
        const feedback = document.getElementById('password-feedback');

        if (value === '') {
            passwordInput.classList.remove('valid', 'invalid');
            feedback.classList.remove('show');
            return false;
        }

        if (value.length < 6) {
            passwordInput.classList.remove('valid');
            passwordInput.classList.add('invalid');
            feedback.innerHTML = '<span class="material-icons">error</span><span>Password must be at least 6 characters</span>';
            feedback.classList.add('show', 'error');
            feedback.classList.remove('success');
            return false;
        }

        passwordInput.classList.remove('invalid');
        passwordInput.classList.add('valid');
        feedback.classList.remove('show');
        return true;
    }

    // Attach event listeners
    usernameInput.addEventListener('input', validateUsername);
    usernameInput.addEventListener('blur', validateUsername);
    passwordInput.addEventListener('input', validatePassword);
    passwordInput.addEventListener('blur', validatePassword);

    // Form submission
    form.addEventListener('submit', function(e) {
        const usernameValid = validateUsername();
        const passwordValid = validatePassword();

        if (!usernameValid || !passwordValid) {
            e.preventDefault();

            if (!usernameValid) {
                usernameInput.focus();
            } else if (!passwordValid) {
                passwordInput.focus();
            }
            return false;
        }

        // Add loading state
        submitBtn.classList.add('auth-btn-loading');
        submitBtn.textContent = 'Logging in...';
    });

    // Clear validation on page load if there are errors
    window.addEventListener('load', function() {
        if (usernameInput.value) {
            validateUsername();
        }
    });
})();
