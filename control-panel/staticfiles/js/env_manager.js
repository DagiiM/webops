/**
 * Environment Variable Management
 * Interactive UI for managing deployment environment variables
 */

'use strict';

// State
let currentEditingKey = null;
let wizardData = null;

// DOM Elements
const variableModal = document.getElementById('variableModal');
const wizardModal = document.getElementById('wizardModal');
const variableForm = document.getElementById('variableForm');
const varKeyInput = document.getElementById('varKey');
const varValueInput = document.getElementById('varValue');
const modalTitle = document.getElementById('modalTitle');
const saveBtnText = document.getElementById('saveBtnText');
const saveBtnLoading = document.getElementById('saveBtnLoading');

// Modal Controls
document.getElementById('addVariableBtn')?.addEventListener('click', () => {
    openAddModal();
});

document.getElementById('closeModal')?.addEventListener('click', () => {
    closeVariableModal();
});

document.getElementById('cancelBtn')?.addEventListener('click', () => {
    closeVariableModal();
});

document.getElementById('generateEnvBtn')?.addEventListener('click', () => {
    openWizardModal();
});

document.getElementById('closeWizard')?.addEventListener('click', () => {
    closeWizardModal();
});

// Close modal on outside click
variableModal?.addEventListener('click', (e) => {
    if (e.target === variableModal) {
        closeVariableModal();
    }
});

wizardModal?.addEventListener('click', (e) => {
    if (e.target === wizardModal) {
        closeWizardModal();
    }
});

// Form submission
variableForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    await saveVariable();
});

// Edit and Delete buttons
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('edit-var')) {
        const row = e.target.closest('tr');
        const key = row.dataset.key;
        openEditModal(key);
    }

    if (e.target.classList.contains('delete-var')) {
        const row = e.target.closest('tr');
        const key = row.dataset.key;
        deleteVariable(key);
    }
});

/**
 * Open modal for adding new variable
 */
function openAddModal() {
    currentEditingKey = null;
    modalTitle.textContent = 'Add Variable';
    varKeyInput.value = '';
    varValueInput.value = '';
    varKeyInput.disabled = false;
    variableModal.classList.add('active');
    varKeyInput.focus();
}

/**
 * Open modal for editing existing variable
 */
function openEditModal(key) {
    currentEditingKey = key;
    modalTitle.textContent = 'Edit Variable';
    varKeyInput.value = key;
    varKeyInput.disabled = true;

    // Get current value from table
    const row = document.querySelector(`tr[data-key="${key}"]`);
    const valueCell = row.querySelector('.env-value');
    const isSecret = valueCell.classList.contains('secret');

    if (isSecret) {
        varValueInput.value = '';
        varValueInput.placeholder = 'Enter new value (leave empty to keep current)';
    } else {
        varValueInput.value = valueCell.textContent.trim();
    }

    variableModal.classList.add('active');
    varValueInput.focus();
}

/**
 * Close variable modal
 */
function closeVariableModal() {
    variableModal.classList.remove('active');
    currentEditingKey = null;
    variableForm.reset();
}

/**
 * Save variable (add or update)
 */
