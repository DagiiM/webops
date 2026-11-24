/* Moved from templates/services/background_management.html (ui-skill rule 17: no inline <script>). */
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

function restartWorkers() {
    if (!confirm('Are you sure you want to restart all Celery workers? This may temporarily interrupt background task processing.')) {
        return;
    }

    const btn = document.getElementById('restartBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="material-icons">hourglass_empty</span> Restarting...';

    fetch(webopsPage().urlRestart, {
        method: 'POST',
        headers: {
            'X-CSRFToken': webopsCsrf(),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Workers restarted successfully!');
            refreshStatus();
        } else {
            alert('Failed to restart workers: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to restart workers');
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerHTML = '<span class="material-icons">restart_alt</span> Restart Workers';
    });
}

// Auto-refresh every 30 seconds
let refreshInterval;

document.addEventListener('DOMContentLoaded', () => {
    refreshInterval = setInterval(() => {
        console.log('Auto-refreshing background processor status...');
        refreshStatus();
    }, 30000);
});

window.addEventListener('beforeunload', () => {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});
