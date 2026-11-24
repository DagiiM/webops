# UI Skill alignment

Review of the control panel against [`ifinsta/ui-skill`](https://github.com/ifinsta/ui-skill)
(`skills/ui/SKILL.md`). Re-run the audit with:

```bash
cd control-panel
S=<path-to-ui-skill>/skills/ui/scripts
python3 $S/gradient_gate.py --root .          # ignore staticfiles/ (untracked collectstatic output)
python3 $S/check.py --brownfield --prefix webops- --css static/css --html templates --no-contrast
```

The checker reads each template alone, so pages that extend `base.html` or use
`{% include %}` report false `html/doc`, `html/skip` and `html/headings` hits. Compose
extends/blocks/includes first and check the composed pages to see real findings.
Add `python3 $S/human_check.py --catalog human/designs.json --root .` for the human brief.

## Done

| Rule | Change |
|---|---|
| 19. No gradients | Flattened the panel, API docs and logo SVG. `staticfiles/` (vendored select2) is no longer tracked; the gate still flags it if a local `collectstatic` has run. |
| 11. Visible focus | Removed `outline: none` from focus rules; `.webops-focus-primary` shows a primary outline. |
| 11. Skip link, landmark, headings | `base.html`, `auth/auth_base.html`, `errors/base_error.html`, `errors/429.html` and `api/docs.html` have a skip link and `<main id="main">`. `components/header.html` renders the page title as the single `<h1>`; in-page titles are `<h2>`. |
| 17. No third-party requests | Removed Google Fonts, Material Icons, Chart.js (jsDelivr) and CodeMirror (cdnjs). Icons come from local SVG masks (`static/js/icons.js`, `static/css/webops-icons.css`), the compliance chart from `webops-bar-chart.js`, and the editor from `webops-code-editor.js` (plain textarea, no syntax highlighting). |
| CSP-compatible markup | No `style=""`, `<style>`, inline `<script>` or inline `on*=` handlers. Static styles moved to `static/css/inline-extracted.css` and `static/css/pages/*.css`, scripts to `static/js/pages/*.js`. Dynamic values use `data-style-width` (`dynamic-style.js`), `webopsPage()` config attributes (`page-config.js`) and `data-on-*` / `data-confirm` (`ui-actions.js`, no `eval`). Branding variables are served from `/branding.css` (`apps/core/branding/views.py`) instead of inlined. |
| Labels, decorative SVGs | Unlabelled controls labelled; decorative SVGs have `aria-hidden="true"`. |
| Duplicate API docs | Removed `apps/api/docs/`, `static/api/docs/` and `templates/api/docs/{index.html,styles.css,script.js}`. `templates/api/docs.html` is the routed page. |
| Motion | `flat-ui.css` keeps shadows off but no longer blanket-disables transitions; `prefers-reduced-motion: reduce` collapses them. |
| Contrast | Checked dark-theme text and accent pairs with `contrast.py` (all at or above 4.5:1 for text). `.webops-btn-danger` used white on red (3.76:1); it now uses the dark text like the other filled buttons (5.26:1). Brand-generated themes are not checked. |
| Human brief | `control-panel/human/designs.json` covers deploy create, delete confirmation, sign-in and dashboard. It passes the structural gate; every review is `pending` and no research was done. |
| Pre-existing bugs | Removed committed diff markers in `automation/template_list.html`; fixed `<span="material-icons">` in `deployments/create.html`. |

## Responsive check

All 63 pages were rendered as static HTML with sample data (templates composed without Django, real CSS and JS) in headless Chrome at 320, 360, 390, 768, 1024, 1280 and 1536 px. The check is page width (`scrollWidth` vs viewport) plus elements past the right edge outside a scroll box. `body` has `overflow-x: hidden`, so `shots.py --fail-on-overflow` does not see these problems.

Found and fixed:
- `.webops-main-content` was a flex item without `min-width: 0`, so any wide child widened the whole page (27 of 58 pages at 390 px, 9 at 768 px).
- 106 `grid-template-columns` declarations used bare `1fr` / `repeat(n, 1fr)` and now use `minmax(0, 1fr)`; 22 `minmax(Npx, 1fr)` minimums of 250 px or more are capped with `min(Npx, 100%)`.
- The API docs layout had a fixed `250px 1fr` grid with no mobile rule (now `.webops-docs-layout`).
- 3 and 4 column grids stack under 640 px; page-header, filter-form and status-banner rows wrap on phones.

Result: no page is wider than the viewport at any tested width. At 320 px, 4 pages still have a small element (button, badge or card header, up to about 40 px) clipped (`compliance/dashboard`, `dashboard`, `deployments/llm_detail`, `integrations/dashboard`). Limits: sample data, no real fonts or API data, drawer and JS states not exercised, Chrome only.

## Remaining, by design or needs a human

1. **JSON data block.** `automation/workflow_builder.html` has `<script type="application/json">`. It is data, not executable, and is allowed under `script-src 'self'`; the checker flags it anyway.
2. **Checker false positives.** Remaining `html/ids` hits come from composition stripping Django tags (`for="x"` placeholders, form-field ids in `core/branding_settings.html`).
3. **`core/user_settings.html`** nav links `#general` and `#security` have no section on the page (the Notifications link is also listed twice). `user-settings.js` was already ineffective for these; the page needs real sections or the links removed.
4. **Token model.** The panel keeps `--webops-*` tokens and the `webops-` BEM prefix, which `check.py --brownfield` accepts.
5. **Not verified at runtime.** Django is not installed in the review environment, so visual parity of the extracted rules, icon rendering, the chart and editor, and `ui-actions` were checked with the gates and Node unit tests only. Run the app and click through before merging.
6. **Human review.** `human/designs.json` reviews are pending; `human_check.py --release` will fail until a real reviewer fills them in.
