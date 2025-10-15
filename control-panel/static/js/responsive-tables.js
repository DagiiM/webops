/**
 * Responsive tables enhancements for WebOps Control Panel.
 * Adds scroll wrappers and header stickiness for wide tables.
 */

(function () {
  'use strict';

  function enhanceTable(table) {
    if (!table) return;

    // Wrap table in a scroll container if it overflows
    var wrapper = document.createElement('div');
    wrapper.className = 'webops-table-wrapper';
    wrapper.style.overflowX = 'auto';
    wrapper.style.webkitOverflowScrolling = 'touch';

    if (!table.parentElement) return;
    table.parentElement.insertBefore(wrapper, table);
    wrapper.appendChild(table);

    // Sticky header support
    var thead = table.querySelector('thead');
    if (thead) {
      thead.style.position = 'sticky';
      thead.style.top = '0';
      thead.style.zIndex = '2';
      thead.style.background = 'var(--webops-color-bg-primary)';
    }
  }

  function init() {
    var tables = document.querySelectorAll('table');
    tables.forEach(function (t) {
      // Skip if already wrapped
      if (t.parentElement && t.parentElement.classList.contains('webops-table-wrapper')) return;
      enhanceTable(t);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();