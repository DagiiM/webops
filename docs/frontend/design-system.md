# Design system

The control panel follows one flat, hairline, token-driven system. It borrows its rules from
[ui-skill](https://github.com/ifinsta/ui-skill) and its console patterns from Hivewire's dashboard.
Everything is plain HTML, CSS and a little JavaScript: no build step, no third-party requests, and it
runs under a strict Content-Security-Policy (no inline styles, scripts or handlers).

## Tokens

| File | Holds |
|---|---|
| `static/css/variables.css` | type scale, space, radius, motion, layers, layout, density, brand seed default |
| `static/css/themes.css` | colour tokens, one block per theme: `dark` (default), `light`, `high-contrast` |

New code reads the `--ui-*` colour tokens (`--ui-bg`, `--ui-surface`, `--ui-line`, `--ui-text`,
`--ui-accent`, `--ui-ok`, `--ui-warn`, `--ui-bad` and their `-tint` pairs). The legacy `--webops-*`
names are aliases of them, so older stylesheets follow the palette until they are migrated.
Components never write a literal colour, radius, shadow or z-index.

### Theme, density and the brand seed

- **Theme** is `data-theme` on `<html>`; the person's choice is `data-theme-pref` (`system`, `light`,
  `dark`, `high-contrast`). `js/theme-boot.js` sets both before first paint, so nothing flashes.
- **Density** is `data-density` (`compact` is the default for an operator's tool, `default`, `roomy`).
  Controls, row padding and gaps come from `--ui-control`, `--ui-row-pad`, `--ui-pad`, `--ui-gap`.
  Touch devices never drop below 44 px targets.
- **Brand seed** comes from Branding settings as `--webops-hue-primary` / `--webops-sat-primary`.
  An untouched brand (hue 0, saturation 0) keeps the default blue; any other hue with 0% saturation
  is a deliberate graphite brand. Accent lightness is chosen per theme so contrast holds for any seed.
  Branding's type, spacing, shape, motion and layout groups are emitted only when an administrator
  has changed them from the defaults.

## Rules

1. One accent means interactive. One primary action per view. Destructive is never the accent.
2. Status is a word on a tint (`webops-badge` + `-success|-warning|-danger|-info`), never colour alone.
3. Hairlines, not heavy lines; flat in-flow surfaces; shadow only on floating layers.
4. One grouped surface per section; several figures share one strip (`ui-strip`).
5. Tables drop columns by their own width (`webops-col-opt`, `-sec`, `-ter`), never clip status.
6. Motion is transform and opacity, under 300 ms. Reduced motion keeps meaning and drops travel.

## Shell and motion

- `templates/base.html` includes `components/aside.html` (six sections: Overview, Apps, Data,
  Operations, Automate, Access) and `components/header.html` (appearance and user menus). The active
  item is chosen by the server (`nav_active`, `apps.core.common.context_processors.navigation`).
- `js/ui-shell.js` is the single owner of the sidebar (drawer on phones, collapsible rail), menus and
  appearance preferences.
- `js/ui-motion.js` and `css/ui-motion.css`: a hairline progress line on navigation, the page steps
  back while leaving, content enters with a short fade, and where the browser supports cross-document
  view transitions the content crossfades while the sidebar and header stay put. The loader (the
  WebOps mark with one stroke tracing it) appears only if work takes longer than a moment
  (`Loader.show()` after 250 ms; navigation after about 0.9 s), so a fast page never flashes it.

## Adding a page

Extend `base.html`, set `header_title` (it becomes the single `<h1>`), use `webops-page-header`
for the in-page heading, and compose from `ui-panel`, `ui-strip`, `webops-table` and `webops-badge`.
Put page rules in `static/css/pages/<name>.css`. No `style=""`, `<style>` or inline `<script>`.
