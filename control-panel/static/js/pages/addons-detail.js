/* Moved from templates/addons/detail.html (ui-skill rule 17: no inline <script>). */
document.addEventListener('DOMContentLoaded', function() {
    // Set the width of success rate fill bars based on data-width attribute
    const successRateFills = document.querySelectorAll('.webops-addon-detail__success-rate-fill');
    successRateFills.forEach(function(fill) {
        const width = fill.getAttribute('data-width');
        if (width) {
            fill.style.width = width + '%';
        }
    });
});
