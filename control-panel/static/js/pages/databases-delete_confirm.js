/* Moved from templates/databases/delete_confirm.html (ui-skill rule 17: no inline <script>). */
// Enable delete button only when checkbox is checked
const confirmCheckbox = document.getElementById('confirm-checkbox');
const deleteBtn = document.getElementById('delete-btn');

const confirmName = document.getElementById('confirm-name');
function syncDeleteButton() {
    const ok = confirmCheckbox.checked && (!confirmName || confirmName.value === confirmName.dataset.expect);
    deleteBtn.disabled = !ok;
    deleteBtn.classList.toggle('webops-opacity-50', !ok);
    deleteBtn.classList.toggle('webops-cursor-pointer', ok);
}
confirmCheckbox.addEventListener('change', syncDeleteButton);
if (confirmName) confirmName.addEventListener('input', syncDeleteButton);

// Handle form submission
document.getElementById('delete-form').addEventListener('submit', function(e) {
    const deleteText = document.getElementById('delete-text');
    const deleteLoading = document.getElementById('delete-loading');

    deleteText.classList.add('webops-hidden');
    deleteLoading.classList.remove('webops-hidden');

    // Disable the button only: disabled inputs are not submitted, and the confirmation must be.
    deleteBtn.disabled = true;
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
