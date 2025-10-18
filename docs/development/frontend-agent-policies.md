# WebOps Frontend CSS & Template Policies

Scope: These policies apply to the Django templates in `control-panel/templates/` and all CSS under `control-panel/static/css/` (and `staticfiles/css/`). They aim for maintainability, scalability, and consistency with our design system while allowing documented variances.

## 1. CSS Class Naming Conventions

- BEM mandated:
  - Block: top-level component (e.g., `.webops-card`).
  - Element: part of a block, `__` separator (e.g., `.webops-card__header`).
  - Modifier: variations, `--` separator (e.g., `.webops-card--compact`).
- Project prefixes:
  - Components/blocks: `webops-` (required). Example: `.webops-button`, `.webops-tag`.
  - Utilities: `u-` (limited scope helper classes), e.g., `.u-hidden`, `.u-flex`, `.u-mt-8`.
  - State flags: `is-` / `has-`, e.g., `.is-loading`, `.has-error`.
  - CSS variables: `--webops-*` (e.g., `--webops-color-primary`).
- Prohibit generic names:
  - Do not use `.button`, `.title`, `.card`, `.header`, `.footer`, `.container`, etc.
- Specificity & selectors:
  - Max nesting: 2 levels (prefer flat BEM selectors).
  - Avoid IDs and `!important` (allowed only in vetted utilities with rationale documented).
  - No tag selectors for styling (e.g., `h1 {}`) outside reset/normalize layers.
- File organization:
  - One block per file under `static/css/components/` (e.g., `webops-card.css`).
  - Modifiers live with their block. Elements live with their block.
  - Shared utilities live under `static/css/utilities/`.

## 2. Template Documentation Standards

- Inline comments for complex logic:
  - Use Django template comments `{# ... #}` above conditionals, loops, includes, and macro-like patterns.
  - Explain non-obvious data dependencies (what context keys are required and why).
- Template registry (required):
  - Location: `docs/reference/template-registry.md` (Markdown) or `control-panel/templates/_registry.json` (JSON).
  - Each entry documents: name, path, purpose, block(s) used, dependencies (includes/partials), required context contract, owner, and example usage link.
  - Example (YAML):
    ```yaml
    - name: Card
      path: control-panel/templates/components/card.html
      purpose: Display content in a standardized card layout
      blocks: [webops-card]
      dependencies:
        - components/icon.html
        - components/button.html
      context_contract:
        title: string
        body: safe_html
        icon: optional string
      owner: ui-platform
      examples: docs/reference/components/card.md
    ```
- Usage examples for shared components:
  - Provide minimal examples under `docs/reference/components/` or inline in registry entries.
  - Include context payloads and rendered screenshots where practical.

## 3. Version Control Protocols

- Atomic commits:
  - One commit per logical change (e.g., add modifier, update a template include). Avoid batching unrelated CSS/template changes.
- Commit messages:
  - Prefix scope and reference design system version, e.g.:
    - `feat(css): webops-card -- add compact modifier [DS v2.3]`
    - `fix(template): card.html -- correct header aria semantics [DS v2.3]`
- Branch protection:
  - Protect `control-panel/static/css/` and `control-panel/templates/components/` via branch rules.
  - Require code owner review (see `.github/CODEOWNERS`).

## 4. Implementation Audit Checklist

- Design system compliance:
  - Use tokens from `docs/reference/design-system-v2.md` (colors, spacing, typography).
  - Validate component anatomy against documented patterns.
- Performance metrics:
  - CSS specificity: keep selectors ≤ `0,2,0` (no IDs). Avoid deep descendant selectors.
  - Render: confirm no >5% regression in Lighthouse Performance for affected views.
- Accessibility (WCAG 2.1 AA):
  - Contrast ≥ 4.5:1; visible focus states; semantic HTML; proper ARIA where necessary.
  - Test with axe (CLI or browser extension) and manual keyboard checks.
