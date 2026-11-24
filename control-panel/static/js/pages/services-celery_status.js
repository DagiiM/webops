/* Moved from templates/services/celery_status.html (ui-skill rule 17: no inline <script>). */
function refreshStatus() {
    location.reload();
}

function inspectWorker(workerName) {
    fetch(`${webopsPage().urlInspect}?worker=${workerName}`, {
        headers: {
            'X-CSRFToken': webopsCsrf()
        }
    })
    .then(response => response.json())
    .then(data => {
        let info = `Worker: ${workerName}\n\n`;
        info += `Active Tasks: ${data.active || 0}\n`;
        info += `Scheduled: ${data.scheduled || 0}\n`;
        info += `Reserved: ${data.reserved || 0}\n`;
        info += `\nConfiguration:\n`;
        info += JSON.stringify(data.config, null, 2);

        alert(info);
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to inspect worker');
    });
}

// Auto-refresh every 30 seconds
let refreshInterval;

document.addEventListener('DOMContentLoaded', () => {
    refreshInterval = setInterval(() => {
        console.log('Auto-refreshing Celery status...');
        refreshStatus();
    }, 30000);
});

window.addEventListener('beforeunload', () => {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});
