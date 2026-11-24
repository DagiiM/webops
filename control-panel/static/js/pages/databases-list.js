/* Moved from templates/databases/list.html (ui-skill rule 17: no inline <script>). */
// Enhanced dependency status management for modal
class ModalDependencyStatusManager {
    constructor() {
        this.currentDbType = null;
        this.dependencies = [];
        this.installationPromises = new Map();
    }

    async checkDependencies(dbType) {
        try {
            const response = await fetch(`/databases/check-dependencies/?db_type=${dbType}`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // Handle the case where the response is an error page (HTML)
            if (typeof data === 'string' && data.includes('<!DOCTYPE')) {
                throw new Error('Server returned HTML instead of JSON');
            }

            return data;
        } catch (error) {
            console.error('Failed to check dependencies:', error);
            return { success: false, status: 'error', message: 'Failed to check dependencies: ' + error.message };
        }
    }

    async installDependency(dependency, dbType) {
        try {
            const response = await fetch('/databases/install-dependencies/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    db_type: dbType,
                    dependencies: [dependency]
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // Handle the case where the response is an error page (HTML)
            if (typeof data === 'string' && data.includes('<!DOCTYPE')) {
                throw new Error('Server returned HTML instead of JSON');
            }

            return data;
        } catch (error) {
            console.error('Failed to install dependency:', error);
            return { success: false, status: 'error', message: 'Installation failed: ' + error.message };
        }
    }

    async performInstallation(dependency, dbType) {
        try {
            const response = await fetch('/databases/install-dependencies/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    db_type: dbType,
                    dependencies: [dependency]
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // Handle the case where the response is an error page (HTML)
            if (typeof data === 'string' && data.includes('<!DOCTYPE')) {
                throw new Error('Server returned HTML instead of JSON');
            }

            return data;
        } catch (error) {
            console.error('Failed to install dependency:', error);
            return { success: false, status: 'error', message: 'Installation failed: ' + error.message };
        }
    }

    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
               document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
               document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1];
    }

    updateDependencyCard(data) {
        const card = document.getElementById('dependency-status-card-modal');
        const overview = document.getElementById('dependency-overview-modal');
        const statusText = document.getElementById('dependency-status-text-modal');
        const summary = document.getElementById('dependency-summary-modal');
        const icon = document.getElementById('dependency-icon-modal');
        const details = document.getElementById('dependency-details-modal');
        const list = document.getElementById('dependency-list-modal');
        const actions = document.getElementById('dependency-actions-modal');

        if (!data.success || data.status === 'error') {
            this.showErrorState(data.message || 'Unknown error occurred');
            return;
        }

        const allInstalled = data.all_installed || (data.dependencies && data.dependencies.every(dep => dep.installed));
        const hasMissing = !allInstalled;

        if (allInstalled) {
            icon.textContent = 'check_circle';
            icon.className = 'material-icons';
            icon.classList.add('webops-text-success');
            statusText.textContent = 'All Dependencies Installed';
            statusText.className = 'webops-badge webops-badge-success';
            summary.textContent = 'All required dependencies are ready for use';
            actions.innerHTML = '<button class="webops-btn webops-btn-sm webops-btn-success" disabled><span class="material-icons">check</span> Ready</button>';
        } else if (hasMissing) {
            icon.textContent = 'warning';
            icon.className = 'material-icons';
            icon.classList.add('webops-text-warning');
            statusText.textContent = 'Missing Dependencies';
            statusText.className = 'webops-badge webops-badge-warning';

            const missingCount = data.dependencies ? data.dependencies.filter(dep => !dep.installed).length :
                               (data.missing_deps ? data.missing_deps.length : 0);
            summary.textContent = `${missingCount} dependencies need to be installed`;
            actions.innerHTML = '<button id="install-all-btn-modal" class="webops-btn webops-btn-sm webops-btn-primary"><span class="material-icons">download</span> Install All</button>';

            // Add install all functionality
            document.getElementById('install-all-btn-modal')?.addEventListener('click', () => {
                this.installAllDependencies(data.dependencies);
            });
        }

        // Update dependency list
        list.innerHTML = '';
        data.dependencies.forEach(dep => {
            const item = this.createDependencyItem(dep);
            list.appendChild(item);
        });

        // Show details
        details.classList.remove('webops-hidden');
        card.classList.remove('webops-hidden');
    }

    createDependencyItem(dep) {
        const item = document.createElement('div');
        item.className = `dependency-item ${dep.installed ? 'installed' : 'missing'}`;
        item.id = `modal-dep-${webopsEscape(dep.name)}`;

        item.innerHTML = `
            <div class="dependency-info">
                <span class="material-icons dependency-icon ${dep.installed ? 'installed' : 'missing'}">
                    ${dep.installed ? 'check_circle' : 'warning'}
                </span>
                <div class="dependency-details">
                    <div class="dependency-name">${webopsEscape(dep.name)}</div>
                    <div class="dependency-description">${webopsEscape(dep.description || 'Required dependency')}</div>
                </div>
            </div>
            <div class="dependency-status ${dep.installed ? 'installed' : 'missing'}">
                <span class="material-icons webops-icon--small">
                    ${dep.installed ? 'check_circle' : 'warning'}
                </span>
                ${dep.installed ? 'Installed' : 'Missing'}
            </div>
            <div class="dependency-actions">
                ${dep.installed ?
                    '<button class="dependency-install-btn installed" disabled><span class="material-icons">check</span>Installed</button>' :
                    `<button class="dependency-install-btn missing" data-on-click="modalDependencyManager.installDependency('${webopsEscape(dep.name)}', '${this.currentDbType}')">
                        <span class="material-icons">download</span>Install
                    </button>`
                }
            </div>
        `;

        return item;
    }

    async installDependency(dependency, dbType) {
        const button = document.querySelector(`#modal-dep-${dependency} .dependency-install-btn`);
        const status = document.querySelector(`#modal-dep-${dependency} .dependency-status`);
        const item = document.getElementById(`modal-dep-${dependency}`);

        if (this.installationPromises.has(dependency)) {
            return; // Already installing
        }

        // Update UI to installing state
        button.className = 'dependency-install-btn installing';
        button.disabled = true;
        button.innerHTML = '<span class="material-icons">hourglass_empty</span>Installing...';

        status.className = 'dependency-status installing';
        status.innerHTML = '<span class="material-icons webops-icon--small">hourglass_empty</span>Installing...';

        item.className = 'dependency-item installing';

        try {
            console.log(`Installing dependency ${dependency} for ${dbType}...`);
            const result = await this.performInstallation(dependency, dbType);
            console.log('Installation result:', result);

            // Check if the installation was successful
            const installSuccess = result.success &&
                                  result.status !== 'error' &&
                                  result.results &&
                                  result.results[dependency] &&
                                  result.results[dependency].success;

            console.log(`Install success for ${dependency}:`, installSuccess);

            if (installSuccess) {
                // Update to installed state
                button.className = 'dependency-install-btn installed';
                button.disabled = true;
                button.innerHTML = '<span class="material-icons">check</span>Installed';

                status.className = 'dependency-status installed';
                status.innerHTML = '<span class="material-icons webops-icon--small">check_circle</span>Installed';

                item.className = 'dependency-item installed';

                // Check if all dependencies are now installed
                console.log(`Re-checking dependencies for ${dbType} after installing ${dependency}...`);
                this.checkDependencies(dbType).then(data => {
                    console.log('Dependency check result after installation:', data);
                    this.updateDependencyCard(data);
                });
            } else {
                throw new Error(result.message || 'Installation failed');
            }
        } catch (error) {
            // Update to failed state
            button.className = 'dependency-install-btn failed';
            button.disabled = false;
            button.innerHTML = '<span class="material-icons">error</span>Retry';

            status.className = 'dependency-status failed';
            status.innerHTML = '<span class="material-icons webops-icon--small">error</span>Failed';

            item.className = 'dependency-item failed';

            console.error('Installation failed:', error);
        } finally {
            this.installationPromises.delete(dependency);
        }
    }

    async installAllDependencies(dependencies) {
        const installAllBtn = document.getElementById('install-all-btn-modal');
        if (installAllBtn) {
            installAllBtn.disabled = true;
            installAllBtn.innerHTML = '<span class="material-icons webops-icon--small">hourglass_empty</span>Installing All...';
        }

        const missingDeps = dependencies.filter(dep => !dep.installed);

        for (const dep of missingDeps) {
            await this.installDependency(dep.name, this.currentDbType);
        }

        if (installAllBtn) {
            installAllBtn.classList.add('webops-hidden');
        }
    }

    showErrorState(message) {
        const card = document.getElementById('dependency-status-card-modal');
        const overview = document.getElementById('dependency-overview-modal');
        const icon = document.getElementById('dependency-icon-modal');
        const statusText = document.getElementById('dependency-status-text-modal');
        const summary = document.getElementById('dependency-summary-modal');

        icon.textContent = 'error';
        icon.className = 'material-icons';
        icon.classList.add('webops-text-error');
        statusText.textContent = 'Error';
        statusText.className = 'webops-badge webops-badge-error';
        summary.textContent = message;

        card.classList.remove('webops-hidden');
    }

}

// Initialize modal dependency manager
const modalDependencyManager = new ModalDependencyStatusManager();

// Search functionality
const searchInput = document.getElementById('search');
if (searchInput) {
    searchInput.addEventListener('input', function(e) {
        const searchTerm = e.target.value.toLowerCase();
        const rows = document.querySelectorAll('tbody tr');

        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.classList.toggle('webops-hidden', !text.includes(searchTerm));
        });
    });
}

