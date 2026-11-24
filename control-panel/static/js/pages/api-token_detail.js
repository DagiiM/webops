/* Moved from templates/api/token_detail.html (ui-skill rule 17: no inline <script>). */
const tokenValue = webopsPage().token;
let tokenVisible = false;

function toggleToken() {
    const tokenEl = document.getElementById('token-value');
    const toggleBtn = document.getElementById('toggle-btn');

    tokenVisible = !tokenVisible;

    if (tokenVisible) {
        tokenEl.classList.remove('webops-token-display__value--hidden');
        toggleBtn.innerHTML = '<span class="material-icons webops-s-7da4e82" >visibility_off</span> Hide Token';
    } else {
        tokenEl.classList.add('webops-token-display__value--hidden');
        toggleBtn.innerHTML = '<span class="material-icons webops-s-7da4e82" >visibility</span> Show Token';
    }
}

function copyToken() {
    navigator.clipboard.writeText(tokenValue).then(() => {
        showNotification('Token copied to clipboard!');
    });
}

function copyCode(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Code copied to clipboard!');
    });
}

function showNotification(message) {
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: var(--success);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: var(--webops-radius-md);
        box-shadow: none;
        z-index: 10000;
        animation: none;
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 2000);
}
