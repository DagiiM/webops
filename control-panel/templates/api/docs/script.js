/**
 * WebOps API Documentation - Interactive Features
 * Mintlify-inspired modern documentation experience
 */

'use strict';

// ============================================================================
// Tab Switching
// ============================================================================
function switchTab(event, tabId) {
    const button = event.currentTarget;
    const tabContainer = button.closest('.tabs');

    // Hide all tab contents
    const allContents = tabContainer.querySelectorAll('.tab-content');
    allContents.forEach(content => {
        content.classList.remove('active');
    });

    // Deactivate all tab buttons
    const allButtons = tabContainer.querySelectorAll('.tab-btn');
    allButtons.forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab content
    const selectedContent = document.getElementById(tabId);
    if (selectedContent) {
        selectedContent.classList.add('active');
    }

    // Activate clicked button
    button.classList.add('active');
}

// ============================================================================
// Code Copying
// ============================================================================
function copyCode(button) {
    const codeBlock = button.closest('.code-block');
    const code = codeBlock.querySelector('code');

    if (!code) return;

    const text = code.textContent;

    // Copy to clipboard
    navigator.clipboard.writeText(text).then(() => {
        // Visual feedback
        const originalHTML = button.innerHTML;
        button.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M3 8L6 11L13 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            Copied!
        `;
        button.style.color = '#10b981';

        // Reset after 2 seconds
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.style.color = '';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        button.innerHTML = 'Failed';
        setTimeout(() => {
            button.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <rect x="5" y="5" width="9" height="9" rx="1" stroke="currentColor" stroke-width="1.5"/>
                    <path d="M3 10.5V3C3 2.44772 3.44772 2 4 2H10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                Copy
            `;
        }, 2000);
    });
}

// ============================================================================
// Smooth Scrolling with Offset
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    const navbarHeight = 64;
    const offset = 20;

    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');

            // Skip empty hrefs
            if (href === '#') {
                e.preventDefault();
                return;
            }

            const targetElement = document.querySelector(href);

            if (targetElement) {
                e.preventDefault();

                const elementPosition = targetElement.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - navbarHeight - offset;

                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });

                // Update URL
                history.pushState(null, null, href);

                // Update active sidebar link
                updateActiveSidebarLink(href);
            }
        });
    });
});

// ============================================================================
// Update Active Sidebar Link on Scroll
// ============================================================================
function updateActiveSidebarLink(targetId) {
    // Remove active class from all sidebar links
    document.querySelectorAll('.sidebar-link').forEach(link => {
        link.classList.remove('active');
    });

    // Add active class to matching link
    const activeLink = document.querySelector(`.sidebar-link[href="${targetId}"]`);
    if (activeLink) {
        activeLink.classList.add('active');
    }
}

// Intersection Observer for automatic sidebar highlighting
const observerOptions = {
    root: null,
    rootMargin: '-80px 0px -80% 0px',
    threshold: 0
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const id = entry.target.getAttribute('id');
            if (id) {
                updateActiveSidebarLink(`#${id}`);
            }
        }
    });
}, observerOptions);

// Observe all sections
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('section[id], .endpoint-group[id]').forEach(section => {
        observer.observe(section);
    });
});

// ============================================================================
// Keyboard Shortcuts
// ============================================================================
document.addEventListener('keydown', (e) => {
    // Cmd/Ctrl + K for search (future feature)
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        console.log('Search shortcut triggered (feature coming soon)');
        // Future: Open search modal
    }

    // Escape to close modals (future feature)
    if (e.key === 'Escape') {
        // Future: Close any open modals
    }
});