// Modal functions
function openCreateModal() {
    document.getElementById('createModal').classList.add('active');
    document.getElementById('name').focus();
}

function closeCreateModal() {
    document.getElementById('createModal').classList.remove('active');
    document.getElementById('createForm').reset();
}

// Close modal on outside click
document.getElementById('createModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeCreateModal();
    }
});

// Close modal on escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeCreateModal();
    }
});

// Database type selection handler
document.getElementById('db_type').addEventListener('change', async function(e) {
    const dbType = e.target.value;

    // Hide all database type fields
    document.querySelectorAll('.db-type-fields').forEach(el => {
        el.classList.add('webops-hidden');
    });

    // Hide notices
    document.getElementById('password-notice').classList.add('webops-hidden');
    document.getElementById('dependency-status-card-modal').classList.add('webops-hidden');

    // Show relevant fields based on database type
    if (dbType) {
        const fields = document.getElementById(dbType + '-fields');
        if (fields) {
            fields.classList.remove('webops-hidden');
        }

        // Show password notice for databases that need password generation
        if (['postgresql', 'mysql'].includes(dbType)) {
            document.getElementById('password-notice').classList.remove('webops-hidden');
        }

        // Check dependencies for databases that require them
        if (['postgresql', 'mysql', 'mongodb', 'redis'].includes(dbType)) {
            modalDependencyManager.currentDbType = dbType;
            const data = await modalDependencyManager.checkDependencies(dbType);
            modalDependencyManager.updateDependencyCard(data);
        } else {
            // Hide dependency card for databases that don't require dependencies
            document.getElementById('dependency-status-card-modal').style.display = 'none';
        }
    }
});

