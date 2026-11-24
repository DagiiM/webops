/* Moved from templates/deployments/llm_detail.html (ui-skill rule 17: no inline <script>). */
const deploymentId = parseInt(webopsPage().deploymentId, 10);
const csrfToken = webopsCsrf();

async function testModel() {
    const btn = document.getElementById('test-btn');
    const output = document.getElementById('test-output');
    const result = document.getElementById('test-result');
    const prompt = document.getElementById('test-prompt').value;
    const maxTokens = parseInt(document.getElementById('max-tokens').value);
    const temperature = parseFloat(document.getElementById('temperature').value);

    btn.disabled = true;
    btn.innerHTML = '<span class="material-icons">hourglass_empty</span> Generating...';
    output.textContent = 'Waiting for response...';
    result.style.display = 'block';

    try {
        const response = await fetch(webopsPage().urlTest, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({
                model: webopsPage().modelName,
                prompt: prompt,
                max_tokens: maxTokens,
                temperature: temperature
            })
        });

        const data = await response.json();

        if (data.choices && data.choices.length > 0) {
            output.textContent = data.choices[0].text;
        } else {
            output.textContent = data.error || 'No response generated';
        }
    } catch (error) {
        output.textContent = 'Error: ' + error.message;
        console.error(error);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="material-icons">send</span> Generate';
    }
}

// Auto-scroll logs to bottom
window.addEventListener('DOMContentLoaded', () => {
    const logsContainer = document.getElementById('deployment-logs');
    if (logsContainer) {
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }
    initLiveLogs();
});

function initLiveLogs() {
    const logsEl = document.getElementById('deployment-logs');
    const autoScrollEl = document.getElementById('auto-scroll-toggle');
    const pauseBtn = document.getElementById('pause-resume-btn');
    const clearBtn = document.getElementById('clear-logs-btn');
    if (!logsEl) return;

    const MAX_LINES = 1000;
    const wsProto = (location.protocol === 'https:') ? 'wss' : 'ws';
    // Force use of port 8009 where Daphne is running
    const wsHost = location.hostname + ':8009';

    // Get WebSocket token before connecting
    async function getWebSocketToken() {
        try {
            const response = await fetch('/api/ws/token/');
            if (!response.ok) {
                throw new Error('Failed to get WebSocket token');
            }
            const data = await response.json();
            return data.token;
        } catch (error) {
            console.error('Error getting WebSocket token:', error);
            appendLine('[ERROR] Failed to get WebSocket token: ' + error.message);
            return null;
        }
    }

    let ws;
    let buffer = [];
    let flushing = false;
    let autoScroll = true;
    let paused = false;
    let reconnectDelay = 1000;
    let wsToken = null;

    function normalizeLogs(logs) {
        return logs.map(l => {
            if (typeof l === 'string') return l;
            const level = (l.level || 'info').toUpperCase();
            const ts = l.created_at ? new Date(l.created_at).toLocaleTimeString() : '';
            return `[${ts}] [${level}] ${l.message}`;
        });
    }

    function appendLine(text) {
        const line = document.createElement('div');
        line.textContent = text;
        line.style.padding = '4px 0';
        line.style.color = 'var(--webops-color-text-secondary)';
        logsEl.appendChild(line);
        while (logsEl.childNodes.length > MAX_LINES) {
            logsEl.removeChild(logsEl.firstChild);
        }
    }

    function flush() {
        if (flushing || paused) return;
        flushing = true;
        requestAnimationFrame(() => {
            while (buffer.length) appendLine(buffer.shift());
            if (autoScroll) logsEl.scrollTop = logsEl.scrollHeight;
            flushing = false;
        });
    }

    function enqueue(logs) {
        buffer.push(...normalizeLogs(logs));
        flush();
    }

    async function connect() {
        // Get a fresh token for each connection attempt
        wsToken = await getWebSocketToken();
        if (!wsToken) {
            appendLine('[ERROR] Failed to get authentication token. Retrying in 5 seconds...');
            setTimeout(() => connect(), 5000);
            return;
        }

        // Build WebSocket URL with token as query parameter
        const wsUrlWithToken = `${wsProto}://${wsHost}/ws/deployments/${deploymentId}/?token=${wsToken}`;

        // Create WebSocket connection with token
        ws = new WebSocket(wsUrlWithToken);
        ws.onopen = () => {
            console.log('WebSocket connected successfully');
            appendLine('[INFO] WebSocket connected successfully');
            reconnectDelay = 1000;
        };
        ws.onmessage = (evt) => {
            try {
                const msg = JSON.parse(evt.data);
                if (msg.type === 'deployment_logs' && Array.isArray(msg.logs)) {
                    enqueue(msg.logs);
                }
            } catch (e) {
                console.error('Error parsing WebSocket message:', e);
                appendLine('[ERROR] Error parsing WebSocket message: ' + e.message);
            }
        };
        ws.onclose = (evt) => {
            const reason = evt.reason || 'Unknown reason';
            console.log('WebSocket closed, attempting reconnect. Code:', evt.code, 'Reason:', reason);

            // If authentication failed (code 4001), get a new token
            if (evt.code === 4001) {
                appendLine('[WARN] Authentication expired. Getting new token...');
                wsToken = null;
            } else {
                appendLine(`[WARN] WebSocket closed (code: ${evt.code}, reason: ${reason}). Reconnecting in ${reconnectDelay/1000}s...`);
            }

            setTimeout(() => {
                reconnectDelay = Math.min(reconnectDelay * 2, 30000);
                connect();
            }, reconnectDelay);
        };
        ws.onerror = (err) => {
            console.error('WebSocket error:', err);
            appendLine('[ERROR] WebSocket connection error. Check browser console for details.');
            try { ws.close(); } catch(e) {}
        };
    }

    // Controls
    if (autoScrollEl) autoScrollEl.addEventListener('change', (e) => { autoScroll = e.target.checked; });
    if (pauseBtn) pauseBtn.addEventListener('click', () => {
        paused = !paused;
        pauseBtn.textContent = paused ? 'Resume' : 'Pause';
        if (!paused) flush();
    });
    if (clearBtn) clearBtn.addEventListener('click', () => {
        logsEl.innerHTML = '';
    });

    connect();
}
