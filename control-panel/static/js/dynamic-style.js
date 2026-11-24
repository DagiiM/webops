/* Applies data-driven widths through the CSSOM, which a strict CSP
   (style-src without 'unsafe-inline') allows, unlike style="" attributes.
   Usage: <div data-style-width="{{ value }}"></div>  (value is a percentage) */
(function () {
    'use strict';
    function apply(root) {
        root.querySelectorAll('[data-style-width]').forEach(function (el) {
            var n = parseFloat(el.getAttribute('data-style-width'));
            if (!isFinite(n)) { return; }
            el.style.width = Math.max(0, Math.min(100, n)) + '%';
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { apply(document); });
    } else {
        apply(document);
    }
    window.webopsApplyDynamicStyles = apply;
})();
