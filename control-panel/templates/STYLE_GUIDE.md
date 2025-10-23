# WebOps Control Panel Style Guide

## Overview

This style guide establishes the design system standards for the WebOps Control Panel. All templates must follow these guidelines to ensure consistency, maintainability, and optimal user experience.

## CSS Architecture

### File Organization

```
control-panel/static/css/
├── variables.css          # CSS custom properties (variables)
├── main.css              # Base styles and typography
├── themes.css           # Theme-specific styles
├── theme-switcher.css   # Theme switching functionality
├── webops-components.css # Reusable component styles (TO BE CREATED)
├── webops-utilities.css  # Utility classes (TO BE CREATED)
├── webops-layout.css     # Layout-specific styles (TO BE CREATED)
├── notifications-center.css
├── toast.css
├── workflow-toolbar.css
└── addon-detail.css
```

### CSS Loading Order

Templates must load CSS files in this specific order:

```html
<!-- Core CSS -->
<link rel="stylesheet" href="{% static 'css/variables.css' %}">
<link rel="stylesheet" href="{% static 'css/main.css' %}">
<link rel="stylesheet" href="{% static 'css/themes.css' %}">

<!-- Component CSS -->
<link rel="stylesheet" href="{% static 'css/webops-components.css' %}">
<link rel="stylesheet" href="{% static 'css/webops-utilities.css' %}">
<link rel="stylesheet" href="{% static 'css/webops-layout.css' %}">

<!-- Feature-specific CSS -->
<link rel="stylesheet" href="{% static 'css/notifications-center.css' %}">
<link rel="stylesheet" href="{% static 'css/toast.css' %}">
```

## CSS Class Naming Conventions

### BEM Methodology with WebOps Prefix

All CSS classes must follow the BEM (Block Element Modifier) methodology with the `webops-` prefix:

```css
/* Block */
.webops-card { }

/* Element */
.webops-card__header { }
.webops-card__body { }
.webops-card__footer { }

/* Modifier */
.webops-card--warning { }
.webops-card--primary { }
.webops-card__header--sticky { }
```

### Prohibited Patterns

❌ **Never use these patterns:**
```css
/* No naked classes without webops- prefix */
.card { }           /* WRONG */
.button { }         /* WRONG */
.header { }         /* WRONG */

/* No inline styles */
<div style="color: red;">  /* WRONG */

/* No non-BEM classes */
.webops-card.warning  /* WRONG */
.webops-card primary   /* WRONG */
```

✅ **Always use these patterns:**
```css
/* Proper BEM with webops- prefix */
.webops-card { }
.webops-card__header { }
.webops-card--warning { }
.webops-btn { }
.webops-btn--primary { }
.webops-btn--sm { }
```

## CSS Variables (Custom Properties)

### Naming Convention

All CSS variables must use the `--webops-` prefix:

```css
/* Colors */
--webops-color-primary: #00ff88;
--webops-color-secondary: #1a1a1a;
--webops-color-success: #00ff88;
--webops-color-error: #ff4444;
--webops-color-warning: #ffaa00;
--webops-color-info: #00aaff;

/* Typography */
--webops-font-family-primary: 'Inter', sans-serif;
--webops-font-size-sm: 0.875rem;
--webops-font-size-base: 1rem;
--webops-font-size-lg: 1.125rem;
--webops-font-weight-normal: 400;
--webops-font-weight-semibold: 600;
--webops-font-weight-bold: 700;

/* Spacing */
--webops-space-0-5: 0.125rem;
--webops-space-1: 0.25rem;
--webops-space-1-5: 0.375rem;
--webops-space-2: 0.5rem;
--webops-space-3: 0.75rem;
--webops-space-4: 1rem;
--webops-space-6: 1.5rem;
--webops-space-8: 2rem;

/* Border Radius */
--webops-radius-sm: 0.25rem;
--webops-radius-md: 0.375rem;
--webops-radius-lg: 0.5rem;
--webops-radius-xl: 0.75rem;

/* Shadows */
--webops-shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
--webops-shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
--webops-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);

/* Transitions */
--webops-transition-fast: 150ms ease-in-out;
--webops-transition-base: 250ms ease-in-out;
--webops-transition-slow: 350ms ease-in-out;
```