// ============================================================================
// Code Syntax Highlighting (Simple)
// ============================================================================
function highlightCode() {
    document.querySelectorAll('code.language-json').forEach(block => {
        let html = block.innerHTML;

        // Simple JSON highlighting
        html = html.replace(/"([^"]+)":/g, '<span style="color: #a78bfa">"$1"</span>:');
        html = html.replace(/: "([^"]+)"/g, ': <span style="color: #86efac">"$1"</span>');
        html = html.replace(/: (\d+)/g, ': <span style="color: #fbbf24">$1</span>');
        html = html.replace(/: (true|false|null)/g, ': <span style="color: #fb923c">$1</span>');

        block.innerHTML = html;
    });

    document.querySelectorAll('code.language-bash, code.language-shell').forEach(block => {
        let html = block.innerHTML;

        // Simple bash highlighting
        html = html.replace(/^(\$|#)/gm, '<span style="color: #60a5fa">$1</span>');
        html = html.replace(/(curl|git|npm|pip|python|node)/g, '<span style="color: #c084fc">$1</span>');
        html = html.replace(/--?[a-zA-Z-]+/g, '<span style="color: #fbbf24">$&</span>');
        html = html.replace(/"([^"]+)"/g, '<span style="color: #86efac">"$1"</span>');

        block.innerHTML = html;
    });

    document.querySelectorAll('code.language-python').forEach(block => {
        let html = block.innerHTML;

        // Simple Python highlighting
        html = html.replace(/\b(import|from|as|def|class|if|else|elif|for|while|return|try|except|with|async|await)\b/g, '<span style="color: #c084fc">$1</span>');
        html = html.replace(/\b(True|False|None)\b/g, '<span style="color: #fb923c">$1</span>');
        html = html.replace(/"([^"]+)"/g, '<span style="color: #86efac">"$1"</span>');
        html = html.replace(/'([^']+)'/g, '<span style="color: #86efac">\'$1\'</span>');
        html = html.replace(/#.+$/gm, '<span style="color: #6b7280">$&</span>');

        block.innerHTML = html;
    });

    document.querySelectorAll('code.language-javascript').forEach(block => {
        let html = block.innerHTML;

        // Simple JavaScript highlighting
        html = html.replace(/\b(const|let|var|function|async|await|return|if|else|for|while|class|import|export|from|new)\b/g, '<span style="color: #c084fc">$1</span>');
        html = html.replace(/\b(true|false|null|undefined)\b/g, '<span style="color: #fb923c">$1</span>');
        html = html.replace(/"([^"]+)"/g, '<span style="color: #86efac">"$1"</span>');
        html = html.replace(/'([^']+)'/g, '<span style="color: #86efac">\'$1\'</span>');
        html = html.replace(/`([^`]+)`/g, '<span style="color: #86efac">`$1`</span>');
        html = html.replace(/\/\/.+$/gm, '<span style="color: #6b7280">$&</span>');

        block.innerHTML = html;
    });
}

// Run on page load
document.addEventListener('DOMContentLoaded', highlightCode);

// ============================================================================
// Mobile Menu Toggle (Future Feature)
// ============================================================================
function toggleMobileMenu() {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
        sidebar.classList.toggle('mobile-open');
    }
}

// ============================================================================
// Search Functionality (Placeholder for Future)
// ============================================================================
function initSearch() {
    // Future: Implement fuzzy search across all documentation
    // Future: Index all endpoints, parameters, and content
    console.log('Search functionality coming soon');
}

// ============================================================================
// Analytics Event Tracking (Optional)
// ============================================================================
function trackEvent(category, action, label) {
    // Future: Integration with analytics
    if (window.gtag) {
        window.gtag('event', action, {
            'event_category': category,
            'event_label': label
        });
    }
}

// Track code copy events
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const codeBlock = btn.closest('.code-block');
            const language = codeBlock.querySelector('code').className.replace('language-', '');
            trackEvent('Code', 'Copy', language);
        });
    });
});

// ============================================================================
// Dark Mode Toggle (Future Feature)
// ============================================================================
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('darkMode', isDark);
    trackEvent('Preferences', 'Toggle Dark Mode', isDark ? 'On' : 'Off');
}

// Load dark mode preference
document.addEventListener('DOMContentLoaded', () => {
    const darkMode = localStorage.getItem('darkMode') === 'true';
    if (darkMode) {
        document.body.classList.add('dark-mode');
    }
});

// ============================================================================
// Endpoint Collapsible (Optional Enhancement)
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.endpoint-header').forEach(header => {
        header.addEventListener('click', () => {
            const card = header.closest('.endpoint-card');
            const body = card.querySelector('.endpoint-body');

            if (body && body.children.length > 0) {
                card.classList.toggle('collapsed');
                // Future: Add collapse animation
            }
        });
    });
});

// ============================================================================
// Table of Contents Generator (Auto-generate from headings)
// ============================================================================
function generateTableOfContents() {
    const toc = document.getElementById('table-of-contents');
    if (!toc) return;

    const headings = document.querySelectorAll('.main-content h2, .main-content h3');
    const tocList = document.createElement('ul');

    headings.forEach(heading => {
        const id = heading.id || heading.textContent.toLowerCase().replace(/\s+/g, '-');
        heading.id = id;

        const li = document.createElement('li');
        const a = document.createElement('a');
        a.href = `#${id}`;
        a.textContent = heading.textContent;
        a.className = heading.tagName === 'H2' ? 'toc-h2' : 'toc-h3';

        li.appendChild(a);
        tocList.appendChild(li);
    });

    toc.appendChild(tocList);
}

// ============================================================================
// Print Optimization
// ============================================================================
window.addEventListener('beforeprint', () => {
    // Expand all collapsed sections before printing
    document.querySelectorAll('.endpoint-card.collapsed').forEach(card => {
        card.classList.remove('collapsed');
    });
});

// ============================================================================
// Performance Monitoring
// ============================================================================
if (window.performance && window.performance.timing) {
    window.addEventListener('load', () => {
        const timing = window.performance.timing;
        const loadTime = timing.loadEventEnd - timing.navigationStart;
        console.log(`Page load time: ${loadTime}ms`);
        trackEvent('Performance', 'Page Load', `${loadTime}ms`);
    });
}

// ============================================================================
// Export for potential module usage
// ============================================================================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        switchTab,
        copyCode,
        toggleDarkMode,
        trackEvent
    };
}

// ============================================================================
// Console Welcome Message
// ============================================================================
console.log(
    '%c🚀 WebOps API Documentation',
    'font-size: 20px; font-weight: bold; color: #667eea;'
);
console.log(
    '%cBuilt with ❤️ for developers',
    'font-size: 12px; color: #6b7280;'
);
console.log('');
console.log('Found a bug? Report it: https://github.com/webops/webops/issues');
console.log('Need help? Visit: https://docs.webops.dev');
