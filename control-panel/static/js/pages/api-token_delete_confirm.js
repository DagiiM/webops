/* Moved from templates/api/token_delete_confirm.html (ui-skill rule 17: no inline <script>). */
const confirmCheckbox = document.getElementById('confirm-delete');
const deleteButton = document.getElementById('delete-button');

confirmCheckbox.addEventListener('change', function() {
    deleteButton.disabled = !this.checked;
});

document.getElementById('delete-form').addEventListener('submit', function(e) {
    if (!confirmCheckbox.checked) {
        e.preventDefault();
        alert('Please confirm that you understand the consequences of deleting this token.');
    }
});
