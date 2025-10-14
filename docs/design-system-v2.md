# WebOps Design System v2.0

**Enterprise-Grade UI/UX Framework for WebOps Platform**

## Overview

The WebOps Design System provides a comprehensive set of design principles, components, and patterns for building consistent, accessible, and high-performance user interfaces across the WebOps platform.

## Design Principles

### 1. Accessibility First
- **WCAG 2.1 AA+ Compliance**: All components meet or exceed accessibility standards
- **Keyboard Navigation**: Full keyboard support with logical tab order
- **Screen Reader Support**: ARIA labels and semantic HTML throughout
- **Color Contrast**: Minimum 4.5:1 contrast ratio for all text
- **Focus Indicators**: Clear visual focus states for all interactive elements

### 2. Performance Optimized
- **Zero Frameworks**: Pure HTML5/CSS3/ES6+ for maximum performance
- **Minimal Dependencies**: No external libraries or build tools
- **Lazy Loading**: Content loads progressively for better perceived performance
- **CSS Optimization**: Efficient selectors and minimal reflows

### 3. Mobile-First Responsive
- **Fluid Layouts**: Flexible grid systems that adapt to any screen size
- **Touch-Friendly**: Minimum 44px touch targets for mobile devices
- **Progressive Enhancement**: Core functionality works on all devices

## Core Components

### Navigation Components
- **Main Navigation**: Persistent sidebar with collapsible sections
- **Breadcrumbs**: Contextual navigation with hierarchical structure
- **Tabs**: Accessible tab interfaces with keyboard support
- **Pagination**: Numbered pagination for large datasets

### Form Components
- **Input Fields**: Accessible text inputs with validation states
- **Select Menus**: Custom dropdowns with search and keyboard navigation
- **Checkboxes & Radios**: Accessible form controls with clear labels
- **Buttons**: Primary, secondary, and tertiary button styles
- **Date Pickers**: Accessible date selection components

### Data Display Components
- **Tables**: Sortable, filterable tables with responsive behavior
- **Cards**: Flexible content containers with consistent spacing
- **Modals**: Accessible modal dialogs with focus trapping
- **Tooltips**: Contextual information on hover/focus
- **Badges**: Status indicators and notification counters

### Feedback Components
- **Alerts**: Success, warning, error, and information messages
- **Loading States**: Skeleton screens and progress indicators
- **Empty States**: Helpful messaging for empty content areas
- **Error States**: Clear error messages with recovery options

## CSS Architecture

### CSS Custom Properties (Variables)
```css
:root {
  /* Colors */
  --color-primary: #2563eb;
  --color-primary-dark: #1d4ed8;
  --color-secondary: #64748b;
  --color-success: #059669;
  --color-warning: #d97706;
  --color-error: #dc2626;
  --color-background: #ffffff;
  --color-surface: #f8fafc;
  --color-border: #e2e8f0;
  
  /* Typography */
  --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.125rem;
  --font-size-xl: 1.25rem;
  --font-size-2xl: 1.5rem;
  
  /* Spacing */
  --spacing-xs: 0.25rem;
  --spacing-sm: 0.5rem;
  --spacing-md: 1rem;
  --spacing-lg: 1.5rem;
  --spacing-xl: 2rem;
  
  /* Border Radius */
  --border-radius-sm: 0.25rem;
  --border-radius-md: 0.375rem;
  --border-radius-lg: 0.5rem;
  --border-radius-xl: 0.75rem;
  
  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}
```

### Utility Classes
```css
/* Text utilities */
.text-sm { font-size: var(--font-size-sm); }
.text-base { font-size: var(--font-size-base); }
.text-lg { font-size: var(--font-size-lg); }
.text-xl { font-size: var(--font-size-xl); }

/* Spacing utilities */
.m-2 { margin: var(--spacing-md); }
.p-4 { padding: var(--spacing-xl); }
.gap-2 { gap: var(--spacing-md); }

/* Color utilities */
.bg-primary { background-color: var(--color-primary); }
.text-primary { color: var(--color-primary); }
.border-error { border-color: var(--color-error); }
```

## JavaScript Patterns

