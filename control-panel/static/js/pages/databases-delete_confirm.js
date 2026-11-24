/* Moved from templates/databases/delete_confirm.html (ui-skill rule 17: no inline <script>). */
// Enable delete button only when checkbox is checked
const confirmCheckbox = document.getElementById('confirm-checkbox');
const deleteBtn = document.getElementById('delete-btn');

confirmCheckbox.addEventListener('change', function() {
    deleteBtn.disabled = !this.checked;
    if (this.checked) {
        deleteBtn.classList.remove('webops-opacity-50');
        deleteBtn.classList.add('webops-cursor-pointer');
    } else {
        deleteBtn.classList.add('webops-opacity-50');
        deleteBtn.classList.remove('webops-cursor-pointer');
    }
});

// Handle form submission
document.getElementById('delete-form').addEventListener('submit', function(e) {
    const deleteText = document.getElementById('delete-text');
    const deleteLoading = document.getElementById('delete-loading');

    deleteText.classList.add('webops-hidden');
    deleteLoading.classList.remove('webops-hidden');

    // Disable form inputs
    const inputs = this.querySelectorAll('input, button');
    inputs.forEach(input => input.disabled = true);
});

// Warn if user tries to leave page
let formSubmitted = false;
document.getElementById('delete-form').addEventListener('submit', function() {
    formSubmitted = true;
});

window.addEventListener('beforeunload', function(e) {
    if (!formSubmitted && confirmCheckbox.checked) {
        e.preventDefault();
        e.returnValue = '';
    }
});
