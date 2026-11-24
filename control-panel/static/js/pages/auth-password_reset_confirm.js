/* Moved from templates/auth/password_reset_confirm.html (ui-skill rule 17: no inline <script>). */
(function() {
    'use strict';

    const form = document.getElementById('resetConfirmForm');
    const password1Input = document.getElementById(webopsPage().password1Id);
    const password2Input = document.getElementById(webopsPage().password2Id);
    const submitBtn = document.getElementById('submitBtn');

    // Add placeholders and classes
    password1Input.placeholder = 'Enter your new password';
    password1Input.className = 'auth-input';
    password1Input.autocomplete = 'new-password';
    password1Input.style.paddingRight = 'var(--webops-space-6)';
    password1Input.setAttribute('aria-describedby', 'password1-feedback');
    password1Input.autofocus = true;

    password2Input.placeholder = 'Confirm your new password';
    password2Input.className = 'auth-input';
    password2Input.autocomplete = 'new-password';
    password2Input.style.paddingRight = 'var(--webops-space-6)';
    password2Input.setAttribute('aria-describedby', 'password2-feedback');

    // Password visibility toggles
    document.getElementById('togglePassword1').addEventListener('click', function() {
        const type = password1Input.type === 'password' ? 'text' : 'password';
        password1Input.type = type;
        this.querySelector('.material-icons').textContent = type === 'password' ? 'visibility_off' : 'visibility';
    });

    document.getElementById('togglePassword2').addEventListener('click', function() {
        const type = password2Input.type === 'password' ? 'text' : 'password';
        password2Input.type = type;
        this.querySelector('.material-icons').textContent = type === 'password' ? 'visibility_off' : 'visibility';
    });

    // Password strength checker
    function checkPasswordStrength(password) {
        let strength = 0;
        const requirements = {
            length: password.length >= 8,
            uppercase: /[A-Z]/.test(password),
            lowercase: /[a-z]/.test(password),
            number: /[0-9]/.test(password)
        };

        // Update requirement indicators
        updateRequirement('req-length', requirements.length);
        updateRequirement('req-uppercase', requirements.uppercase);
        updateRequirement('req-lowercase', requirements.lowercase);
        updateRequirement('req-number', requirements.number);

        // Calculate strength
        if (requirements.length) strength++;
        if (requirements.uppercase) strength++;
        if (requirements.lowercase) strength++;
        if (requirements.number) strength++;

        return { strength, requirements };
    }

    function updateRequirement(id, met) {
        const el = document.getElementById(id);
        const icon = el.querySelector('.material-icons');

        if (met) {
            el.classList.add('met');
            icon.textContent = 'check_circle';
        } else {
            el.classList.remove('met');
            icon.textContent = 'radio_button_unchecked';
        }
    }

    // Password validation
    function validatePassword1() {
        const value = password1Input.value;
        const feedback = document.getElementById('password1-feedback');
        const strengthDiv = document.getElementById('passwordStrength');
        const requirementsDiv = document.getElementById('passwordRequirements');
        const strengthBar = document.getElementById('strengthBar');
        const strengthText = document.getElementById('strengthText');

        if (value === '') {
            password1Input.classList.remove('valid', 'invalid');
            feedback.classList.remove('show');
            strengthDiv.style.display = 'none';
            requirementsDiv.style.display = 'none';
            return false;
        }

        // Show strength meter and requirements
        strengthDiv.style.display = 'block';
        requirementsDiv.style.display = 'block';

        const { strength, requirements } = checkPasswordStrength(value);

        // Update strength bar
        strengthBar.className = 'password-strength-fill';
        if (strength <= 2) {
            strengthBar.classList.add('weak');
            strengthText.textContent = 'Weak';
        } else if (strength === 3) {
            strengthBar.classList.add('medium');
            strengthText.textContent = 'Medium';
        } else {
            strengthBar.classList.add('strong');
            strengthText.textContent = 'Strong';
        }

        // Validate
        const allMet = Object.values(requirements).every(met => met);
        if (!allMet) {
            password1Input.classList.remove('valid');
            password1Input.classList.add('invalid');
            return false;
        }

        password1Input.classList.remove('invalid');
        password1Input.classList.add('valid');
        feedback.classList.remove('show');
        return true;
    }

    // Confirm password validation
    function validatePassword2() {
        const value = password2Input.value;
        const password1Value = password1Input.value;
        const feedback = document.getElementById('password2-feedback');

        if (value === '') {
            password2Input.classList.remove('valid', 'invalid');
            feedback.classList.remove('show');
            return false;
        }

        if (value !== password1Value) {
            password2Input.classList.remove('valid');
            password2Input.classList.add('invalid');
            feedback.innerHTML = '<span class="material-icons">error</span><span>Passwords do not match</span>';
            feedback.classList.add('show', 'error');
            return false;
        }

        password2Input.classList.remove('invalid');
        password2Input.classList.add('valid');
        feedback.innerHTML = '<span class="material-icons">check_circle</span><span>Passwords match</span>';
        feedback.classList.add('show', 'success');
        feedback.classList.remove('error');
        return true;
    }

    // Attach event listeners
    password1Input.addEventListener('input', function() {
        validatePassword1();
        if (password2Input.value) validatePassword2();
    });
    password1Input.addEventListener('blur', validatePassword1);
    password2Input.addEventListener('input', validatePassword2);
    password2Input.addEventListener('blur', validatePassword2);

    // Form submission
    form.addEventListener('submit', function(e) {
        const password1Valid = validatePassword1();
        const password2Valid = validatePassword2();

        if (!password1Valid || !password2Valid) {
            e.preventDefault();

            if (!password1Valid) {
                password1Input.focus();
            } else if (!password2Valid) {
                password2Input.focus();
            }
            return false;
        }

        // Add loading state
        submitBtn.classList.add('auth-btn-loading');
        submitBtn.textContent = 'Resetting...';
    });
})();