- Cross-browser matrix (latest 2 versions):
  - Desktop: Chrome, Firefox, Safari (macOS), Edge.
  - Mobile: iOS Safari, Chrome Android.
- Mobile responsiveness:
  - Validate at breakpoints: 360, 768, 1024, 1280px.
  - Ensure fluid layouts, touch targets ≥ 44px.

## 5. Change Management Process

- New pattern approval:
  - Submit a design spec aligned to DS v2.x. Obtain review from design system maintainers before implementation.
- Peer review:
  - All template modifications require at least one peer review; core components require two reviews.
- Changelog:
  - Record breaking changes in `docs/reference/changelog.md` under a “Style & Templates” section with migration guidance.

## 6. Testing Requirements

- Unit tests (template logic):
  - Use Django `TestCase` to render templates and assert context-driven output.
  - Example:
    ```python
    from django.test import TestCase
    from django.template import engines

    class CardTemplateTests(TestCase):
        def test_card_renders_title(self):
            tpl = engines['django'].get_template('components/card.html')
            html = tpl.render({'title': 'Hello', 'body': 'World'})
            self.assertIn('Hello', html)
    ```
- Integration tests (component interactions):
  - Use Playwright (or Selenium) for DOM interactions (e.g., accordion toggle, modal open).
- Visual regression testing:
  - Capture baseline screenshots per component/state and diff on PRs (Percy or Playwright snapshots).
- Browser compatibility automation:
  - Run the suite across the matrix above (CI job in `.github/workflows/ci.yml` or `nightly.yml`).

## 7. Security Standards

- Sanitize dynamic content:
  - Django auto-escapes variables; avoid `|safe` unless content is sanitized upstream and documented in the registry.
- Restrict inline styles/scripts:
  - Disallow inline `<style>`/`<script>` by default. Variance allowed for critical CSS inline ≤ 5KB with nonce and CSP.
- Content Security Policy (CSP):
  - Configure via Django (`django-csp`) or Nginx (`system-templates/nginx/app.conf.j2`). Example header:
    ```
    Content-Security-Policy:
      default-src 'self';
      style-src 'self' 'nonce-<nonce>'; font-src 'self';
      script-src 'self' 'nonce-<nonce>'; img-src 'self' data:;
      connect-src 'self'; frame-ancestors 'none';
    ```

## 8. Performance Optimization

- Critical CSS extraction:
  - Extract above-the-fold styles per critical view (e.g., `dashboard.html`). If inlining, limit to 5KB with CSP nonce and document rationale.
- CSS bundle size monitoring:
  - Track gzipped size of component bundles. Set alert threshold at 250KB (fail CI >300KB).
- Template render benchmarks:
  - Add micro-benchmarks for template render time (Django test client). No >10% regression allowed per view.
- Lazy-loading:
  - Images: `loading="lazy"`, appropriate `sizes`, `srcset`. Defer non-critical assets, use preconnect/prefetch judiciously.

## Variance Approval Process

- Purpose: Allow deviations from policy when justified by user needs, performance, or compatibility.
- Steps:
  1) Open a PR with a `Variance: <short title>` label.
  2) Include a variance note in the description with justification, risk analysis, mitigation, and sunset date.
  3) Obtain approval from design system maintainers and a peer reviewer.
  4) Record approved variance in `docs/development/variances.md`.
- Template (YAML):
  ```yaml
  id: VAR-2025-01
  title: Inline critical CSS for dashboard hero
  scope: control-panel/templates/dashboard.html
  rationale: Reduce CLS/FCP per Lighthouse audit
  risk: CSP complexity, cache invalidation
  mitigation: Nonce-based CSP, size ≤ 5KB, revisit in 60 days
  owners: ui-platform, security
  approved_on: 2025-01-15
  sunset: 2025-03-15
  status: approved
  ```

## References

- Design system: `docs/reference/design-system-v2.md`
- Security: `docs/security/security-features.md`, `docs/security/security-hardening.md`
- CI workflows: `.github/workflows/ci.yml`, `nightly.yml`