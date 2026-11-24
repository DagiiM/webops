/* Moved from templates/databases/detail.html (ui-skill rule 17: no inline <script>). */
const actualPassword = webopsPage().password;
let passwordVisible = false;

function togglePassword() {
    const passwordEl = document.getElementById('password');
    const toggleBtn = document.getElementById('toggle-btn');

    passwordVisible = !passwordVisible;

    if (passwordVisible) {
        passwordEl.textContent = actualPassword;
        passwordEl.classList.remove('password-hidden');
        toggleBtn.innerHTML = '<span class="material-icons">visibility_off</span>';
    } else {
        passwordEl.textContent = '••••••••••••••••';
        passwordEl.classList.add('password-hidden');
        toggleBtn.innerHTML = '<span class="material-icons">visibility</span>';
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard!');
    });
}

function copyConnectionString() {
    const connectionString = webopsPage().connectionString;
    navigator.clipboard.writeText(connectionString).then(() => {
        showNotification('Connection string copied!');
    });
}

function showNotification(message) {
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: var(--webops-success);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: var(--webops-radius);
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
