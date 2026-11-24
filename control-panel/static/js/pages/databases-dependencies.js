/* Moved from templates/databases/dependencies.html (ui-skill rule 17: no inline <script>). */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard!', 'success');
    });
}

function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `webops-notification webops-notification-${type}`;
    notification.innerHTML = `
        <div class="webops-flex webops-items-center webops-gap-md">
            <span class="material-icons">
                ${type === 'success' ? 'check_circle' : type === 'error' ? 'error' : 'info'}
            </span>
            <div>${message}</div>
        </div>
    `;

    // Style the notification
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: var(--webops-space-3);
        border-radius: var(--webops-radius-md);
        box-shadow: none;
        z-index: 10000;
        max-width: 500px;
        animation: none;
    `;

    // Set background color based on type
    if (type === 'success') {
        notification.style.background = 'var(--webops-color-success)';
        notification.style.color = 'white';
    } else if (type === 'error') {
        notification.style.background = 'var(--webops-color-error)';
        notification.style.color = 'white';
    } else {
        notification.style.background = 'var(--webops-color-primary)';
        notification.style.color = 'white';
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
