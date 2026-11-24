/* Moved from templates/databases/tags/install_button.html (ui-skill rule 17: no inline <script>).
   Loaded once per page: the guard stops repeated listeners when the tag is included several times. */
if (!window.__webopsInstallButtons) {
    window.__webopsInstallButtons = true;
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('.webops-install-btn').forEach(button => {
            button.addEventListener('click', function() {
                const dbType = this.getAttribute('data-db-type');
                const dep = this.getAttribute('data-dep');
                const originalText = this.innerHTML;
            
                // Show loading state
                this.innerHTML = '<span class="material-icons">hourglass_empty</span> Installing...';
                this.disabled = true;
            
                // Prepare form data
                const formData = new FormData();
                formData.append('db_type', dbType);
                if (dep) {
                    formData.append('dependencies', dep);
                }
            
                // Send request
                fetch(this.getAttribute('data-install-url'), {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Check if installation was successful
                        const depName = dep || 'dependencies';
                        let allSuccess = true;
                    
                        if (dep) {
                            allSuccess = data.results[dep] && data.results[dep].success;
                        } else {
                            allSuccess = Object.values(data.results).every(result => result.success);
                        }
                    
                        if (allSuccess) {
                            showNotification(`Successfully installed ${depName}`, 'success');
                            // Reload the page after a short delay
                            setTimeout(() => location.reload(), 1000);
                        } else {
                            showNotification(`Failed to install ${depName}`, 'error');
                            this.innerHTML = originalText;
                            this.disabled = false;
                        }
                    } else {
                        showNotification(`Error: ${data.error}`, 'error');
                        this.innerHTML = originalText;
                        this.disabled = false;
                    }
                })
                .catch(error => {
                    showNotification(`Error: ${error.message}`, 'error');
                    this.innerHTML = originalText;
                    this.disabled = false;
                });
            });
        });
    });

    function showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `webops-notification webops-notification-${type}`;
        notification.innerHTML = `
            <div class="webops-flex webops-items-center webops-gap-md">
                <span class="material-icons">
                    ${type === 'success' ? 'check_circle' : 'error'}
                </span>
                <div>${message}</div>
            </div>
        `;
    
        // Style the notification
        notification.className += ' webops-notification-fixed';
    
        // Set background color based on type
        if (type === 'success') {
            notification.classList.add('webops-notification-success');
        } else {
            notification.classList.add('webops-notification-error');
        }
    
        document.body.appendChild(notification);
    
        // Remove after 3 seconds
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // Add slide animations
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
    `;
    document.head.appendChild(style);

}
