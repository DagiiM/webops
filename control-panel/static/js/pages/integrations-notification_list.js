/* Moved from templates/integrations/notification_list.html (ui-skill rule 17: no inline <script>). */
function showCreateModal() {
    document.getElementById('createModal').style.display = 'block';
}

function hideCreateModal() {
    document.getElementById('createModal').style.display = 'none';
}

function editChannel(channelId) {
    // Implementation for editing channel
    console.log('Edit channel:', channelId);
}

function deleteChannel(channelId) {
    if (confirm('Are you sure you want to delete this notification channel?')) {
        // Implementation for deleting channel
        console.log('Delete channel:', channelId);
    }
}
