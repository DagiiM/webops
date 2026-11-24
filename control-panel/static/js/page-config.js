/* Page configuration without inline scripts (ui-skill rule 17: strict CSP).
   Server values reach scripts through data-* attributes on a hidden element
   (<div id="page-config" hidden data-url-save="...">) rather than template
   tags inside <script> bodies. Attributes are HTML-escaped by Django, which
   also closes the injection risk of writing values into JavaScript strings.
   Loaded synchronously in <head> so page scripts can call it immediately. */
(function () {
    'use strict';
    /** dataset of the page-config element (or another element id); empty object if absent. */
    window.webopsPage = function (id) {
        var el = document.getElementById(id || 'page-config');
        return el ? el.dataset : {};
    };
    /** CSRF token from <meta name="csrf-token">; falls back to the form field or cookie. */
    window.webopsCsrf = function () {
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.content) { return meta.content; }
        var field = document.querySelector('[name=csrfmiddlewaretoken]');
        if (field && field.value) { return field.value; }
        var m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
        return m ? decodeURIComponent(m[1]) : '';
    };
})();