### Usage in CSS

```css
.webops-btn {
  background: var(--webops-color-primary);
  padding: var(--webops-space-3) var(--webops-space-4);
  border-radius: var(--webops-radius-md);
  transition: all var(--webops-transition-fast);
}

.webops-btn--primary {
  background: var(--webops-color-primary);
  color: var(--webops-color-background);
}

.webops-btn--secondary {
  background: transparent;
  color: var(--webops-color-primary);
  border: 1px solid var(--webops-color-primary);
}
```

## Component Standards

### Button Components

#### Base Button
```html
<button class="webops-btn">Button Text</button>
```

#### Button Variants
```html
<button class="webops-btn webops-btn--primary">Primary</button>
<button class="webops-btn webops-btn--secondary">Secondary</button>
<button class="webops-btn webops-btn--danger">Danger</button>
<button class="webops-btn webops-btn--sm">Small</button>
<button class="webops-btn webops-btn--lg">Large</button>
<button class="webops-btn webops-btn--block">Block</button>
```

### Card Components

#### Basic Card
```html
<div class="webops-card">
  <div class="webops-card__header">
    <h3 class="webops-card__title">Card Title</h3>
  </div>
  <div class="webops-card__body">
    <p>Card content goes here</p>
  </div>
</div>
```

#### Card Variants
```html
<div class="webops-card webops-card--warning">
<div class="webops-card webops-card--primary">
```

### Form Components

#### Form Group
```html
<div class="webops-form-group">
  <label class="webops-label" for="input-id">Label Text</label>
  <input class="webops-input" id="input-id" type="text">
</div>
```

#### Form Elements
```html
<input class="webops-input" type="text">
<select class="webops-select"></select>
<textarea class="webops-textarea"></textarea>
<input class="webops-checkbox" type="checkbox">
```

### Alert Components

#### Alert Messages
```html
<div class="webops-alert webops-alert--success">
  <span class="webops-alert__icon">✓</span>
  <div class="webops-alert__content">
    Success message
  </div>
</div>

<div class="webops-alert webops-alert--error">
  <span class="webops-alert__icon">⚠</span>
  <div class="webops-alert__content">
    Error message
  </div>
</div>
```

### Layout Components

#### Page Header
```html
<div class="webops-page-header">
  <div>
    <h2 class="webops-page-title">Page Title</h2>
    <p class="webops-text-muted">Page description</p>
  </div>
  <a href="#" class="webops-btn webops-btn-primary">Action</a>
</div>
```

#### Stats Grid
```html
<div class="webops-stats-grid">
  <div class="webops-stat-card">
    <div class="webops-stat-icon">📊</div>
    <div class="webops-stat-value">123</div>
    <div class="webops-stat-label">Total</div>
  </div>
</div>
```

## Icon Standards

### Material Icons Usage

Use Material Icons consistently across all templates:

```html
<span class="material-icons">dashboard</span>
<span class="material-icons webops-text-primary">settings</span>
<span class="material-icons" style="font-size: 16px;">close</span>
```

### Icon Sizes

```css
/* Standard sizes */
.webops-icon--small { font-size: 16px; }
.webops-icon--medium { font-size: 20px; }
.webops-icon--large { font-size: 24px; }
.webops-icon--xl { font-size: 32px; }
```

## Typography Standards

### Headings
```html
<h1 class="webops-h1">Page Title</h1>
<h2 class="webops-h2">Section Title</h2>
<h3 class="webops-h3">Card Title</h3>
```

### Text Utilities
```html
<p class="webops-text-muted">Secondary text</p>
<strong class="webops-font-semibold">Bold text</strong>
<code class="webops-text-sm">Code snippet</code>
```

## Color Usage

### Semantic Colors
```css
--webops-color-primary: #00ff88;    /* Brand primary */
--webops-color-secondary: #1a1a1a;  /* Dark backgrounds */
--webops-color-success: #00ff88;    /* Success states */
--webops-color-error: #ff4444;      /* Error states */
--webops-color-warning: #ffaa00;    /* Warning states */
--webops-color-info: #00aaff;       /* Info states */
```

