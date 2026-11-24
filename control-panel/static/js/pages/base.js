/* Moved from templates/base.html (ui-skill rule 17: no inline <script>). */
document.addEventListener('DOMContentLoaded', function() {
    // Sidebar toggle for mobile
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('active');
            sidebarOverlay.classList.toggle('active');
        });

        sidebarOverlay.addEventListener('click', function() {
            sidebar.classList.remove('active');
            sidebarOverlay.classList.remove('active');
        });
    }

    // Theme Management - Handled by theme-switcher.js



    // User Dropdown Menu
    const userMenuTrigger = document.getElementById('userMenuTrigger');
    const userDropdown = document.getElementById('userDropdown');
    const userSettingsButton = document.getElementById('userSettingsButton');

    function toggleUserDropdown() {
        const isActive = userDropdown.classList.contains('active');
        if (isActive) {
            userDropdown.classList.remove('active');
            userMenuTrigger.classList.remove('active');
        } else {
            userDropdown.classList.add('active');
            userMenuTrigger.classList.add('active');
        }
    }

    function closeUserDropdown() {
        userDropdown.classList.remove('active');
        userMenuTrigger.classList.remove('active');
    }

    if (userMenuTrigger) {
        userMenuTrigger.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleUserDropdown();
        });
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!userDropdown.contains(e.target) && !userMenuTrigger.contains(e.target)) {
            closeUserDropdown();
        }
    });

    // User settings button in dropdown opens settings modal
    if (userSettingsButton) {
        userSettingsButton.addEventListener('click', function(e) {
            e.preventDefault();
            closeUserDropdown();

            // Show the settings modal
            const settingsModal = document.getElementById('settingsModal');
            if (settingsModal) {
                settingsModal.classList.add('active');
                document.body.style.overflow = 'hidden'; // Prevent background scrolling
            }
        });
    }

    // Close settings modal functionality
    const settingsModal = document.getElementById('settingsModal');
    const closeSettingsBtn = document.getElementById('closeSettings');

    if (closeSettingsBtn && settingsModal) {
        closeSettingsBtn.addEventListener('click', function() {
            settingsModal.classList.remove('active');
            document.body.style.overflow = ''; // Restore scrolling
        });

        // Close modal when clicking on the overlay
        settingsModal.addEventListener('click', function(e) {
            if (e.target === settingsModal) {
                settingsModal.classList.remove('active');
                document.body.style.overflow = ''; // Restore scrolling
            }
        });
    }

    // Close dropdown when ESC key is pressed
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeUserDropdown();
        }
    });

    // Animations Toggle
    const animationsToggle = document.getElementById('animationsToggle');
    const savedAnimations = localStorage.getItem('animations') !== 'false';
    if (animationsToggle) {
        animationsToggle.checked = savedAnimations;
        document.documentElement.classList.toggle('webops-no-animations', !savedAnimations);

        animationsToggle.addEventListener('change', function() {
            const enabled = this.checked;
            localStorage.setItem('animations', enabled);
            document.documentElement.classList.toggle('webops-no-animations', !enabled);
            if (window.WebOps && window.WebOps.Toast) {
                window.WebOps.Toast.success('Animations ' + (enabled ? 'enabled' : 'disabled'));
            }
        });
    }

    // Compact View Toggle
    const compactToggle = document.getElementById('compactToggle');
    const savedCompact = localStorage.getItem('compact') === 'true';
    if (compactToggle) {
        compactToggle.checked = savedCompact;
        document.documentElement.classList.toggle('webops-compact-view', savedCompact);

        compactToggle.addEventListener('change', function() {
            const enabled = this.checked;
            localStorage.setItem('compact', enabled);
            document.documentElement.classList.toggle('webops-compact-view', enabled);
            if (window.WebOps && window.WebOps.Toast) {
                window.WebOps.Toast.success('Compact view ' + (enabled ? 'enabled' : 'disabled'));
            }
        });
    }
});
