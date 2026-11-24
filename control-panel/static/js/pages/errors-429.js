/* Moved from templates/errors/429.html (ui-skill rule 17: no inline <script>). */
// Rate limit data from server
const retryAfter = parseInt(webopsPage().retryAfter, 10) || 60;
const resetTimestamp = (parseInt(webopsPage().reset, 10) || 0) * 1000; // Convert to milliseconds
const initialRetryAfter = retryAfter;

// DOM elements
const countdownEl = document.getElementById('countdown');
const countdownShortEl = document.getElementById('countdown-short');
const progressBarEl = document.getElementById('progress-bar');
const resetTimeEl = document.getElementById('reset-timestamp');

// Format time display
function formatTime(seconds) {
    if (seconds <= 0) return '0s';

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

// Format timestamp
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
}

// Update countdown display
function updateCountdown() {
    const now = Date.now();
    const remaining = Math.max(0, Math.ceil((resetTimestamp - now) / 1000));

    // Update countdown displays
    countdownEl.textContent = formatTime(remaining);
    countdownShortEl.textContent = formatTime(remaining);

    // Update progress bar
    const progress = ((initialRetryAfter - remaining) / initialRetryAfter) * 100;
    progressBarEl.style.width = `${progress}%`;

    // Auto-reload when countdown reaches 0
    if (remaining <= 0) {
        countdownEl.textContent = 'Ready!';
        countdownShortEl.textContent = 'Ready!';
        progressBarEl.style.width = '100%';

        // Show success message
        setTimeout(() => {
            location.reload();
        }, 1000);

        return;
    }

    // Continue countdown
    requestAnimationFrame(() => setTimeout(updateCountdown, 1000));
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Set reset timestamp display
    if (resetTimestamp > 0) {
        resetTimeEl.textContent = formatTimestamp(resetTimestamp);
    } else {
        document.getElementById('reset-time').style.display = 'none';
    }

    // Start countdown
    updateCountdown();
});

// Handle page visibility (pause/resume countdown)
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        // Recalculate when page becomes visible
        updateCountdown();
    }
});
