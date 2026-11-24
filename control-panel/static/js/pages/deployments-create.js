/* Moved from templates/deployments/create.html (ui-skill rule 17: no inline <script>). */
// Repository search
const searchInput = document.getElementById('repoSearch');
if (searchInput) {
    searchInput.addEventListener('input', function(e) {
        const searchTerm = e.target.value.toLowerCase();
        const repoCards = document.querySelectorAll('.repo-card');
        let visibleCount = 0;

        repoCards.forEach(card => {
            const name = card.dataset.repoName;
            const desc = card.dataset.repoDesc;

            if (name.includes(searchTerm) || desc.includes(searchTerm)) {
                card.style.display = '';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });

        // Show/hide no results message
        const noResults = document.getElementById('noResults');
        const repoGrid = document.getElementById('repoGrid');
        if (visibleCount === 0) {
            repoGrid.style.display = 'none';
            noResults.style.display = 'block';
        } else {
            repoGrid.style.display = 'grid';
            noResults.style.display = 'none';
        }
    });
}

// Select repository
function selectRepository(repoUrl, fullName, defaultBranch, repoName) {
    // Auto-fill form fields
    document.getElementById('repo_url').value = repoUrl;
    document.getElementById('branch').value = defaultBranch || 'main';

    // Auto-generate app name from repo name and show sanitized preview
    const rawName = repoName || '';
    const sanitized = sanitizeNameClient(rawName);
    document.getElementById('name').value = sanitized;
    showSanitizedPreview(rawName);

    // Scroll to form
    const form = document.getElementById('deploymentForm');
    if (form) {
        form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Highlight form briefly - fix null reference
    const cards = document.querySelectorAll('.webops-card');
    const lastCard = cards[cards.length - 1];
    if (lastCard) {
        lastCard.style.boxShadow = '0 0 0 3px var(--webops-color-primary-alpha-30)';
        setTimeout(() => {
            lastCard.style.boxShadow = '';
        }, 2000);
    }

    // Fetch branches
    fetchBranches(fullName);
}

// Basic client-side sanitization that mirrors server rules
function sanitizeNameClient(name) {
    if (!name) return '';
    let s = name.trim().toLowerCase();
    s = s.replace(/[^a-z0-9-_]/g, '-');
    s = s.replace(/-+/g, '-');
    s = s.replace(/(^-+|-+$)/g, '');
    if (!s) return '';
    if (!/^[a-z0-9]/.test(s)) s = 'app-' + s;
    if (!/[a-z0-9]$/.test(s)) s = s + '-app';
    // Enforce max length 100
    if (s.length > 100) s = s.slice(0, 100);
    return s;
}

function showSanitizedPreview(raw) {
    const preview = document.getElementById('namePreview');
    const code = document.getElementById('nameSanitized');
    const sanitized = sanitizeNameClient(raw || document.getElementById('name').value);
    if (!sanitized) {
        preview.style.display = 'none';
        code.textContent = '';
        return;
    }
    code.textContent = sanitized;
    preview.style.display = 'block';
}

// Live preview as user types
const nameInput = document.getElementById('name');
if (nameInput) {
    nameInput.addEventListener('input', function() {
        showSanitizedPreview(this.value);
    });
}

// Understand whatever form of GitHub address was pasted (mirrors the server's parser).
function parseGithubRepo(raw) {
    let t = (raw || '').trim();
    if (!t || /\s/.test(t)) return null;
    let m = t.match(/^git@github\.com:([^\/]+)\/([^\/]+?)(?:\.git)?\/?$/i);
    if (m) return { owner: m[1], repo: m[2], branch: null, ssh: true };
    t = t.replace(/[?#].*$/, '').replace(/^https?:\/\//i, '').replace(/^www\./i, '');
    if (/^github\.com\//i.test(t)) t = t.slice('github.com/'.length);
    else if ((t.split('/')[0] || '').includes('.')) return null;
    const parts = t.replace(/^\/+|\/+$/g, '').split('/').filter(Boolean);
    if (parts.length < 2) return null;
    const owner = parts[0], repo = parts[1].replace(/\.git$/i, '');
    if (!/^[A-Za-z0-9][A-Za-z0-9-]{0,38}$/.test(owner) || !/^[\w.-]{1,100}$/.test(repo)) return null;
    const rest = parts.slice(2);
    let branch = null;
    if (rest.length) {
        if (!['tree', 'blob', 'commits', 'commit', 'releases', 'issues', 'pull', 'pulls', 'actions', 'wiki', 'tags'].includes(rest[0].toLowerCase())) return null;
        if (rest[0].toLowerCase() === 'tree' && rest.length > 1) branch = rest.slice(1).join('/');
    }
    return { owner: owner, repo: repo, branch: branch, ssh: false };
}

// Fetch branches when repo URL changes
let currentRepo = null;

const repoUrlInput = document.getElementById('repo_url');
if (repoUrlInput) repoUrlInput.addEventListener('blur', function() {
    const parsed = parseGithubRepo(this.value);
    if (!parsed) return;
    if (!parsed.ssh) this.value = 'https://github.com/' + parsed.owner + '/' + parsed.repo;
    const branchInput = document.getElementById('branch');
    if (parsed.branch && branchInput && (!branchInput.value || branchInput.value === 'main')) branchInput.value = parsed.branch;
    const nameInput = document.getElementById('name');
    if (nameInput && !nameInput.value.trim()) {   // a pasted URL used to leave the name empty
        nameInput.value = sanitizeNameClient(parsed.repo);
        showSanitizedPreview(parsed.repo);
    }
    const fullName = parsed.owner + '/' + parsed.repo;
    if (webopsPage().githubConnected === 'true' && fullName !== currentRepo) {
        currentRepo = fullName;
        fetchBranches(fullName);
    }
});

function fetchBranches(fullName) {
    const branchLoader = document.getElementById('branchLoader');
    const branchSelector = document.getElementById('branchSelector');
    const branchSelect = document.getElementById('branchSelect');

    branchLoader.style.display = 'block';
    branchSelector.style.display = 'none';

    fetch(`${webopsPage().urlBranches}?repo=${encodeURIComponent(fullName)}`)
        .then(response => response.json())
        .then(data => {
            branchLoader.style.display = 'none';

            if (data.success && data.branches.length > 0) {
                branchSelect.innerHTML = '<option value="">Select a branch...</option>';
                data.branches.forEach(branch => {
                    const option = document.createElement('option');
                    option.value = branch;
                    option.textContent = branch;
                    branchSelect.appendChild(option);
                });

                // Set current branch value as selected
                const currentBranch = document.getElementById('branch').value;
                if (currentBranch && data.branches.includes(currentBranch)) {
                    branchSelect.value = currentBranch;
                }

                branchSelector.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Failed to fetch branches:', error);
            branchLoader.style.display = 'none';
        });
}

// Update branch input when selection changes
document.getElementById('branchSelect').addEventListener('change', function() {
    if (this.value) {
        document.getElementById('branch').value = this.value;
    }
});

// On submit, show loader
document.getElementById('deploymentForm').addEventListener('submit', function() {
    showLoader();
});

// Docker options toggle (only if Docker addon is enabled)
const useDockerCheckbox = document.getElementById('use_docker');
if (useDockerCheckbox) {
    useDockerCheckbox.addEventListener('change', function() {
        const dockerOptions = document.getElementById('dockerOptions');
        if (dockerOptions) {
            if (this.checked) {
                dockerOptions.style.display = 'block';
            } else {
                dockerOptions.style.display = 'none';
            }
        }
    });
}

// Service Management Functions
function refreshCoreServices() {
    const refreshBtn = document.getElementById('refreshServicesBtn');
    const refreshIcon = refreshBtn.querySelector('i');

    // Show loading state
    refreshIcon.className = 'fas fa-spinner fa-spin';
    refreshBtn.disabled = true;

    fetch(webopsPage().urlCoreStatus)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateServiceStatusDisplay(data.services);
                showNotification('Services status refreshed', 'success');
            } else {
                showNotification('Failed to refresh services status', 'error');
            }
        })
        .catch(error => {
            console.error('Error refreshing services:', error);
            showNotification('Error refreshing services status', 'error');
        })
        .finally(() => {
            refreshIcon.className = 'fas fa-sync-alt';
            refreshBtn.disabled = false;
        });
}

function restartService(serviceName) {
    const restartBtn = document.getElementById(`restart-${serviceName}`);
    if (!restartBtn) return;

    const originalText = restartBtn.innerHTML;
    restartBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Restarting...';
    restartBtn.disabled = true;

    fetch(webopsPage().urlRestartService.replace('SERVICE_NAME', serviceName))
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(`${serviceName} restarted successfully`, 'success');
                // Refresh the service status after restart
                setTimeout(() => refreshCoreServices(), 2000);
            } else {
                showNotification(`Failed to restart ${serviceName}: ${data.message}`, 'error');
            }
        })
        .catch(error => {
            console.error(`Error restarting ${serviceName}:`, error);
            showNotification(`Error restarting ${serviceName}`, 'error');
        })
        .finally(() => {
            restartBtn.innerHTML = originalText;
            restartBtn.disabled = false;
        });
}

