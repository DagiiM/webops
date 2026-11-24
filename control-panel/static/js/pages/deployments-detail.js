/* Moved from templates/deployments/detail.html (ui-skill rule 17: no inline <script>). */
let envEditorActive = false;
const deploymentId = webopsPage().deploymentId;
const csrfToken = webopsCsrf();

// Load initial env vars
const initialEnvVars = JSON.parse(webopsPage().envVars || '{}');

function toggleEnvEditor() {
    envEditorActive = !envEditorActive;
    const display = document.getElementById('env-display');
    const editor = document.getElementById('env-editor');
    const editBtn = document.getElementById('edit-env-btn');

    if (envEditorActive) {
        display.style.display = 'none';
        editor.style.display = 'block';
        editBtn.innerHTML = '<span class="material-icons webops-s-7da4e82" >close</span> Close Editor';
        populateEnvEditor();
    } else {
        display.style.display = 'block';
        editor.style.display = 'none';
        editBtn.innerHTML = '<span class="material-icons webops-s-7da4e82" >edit</span> Edit';
    }
}

function populateEnvEditor() {
    const container = document.getElementById('env-inputs');
    container.innerHTML = '';

    // Add existing env vars
    for (const [key, value] of Object.entries(initialEnvVars)) {
        addEnvVarRow(key, value);
    }

    // Add one empty row if no vars exist
    if (Object.keys(initialEnvVars).length === 0) {
        addEnvVarRow('', '');
    }
}

function addEnvVar() {
    addEnvVarRow('', '');
}

function addEnvVarRow(key = '', value = '') {
    const container = document.getElementById('env-inputs');
    const row = document.createElement('div');
    row.className = 'webops-env-input-row';
    row.innerHTML = `
        <input type="text" placeholder="KEY" value="${webopsEscape(key)}" class="env-key-input">
        <input type="text" placeholder="value" value="${webopsEscape(value)}" class="env-value-input">
        <button data-on-click="removeEnvVarRow(this)" title="Remove">
            <span class="material-icons webops-s-7da4e82" >delete</span>
        </button>
    `;
    container.appendChild(row);
}

function removeEnvVarRow(btn) {
    btn.parentElement.remove();
}

