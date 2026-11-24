/* Moved from templates/integrations/dashboard.html (ui-skill rule 17: no inline <script>). */
function testGitHub() {
    fetch(webopsPage().urlGithub, {
        method: 'POST',
        headers: {
            'X-CSRFToken': webopsCsrf()
        }
    })
    .then(r => r.json())
    .then(data => {
        alert(data.valid ? '✓ ' + data.message : '✗ ' + data.message);
    });
}

function testHF() {
    fetch(webopsPage().urlHuggingface, {
        method: 'POST',
        headers: {
            'X-CSRFToken': webopsCsrf()
        }
    })
    .then(r => r.json())
    .then(data => {
        alert(data.valid ? '✓ ' + data.message : '✗ ' + data.message);
    });
}

function testGoogle() {
    fetch(webopsPage().urlGoogle, {
        method: 'POST',
        headers: {
            'X-CSRFToken': webopsCsrf()
        }
    })
    .then(r => r.json())
    .then(data => {
        alert(data.valid ? '✓ ' + data.message : '✗ ' + data.message);
    });
}