function restartAllFailedServices() {
    const failedServices = document.querySelectorAll('.service-item .text-danger');
    const serviceNames = Array.from(failedServices).map(el => {
        const serviceItem = el.closest('.service-item');
        return serviceItem ? serviceItem.dataset.service : null;
    }).filter(name => name);

    if (serviceNames.length === 0) {
        showNotification('No failed services to restart', 'info');
        return;
    }

    const restartBtn = document.getElementById('restartAllFailedBtn');
    const originalText = restartBtn.innerHTML;
    restartBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Restarting All...';
    restartBtn.disabled = true;

    let restartPromises = serviceNames.map(serviceName => 
        fetch(webopsPage().urlRestartService.replace('SERVICE_NAME', serviceName))
            .then(response => response.json())
            .then(data => ({ service: serviceName, success: data.success, message: data.message }))
            .catch(error => ({ service: serviceName, success: false, message: error.message }))
    );

    Promise.all(restartPromises)
        .then(results => {
            const successful = results.filter(r => r.success).length;
            const failed = results.filter(r => !r.success).length;

            if (successful > 0) {
                showNotification(`Successfully restarted ${successful} service(s)`, 'success');
            }
            if (failed > 0) {
                showNotification(`Failed to restart ${failed} service(s)`, 'error');
            }

            // Refresh status after all restarts
            setTimeout(() => refreshCoreServices(), 2000);
        })
        .finally(() => {
            restartBtn.innerHTML = originalText;
            restartBtn.disabled = false;
        });
}

