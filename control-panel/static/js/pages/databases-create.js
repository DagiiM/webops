/* Moved from templates/databases/create.html (ui-skill rule 17: no inline <script>). */
document.getElementById('create-form').addEventListener('submit', function() {
    const submitText = document.getElementById('submit-text');
    const submitLoading = document.getElementById('submit-loading');

    submitText.style.display = 'none';
    submitLoading.style.display = 'inline';

    // Disable form inputs
    const inputs = this.querySelectorAll('input, button');
    inputs.forEach(input => input.disabled = true);
});

// Database type descriptions
const dbDescriptions = {
    'postgresql': 'High-performance relational database (recommended for production)',
    'mysql': 'Popular open-source relational database',
    'mongodb': 'Flexible NoSQL document database for unstructured data',
    'sqlite': 'Lightweight file-based database (ideal for development and small applications)',
    'redis': 'In-memory key-value store for caching and messaging',
    'pinecone': 'Vector database for AI/ML applications'
};

// Enhanced dependency status management
class DependencyStatusManager {
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
        const card = document.getElementById('dependency-status-card');
        const overview = document.getElementById('dependency-overview');
        const statusText = document.getElementById('dependency-status-text');
        const summary = document.getElementById('dependency-summary');
        const icon = document.getElementById('dependency-icon');
        const details = document.getElementById('dependency-details');
        const list = document.getElementById('dependency-list');
        const actions = document.getElementById('dependency-actions');

        if (data.status === 'error') {
            this.showErrorState(data.message);
            return;
        }

        // Update overview
        if (!data.success || data.status === 'error') {
            this.showErrorState(data.message || 'Unknown error occurred');
            return;
        }

        const allInstalled = data.all_installed || (data.dependencies && data.dependencies.every(dep => dep.installed));
        const hasMissing = !allInstalled;

