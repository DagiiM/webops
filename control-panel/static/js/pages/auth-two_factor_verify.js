/* Moved from templates/auth/two_factor_verify.html (ui-skill rule 17: no inline <script>). */
(function() {
    'use strict';

    const form = document.getElementById('verifyForm');
    const codeInput = document.getElementById(webopsPage().codeId);
    const backupCodeInput = document.getElementById(webopsPage().backupCodeId);
    const submitBtn = document.getElementById('submitBtn');
    const backupDetails = document.getElementById('backupCodeDetails');

    // Add placeholders and classes
    codeInput.placeholder = '000000';
    codeInput.className = 'auth-input code-input';
    codeInput.autocomplete = 'one-time-code';
    codeInput.setAttribute('inputmode', 'numeric');
    codeInput.setAttribute('pattern', '[0-9]*');
    codeInput.setAttribute('maxlength', '6');
    codeInput.setAttribute('aria-describedby', 'code-feedback');
    codeInput.autofocus = true;

    backupCodeInput.placeholder = 'XXXX-XXXX-XXXX';
    backupCodeInput.className = 'auth-input backup-code-input';
    backupCodeInput.autocomplete = 'off';
    backupCodeInput.setAttribute('maxlength', '14');
    backupCodeInput.setAttribute('aria-describedby', 'backup-feedback');

    // Code validation
    function validateCode() {
        const value = codeInput.value.trim();
        const feedback = document.getElementById('code-feedback');
        const icon = document.getElementById('code-icon');

        if (value === '') {
            codeInput.classList.remove('valid', 'invalid');
            icon.textContent = '';
            feedback.classList.remove('show');
            return false;
        }

        // Check if it's 6 digits
        if (!/^\d{6}$/.test(value)) {
            codeInput.classList.remove('valid');
            codeInput.classList.add('invalid');
            icon.textContent = 'error';
            icon.classList.remove('success');
            icon.classList.add('error');
            feedback.innerHTML = '<span class="material-icons">error</span><span>Code must be 6 digits</span>';
            feedback.classList.add('show', 'error');
            feedback.classList.remove('success');
            return false;
        }

        codeInput.classList.remove('invalid');
        codeInput.classList.add('valid');
        icon.textContent = 'check_circle';
        icon.classList.remove('error');
        icon.classList.add('success');
        feedback.classList.remove('show');
        return true;
    }

    // Backup code validation
    function validateBackupCode() {
        const value = backupCodeInput.value.trim();
        const feedback = document.getElementById('backup-feedback');
        const icon = document.getElementById('backup-icon');

        if (value === '') {
            backupCodeInput.classList.remove('valid', 'invalid');
            icon.textContent = '';
            feedback.classList.remove('show');
            return false;
        }

        // Remove hyphens for validation
        const cleanValue = value.replace(/-/g, '');

        // Check if it's 12 alphanumeric characters
        if (!/^[A-Z0-9]{12}$/i.test(cleanValue)) {
            backupCodeInput.classList.remove('valid');
            backupCodeInput.classList.add('invalid');
            icon.textContent = 'error';
            icon.classList.remove('success');
            icon.classList.add('error');
            feedback.innerHTML = '<span class="material-icons">error</span><span>Invalid backup code format</span>';
            feedback.classList.add('show', 'error');
            feedback.classList.remove('success');
            return false;
        }

        backupCodeInput.classList.remove('invalid');
        backupCodeInput.classList.add('valid');
        icon.textContent = 'check_circle';
        icon.classList.remove('error');
        icon.classList.add('success');
        feedback.classList.remove('show');
        return true;
    }

    // Auto-format code input (numbers only)
    codeInput.addEventListener('input', function(e) {
        // Remove non-digits
        this.value = this.value.replace(/\D/g, '');

        // Validate
        validateCode();

        // Auto-submit when 6 digits are entered
        if (this.value.length === 6) {
            validateCode();
            // Give user a moment to see the validation
            setTimeout(() => {
                if (validateCode()) {
                    submitBtn.classList.add('auth-btn-loading');
                    submitBtn.textContent = 'Verifying...';
                    form.submit();
                }
            }, 300);
        }
    });

    // Auto-format backup code (add hyphens)
    backupCodeInput.addEventListener('input', function(e) {
        let value = this.value.replace(/-/g, '').toUpperCase();

        // Add hyphens every 4 characters
        if (value.length > 4) {
            value = value.match(/.{1,4}/g).join('-');
        }

        this.value = value;
        validateBackupCode();
    });

    // Handle paste for code input
    codeInput.addEventListener('paste', function(e) {
        e.preventDefault();
        const pastedText = (e.clipboardData || window.clipboardData).getData('text');
        const cleaned = pastedText.replace(/\D/g, '').substring(0, 6);
        this.value = cleaned;
        validateCode();

        if (cleaned.length === 6 && validateCode()) {
            setTimeout(() => {
                submitBtn.classList.add('auth-btn-loading');
                submitBtn.textContent = 'Verifying...';
                form.submit();
            }, 300);
        }
    });

    // Handle paste for backup code input
    backupCodeInput.addEventListener('paste', function(e) {
        e.preventDefault();
        const pastedText = (e.clipboardData || window.clipboardData).getData('text');
        const cleaned = pastedText.replace(/[^A-Z0-9]/gi, '').toUpperCase().substring(0, 12);

        // Format with hyphens
        const formatted = cleaned.match(/.{1,4}/g)?.join('-') || cleaned;
        this.value = formatted;
        validateBackupCode();
    });

    // Toggle between code and backup code
    backupDetails.addEventListener('toggle', function() {
        if (this.open) {
            // Clear and focus backup code input
            codeInput.value = '';
            codeInput.classList.remove('valid', 'invalid');
            document.getElementById('code-icon').textContent = '';
            document.getElementById('code-feedback').classList.remove('show');

            // Focus backup code input
            setTimeout(() => backupCodeInput.focus(), 100);
        } else {
            // Clear and focus regular code input
            backupCodeInput.value = '';
            backupCodeInput.classList.remove('valid', 'invalid');
            document.getElementById('backup-icon').textContent = '';
            document.getElementById('backup-feedback').classList.remove('show');

            // Focus code input
            setTimeout(() => codeInput.focus(), 100);
        }
    });

    // Attach event listeners
    codeInput.addEventListener('blur', validateCode);
    backupCodeInput.addEventListener('blur', validateBackupCode);

    // Form submission
    form.addEventListener('submit', function(e) {
        const usingBackupCode = backupDetails.open;

        if (usingBackupCode) {
            const backupValid = validateBackupCode();
            if (!backupValid) {
                e.preventDefault();
                backupCodeInput.focus();
                return false;
            }

            // Clear the regular code field
            codeInput.value = '';
        } else {
            const codeValid = validateCode();
            if (!codeValid) {
                e.preventDefault();
                codeInput.focus();
                return false;
            }

            // Clear the backup code field
            backupCodeInput.value = '';
        }

        // Add loading state
        if (!submitBtn.classList.contains('auth-btn-loading')) {
            submitBtn.classList.add('auth-btn-loading');
            submitBtn.textContent = 'Verifying...';
        }
    });

    // Focus on code input initially
    codeInput.focus();
})();