### Event Handling
```javascript
// Use event delegation for dynamic content
document.addEventListener('click', function(event) {
  if (event.target.matches('[data-action="delete"]')) {
    handleDelete(event.target.dataset.id);
  }
});

// Keyboard accessibility
document.addEventListener('keydown', function(event) {
  if (event.key === 'Escape') {
    closeModal();
  }
});
```

### State Management
```javascript
// Simple state management pattern
const state = {
  deployments: [],
  loading: false,
  error: null
};

function updateState(newState) {
  Object.assign(state, newState);
  render(); // Re-render based on new state
}
```

## Accessibility Features

### ARIA Implementation
```html
<!-- Proper ARIA usage -->
<button aria-label="Close modal" onclick="closeModal()">×</button>

<!-- Live regions for dynamic content -->
<div aria-live="polite" id="status-message"></div>

<!-- Form validation -->
<input aria-invalid="true" aria-describedby="email-error" />
<div id="email-error" class="error-message">Invalid email format</div>
```

### Focus Management
```javascript
// Trap focus in modals
function trapFocus(modal) {
  const focusableElements = modal.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  
  const firstElement = focusableElements[0];
  const lastElement = focusableElements[focusableElements.length - 1];
  
  modal.addEventListener('keydown', function(event) {
    if (event.key === 'Tab') {
      if (event.shiftKey) {
        if (document.activeElement === firstElement) {
          event.preventDefault();
          lastElement.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          event.preventDefault();
          firstElement.focus();
        }
      }
    }
  });
}
```

## Performance Optimization

### Lazy Loading
```javascript
// Intersection Observer for lazy loading
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const img = entry.target;
      img.src = img.dataset.src;
      observer.unobserve(img);
    }
  });
});

document.querySelectorAll('img[data-src]').forEach(img => {
  observer.observe(img);
});
```

### Efficient DOM Updates
```javascript
// Use DocumentFragment for batch updates
function renderItems(items) {
  const fragment = document.createDocumentFragment();
  
  items.forEach(item => {
    const element = createItemElement(item);
    fragment.appendChild(element);
  });
  
  container.innerHTML = '';
  container.appendChild(fragment);
}
```

## Browser Support

- **Chrome**: 88+
- **Firefox**: 85+
- **Safari**: 14+
- **Edge**: 88+
- **Mobile**: iOS Safari 14+, Chrome Mobile 88+

## Getting Started

### Basic Setup
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WebOps Control Panel</title>
  <link rel="stylesheet" href="/static/css/webops.css">
</head>
<body>
  <nav class="main-nav">
    <!-- Navigation content -->
  </nav>
  
  <main class="main-content">
    <!-- Page content -->
  </main>
  
  <script src="/static/js/webops.js"></script>
</body>
</html>
```

### Component Usage
```html
<!-- Button component -->
<button class="btn btn-primary" type="button">
  Create Deployment
</button>

<!-- Card component -->
<div class="card">
  <div class="card-header">
    <h3 class="card-title">Deployment Status</h3>
  </div>
  <div class="card-body">
    <p>Deployment is running successfully</p>
  </div>
  <div class="card-footer">
    <button class="btn btn-secondary">View Logs</button>
  </div>
</div>
```

## Customization

### Theming
```css
/* Custom theme override */
:root {
  --color-primary: #7c3aed; /* Purple theme */
  --color-primary-dark: #6d28d9;
}

/* Dark mode */
@media (prefers-color-scheme: dark) {
  :root {
    --color-background: #0f172a;
    --color-surface: #1e293b;
    --color-text: #f1f5f9;
  }
}
```

### Component Customization
```css
/* Custom button variant */
.btn-gradient {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-dark));
  border: none;
  color: white;
}

.btn-gradient:hover {
  background: linear-gradient(135deg, var(--color-primary-dark), var(--color-primary));
}
```

## Best Practices

### Code Organization
- Keep CSS modular and component-focused
- Use semantic HTML elements
- Separate concerns (HTML structure, CSS styling, JavaScript behavior)
- Follow accessibility guidelines from the start

### Performance
- Minimize DOM manipulation
- Use efficient CSS selectors
- Implement lazy loading for non-critical content
- Optimize images and assets

### Maintenance
- Document component usage and variants
- Provide clear examples in documentation
- Include accessibility testing in development workflow
- Regularly audit performance and accessibility

---

**WebOps Design System v2.0** - *Building accessible, performant, and beautiful interfaces* 🎨