async function saveEnvVars() {
    const rows = document.querySelectorAll('.webops-env-input-row');
    const envVars = {};

    rows.forEach(row => {
        const key = row.querySelector('.env-key-input').value.trim();
        const value = row.querySelector('.env-value-input').value;

        if (key) {
            envVars[key] = value;
        }
    });

    try {
        const response = await fetch(`/deployments/${deploymentId}/env/update/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ env_vars: envVars })
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Environment variables updated! Service restarting...', 'success');
            setTimeout(() => {
                location.reload();
            }, 2000);
        } else {
            showNotification('Error: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to update environment variables', 'error');
        console.error(error);
    }
}

function cancelEnvEdit() {
    envEditorActive = false;
    document.getElementById('env-display').style.display = 'block';
    document.getElementById('env-editor').style.display = 'none';
    document.getElementById('edit-env-btn').innerHTML = '<span class="material-icons webops-s-7da4e82" >edit</span> Edit';
}

function refreshLogs() {
    location.reload();
}

function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? 'var(--success)' : 'var(--danger)'};
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
    }, 3000);
}

// Auto-scroll logs to bottom
const logsContainer = document.getElementById('logs-container');
if (logsContainer) {
    logsContainer.scrollTop = logsContainer.scrollHeight;
}

// File browser and validation functions
let currentPath = '';

function switchTab(tabName, tabEl) {
    // Update tab buttons
    document.querySelectorAll('.webops-tab').forEach(tab => tab.classList.remove('active'));
    if (tabEl) {
        tabEl.classList.add('active');
    }

    // Update tab content
    document.querySelectorAll('.webops-tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // Load initial content for tabs
    if (tabName === 'files' && !document.getElementById('file-list').hasChildNodes()) {
        navigateTo('');
    }
}

async function navigateTo(path) {
    currentPath = path;

    try {
        const response = await fetch(`/deployments/${deploymentId}/files/?path=${encodeURIComponent(path)}`);
        const data = await response.json();

        if (!data.success) {
            showNotification(data.error, 'error');
            return;
        }

        if (data.type === 'directory') {
            displayDirectory(data);
        } else if (data.type === 'file') {
            displayFile(data);
        }
    } catch (error) {
        showNotification('Error loading files', 'error');
        console.error(error);
    }
}

function displayDirectory(data) {
    const fileList = document.getElementById('file-list');
    const fileViewer = document.getElementById('file-viewer');

    fileViewer.style.display = 'none';
    fileList.innerHTML = '';

    // Update breadcrumb
    updateBreadcrumb(data.path);

    // Display items
    if (data.items.length === 0) {
        fileList.innerHTML = '<p class="text-muted">Empty directory</p>';
        return;
    }

    data.items.forEach(item => {
        const itemDiv = document.createElement('div');
        itemDiv.className = ` ${item.type}`;
        itemDiv.onclick = () => navigateTo(item.path);

        itemDiv.innerHTML = `
            <span class="material-icons">${item.type === 'directory' ? 'folder' : 'description'}</span>
            <div class="file-info">
                <div class="file-name">${webopsEscape(item.name)}</div>
                ${item.type === 'file' ? `<div class="file-size">${formatFileSize(item.size)}</div>` : ''}
            </div>
        `;

        fileList.appendChild(itemDiv);
    });
}

function displayFile(data) {
    const fileList = document.getElementById('file-list');
    const fileViewer = document.getElementById('file-viewer');
    const fileName = document.getElementById('file-name');
    const fileContent = document.getElementById('file-content');

    fileList.style.display = 'none';
    fileViewer.style.display = 'block';

    fileName.textContent = data.name;
    fileContent.textContent = data.content;
}

function closeFileViewer() {
    document.getElementById('file-list').style.display = 'flex';
    document.getElementById('file-viewer').style.display = 'none';

    // Navigate back to parent directory
    const pathParts = currentPath.split('/');
    pathParts.pop();
    navigateTo(pathParts.join('/'));
}

function updateBreadcrumb(path) {
    const breadcrumb = document.getElementById('breadcrumb');
    breadcrumb.textContent = '';

    // Built with DOM APIs: file names come from the repository and are untrusted.
    const addCrumb = (label, target) => {
        const crumb = document.createElement('span');
        crumb.className = 'breadcrumb-item';
        crumb.setAttribute('role', 'button');
        crumb.tabIndex = 0;
        crumb.dataset.path = target;
        crumb.setAttribute('data-on-click', 'navigateTo(this.dataset.path)');
        crumb.textContent = label;
        breadcrumb.appendChild(crumb);
    };

    addCrumb('Root', '');
    if (!path) return;

    const parts = path.split('/').filter(p => p);
    let currentPath = '';

    parts.forEach((part, index) => {
        currentPath += (index > 0 ? '/' : '') + part;
        const separator = document.createElement('span');
        separator.className = 'breadcrumb-separator';
        separator.textContent = '/';
        breadcrumb.appendChild(separator);
        addCrumb(part, currentPath);
    });
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

async function runValidation() {
    const btn = document.getElementById('validate-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="material-icons webops-s-7da4e82" >hourglass_empty</span> Validating...';

    try {
        // Prefer API route (requires token) if available via global API base
        let response;
        if (window.WEBOPS_API_BASE && window.WEBOPS_API_TOKEN) {
            response = await fetch(`${window.WEBOPS_API_BASE}/deployments/${webopsPage().name}/project/validate/`, {
                headers: { 'Authorization': `Bearer ${window.WEBOPS_API_TOKEN}` }
            });
        } else {
            // Fallback to server-rendered view by PK
            response = await fetch(`/deployments/${deploymentId}/validate/`);
        }
        const data = await response.json();

        if (!data.success) {
            showNotification(data.error || 'Validation failed', 'error');
            return;
        }

        displayValidationResults(data);

        // Switch to validation tab
        const tabs = document.querySelectorAll('.webops-tab');
        tabs.forEach(t => t.classList.remove('active'));
        document.querySelector(".webops-tab[onclick*='validation']").classList.add('active');
        document.getElementById('files-tab').classList.remove('active');
        document.getElementById('validation-tab').classList.add('active');

    } catch (error) {
        showNotification('Error running validation', 'error');
        console.error(error);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="material-icons webops-s-7da4e82" >verified</span> Validate';
    }
}

function displayValidationResults(data) {
    const container = document.getElementById('validation-results');
    container.innerHTML = '';

    // Summary
    const summary = document.createElement('div');
    summary.className = 'validation-summary';

    const errorCount = data.results.filter(r => r.level === 'error').length;
    const warningCount = data.results.filter(r => r.level === 'warning').length;
    const passedCount = data.results.filter(r => r.passed).length;

    summary.innerHTML = `
        <div class="validation-stat">
            <span class="material-icons webops-s-26deb88" >check_circle</span>
            <span>${passedCount} Passed</span>
        </div>
        <div class="validation-stat">
            <span class="material-icons webops-s-9cb6f55" >error</span>
            <span>${errorCount} Errors</span>
        </div>
        <div class="validation-stat">
            <span class="material-icons webops-s-cab13eb" >warning</span>
            <span>${warningCount} Warnings</span>
        </div>
    `;

    container.appendChild(summary);

    // Results
    data.results.forEach(result => {
        const item = document.createElement('div');
        const levelClass = result.passed ? 'passed' : result.level;
        item.className = `validation-result-item ${levelClass}`;

        const icon = result.passed ? 'check_circle' :
                     result.level === 'error' ? 'error' :
                     result.level === 'warning' ? 'warning' : 'info';

        item.innerHTML = `
            <span class="material-icons">${icon}</span>
            <div class="validation-message">
                <div class="webops-s-81595a9">${webopsEscape(result.message)}</div>
                ${result.details && result.details.suggestion ?
                    `<div class="webops-s-e1394aa">
                        💡 ${webopsEscape(result.details.suggestion)}
                    </div>` : ''
                }
            </div>
        `;

        container.appendChild(item);
    });
}

async function loadEnvWizard() {
    try {
        const response = await fetch(`/deployments/${deploymentId}/env-wizard/`);
        const data = await response.json();

        if (!data.available) {
            showNotification(data.error || 'No .env.example file found', 'info');
            return;
        }

        // Show modal with env wizard
        showEnvWizardModal(data);

    } catch (error) {
        showNotification('Error loading .env wizard', 'error');
        console.error(error);
    }
}

function showEnvWizardModal(data) {
    // Create modal
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        padding: 20px;
    `;

    const modalContent = document.createElement('div');
    modalContent.style.cssText = `
        background: var(--webops-color-bg-tertiary);
        border-radius: 8px;
        max-width: 800px;
        width: 100%;
        max-height: 90vh;
        overflow: auto;
        padding: 2rem;
    `;

    let envInputsHTML = '';
    data.variables.forEach(variable => {
        const value = initialEnvVars[variable.key] || variable.suggested_value || variable.default_value || '';

        envInputsHTML += `
            <div class="webops-s-c2c0d0a">
                <label class="webops-s-26c8c3a">
                    ${variable.key}
                    ${variable.required ? '<span class="webops-s-9cb6f55">*</span>' : ''}
                </label>
                ${variable.comment ? `<div class="webops-s-0c1db65">${variable.comment}</div>` : ''}
                <input type="${variable.is_secret ? 'password' : 'text'}"
                       class="form-input env-wizard-input"
                       data-key="${variable.key}"
                       value="${webopsEscape(value)}"
                       placeholder="${variable.suggested_value}"
                       ${variable.required ? 'required' : ''}>
            </div>
        `;
    });

    modalContent.innerHTML = `
        <h2 class="webops-s-ec0f7ff">Environment Variables Wizard</h2>
        <p class="webops-s-b1e8fac">Configure environment variables from .env.example</p>
        <div class="webops-s-6813d52">
            ${envInputsHTML}
        </div>
        <div class="webops-s-5a927fb">
            <button data-on-click="this.closest('[style*=fixed]').remove()" class="webops-btn btn-outline">Cancel</button>
            <button data-on-click="applyEnvWizard()" class="webops-btn webops-btn-primary">Apply & Restart</button>
        </div>
    `;

    modal.appendChild(modalContent);
    document.body.appendChild(modal);

    // Close on background click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

async function applyEnvWizard() {
    const inputs = document.querySelectorAll('.env-wizard-input');
    const envVars = {};

    inputs.forEach(input => {
        const key = input.dataset.key;
        const value = input.value.trim();
        if (value) {
            envVars[key] = value;
        }
    });

    try {
        const response = await fetch(`/deployments/${deploymentId}/env/update/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ env_vars: envVars })
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Environment variables applied! Service restarting...', 'success');
            document.querySelector('[style*=fixed]').remove();
            setTimeout(() => location.reload(), 2000);
        } else {
            showNotification('Error: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to apply environment variables', 'error');
        console.error(error);
    }
}

// Auto-load file browser on page load
document.addEventListener('DOMContentLoaded', () => {
    navigateTo('');
});
