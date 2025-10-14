/**
 * WebOps Responsive Tables Helper
 * Automatically detects table size and applies responsive layout
 */

(function() {
    'use strict';
    
    // Initialize when DOM is loaded
    document.addEventListener('DOMContentLoaded', function() {
        initResponsiveTables();
    });
    
    /**
     * Initialize responsive tables
     */
    function initResponsiveTables() {
        const tableContainers = document.querySelectorAll('.webops-table-responsive');
        
        if (tableContainers.length === 0) return;
        
        tableContainers.forEach(container => {
            // Add data-responsive attribute for CSS targeting
            container.setAttribute('data-responsive', 'auto');
            
            // Get the table element
            const table = container.querySelector('.webops-table');
            if (!table) return;
            
            // Add data-label attributes to table cells
            addDataLabels(table);
            
            // Check if table needs mobile layout
            checkTableLayout(container, table);
            
            // Listen for resize events
            window.addEventListener('resize', function() {
                checkTableLayout(container, table);
            });
        });
    }
    
    /**
     * Add data-label attributes to table cells based on column headers
     */
    function addDataLabels(table) {
        const headers = table.querySelectorAll('thead th');
        const rows = table.querySelectorAll('tbody tr');
        
        if (headers.length === 0 || rows.length === 0) return;
        
        // Create array of header texts
        const headerTexts = Array.from(headers).map(th => th.textContent.trim());
        
        // Add data-label to each cell
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            
            cells.forEach((cell, index) => {
                if (headerTexts[index]) {
                    cell.setAttribute('data-label', headerTexts[index]);
                }
            });
        });
    }
    
    /**
     * Check if table needs mobile layout based on container width
     */
    function checkTableLayout(container, table) {
        const containerWidth = container.offsetWidth;
        const tableWidth = table.scrollWidth;
        
        // If table is wider than container or container is very small, use mobile layout
        if (tableWidth > containerWidth || containerWidth < 480) {
            container.setAttribute('data-responsive', 'mobile');
        } else {
            container.setAttribute('data-responsive', 'desktop');
        }
    }
    
    /**
     * Manually force mobile layout on all tables
     */
    function forceMobileLayout() {
        const tableContainers = document.querySelectorAll('.webops-table-responsive');
        
        tableContainers.forEach(container => {
            container.setAttribute('data-responsive', 'mobile');
        });
    }
    
    /**
     * Manually force desktop layout on all tables
     */
    function forceDesktopLayout() {
        const tableContainers = document.querySelectorAll('.webops-table-responsive');
        
        tableContainers.forEach(container => {
            container.setAttribute('data-responsive', 'desktop');
        });
    }
    
    // Expose functions for manual control
    window.WebOps = window.WebOps || {};
    window.WebOps.ResponsiveTables = {
        init: initResponsiveTables,
        forceMobile: forceMobileLayout,
        forceDesktop: forceDesktopLayout
    };
})();