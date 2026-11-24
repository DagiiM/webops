/* Moved from templates/services/ssl_configuration.html (ui-skill rule 17: no inline <script>). */
function toggleCertificateFields(certificateType) {
    const letsEncryptFields = document.getElementById('lets-encrypt-fields');
    const customCertificateFields = document.getElementById('custom-certificate-fields');

    if (certificateType === 'lets_encrypt') {
        letsEncryptFields.style.display = 'block';
        customCertificateFields.style.display = 'none';
    } else if (certificateType === 'custom' || certificateType === 'wildcard') {
        letsEncryptFields.style.display = 'none';
        customCertificateFields.style.display = 'block';
    } else {
        letsEncryptFields.style.display = 'none';
        customCertificateFields.style.display = 'none';
    }
}

// Form submission handling
document.getElementById('ssl-config-form').addEventListener('submit', function(e) {
    e.preventDefault();

    const form = this;
    const formData = new FormData(form);

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Show success message
            showNotification('SSL configuration updated successfully', 'success');
            // Reload page after short delay
            setTimeout(() => location.reload(), 1500);
        } else {
            // Show error message
            showNotification(data.message || 'Error updating SSL configuration', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error updating SSL configuration', 'error');
    });
});

function showNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `webops-notification webops-notification-${type}`;
    notification.innerHTML = `
        <span class="material-icons">${type === 'success' ? 'check_circle' : 'error'}</span>
        <span>${message}</span>
    `;

    // Add to page
    document.body.appendChild(notification);

    // Remove after 3 seconds
    setTimeout(() => {
        notification.remove();
    }, 3000);
}
