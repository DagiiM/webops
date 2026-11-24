/* Moved from templates/automation/execution_detail.html (ui-skill rule 17: no inline <script>). */
document.addEventListener('DOMContentLoaded', function() {
    const autoRefreshBtn = document.getElementById('btn-auto-refresh');
    const downloadBtn = document.getElementById('btn-download-logs');
    let autoRefreshInterval;

    // Initialize progress bar widths from data-progress attributes
    document.querySelectorAll('.webops-progress-bar').forEach(bar => {
        const pct = parseFloat(bar.getAttribute('data-progress'));
        if (!isNaN(pct)) {
            bar.style.width = `${Math.max(0, Math.min(100, pct))}%`;
        }
    });

    // Auto refresh functionality
    if (autoRefreshBtn) {
        autoRefreshBtn.addEventListener('click', function() {
            const isAutoRefresh = this.dataset.autoRefresh === 'true';

            if (isAutoRefresh) {
                // Stop auto refresh
                clearInterval(autoRefreshInterval);
                this.dataset.autoRefresh = 'false';
                this.classList.remove('webops-btn-primary');
                this.classList.add('webops-btn-secondary');
            } else {
                // Start auto refresh
                autoRefreshInterval = setInterval(() => {
                    window.location.reload();
                }, 5000);
                this.dataset.autoRefresh = 'true';
                this.classList.remove('webops-btn-secondary');
                this.classList.add('webops-btn-primary');
            }
        });

        // Start auto refresh if execution is running
        if (autoRefreshBtn.dataset.autoRefresh === 'true') {
            autoRefreshInterval = setInterval(() => {
                window.location.reload();
            }, 5000);
            autoRefreshBtn.classList.remove('webops-btn-secondary');
            autoRefreshBtn.classList.add('webops-btn-primary');
        }
    }

    // Download logs functionality
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function() {
            const logEntries = document.querySelectorAll('.webops-log-entry');
            let logText = '';

            logEntries.forEach(entry => {
                const timestamp = entry.querySelector('.webops-log-entry__timestamp').textContent;
                const level = entry.querySelector('.webops-log-entry__level').textContent;
                const message = entry.querySelector('.webops-log-entry__message').textContent;
                logText += `${timestamp} [${level}] ${message}\n`;
            });

            const blob = new Blob([logText], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `execution-${webopsPage().executionId}-logs.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });
    }
});