### Background Colors
```css
--webops-color-bg-primary: #0a0a0a;    /* Main background */
--webops-color-bg-secondary: #1a1a1a;  /* Card backgrounds */
--webops-color-bg-tertiary: #2a2a2a;   /* Input backgrounds */
```

## Spacing Standards

### Consistent Spacing Scale
```css
--webops-space-0-5: 0.125rem;  /* 2px */
--webops-space-1: 0.25rem;     /* 4px */
--webops-space-1-5: 0.375rem;  /* 6px */
--webops-space-2: 0.5rem;      /* 8px */
--webops-space-3: 0.75rem;     /* 12px */
--webops-space-4: 1rem;        /* 16px */
--webops-space-6: 1.5rem;      /* 24px */
--webops-space-8: 2rem;        /* 32px */
```

### Margin/Padding Classes
```html
<div class="webops-m-md">Margin medium</div>
<div class="webops-p-lg">Padding large</div>
<div class="webops-mb-sm">Margin bottom small</div>
```

## Responsive Design

### Breakpoints
```css
/* Mobile first approach */
@media (min-width: 640px) { /* sm */ }
@media (min-width: 768px) { /* md */ }
@media (min-width: 1024px) { /* lg */ }
@media (min-width: 1280px) { /* xl */ }
```

### Responsive Utilities
```html
<div class="webops-grid webops-grid-1 webops-md-grid-2 webops-lg-grid-3">
  <!-- Responsive grid -->
</div>
```

## Template Inheritance

### Required Structure

All templates must extend `base.html`:

```html
{% extends 'base.html' %}

{% block title %}Page Title - WebOps{% endblock %}
{% block header_title %}Page Title{% endblock %}

{% block content %}
<!-- Page content here -->
{% endblock %}
```

### Block Usage

#### Required Blocks
- `title` - Page title for <head>
- `header_title` - Title shown in header
- `content` - Main page content

#### Optional Blocks
- `extra_css` - Additional CSS links
- `extra_js` - Additional JavaScript
- `aside` - Custom sidebar content
- `header` - Custom header content

## Validation Rules

### Automated Checks

The following must pass automated validation:

1. **No inline styles**: `grep -r "style=" templates/` should return empty
2. **WebOps prefix only**: All classes must start with `webops-`
3. **Template inheritance**: All templates must extend `base.html`
4. **CSS variables**: All colors/spacing must use CSS variables

### Manual Review Checklist

- [ ] Consistent spacing and alignment
- [ ] Proper color usage from palette
- [ ] Responsive design works on mobile
- [ ] Icons are properly sized and colored
- [ ] Typography hierarchy is maintained
- [ ] Interactive elements have proper hover states
- [ ] Accessibility features are implemented

## Migration Guide

### From Old Patterns to New

| Old Pattern | New Pattern |
|-------------|-------------|
| `<div style="margin: 1rem;">` | `<div class="webops-m-lg">` |
| `<button class="btn btn-primary">` | `<button class="webops-btn webops-btn--primary">` |
| `<div class="card">` | `<div class="webops-card">` |
| `color: #00ff88;` | `color: var(--webops-color-primary);` |
| `<span class="material-icons">` | `<span class="material-icons">` (unchanged) |

## Examples

### Complete Component Example

```html
<div class="webops-card">
  <div class="webops-card__header">
    <h3 class="webops-h3">
      <span class="material-icons webops-text-primary">dashboard</span>
      Dashboard Overview
    </h3>
  </div>
  <div class="webops-card__body">
    <div class="webops-stats-grid">
      <div class="webops-stat-card">
        <div class="webops-stat-icon webops-stat-icon--success">
          <span class="material-icons">check_circle</span>
        </div>
        <div class="webops-stat-value">42</div>
        <div class="webops-stat-label">Active</div>
      </div>
    </div>
    <div class="webops-form-group">
      <label class="webops-label" for="search">Search</label>
      <input class="webops-input" id="search" type="text" placeholder="Search...">
    </div>
    <div class="webops-alert webops-alert--info">
      <span class="webops-alert__icon">ℹ️</span>
      <div class="webops-alert__content">
        Information message
      </div>
    </div>
  </div>
</div>
```

This style guide ensures consistency across all WebOps Control Panel templates and provides a foundation for scalable, maintainable frontend development.
