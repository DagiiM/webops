/* Moved from templates/auth/two_factor_backup_codes.html (ui-skill rule 17: no inline <script>). */
function copyBackupCodes() {
    const codes = webopsPage().codes.split(',').join('\n');
    navigator.clipboard.writeText(codes).then(() => {
        if (window.WebOps && window.WebOps.Toast) {
            window.WebOps.Toast.success('Backup codes copied to clipboard');
        } else {
            alert('Backup codes copied to clipboard');
        }
    });
}

function downloadBackupCodes() {
    const codes = webopsPage().codes.split(',').join('\n');
    const blob = new Blob([
        'WebOps 2FA Backup Codes\n',
        '========================\n\n',
        'Username: ' + webopsPage().username + '\n',
        'Generated: ' + webopsPage().generated + '\n\n',
        'Backup Codes:\n',
        codes
    ], { type: 'text/plain' });

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'webops-2fa-backup-codes.txt';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);

    if (window.WebOps && window.WebOps.Toast) {
        window.WebOps.Toast.success('Backup codes downloaded');
    }
}