async function saveVariable() {
    const key = varKeyInput.value.trim();
    const value = varValueInput.value.trim();

    if (!key) {
        alert('Variable name is required');
        return;
    }

    // Show loading state
    saveBtnText.style.display = 'none';
    saveBtnLoading.style.display = 'inline-block';

    try {
        const response = await fetch(`/api/deployments/${DEPLOYMENT_ID}/env/set/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify({ key, value })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification('Variable saved successfully', 'success');
            closeVariableModal();
            // Reload page to show updated values
            setTimeout(() => window.location.reload(), 500);
        } else {
            throw new Error(data.error || 'Failed to save variable');
        }
    } catch (error) {
        console.error('Error saving variable:', error);
        showNotification(error.message, 'error');
    } finally {
        // Reset loading state
        saveBtnText.style.display = 'inline';
        saveBtnLoading.style.display = 'none';
    }
}

/**
 * Delete variable
 */
async function deleteVariable(key) {
    if (!confirm(`Are you sure you want to delete ${key}?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/deployments/${DEPLOYMENT_ID}/env/unset/`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify({ key })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification('Variable deleted successfully', 'success');
            // Remove row from table
            const row = document.querySelector(`tr[data-key="${key}"]`);
            row?.remove();

            // Check if table is empty
            const tbody = document.getElementById('envTableBody');
            if (tbody && tbody.children.length === 0) {
                setTimeout(() => window.location.reload(), 500);
            }
        } else {
            throw new Error(data.error || 'Failed to delete variable');
        }
    } catch (error) {
        console.error('Error deleting variable:', error);
        showNotification(error.message, 'error');
    }
}

/**
 * Open wizard modal
 */
async function openWizardModal() {
    wizardModal.classList.add('active');
    await loadWizardData();
}

/**
 * Close wizard modal
 */
function closeWizardModal() {
    wizardModal.classList.remove('active');
    wizardData = null;
}

/**
 * Load wizard data from API
 */
async function loadWizardData() {
    const wizardContent = document.getElementById('wizardContent');

    try {
        const response = await fetch(`/deployments/${DEPLOYMENT_ID}/env-wizard/`);
        const data = await response.json();

        if (!data.available) {
            wizardContent.innerHTML = `
                <div class="alert alert-warning">
                    <strong>Wizard not available.</strong><br>
                    ${data.error || 'No .env.example file found in repository.'}
                </div>
            `;
            return;
        }

        wizardData = data;
        renderWizard(data);
    } catch (error) {
        console.error('Error loading wizard data:', error);
        wizardContent.innerHTML = `
            <div class="alert alert-danger">
                <strong>Error loading wizard.</strong><br>
                ${error.message}
            </div>
        `;
    }
}

/**
 * Render wizard interface
 */
function renderWizard(data) {
    const wizardContent = document.getElementById('wizardContent');

    let html = `
        <div class="alert alert-info" style="margin-bottom: 1.5rem;">
            Found <strong>${data.total}</strong> variables
            (<strong>${data.required}</strong> required)
            ${data.has_env_file ? '- Will update existing .env file' : '- Will create new .env file'}
        </div>

        <div style="max-height: 400px; overflow-y: auto; margin-bottom: 1.5rem;">
    `;

    data.variables.forEach((variable, index) => {
        const isSecret = ['secret_key', 'encryption_key', 'api_key', 'api_secret', 'jwt_secret', 'password'].includes(variable.type);
        const hasValue = variable.value && variable.value.length > 0;

        html += `
            <div style="padding: 1rem; border: 1px solid #e5e7eb; border-radius: 6px; margin-bottom: 0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.5rem;">
                    <div>
                        <strong style="font-family: monospace; color: #1f2937;">${variable.key}</strong>
                        ${variable.required ? '<span style="color: #ef4444; margin-left: 0.5rem;">*</span>' : ''}
                        ${variable.comment ? `<p style="color: #6b7280; font-size: 0.75rem; margin: 0.25rem 0 0 0;">${variable.comment.replace(/^#\s*/gm, '')}</p>` : ''}
                    </div>
                    <span style="font-size: 0.75rem; background: #e5e7eb; padding: 0.25rem 0.5rem; border-radius: 4px;">${variable.type}</span>
                </div>
                <div style="margin-top: 0.5rem;">
                    <input
                        type="${isSecret ? 'password' : 'text'}"
                        id="wizard_${index}"
                        data-key="${variable.key}"
                        value="${variable.value || ''}"
                        placeholder="${variable.example_value || 'Will be auto-generated'}"
                        style="width: 100%; padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 4px; font-family: monospace; font-size: 0.875rem;"
                        ${hasValue && isSecret ? 'readonly' : ''}
                    >
                    ${hasValue && isSecret ? '<p style="font-size: 0.75rem; color: #6b7280; margin: 0.25rem 0 0 0;">Value already set (leave as-is or clear to regenerate)</p>' : ''}
                </div>
            </div>
        `;
    });

    html += `
        </div>

        <div style="display: flex; gap: 0.75rem; justify-content: flex-end;">
            <button type="button" class="webops-btn btn-secondary" onclick="closeWizardModal()">Cancel</button>
            <button type="button" class="webops-btn btn-success" onclick="generateEnvFile()">
                <span id="generateBtnText">Generate .env File</span>
                <span id="generateBtnLoading" class="loading" style="display: none;"></span>
            </button>
        </div>
    `;

    wizardContent.innerHTML = html;
}

/**
 * Generate .env file from wizard
 */
async function generateEnvFile() {
    const generateBtnText = document.getElementById('generateBtnText');
    const generateBtnLoading = document.getElementById('generateBtnLoading');

    // Collect custom values from inputs
    const customVars = {};
    wizardData.variables.forEach((variable, index) => {
        const input = document.getElementById(`wizard_${index}`);
        if (input && input.value && input.value !== variable.value) {
            customVars[variable.key] = input.value;
        }
    });

    // Show loading state
    generateBtnText.style.display = 'none';
    generateBtnLoading.style.display = 'inline-block';

    try {
        const response = await fetch(`/api/deployments/${DEPLOYMENT_ID}/env/generate/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify({
                debug: false,
                custom_vars: customVars
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification('Environment file generated successfully!', 'success');
            closeWizardModal();
            // Reload page to show new variables
            setTimeout(() => window.location.reload(), 1000);
        } else {
            throw new Error(data.error || 'Failed to generate environment file');
        }
    } catch (error) {
        console.error('Error generating env file:', error);
        showNotification(error.message, 'error');
        generateBtnText.style.display = 'inline';
        generateBtnLoading.style.display = 'none';
    }
}

/**
 * Show notification message
 */
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 2000;
        min-width: 300px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    `;
    notification.textContent = message;

    document.body.appendChild(notification);

    // Remove after 5 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transition = 'opacity 0.3s';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

// Make functions globally available
window.closeWizardModal = closeWizardModal;
window.generateEnvFile = generateEnvFile;
