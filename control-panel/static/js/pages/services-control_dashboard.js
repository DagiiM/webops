/* Moved from templates/services/control_dashboard.html (ui-skill rule 17: no inline <script>). */
// Auto-refresh service status
let refreshInterval;

function refreshServiceStatus() {
    fetch(webopsPage().urlSystemHealth)
        .then(response => response.json())
        .then(data => {
            // Update without full page reload if needed
            console.log('System health updated:', data);
        })
        .catch(error => console.error('Error refreshing status:', error));
}

// Refresh every 30 seconds
document.addEventListener('DOMContentLoaded', () => {
    refreshInterval = setInterval(refreshServiceStatus, 30000);
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});

// SSL Configuration Modal
const sslModal = document.createElement('div');
sslModal.id = 'ssl-config-modal';
sslModal.className = 'webops-modal';
sslModal.innerHTML = `
    <div class="webops-modal-content webops-s-2e56d29" >
        <div class="webops-modal-header">
            <h3 class="webops-modal-title">SSL Configuration</h3>
            <button type="button" class="webops-modal-close" data-on-click="closeSSLModal()">&times;</button>
        </div>
        <div class="webops-modal-body">
            <div id="ssl-status-info" class="webops-alert webops-alert-info webops-s-c2c0d0a" >
                <div class="webops-alert-content">
                    <span class="material-icons webops-alert-icon">info</span>
                    <div class="webops-alert-text">
                        <div class="webops-alert-title">Loading SSL status...</div>
                        <div class="webops-alert-description">Please wait while we check the SSL configuration.</div>
                    </div>
                </div>
            </div>

            <form id="ssl-config-form" enctype="multipart/form-data">
                <input type="hidden" id="ssl-deployment-id" name="deployment_id">

                <div class="webops-form-group">
                    <label class="webops-label">SSL Status</label>
                    <div class="webops-flex webops-gap-md webops-align-center">
                        <label class="webops-switch">
                            <input type="checkbox" id="ssl-enabled" name="enabled">
                            <span class="webops-switch-slider"></span>
                        </label>
                        <span id="ssl-status-text">Disabled</span>
                    </div>
                </div>

                <div class="webops-form-group">
                    <label class="webops-label" for="ssl-domain">Domain Name</label>
                    <input type="text" id="ssl-domain" name="domain" class="webops-input" placeholder="example.com">
                </div>

                <div class="webops-form-group">
                    <label class="webops-label" for="ssl-certificate-type">Certificate Type</label>
                    <select id="ssl-certificate-type" name="certificate_type" class="webops-select">
                        <option value="self_signed">Self-Signed Certificate</option>
                        <option value="lets_encrypt">Let's Encrypt (Not Available)</option>
                        <option value="custom">Custom Certificate</option>
                    </select>
                </div>

                <div id="custom-certificate-fields" class="webops-s-5790ffb">
                    <div class="webops-form-group">
                        <label class="webops-label" for="ssl-certificate">Certificate File (.pem)</label>
                        <input type="file" id="ssl-certificate" name="certificate" class="webops-input" accept=".pem,.crt,.cert">
                    </div>

                    <div class="webops-form-group">
                        <label class="webops-label" for="ssl-private-key">Private Key File (.pem)</label>
                        <input type="file" id="ssl-private-key" name="private_key" class="webops-input" accept=".pem,.key">
                    </div>
                </div>

                <div class="webops-form-group">
                    <label class="webops-label" for="ssl-encryption-protocol">Encryption Protocol</label>
                    <select id="ssl-encryption-protocol" name="encryption_protocol" class="webops-select">
                        <option value="TLSv1.3">TLS 1.3 (Recommended)</option>
                        <option value="TLSv1.2">TLS 1.2</option>
                    </select>
                </div>

                <div class="webops-form-group">
                    <label class="webops-switch">
                        <input type="checkbox" id="ssl-hsts-enabled" name="hsts_enabled" checked>
                        <span class="webops-switch-slider"></span>
                    </label>
                    <span>Enable HSTS (HTTP Strict Transport Security)</span>
                </div>
            </form>
        </div>
        <div class="webops-modal-footer">
            <button type="button" class="webops-btn webops-btn-secondary" data-on-click="closeSSLModal()">Cancel</button>
            <button type="button" class="webops-btn webops-btn-primary" data-on-click="saveSSLConfig()">Save Configuration</button>
        </div>
    </div>
`;

