/* Moved from templates/services/configuration_list.html (ui-skill rule 17: no inline <script>). */
function resetToDefaults() {
    if (!confirm('Reset all configuration to default values? This cannot be undone.')) {
        return;
    }

    fetch(webopsPage().urlResetAll, {
        method: 'POST',
        headers: {
            'X-CSRFToken': webopsCsrf(),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Configuration reset to defaults successfully!');
            window.location.reload();
        } else {
            alert('Failed to reset configuration: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to reset configuration');
    });
}
