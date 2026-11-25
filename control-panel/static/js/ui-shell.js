/* WebOps shell behaviour: one owner for the sidebar, header menus and appearance preferences.
 * Replaces header.js, sidebar-toggle.js, theme-switcher.js, theme-integration.js,
 * dynamic-theme-loader.js and the duplicated handlers in pages/base.js and main.js. */
(function () {
    'use strict';

    var root = document.documentElement;
    var $ = function (s, r) { return (r || document).querySelector(s); };
    var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
    var store = {
        get: function (k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } },
        set: function (k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* storage blocked: keep going */ } }
    };
    var reduced = function () {
        return (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) ||
            root.classList.contains('webops-no-animations');
    };
    var toast = function (kind, msg) {
        if (window.WebOps && window.WebOps.Toast && window.WebOps.Toast[kind]) { window.WebOps.Toast[kind](msg); }
    };

    /* ───────── Appearance: theme, density, animations ───────── */
    var systemQuery = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;

    function resolveTheme(pref) {
        if (pref === 'system') { return (systemQuery && systemQuery.matches) ? 'light' : 'dark'; }
        return pref;
    }

    function swapWithTransition(change) {
        if (reduced()) { change(); return; }
        if (document.startViewTransition) {           /* crossfade the whole page in one frame */
            document.startViewTransition(change);
            return;
        }
        root.classList.add('ui-theme-fade');          /* otherwise fade colours briefly */
        change();
        window.setTimeout(function () { root.classList.remove('ui-theme-fade'); }, 300);
    }

    function syncPressed(pref) {
        $$('[data-pref]').forEach(function (b) {
            var k = b.getAttribute('data-pref');
            var current = k === 'theme' ? root.getAttribute('data-theme-pref') : root.getAttribute('data-density');
            b.setAttribute('aria-pressed', String(b.getAttribute('data-val') === current));
        });
    }

    function setTheme(pref) {
        if (root.getAttribute('data-theme-pref') === pref && root.getAttribute('data-theme') === resolveTheme(pref)) { store.set('webops-theme', pref); syncPressed(); return; }
        swapWithTransition(function () {
            root.setAttribute('data-theme-pref', pref);
            root.setAttribute('data-theme', resolveTheme(pref));
        });
        store.set('webops-theme', pref);
        syncPressed();
        document.dispatchEvent(new CustomEvent('webops:themechange', { detail: { preference: pref, theme: resolveTheme(pref) } }));
    }

    function setDensity(value) {
        root.setAttribute('data-density', value);
        store.set('webops-density', value);
        syncPressed();
    }

    if (systemQuery) {
        var onSystem = function () {
            if (root.getAttribute('data-theme-pref') === 'system') { swapWithTransition(function () { root.setAttribute('data-theme', resolveTheme('system')); }); }
        };
        if (systemQuery.addEventListener) { systemQuery.addEventListener('change', onSystem); }
    }

    document.addEventListener('click', function (e) {
        var b = e.target.closest('[data-pref]');
        if (!b) { return; }
        if (b.getAttribute('data-pref') === 'theme') { setTheme(b.getAttribute('data-val')); }
        else if (b.getAttribute('data-pref') === 'density') { setDensity(b.getAttribute('data-val')); }
    });

    var anim = $('#animationsToggle');
    if (anim) {
        anim.checked = store.get('animations') !== 'false';
        anim.addEventListener('change', function () {
            store.set('animations', String(anim.checked));
            root.classList.toggle('webops-no-animations', !anim.checked);
            toast('info', 'Animations ' + (anim.checked ? 'on' : 'off'));
        });
    }
    syncPressed();

    /* ───────── Menus: appearance and user ───────── */
    var menus = $$('[data-ui-menu]');

    function setMenu(menu, open, returnFocus) {
        var trigger = $('button[aria-haspopup]', menu);
        menu.classList.toggle('is-open', open);
        if (trigger) { trigger.setAttribute('aria-expanded', String(open)); }
        if (!open && returnFocus && trigger) { trigger.focus(); }
    }
    function closeAll(except) { menus.forEach(function (m) { if (m !== except) { setMenu(m, false); } }); }

    menus.forEach(function (menu) {
        var trigger = $('button[aria-haspopup]', menu);
        var panel = $('.ui-menu__panel', menu);
        if (!trigger || !panel) { return; }
        trigger.addEventListener('click', function (e) {
            e.stopPropagation();
            var open = !menu.classList.contains('is-open');
            closeAll(menu);
            setMenu(menu, open);
            if (open && panel.getAttribute('role') === 'menu') {
                var first = $('[role="menuitem"]', panel); if (first) { first.focus(); }
            }
        });
        panel.addEventListener('keydown', function (e) {
            if (panel.getAttribute('role') !== 'menu') { return; }
            var items = $$('[role="menuitem"]', panel), i = items.indexOf(document.activeElement);
            if (e.key === 'ArrowDown') { e.preventDefault(); items[(i + 1) % items.length].focus(); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
            else if (e.key === 'Home') { e.preventDefault(); items[0].focus(); }
            else if (e.key === 'End') { e.preventDefault(); items[items.length - 1].focus(); }
        });
    });
    document.addEventListener('click', function (e) { if (!e.target.closest('[data-ui-menu]')) { closeAll(); } });

    /* ───────── Sidebar: drawer on phones, collapsible rail on desktop ───────── */
    var sidebar = $('#sidebar');
    var overlay = $('#sidebar-overlay');
    var openBtn = $('#sidebar-toggle');
    var collapseBtn = $('#btn-toggle-sidebar');
    var phone = window.matchMedia ? window.matchMedia('(max-width: 48rem)') : null;

    function setDrawer(open, returnFocus) {
        if (!sidebar) { return; }
        sidebar.classList.toggle('is-open', open);
        if (overlay) { overlay.classList.toggle('is-open', open); }
        document.body.classList.toggle('ui-lock', open);
        if (openBtn) { openBtn.setAttribute('aria-expanded', String(open)); }
        if (open) { var first = $('.webops-nav-item', sidebar); if (first) { first.focus({ preventScroll: true }); } }
        else if (returnFocus && openBtn) { openBtn.focus(); }
    }
    if (openBtn) { openBtn.addEventListener('click', function () { setDrawer(!sidebar.classList.contains('is-open')); }); }
    if (overlay) { overlay.addEventListener('click', function () { setDrawer(false); }); }
    if (sidebar) {
        sidebar.addEventListener('click', function (e) { if (phone && phone.matches && e.target.closest('.webops-nav-item')) { setDrawer(false); } });
    }
    if (phone && phone.addEventListener) {
        phone.addEventListener('change', function () { setDrawer(false); });
    }

    function setCollapsed(collapsed) {
        if (collapsed) { root.setAttribute('data-sidebar', 'collapsed'); } else { root.removeAttribute('data-sidebar'); }
        store.set('sidebar-minimized', String(collapsed));
        if (collapseBtn) {
            var label = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
            collapseBtn.setAttribute('aria-pressed', String(collapsed));
            collapseBtn.setAttribute('aria-label', label);
            collapseBtn.setAttribute('title', label);
            var glyph = $('.material-icons', collapseBtn);          /* the icon set swaps SVGs when the name changes */
            if (glyph) { glyph.textContent = collapsed ? 'left_panel_open' : 'left_panel_close'; }
        }
        /* a collapsed rail has no text, so each item needs its name as a tooltip */
        $$('.webops-nav-item', sidebar || document).forEach(function (a) {
            var t = $('.webops-nav-item__text', a);
            if (collapsed && t) { a.setAttribute('title', t.textContent.trim()); } else { a.removeAttribute('title'); }
        });
    }
    if (collapseBtn) {
        collapseBtn.addEventListener('click', function () { setCollapsed(root.getAttribute('data-sidebar') !== 'collapsed'); });
        setCollapsed(root.getAttribute('data-sidebar') === 'collapsed');
    }

    /* Escape closes whatever is open, in the order a person would expect */
    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') { return; }
        var open = menus.filter(function (m) { return m.classList.contains('is-open'); })[0];
        if (open) { setMenu(open, false, true); return; }
        if (sidebar && sidebar.classList.contains('is-open')) { setDrawer(false, true); }
    });

    /* Keep the current nav item in view when the sidebar scrolls */
    var current = $('.webops-nav-item[aria-current="page"]');
    if (current && current.scrollIntoView) { current.scrollIntoView({ block: 'nearest' }); }

    window.WebOpsShell = { setTheme: setTheme, setDensity: setDensity, setCollapsed: setCollapsed, setDrawer: setDrawer };
})();
