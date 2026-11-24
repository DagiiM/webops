/* Moved from templates/api/token_create.html (ui-skill rule 17: no inline <script>). */
document.getElementById('create-form').addEventListener('submit', function() {
    const submitText = document.getElementById('submit-text');
    const submitLoading = document.getElementById('submit-loading');

    submitText.style.display = 'none';
    submitLoading.style.display = 'inline';

    // Disable form inputs
    const inputs = this.querySelectorAll('input, select, button');
    inputs.forEach(input => input.disabled = true);
});

// Character counter for token name
const nameInput = document.getElementById('name');
nameInput.addEventListener('input', function() {
    const length = this.value.length;
    const maxLength = this.maxLength;

    if (length > maxLength * 0.9) {
        this.style.borderColor = 'var(--webops-color-warning)';
    } else {
        this.style.borderColor = '';
    }
});
