/* Moved from templates/deployments/monitoring.html (ui-skill rule 17: no inline <script>). */
const DEPLOYMENT_ID = parseInt(webopsPage().deploymentId, 10);
const CSRF_TOKEN = webopsCsrf();

// Run health check
document.getElementById('runHealthCheckBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('runHealthCheckBtn');
    const btnText = document.getElementById('runHealthCheckText');
    const btnLoading = document.getElementById('runHealthCheckLoading');

    btnText.style.display = 'none';
    btnLoading.style.display = 'inline-block';
    btn.disabled = true;

    try {
        const response = await fetch(`/deployments/${DEPLOYMENT_ID}/health-check/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': CSRF_TOKEN
            }
        });

        const data = await response.json();

        if (data.success) {
            // Reload page to show new results
            window.location.reload();
        } else {
            alert('Health check failed: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Health check error:', error);
        alert('Failed to run health check: ' + error.message);
    } finally {
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        btn.disabled = false;
    }
});

// Chart data comes from the page-config element (see data-health-* attributes)
const healthData = webopsPage().totalChecks > 0 ? {
    labels: JSON.parse(webopsPage().healthLabels),
    healthy: JSON.parse(webopsPage().healthHealthy),
    cpu: JSON.parse(webopsPage().healthCpu),
    memory: JSON.parse(webopsPage().healthMemory),
    responseTime: JSON.parse(webopsPage().healthResponseTime)
} : null;

if (healthData) {
    console.log('Health data loaded:', healthData);
}
