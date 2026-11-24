# Changelog

For the complete changelog, see docs/changelog.md

Changes are documented per release using Keep a Changelog style and Semantic Versioning.

## Unreleased

### Changed
- Control panel redesign (see `docs/frontend/design-system.md`): flat, hairline, token-driven look;
  one colour system with dark, light and high-contrast themes; compact density by default with a
  per-person switch; a blue default brand seed.
- New shell: six-section sidebar with a server-chosen active item, collapsible rail, phone drawer,
  appearance and user menus.
- Overview rebuilt as a summary strip, a deployments table (needs attention first), a "Waiting on
  you" list (failed deploys, review requests, expiring tokens) and recent changes. Deployments list
  rebuilt with priority columns.
- Smooth transitions: navigation progress line, page enter, cross-document view transitions, theme
  fade, and a minimal loader that appears only for slow work.
- Branding CSS emits type, spacing, shape, motion and layout tokens only when they were customised.

### Fixed
- `extra_css` and `extra_scripts` blocks defined by four templates were never rendered by `base.html`.
- Django admin stylesheet was misspelled (`webops-admmin.css`) so it never loaded, and imported Google Fonts.
- Malformed settings-gear SVG path in the header logged a console error on every page.
- Theme and sidebar logic was implemented three times and toggled the same classes twice on phones.

### Removed
- `flat-ui.css`, `theme-transitions.css`, `theme-switcher.css`, `themes/*.css`, `pages/base.css`,
  `header.js`, `sidebar-toggle.js`, `theme-switcher.js`, `theme-integration.js`,
  `dynamic-theme-loader.js`, `pages/base.js` (replaced by `ui-*` files and `theme-boot.js`).
