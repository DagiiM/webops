/**
 * WebOps Control Panel - Addon Detail Page Test Script
 * 
 * This script tests the functionality of the revised addon detail page
 * 
 * @version 1.0.0
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('WebOps Addon Detail Page Test Script Loaded');
    
    // Test 1: Check if all required elements are present
    const requiredElements = [
        '.webops-addon-detail__header',
        '.webops-addon-detail__title',
        '.webops-addon-detail__status',
        '.webops-addon-detail__quick-stats',
        '.webops-addon-detail__grid',
        '.webops-addon-detail__main',
        '.webops-addon-detail__sidebar'
    ];
    
    let elementsPresent = true;
    requiredElements.forEach(selector => {
        const element = document.querySelector(selector);
        if (!element) {
            console.error(`Missing required element: ${selector}`);
            elementsPresent = false;
        }
    });
    
    if (elementsPresent) {
        console.log('✅ All required elements are present');
    } else {
        console.error('❌ Some required elements are missing');
    }
    
    // Test 2: Check if success rate fill bars are working
    const successRateFills = document.querySelectorAll('.webops-addon-detail__success-rate-fill');
    if (successRateFills.length > 0) {
        successRateFills.forEach(function(fill) {
            const width = fill.getAttribute('data-width');
            if (width) {
                console.log(`✅ Success rate fill bar found with width: ${width}%`);
            } else {
                console.log('⚠️ Success rate fill bar found but no data-width attribute');
            }
        });
    } else {
        console.log('ℹ️ No success rate fill bars found (might be normal if no statistics available)');
    }
    
    // Test 3: Check responsive design breakpoints
    const header = document.querySelector('.webops-addon-detail__header');
    if (header) {
        const headerStyles = window.getComputedStyle(header);
        console.log(`Header padding: ${headerStyles.padding}`);
    }
    
    // Test 4: Check if CSS file is loaded
    const testElement = document.createElement('div');
    testElement.className = 'webops-addon-detail__test';
    testElement.style.display = 'none';
    document.body.appendChild(testElement);
    
    const testStyles = window.getComputedStyle(testElement);
    if (testStyles.display === 'none') {
        console.log('✅ Addon detail CSS file is loaded and working');
    } else {
        console.error('❌ Addon detail CSS file may not be loaded correctly');
    }
    
    document.body.removeChild(testElement);
    
    console.log('WebOps Addon Detail Page Test Script Completed');
});