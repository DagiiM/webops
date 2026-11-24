/* Moved from templates/integrations/webhook_list.html (ui-skill rule 17: no inline <script>). */
function showCreateModal() {
    document.getElementById('createModal').style.display = 'block';
}

function hideCreateModal() {
    document.getElementById('createModal').style.display = 'none';
}

function testWebhook(webhookId) {
    // Implementation for testing webhook
    console.log('Test webhook:', webhookId);
}

function editWebhook(webhookId) {
    // Implementation for editing webhook
    console.log('Edit webhook:', webhookId);
}

function deleteWebhook(webhookId) {
    if (confirm('Are you sure you want to delete this webhook?')) {
        // Implementation for deleting webhook
        console.log('Delete webhook:', webhookId);
    }
}