document.body.appendChild(sslModal);

// SSL Status Functions
function updateSSLStatus() {
    const sslStatusElements = document.querySelectorAll('.ssl-status');

    sslStatusElements.forEach(element => {
        const deploymentId = element.dataset.deploymentId;

        fetch(`/monitoring/ssl/status/${deploymentId}/`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    let statusHtml = '';

                    if (data.enabled && data.is_valid) {
                        statusHtml = `
                            <span class="webops-badge webops-badge-success">
                                <span class="material-icons webops-icon-xs">lock</span>
                                SSL Active
                            </span>
                        `;
                    } else if (data.enabled && !data.is_valid) {
                        statusHtml = `
                            <span class="webops-badge webops-badge-warning">
                                <span class="material-icons webops-icon-xs">warning</span>
                                Invalid Cert
                            </span>
                        `;
                    } else if (data.configured) {
                        statusHtml = `
                            <span class="webops-badge webops-badge-secondary">
                                <span class="material-icons webops-icon-xs">lock_open</span>
                                SSL Disabled
                            </span>
                        `;
                    } else {
                        statusHtml = `
                            <span class="webops-badge webops-badge-secondary">
                                <span class="material-icons webops-icon-xs">lock_open</span>
                                Not Configured
                            </span>
                        `;
                    }

                    element.innerHTML = statusHtml;
                } else {
                    element.innerHTML = `
                        <span class="webops-badge webops-badge-error">
                            <span class="material-icons webops-icon-xs">error</span>
                            Error
                        </span>
                    `;
                }
            })
            .catch(error => {
                console.error('Error fetching SSL status:', error);
                element.innerHTML = `
                    <span class="webops-badge webops-badge-error">
                        <span class="material-icons webops-icon-xs">error</span>
                        Error
                    </span>
                `;
            });
    });
}