        if (allInstalled) {
            icon.textContent = 'check_circle';
            icon.className = 'material-icons';
            icon.style.color = 'var(--webops-color-success)';
            statusText.textContent = 'All Dependencies Installed';
            statusText.className = 'webops-badge webops-badge-success';
            summary.textContent = 'All required dependencies are ready for use';
            actions.innerHTML = '<button class="webops-btn webops-btn-sm webops-btn-success" disabled><span class="material-icons">check</span> Ready</button>';
        } else if (hasMissing) {
            icon.textContent = 'warning';
            icon.className = 'material-icons';
            icon.style.color = 'var(--webops-color-warning)';
            statusText.textContent = 'Missing Dependencies';
            statusText.className = 'webops-badge webops-badge-warning';

            const missingCount = data.dependencies ? data.dependencies.filter(dep => !dep.installed).length :
                               (data.missing_deps ? data.missing_deps.length : 0);
            summary.textContent = `${missingCount} dependencies need to be installed`;
            actions.innerHTML = '<button id="install-all-btn" class="webops-btn webops-btn-sm webops-btn-primary"><span class="material-icons">download</span> Install All</button>';

            // Add install all functionality
            document.getElementById('install-all-btn')?.addEventListener('click', () => {
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
        details.style.display = 'block';
        card.classList.remove('webops-hidden');
    }

    createDependencyItem(dep) {
        const item = document.createElement('div');
        item.className = `dependency-item ${dep.installed ? 'installed' : 'missing'}`;
        item.id = `dep-${dep.name}`;

        item.innerHTML = `
            <div class="dependency-info">
                <span class="material-icons dependency-icon ${dep.installed ? 'installed' : 'missing'}">
                    ${dep.installed ? 'check_circle' : 'warning'}
                </span>
                <div class="dependency-details">
                    <div class="dependency-name">${dep.name}</div>
                    <div class="dependency-description">${dep.description || 'Required dependency'}</div>
                </div>
            </div>
            <div class="dependency-status ${dep.installed ? 'installed' : 'missing'}">
                <span class="material-icons webops-s-7da4e82" >
                    ${dep.installed ? 'check_circle' : 'warning'}
                </span>
                ${dep.installed ? 'Installed' : 'Missing'}
            </div>
            <div class="dependency-actions">
                ${dep.installed ? 
                    '<button class="dependency-install-btn installed" disabled><span class="material-icons">check</span>Installed</button>' :
                    `<button class="dependency-install-btn missing" data-on-click="dependencyManager.installDependency('${dep.name}', '${this.currentDbType}')">
                        <span class="material-icons">download</span>Install
                    </button>`
                }
            </div>
        `;

        return item;
    }

    async installDependency(dependency, dbType) {
        const button = document.querySelector(`#dep-${dependency} .dependency-install-btn`);
        const status = document.querySelector(`#dep-${dependency} .dependency-status`);
        const item = document.getElementById(`dep-${dependency}`);

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
        const installAllBtn = document.getElementById('install-all-btn');
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
        const card = document.getElementById('dependency-status-card');
        const overview = document.getElementById('dependency-overview');
        const icon = document.getElementById('dependency-icon');
        const statusText = document.getElementById('dependency-status-text');
        const summary = document.getElementById('dependency-summary');

        icon.textContent = 'error';
        icon.className = 'material-icons';
        icon.classList.add('webops-text-error');
        statusText.textContent = 'Error';
        statusText.className = 'webops-badge webops-badge-error';
        summary.textContent = message;

        card.style.display = 'block';
    }

}

// Initialize dependency manager
const dependencyManager = new DependencyStatusManager();

// Dynamic form configuration based on selected database type
document.getElementById('db_type').addEventListener('change', async function(e) {
    const dbType = e.target.value;
    const selectedOption = e.target.options[e.target.selectedIndex];

    // Update description
    document.getElementById('db-description').textContent = dbDescriptions[dbType] || '';

    // Update dependency manager
    dependencyManager.currentDbType = dbType;

    // Check dependencies for databases that require them
    if (['postgresql', 'mysql', 'mongodb', 'redis'].includes(dbType)) {
        const data = await dependencyManager.checkDependencies(dbType);
        dependencyManager.updateDependencyCard(data);
    } else {
        // Hide dependency card for databases that don't require dependencies
        document.getElementById('dependency-status-card').classList.add('webops-hidden');
    }

    // Hide addon selection initially
    document.getElementById('addon-selection').classList.add('webops-hidden');

    // Hide all config sections
    document.querySelectorAll('.db-config').forEach(el => el.classList.add('webops-hidden'));

    // Show relevant config sections
    if (dbType === 'postgresql' || dbType === 'mysql') {
        document.querySelector('.db-config-relational').classList.remove('webops-hidden');
        const port = selectedOption.dataset.port;
        if (port) {
            document.getElementById('port').value = port;
        }
    } else if (dbType === 'mongodb') {
        document.querySelector('.db-config-relational').classList.remove('webops-hidden');
        document.querySelector('.db-config-mongodb').classList.remove('webops-hidden');
        const port = selectedOption.dataset.port;
        if (port) {
            document.getElementById('port').value = port;
        }
    } else if (dbType === 'sqlite') {
        document.querySelector('.db-config-sqlite').classList.remove('webops-hidden');
    } else if (dbType === 'pinecone') {
        document.querySelector('.db-config-cloud').classList.remove('webops-hidden');
    } else if (dbType === 'redis') {
        document.querySelector('.db-config-redis').classList.remove('webops-hidden');
        const port = selectedOption.dataset.port;
        if (port) {
            document.getElementById('port_redis').value = port;
        }
    }
});

// Auto-generate username suggestion from database name
document.getElementById('name').addEventListener('input', function(e) {
    const usernameInput = document.getElementById('username');
    if (usernameInput && !usernameInput.value) {
        const suggestion = e.target.value.replace(/_db$/, '_user');
        usernameInput.value = suggestion;
    }
});

// Real-time validation feedback
document.querySelectorAll('.webops-input[pattern]').forEach(input => {
    input.addEventListener('blur', function() {
        if (this.value && !this.validity.valid) {
            this.classList.add('webops-border-error');
            this.classList.remove('webops-border-success');
        } else {
            this.classList.remove('webops-border-error');
            this.classList.remove('webops-border-success');
        }
    });

    input.addEventListener('input', function() {
        if (this.validity.valid) {
            this.classList.add('webops-border-success');
            this.classList.remove('webops-border-error');
        }
    });
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Trigger change event to show initial configuration
    const dbTypeSelect = document.getElementById('db_type');
    if (dbTypeSelect.value) {
        dbTypeSelect.dispatchEvent(new Event('change'));
    }
});
