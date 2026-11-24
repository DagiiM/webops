/* Runs in <head>, before first paint: applies theme, density and sidebar state so there is no flash.
 * External file (not inline) so the strict Content-Security-Policy still holds. */
(function () {
    'use strict';
    var d = document.documentElement;
    function read(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }

    var themes = { dark: 1, light: 1, 'high-contrast': 1, system: 1 };
    var pref = read('webops-theme') || read('theme') || 'system';
    if (!themes[pref]) { pref = 'system'; }
    var resolved = pref;
    if (pref === 'system') {
        resolved = (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
    }
    d.setAttribute('data-theme-pref', pref);
    d.setAttribute('data-theme', resolved);

    var density = read('webops-density');
    if (density !== 'compact' && density !== 'default' && density !== 'roomy') {
        density = read('compact') === 'false' ? 'default' : 'compact';  /* honour the old Compact View switch */
    }
    d.setAttribute('data-density', density);

    if (read('sidebar-minimized') === 'true') { d.setAttribute('data-sidebar', 'collapsed'); }
    if (read('animations') === 'false') { d.classList.add('webops-no-animations'); }
    if (window.CSSViewTransitionRule) { d.classList.add('ui-vt'); }  /* cross-document view transitions available */
})();