// Auto-suggest username from database name for PostgreSQL and MySQL
document.getElementById('name').addEventListener('input', function(e) {
    const dbType = document.getElementById('db_type').value;
    let usernameInput = null;

    if (dbType === 'postgresql') {
        usernameInput = document.getElementById('username_postgresql');
    } else if (dbType === 'mysql') {
        usernameInput = document.getElementById('username_mysql');
    } else if (dbType === 'mongodb') {
        usernameInput = document.getElementById('username_mongodb');
    }

    if (usernameInput && !usernameInput.value) {
        const suggestion = e.target.value.replace(/_db$/, '_user');
        usernameInput.value = suggestion;
    }
});

// Show loader on form submit
document.getElementById('createForm').addEventListener('submit', function() {
    showLoader();
});

// Install dependency functionality for list view
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('install-deps-btn')) {
        e.preventDefault();

        const button = e.target;
        const dbType = button.dataset.dbType;
        const dbId = button.dataset.dbId;

        // Disable button and show loading state
        button.disabled = true;
        button.innerHTML = '<span class="material-icons webops-icon--x-small webops-align-middle">sync</span> Installing...';
        button.classList.add('webops-btn-loading');

        // Make AJAX request to install dependencies
        fetch(webopsPage().urlInstallDeps, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: `db_type=${encodeURIComponent(dbType)}&dependencies=${encodeURIComponent(dbType)}`
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Check if all dependencies were installed successfully
                const allSuccess = Object.values(data.results).every(result => result.success);

                if (allSuccess) {
                    // Update the dependency status in the UI
                    const depCell = button.closest('td');
                    depCell.innerHTML = `
                        <span class="webops-badge webops-badge-success" title="All dependencies installed">
                            <span class="material-icons webops-icon--small webops-icon--align-middle">check_circle</span>
                            Ready
                        </span>
                    `;

                    showToast('Dependencies installed successfully!', 'success');
                } else {
                    // Some dependencies failed
                    const failedDeps = Object.entries(data.results)
                        .filter(([_, result]) => !result.success)
                        .map(([dep, result]) => `${dep}: ${result.error}`);

                    showToast(`Some dependencies failed to install: ${failedDeps.join(', ')}`, 'error');

                    // Reset button state
                    button.disabled = false;
                    button.innerHTML = 'Install';
                    button.classList.remove('webops-btn-loading');
                }
            } else {
                showToast(`Error: ${data.error}`, 'error');

                // Reset button state
                button.disabled = false;
                button.innerHTML = 'Install';
                button.classList.remove('webops-btn-loading');
            }
        })
        .catch(error => {
            console.error('Error installing dependencies:', error);
            showToast('Network error while installing dependencies', 'error');

            // Reset button state
            button.disabled = false;
            button.innerHTML = 'Install';
            button.classList.remove('webops-btn-loading');
        });
    }
});

// Helper function to show toast notifications (if available)
function showToast(message, type = 'info') {
    // Check if toast system is available
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
    } else {
        // Fallback to alert
        alert(message);
    }
}
