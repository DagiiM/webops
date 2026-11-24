/* WebOps motion: marks the page ready, shows the navigation progress line, and shows the loader
 * only when something takes longer than a moment (a fast page never flashes it). */
(function () {
    'use strict';
    var root = document.documentElement;
    var SHOW_AFTER = 250;          /* ms before the loader overlay appears for async work */
    var NAV_OVERLAY_AFTER = 900;   /* ms of navigation before the overlay joins the progress line */
    var navTimer = null;

    function ready() { root.classList.add('ui-ready'); }
    if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', ready); } else { ready(); }

    function overlay() { return document.getElementById('webopsLoader'); }

    function navStart(label) {
        root.classList.add('ui-navigating');
        window.clearTimeout(navTimer);
        navTimer = window.setTimeout(function () {
            var o = overlay(); if (!o) { return; }
            var t = o.querySelector('.webops-loader-text'); if (t && label) { t.textContent = label; }
            o.classList.add('active'); o.setAttribute('aria-hidden', 'false');
        }, NAV_OVERLAY_AFTER);
    }
    function navEnd() {
        window.clearTimeout(navTimer);
        root.classList.remove('ui-navigating');
        var o = overlay();
        if (o && !window.Loader_busy) { o.classList.remove('active'); o.setAttribute('aria-hidden', 'true'); }
    }

    /* Back/forward cache restores the old DOM with the navigating state still on it */
    window.addEventListener('pageshow', function (e) { if (e.persisted) { navEnd(); ready(); } });
    window.addEventListener('pagehide', function () { window.clearTimeout(navTimer); });

    document.addEventListener('click', function (e) {
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) { return; }
        var a = e.target.closest('a[href]');
        if (!a || a.target || a.hasAttribute('download') || a.hasAttribute('data-no-loader')) { return; }
        var href = a.getAttribute('href');
        if (!href || href.charAt(0) === '#' || /^(mailto:|tel:|javascript:)/i.test(href)) { return; }
        try {
            var dest = new URL(a.href, document.baseURI), cur = window.location;
            if (dest.origin !== cur.origin) { return; }
            if (dest.pathname === cur.pathname && dest.search === cur.search) { return; }
        } catch (err) { return; }
        navStart('Loading');
    });

    document.addEventListener('submit', function (e) {
        var f = e.target;
        if (e.defaultPrevented || !f || (f.hasAttribute && f.hasAttribute('data-no-loader'))) { return; }
        if (f.target && f.target !== '_self') { return; }
        navStart('Working');
    });

    window.webopsMotion = { navStart: navStart, navEnd: navEnd, showAfter: SHOW_AFTER };
})();
