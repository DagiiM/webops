# WebOps API Documentation

**Ultra-sleek, Mintlify-inspired API documentation for WebOps**

## 🎨 Design Philosophy

This documentation is built with a modern, developer-first approach inspired by [Mintlify](https://mintlify.com):

- **Clean & Minimalist** - Focus on content, not clutter
- **Beautiful by Default** - Gorgeous out-of-the-box design
- **Zero Dependencies** - Pure HTML, CSS, and vanilla JavaScript
- **Fast & Responsive** - Optimized for all devices
- **Developer-Friendly** - Code-first documentation experience

## 📁 Files

```
docs/
├── index.html        # Main documentation page (comprehensive API reference)
├── styles.css        # Mintlify-inspired design system
├── script.js         # Interactive features (tabs, copy, highlighting)
└── README.md         # This file
```

## 🚀 Features

### Design Features
- ✨ Gradient accents and smooth transitions
- 🎯 Sticky navigation with blur backdrop
- 📱 Fully responsive (mobile, tablet, desktop)
- 🎨 Beautiful syntax highlighting
- 💫 Smooth scroll animations
- 🌈 Modern color palette with semantic meaning

### Interactive Features
- 📋 One-click code copying
- 🔄 Language switcher for code examples (cURL, Python, JavaScript)
- 🔗 Deep linking to sections
- 📍 Auto-highlighting active section in sidebar
- ⌨️ Keyboard shortcuts (Cmd+K for search - coming soon)
- 🖨️ Print-optimized layouts

### Content Features
- 📖 Complete API reference for all endpoints
- 🔐 Authentication guide with security best practices
- 📊 Error codes reference
- ⚡ Rate limits documentation
- 🛠️ SDK listings for multiple languages
- 💡 Step-by-step quickstart guide

## 🎨 Design System

### Color Palette

**Primary Colors**
- Primary: `#667eea` - Used for CTAs and highlights
- Secondary: `#764ba2` - Gradient accents
- Accent: `#f093fb` - Special highlights

**Semantic Colors**
- Success: `#10b981` (Green)
- Warning: `#f59e0b` (Amber)
- Error: `#ef4444` (Red)
- Info: `#3b82f6` (Blue)

**Grays**
- 50-900 scale for backgrounds, borders, and text

### Typography

**Font Families**
- Sans: `Inter` - Clean, modern, highly readable
- Mono: `JetBrains Mono` - Perfect for code blocks

**Font Sizes** (Responsive Scale)
- xs: 12px → sm: 14px → base: 16px → xl: 20px → 5xl: 48px

### Spacing System
Consistent 4px-based spacing scale:
- `1` (4px) → `2` (8px) → `4` (16px) → `8` (32px) → `20` (80px)

### Component Styles

**Cards**
- Border radius: 12-16px
- Subtle shadows with hover effects
- 1px borders in light gray
- White backgrounds with hover state

**Buttons**
- Primary: Gradient background with shadow
- Secondary: White with border
- Hover: Transform + shadow change
- Padding: 12px 24px

**Code Blocks**
- Dark background (`#1e1e2e`)
- Syntax highlighting
- Copy button in header
- Rounded corners (8px)

## 🛠️ Customization

### Changing Colors

Edit `styles.css` CSS variables:

```css
:root {
    --color-primary: #667eea;        /* Your brand color */
    --color-secondary: #764ba2;      /* Secondary accent */
    /* ... other colors ... */
}
```

### Adding New Endpoints

1. Find the appropriate endpoint group in `index.html`
2. Copy an existing `.endpoint-card` block
3. Update the method, path, parameters, and response
4. Add to the sidebar navigation

Example:
```html
<div class="endpoint-card">
    <div class="endpoint-header">
        <div class="endpoint-method-url">
            <span class="method method-get">GET</span>
            <code class="endpoint-path">/v1/your-endpoint</code>
        </div>
        <span class="endpoint-title">Your endpoint title</span>
    </div>
    <!-- Add endpoint body... -->
</div>
```

### Adding Language Examples

In the tabs section:
```html
<div class="tabs">
    <div class="tab-buttons">
        <button class="tab-btn active" onclick="switchTab(event, 'your-curl')">cURL</button>
        <button class="tab-btn" onclick="switchTab(event, 'your-python')">Python</button>
        <!-- Add more languages -->
    </div>

    <div id="your-curl" class="tab-content active">
        <!-- cURL example -->
    </div>

    <div id="your-python" class="tab-content">
        <!-- Python example -->
    </div>
</div>
```

## 🌐 Serving the Documentation

### Option 1: Django Static Files

Add to your Django app:

```python
# apps/api/views.py
from django.views.generic import TemplateView

class APIDocsView(TemplateView):
    template_name = 'api/docs/index.html'

# apps/api/urls.py
from django.urls import path
from .views import APIDocsView

urlpatterns = [
    path('docs/', APIDocsView.as_view(), name='api-docs'),
    # ... other URLs
]
```

### Option 2: Static File Server

Serve directly with Python:
```bash
cd apps/api/docs
python -m http.server 8080
```

Visit: `http://localhost:8080`

### Option 3: Nginx

```nginx
location /api/docs/ {
    alias /path/to/webops/control-panel/apps/api/docs/;
    index index.html;
}
```

## 📱 Responsive Breakpoints

- **Desktop**: 1024px+ (full sidebar, all features)
- **Tablet**: 768px-1024px (collapsible sidebar)
- **Mobile**: <768px (hamburger menu, stacked layout)

## ♿ Accessibility

- Semantic HTML5 elements
- ARIA labels where needed
- Keyboard navigation support
- High contrast ratios (WCAG AA compliant)
- Focus indicators on interactive elements
- Alt text for icons and images

## 🎯 Best Practices Used

### Performance
- No external dependencies (no jQuery, no frameworks)
- Minimal JavaScript (~350 lines)
- CSS custom properties for theming
- Optimized fonts (Inter, JetBrains Mono)
- Lazy-loaded sections

### Code Quality
- Well-commented CSS and JS
- Modular CSS with clear sections
- Reusable components
- Consistent naming conventions
- BEM-like methodology for classes

### Developer Experience
- Clear code examples in multiple languages
- Copy-to-clipboard functionality
- Interactive code snippets
- Visual feedback on all actions
- Helpful error messages

## 🚧 Future Enhancements

Planned features (marked as "Future" in code):

- [ ] Search functionality (fuzzy search)
- [ ] Dark mode toggle
- [ ] API playground (interactive testing)
- [ ] Export to PDF
- [ ] Version switcher
- [ ] Code language auto-detection
- [ ] Collapsible endpoint sections
- [ ] Advanced filtering
- [ ] Usage analytics
- [ ] Offline support (PWA)

## 🤝 Contributing

To improve the documentation:

1. Edit the appropriate file (`index.html`, `styles.css`, `script.js`)
2. Test locally
3. Ensure responsive design works
4. Check browser compatibility
5. Submit changes

## 📝 Documentation Structure

```
├── Introduction & Hero
├── Quickstart (3-step guide)
├── Authentication
├── API Endpoints
│   ├── Deployments
│   │   ├── List deployments
│   │   ├── Create deployment
│   │   ├── Get deployment
│   │   ├── Start/Stop/Restart
│   │   └── Get logs
│   ├── Databases
│   │   ├── List databases
│   │   └── Get credentials
│   └── Status
│       └── Health check
├── Error Codes
├── Rate Limits
└── SDKs & Libraries
```

## 🎨 Component Reference

### Cards
- `.step-card` - Numbered step cards with icon
- `.endpoint-card` - API endpoint documentation
- `.error-card` - Error code reference
- `.sdk-card` - SDK/library card
- `.sidebar-card` - Sidebar info boxes

### Badges & Tags
- `.badge` - Version badge
- `.method` - HTTP method tag (GET, POST, etc.)
- `.param-required` - Required parameter badge
- `.param-optional` - Optional parameter badge

### Info Boxes
- `.info-box` - Blue informational callout
- `.warning-box` - Yellow warning callout
- `.error-box` - Red error callout (add if needed)

## 🐛 Browser Support

- Chrome/Edge: Latest 2 versions ✅
- Firefox: Latest 2 versions ✅
- Safari: Latest 2 versions ✅
- Mobile Safari: iOS 12+ ✅
- Chrome Mobile: Latest ✅

## 📄 License

This documentation template is part of WebOps and follows the same license.

---

**Built with ❤️ for developers**

Need help? Check out the [main documentation](https://github.com/DagiiM/webops/tree/main/docs) or [open an issue](https://github.com/DagiiM/webops/issues).
