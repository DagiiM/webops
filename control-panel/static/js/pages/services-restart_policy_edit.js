/* Moved from templates/services/restart_policy_edit.html (ui-skill rule 17: no inline <script>). */
function updatePolicyDescription() {
    const policyType = document.getElementById('policy_type').value;
    const description = document.getElementById('policy_description');
    const backoffSection = document.getElementById('backoff_section');

    const descriptions = {
        'always': 'Service will always be restarted regardless of failure type or count',
        'on_failure': 'Service will be restarted only when it fails (default behavior)',
        'never': 'Service will never be automatically restarted - manual intervention required',
        'backoff': 'Service will be restarted with exponentially increasing delays between attempts'
    };

    description.textContent = descriptions[policyType] || 'Select how the service should be restarted on failure';

    // Show/hide backoff section
    if (policyType === 'backoff') {
        backoffSection.style.display = 'block';
    } else {
        backoffSection.style.display = 'none';
    }
}

function toggleHealthCheckRetries() {
    const requireCheck = document.getElementById('require_health_check').checked;
    const retriesGroup = document.getElementById('health_check_retries_group');

    if (requireCheck) {
        retriesGroup.style.display = 'block';
    } else {
        retriesGroup.style.display = 'none';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    updatePolicyDescription();
    toggleHealthCheckRetries();
});