// SSL Configuration Modal Functions
function openSSLModal(deploymentId, deploymentName) {
    document.getElementById('ssl-deployment-id').value = deploymentId;
    document.querySelector('.webops-modal-title').textContent = `SSL Configuration - ${deploymentName}`;

    // Fetch current SSL configuration
    fetch(`/monitoring/ssl/status/${deploymentId}/`)
        .then(response => response.json())
        .then(data => {
            if (data.configured) {
                document.getElementById('ssl-enabled').checked = data.enabled;
                document.getElementById('ssl-domain').value = data.domain || '';
                document.getElementById('ssl-certificate-type').value = data.certificate_type || 'self_signed';
                document.getElementById('ssl-encryption-protocol').value = data.encryption_protocol || 'TLSv1.3';
                document.getElementById('ssl-hsts-enabled').checked = data.hsts_enabled || false;

                updateSSLStatusText();
                updateCertificateFields();

                let statusInfo = '';
                if (data.is_valid) {
                    statusInfo = `
                        <div class="webops-alert webops-alert-success">
                            <div class="webops-alert-content">
                                <span class="material-icons webops-alert-icon">check_circle</span>
                                <div class="webops-alert-text">
                                    <div class="webops-alert-title">SSL Certificate Valid</div>
                                    <div class="webops-alert-description">Valid until ${data.valid_until ? new Date(data.valid_until).toLocaleDateString() : 'Unknown'}</div>
                                </div>
                            </div>
                        </div>
                    `;
                } else {
                    statusInfo = `
                        <div class="webops-alert webops-alert-warning">
                            <div class="webops-alert-content">
                                <span class="material-icons webops-alert-icon">warning</span>
                                <div class="webops-alert-text">
                                    <div class="webops-alert-title">Certificate Invalid</div>
                                    <div class="webops-alert-description">${webopsEscape(data.message)}</div>
                                </div>
                            </div>
                        </div>
                    `;
                }
                document.getElementById('ssl-status-info').innerHTML = statusInfo;
            } else {
                document.getElementById('ssl-enabled').checked = false;
                document.getElementById('ssl-domain').value = '';
                document.getElementById('ssl-certificate-type').value = 'self_signed';
                document.getElementById('ssl-encryption-protocol').value = 'TLSv1.3';
                document.getElementById('ssl-hsts-enabled').checked = true;

                updateSSLStatusText();
                updateCertificateFields();

                document.getElementById('ssl-status-info').innerHTML = `
                    <div class="webops-alert webops-alert-info">
                        <div class="webops-alert-content">
                            <span class="material-icons webops-alert-icon">info</span>
                            <div class="webops-alert-text">
                                <div class="webops-alert-title">SSL Not Configured</div>
                                <div class="webops-alert-description">Configure SSL settings for this deployment.</div>
                            </div>
                        </div>
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error fetching SSL configuration:', error);
            document.getElementById('ssl-status-info').innerHTML = `
                <div class="webops-alert webops-alert-error">
                    <div class="webops-alert-content">
                        <span class="material-icons webops-alert-icon">error</span>
                        <div class="webops-alert-text">
                            <div class="webops-alert-title">Error Loading Configuration</div>
                            <div class="webops-alert-description">Failed to load SSL configuration.</div>
                        </div>
                    </div>
                </div>
            `;
        });

    sslModal.style.display = 'flex';
}

function closeSSLModal() {
    sslModal.style.display = 'none';
    document.getElementById('ssl-config-form').reset();
}

function updateSSLStatusText() {
    const enabled = document.getElementById('ssl-enabled').checked;
    document.getElementById('ssl-status-text').textContent = enabled ? 'Enabled' : 'Disabled';
}

function updateCertificateFields() {
    const certType = document.getElementById('ssl-certificate-type').value;
    const customFields = document.getElementById('custom-certificate-fields');

    if (certType === 'custom') {
        customFields.style.display = 'block';
    } else {
        customFields.style.display = 'none';
    }
}

function saveSSLConfig() {
    const formData = new FormData(document.getElementById('ssl-config-form'));
    const deploymentId = document.getElementById('ssl-deployment-id').value;

    // Show loading state
    const saveButton = document.querySelector('.webops-modal-footer .webops-btn-primary');
    saveButton.disabled = true;
    saveButton.textContent = 'Saving...';

    fetch(`/monitoring/ssl/configure/${deploymentId}/`, {
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
            document.getElementById('ssl-status-info').innerHTML = `
                <div class="webops-alert webops-alert-success">
                    <div class="webops-alert-content">
                        <span class="material-icons webops-alert-icon">check_circle</span>
                        <div class="webops-alert-text">
                            <div class="webops-alert-title">Configuration Saved</div>
                            <div class="webops-alert-description">${webopsEscape(data.message)}</div>
                        </div>
                    </div>
                </div>
            `;

            // Update SSL status display
            setTimeout(() => {
                closeSSLModal();
                updateSSLStatus();
            }, 1500);
        } else {
            // Show error message
            document.getElementById('ssl-status-info').innerHTML = `
                <div class="webops-alert webops-alert-error">
                    <div class="webops-alert-content">
                        <span class="material-icons webops-alert-icon">error</span>
                        <div class="webops-alert-text">
                            <div class="webops-alert-title">Configuration Failed</div>
                            <div class="webops-alert-description">${webopsEscape(data.message || 'Unknown error occurred')}</div>
                        </div>
                    </div>
                </div>
            `;
        }
    })
    .catch(error => {
        console.error('Error saving SSL configuration:', error);
        document.getElementById('ssl-status-info').innerHTML = `
            <div class="webops-alert webops-alert-error">
                <div class="webops-alert-content">
                    <span class="material-icons webops-alert-icon">error</span>
                    <div class="webops-alert-text">
                        <div class="webops-alert-title">Network Error</div>
                        <div class="webops-alert-description">Failed to save configuration. Please try again.</div>
                    </div>
                </div>
            </div>
        `;
    })
    .finally(() => {
        saveButton.disabled = false;
        saveButton.textContent = 'Save Configuration';
    });
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // SSL configuration buttons
    document.querySelectorAll('.ssl-config-btn').forEach(button => {
        button.addEventListener('click', (e) => {
            const deploymentId = e.target.closest('button').dataset.deploymentId;
            const deploymentName = e.target.closest('button').dataset.deploymentName;
            openSSLModal(deploymentId, deploymentName);
        });
    });

    // SSL status toggle
    document.getElementById('ssl-enabled').addEventListener('change', updateSSLStatusText);

    // Certificate type change
    document.getElementById('ssl-certificate-type').addEventListener('change', updateCertificateFields);

    // Initial SSL status update
    updateSSLStatus();

    // Refresh SSL status periodically
    setInterval(updateSSLStatus, 60000); // Every minute
});

// Close modal when clicking outside
sslModal.addEventListener('click', (e) => {
    if (e.target === sslModal) {
        closeSSLModal();
    }
});
