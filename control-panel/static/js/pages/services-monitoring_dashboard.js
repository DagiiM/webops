/* Moved from templates/services/monitoring_dashboard.html (ui-skill rule 17: no inline <script>). */
let autoRefreshInterval = null;
let autoRefreshEnabled = localStorage.getItem('monitoringAutoRefresh') === 'true';

function refreshMetrics() {
    showLoader('Refreshing metrics');
    location.reload();
}

function toggleAutoRefresh() {
    autoRefreshEnabled = !autoRefreshEnabled;
    localStorage.setItem('monitoringAutoRefresh', autoRefreshEnabled);

    if (autoRefreshEnabled) {
        startAutoRefresh();
        if (window.WebOps && window.WebOps.Toast) {
            WebOps.Toast.success('Auto-refresh enabled');
        }
    } else {
        stopAutoRefresh();
        if (window.WebOps && window.WebOps.Toast) {
            WebOps.Toast.success('Auto-refresh disabled');
        }
    }

    updateRefreshButton();
}

function startAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    autoRefreshInterval = setInterval(refreshMetrics, 30000); // 30 seconds
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

function updateRefreshButton() {
    const toggleBtn = document.getElementById('autoRefreshToggle');
    const textSpan = document.getElementById('autoRefreshText');

    if (toggleBtn && textSpan) {
        if (autoRefreshEnabled) {
            toggleBtn.classList.remove('webops-btn-secondary');
            toggleBtn.classList.add('webops-btn-primary');
            textSpan.textContent = 'Auto-Refresh: ON';
        } else {
            toggleBtn.classList.remove('webops-btn-primary');
            toggleBtn.classList.add('webops-btn-secondary');
            textSpan.textContent = 'Enable Auto-Refresh';
        }
    }
}

// Update button on load
document.addEventListener('DOMContentLoaded', () => {
    updateRefreshButton();

    // Only start auto-refresh if enabled
    if (autoRefreshEnabled) {
        startAutoRefresh();
    }
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    stopAutoRefresh();
});
