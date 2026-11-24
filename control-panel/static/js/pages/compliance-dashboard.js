/* Moved from templates/compliance/dashboard.html (ui-skill rule 17: no inline <script>). */
// Compliance chart (local SVG renderer, no chart library)
const frameworkStats = JSON.parse(document.getElementById('framework-stats').textContent);

webopsBarChart(document.getElementById('complianceChart'), {
    title: 'Compliance controls overview',
    labels: frameworkStats.map(stat => stat.framework.name),
    series: [
        { name: 'Total controls', values: frameworkStats.map(stat => stat.total_controls) },
        { name: 'Implemented controls', values: frameworkStats.map(stat => stat.implemented_controls) },
        { name: 'Automated controls', values: frameworkStats.map(stat => stat.automated_controls) }
    ]
});

// Trigger Security Scan
function triggerScan() {
    const scanType = prompt('Select scan type:', 'comprehensive');
    if (!scanType) return;

    fetch(webopsPage().urlScan, {
        method: 'POST',
        headers: {
            'X-CSRFToken': webopsCsrf(),
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `scan_type=${scanType}&target=system`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Security scan initiated successfully!');
            window.location.reload();
        } else {
            alert('Error: ' + data.error);
        }
    })
    .catch(error => {
        alert('Error: ' + error);
    });
}

// Generate Report
function generateReport() {
    const frameworkId = prompt('Enter framework ID:');
    if (!frameworkId) return;

    const reportType = prompt('Select report type:', 'assessment');
    if (!reportType) return;

    const periodStart = prompt('Enter period start (YYYY-MM-DD):');
    if (!periodStart) return;

    const periodEnd = prompt('Enter period end (YYYY-MM-DD):');
    if (!periodEnd) return;

    fetch(webopsPage().urlReport, {
        method: 'POST',
        headers: {
            'X-CSRFToken': webopsCsrf(),
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `framework_id=${frameworkId}&report_type=${reportType}&period_start=${periodStart}&period_end=${periodEnd}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Report generated successfully!');
            window.location.href = webopsPage().urlReportDetail.replace('0', data.report_id);
        } else {
            alert('Error: ' + data.error);
        }
    })
    .catch(error => {
        alert('Error: ' + error);
    });
}

// Resolve Alert
function resolveAlert(alertId) {
    if (confirm('Are you sure you want to resolve this alert?')) {
        fetch(webopsPage().urlResolveAlert.replace('0', alertId), {
            method: 'POST',
            headers: {
                'X-CSRFToken': webopsCsrf(),
            }
        })
        .then(response => {
            if (response.ok) {
                window.location.reload();
            } else {
                alert('Error resolving alert');
            }
        })
        .catch(error => {
            alert('Error: ' + error);
        });
    }
}

// Auto-refresh dashboard every 30 seconds
setInterval(function() {
    fetch(webopsPage().urlStats)
    .then(response => response.json())
    .then(data => {
        // Update dashboard cards with new data
        // This is a simplified version - in a real implementation,
        // you'd update specific elements rather than reloading
        if (data.active_alerts !== parseInt(webopsPage().alertCount, 10)) {
            window.location.reload();
        }
    })
    .catch(error => console.error('Error refreshing dashboard:', error));
}, 30000);