function updateServiceStatusDisplay(services) {
    services.forEach(service => {
        const serviceItem = document.querySelector(`[data-service="${service.name}"]`);
        if (!serviceItem) return;

        const statusIcon = serviceItem.querySelector('.service-status i');
        const statusText = serviceItem.querySelector('.service-status');
        const restartBtn = serviceItem.querySelector('.restart-btn');

        if (service.active) {
            statusIcon.className = 'fas fa-check-circle text-success';
            statusText.innerHTML = '<i class="fas fa-check-circle text-success"></i> Running';
            if (restartBtn) restartBtn.style.display = 'none';
        } else {
            statusIcon.className = 'fas fa-times-circle text-danger';
            statusText.innerHTML = '<i class="fas fa-times-circle text-danger"></i> Stopped';
            if (restartBtn) restartBtn.style.display = 'inline-block';
        }
    });

    // Update overall status
    const allOk = services.every(service => service.active);
    const warningAlert = document.getElementById('serviceWarning');
    const submitBtn = document.querySelector('#deploymentForm button[type="submit"]');

    if (allOk) {
        warningAlert.style.display = 'none';
        if (submitBtn) {
            submitBtn.removeAttribute('disabled');
            submitBtn.removeAttribute('aria-disabled');
        }
    } else {
        warningAlert.style.display = 'block';
        if (submitBtn) {
            submitBtn.setAttribute('disabled', 'disabled');
            submitBtn.setAttribute('aria-disabled', 'true');
        }
    }
}

function showNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'} alert-dismissible fade show`;
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '9999';
    notification.style.minWidth = '300px';
    notification.innerHTML = `
        ${webopsEscape(message)}
        <button type="button" class="close" data-dismiss="alert" aria-label="Close">
            <span aria-hidden="true">&times;</span>
        </button>
    `;

    document.body.appendChild(notification);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 5000);

    // Manual dismiss
    notification.querySelector('.close').addEventListener('click', function() {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    });
}

// Add event listeners for service management buttons
document.addEventListener('DOMContentLoaded', function() {
    const refreshBtn = document.getElementById('refreshServicesBtn');
    const restartAllBtn = document.getElementById('restartAllFailedBtn');

    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshCoreServices);
    }

    if (restartAllBtn) {
        restartAllBtn.addEventListener('click', restartAllFailedServices);
    }

    // Add click listeners to individual restart buttons
    document.querySelectorAll('.restart-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const serviceName = this.dataset.service;
            if (serviceName) {
                restartService(serviceName);
            }
        });
    });
});
