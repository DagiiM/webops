/* Moved from templates/core/branding_settings.html (ui-skill rule 17: no inline <script>). */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize color engine
    const colorEngine = new WebOpsColorEngine();

    // Theme card click handlers
    document.querySelectorAll('.webops-theme-card').forEach(card => {
        card.addEventListener('click', function() {
            const theme = this.dataset.theme;

            // Update the theme preset select
            const themeSelect = document.getElementById('id_theme_preset');
            if (themeSelect) {
                themeSelect.value = theme;

                // Trigger change event to apply the theme
                const changeEvent = new Event('change', { bubbles: true });
                themeSelect.dispatchEvent(changeEvent);
            }

            // Update visual selection
            document.querySelectorAll('.webops-theme-card').forEach(c => c.classList.remove('selected'));
            this.classList.add('selected');
        });
    });

    // Initialize theme card selection based on current value
    function updateThemeCardSelection() {
        const currentTheme = document.getElementById('id_theme_preset')?.value || 'custom';
        document.querySelectorAll('.webops-theme-card').forEach(card => {
            card.classList.toggle('selected', card.dataset.theme === currentTheme);
        });
    }

    // Call on page load
    updateThemeCardSelection();

    // Update selection when theme preset changes
    document.getElementById('id_theme_preset')?.addEventListener('change', updateThemeCardSelection);

    // Get form elements
    const themePresetSelect = document.getElementById('id_theme_preset');
    const hueInput = document.getElementById('id_primary_hue');
    const saturationInput = document.getElementById('id_primary_saturation');
    const lightnessInput = document.getElementById('id_primary_lightness');
    const harmonySelect = document.getElementById('id_color_harmony');
    const wcagAACheckbox = document.getElementById('id_enforce_wcag_aa');
    const wcagAAACheckbox = document.getElementById('id_enforce_wcag_aaa');
    const darkModeCheckbox = document.getElementById('id_supports_dark_mode');

    // Get generated color inputs
    const primaryColorInput = document.getElementById('id_primary_color');
    const secondaryColorInput = document.getElementById('id_secondary_color');
    const accentColorInput = document.getElementById('id_accent_color');
    const headerBgColorInput = document.getElementById('id_header_bg_color');

    // Get preview elements
    const colorScales = document.getElementById('colorScales');
    const contrastChecks = document.getElementById('contrastChecks');
    const simulationGrid = document.getElementById('simulationGrid');
    const previewInterface = document.getElementById('previewInterface');

    // Theme preset definitions
    const themePresets = {
        'forest': {
            primary_hue: 142,
            primary_saturation: 71,
            primary_lightness: 45,
            color_harmony: 'analogous',
            supports_dark_mode: true,
            accent_color: '#8B5A2B',
            header_bg_color: '#2D5016',
        },
        'ocean': {
            primary_hue: 200,
            primary_saturation: 85,
            primary_lightness: 50,
            color_harmony: 'complementary',
            supports_dark_mode: true,
            accent_color: '#20B2AA',
            header_bg_color: '#1E3A8A',
        },
        'dark': {
            primary_hue: 220,
            primary_saturation: 25,
            primary_lightness: 65,
            color_harmony: 'monochromatic',
            supports_dark_mode: true,
            accent_color: '#374151',
            header_bg_color: '#111827',
        },
        'premium': {
            primary_hue: 260,
            primary_saturation: 95,
            primary_lightness: 40,
            color_harmony: 'triadic',
            supports_dark_mode: true,
            accent_color: '#F59E0B',
            header_bg_color: '#1F2937',
            enforce_wcag_aaa: true,
        }
    };

    // Apply theme preset
    function applyThemePreset(presetName) {
        if (presetName === 'custom') return;

        const preset = themePresets[presetName];
        if (!preset) return;

        // Update form values
        hueInput.value = preset.primary_hue;
        saturationInput.value = preset.primary_saturation;
        lightnessInput.value = preset.primary_lightness;
        harmonySelect.value = preset.color_harmony;
        darkModeCheckbox.checked = preset.supports_dark_mode;

        if (preset.enforce_wcag_aaa) {
            wcagAAACheckbox.checked = true;
        }

        // Update colors and preview
        updateColorsAndPreview();
    }

    // Theme preset change handler
    themePresetSelect.addEventListener('change', function() {
        applyThemePreset(this.value);
    });

    // Update colors and preview
    function updateColorsAndPreview() {
        const hue = parseInt(hueInput.value) || 220;
        const saturation = parseInt(saturationInput.value) || 85;
        const lightness = parseInt(lightnessInput.value) || 50;
        const harmony = harmonySelect.value || 'monochromatic';

        // Generate palette
        const palette = colorEngine.generateColorPalette(hue, saturation, lightness, harmony);

        // Apply theme-specific accent and header colors if not custom
        const selectedTheme = themePresetSelect.value;
        if (selectedTheme !== 'custom' && themePresets[selectedTheme]) {
            const preset = themePresets[selectedTheme];
            accentColorInput.value = preset.accent_color;
            headerBgColorInput.value = preset.header_bg_color;
        } else {
            // Use generated colors for custom theme
            accentColorInput.value = palette.success['400'];
            headerBgColorInput.value = palette.neutral['800'];
        }

        // Update generated color inputs
        primaryColorInput.value = palette.primary['400'];
        secondaryColorInput.value = palette.secondary['400'];

        // Update CSS custom properties for live preview
        updateCSSVariables(palette);

        // Update preview panels
        updateColorScalesPreview(palette);
        updateAccessibilityReport(palette);
        updateColorBlindnessSimulation(palette);
        updateSliderBackgrounds(hue, saturation, lightness);
    }

    function updateCSSVariables(palette) {
        const root = document.documentElement;

        // Update primary colors
        Object.entries(palette.primary).forEach(([shade, color]) => {
            root.style.setProperty(`--webops-color-primary-${shade}`, color);
        });

        // Update main color variables
        root.style.setProperty('--webops-color-primary', palette.primary['400']);
        root.style.setProperty('--webops-color-secondary', palette.secondary['400']);
        root.style.setProperty('--webops-color-accent', palette.success['400']);
        root.style.setProperty('--webops-header-bg', palette.neutral['800']);
    }

    function updateColorScalesPreview(palette) {
        colorScales.innerHTML = '';

        Object.entries(palette).forEach(([colorName, colorScale]) => {
            if (typeof colorScale === 'object') {
                const scaleDiv = document.createElement('div');
                scaleDiv.className = 'webops-color-scale';
                scaleDiv.innerHTML = `<div class="webops-s-4e9010c">${colorName}</div>`;

                Object.entries(colorScale).forEach(([shade, hexValue]) => {
                    const swatch = document.createElement('div');
                    swatch.className = 'webops-color-swatch';
                    swatch.style.backgroundColor = hexValue;
                    swatch.textContent = shade;

                    // Use optimal text color
                    const textColor = colorEngine.getOptimalTextColor(hexValue);
                    swatch.style.color = textColor;

                    scaleDiv.appendChild(swatch);
                });

                colorScales.appendChild(scaleDiv);
            }
        });
    }

    function updateAccessibilityReport(palette) {
        contrastChecks.innerHTML = '';

        const enforceAA = wcagAACheckbox.checked;
        const enforceAAA = wcagAAACheckbox.checked;

        const testCombinations = [
            { fg: palette.primary['400'], bg: '#ffffff', name: 'Primary on White' },
            { fg: palette.primary['400'], bg: '#000000', name: 'Primary on Black' },
            { fg: '#ffffff', bg: palette.primary['400'], name: 'White on Primary' },
            { fg: '#000000', bg: palette.primary['400'], name: 'Black on Primary' },
            { fg: palette.secondary['400'], bg: '#ffffff', name: 'Secondary on White' },
            { fg: '#ffffff', bg: palette.neutral['800'], name: 'White on Header' }
        ];

        testCombinations.forEach(combo => {
            const result = colorEngine.validateAccessibility(combo.fg, combo.bg);

            // Determine grade based on enforcement settings
            let grade = 'fail';
            if (result.ratio >= 7) {
                grade = 'aaa';
            } else if (result.ratio >= 4.5) {
                grade = 'aa';
            }

            // Override grade if enforcement is enabled and requirements not met
            if (enforceAAA && result.ratio < 7) {
                grade = 'fail';
            } else if (enforceAA && result.ratio < 4.5) {
                grade = 'fail';
            }

            const checkDiv = document.createElement('div');
            checkDiv.className = 'webops-contrast-check';
            checkDiv.innerHTML = `
                <span>${combo.name}</span>
                <div>
                    <span class="webops-contrast-ratio">${result.ratio.toFixed(2)}:1</span>
                    <span class="webops-contrast-grade ${grade}">${grade.toUpperCase()}</span>
                </div>
            `;

            contrastChecks.appendChild(checkDiv);
        });
    }

    function updateColorBlindnessSimulation(palette) {
        simulationGrid.innerHTML = '';

        const colors = [
            { color: palette.primary['400'], name: 'Primary' },
            { color: palette.secondary['400'], name: 'Secondary' },
            { color: palette.success['400'], name: 'Accent' }
        ];

        const simulations = [
            { type: 'normal', name: 'Normal' },
            { type: 'protanopia', name: 'Protanopia' },
            { type: 'deuteranopia', name: 'Deuteranopia' },
            { type: 'tritanopia', name: 'Tritanopia' }
        ];

        simulations.forEach(sim => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'webops-simulation-item';

            let swatchesHtml = '';
            colors.forEach(({ color, name }) => {
                const simulatedColor = sim.type === 'normal' ? color : 
                                     colorEngine.simulateColorBlindness(color, sim.type);

                swatchesHtml += `<div class="webops-mini-swatch" data-swatch="${simulatedColor}" title="${name}"></div>`;
            });

            itemDiv.innerHTML = `
                <div class="webops-simulation-swatches">${swatchesHtml}</div>
                <div class="webops-simulation-label">${sim.name}</div>
            `;

            // Colour applied through the CSSOM: style="" attributes are blocked by a strict CSP
            itemDiv.querySelectorAll('[data-swatch]').forEach(el => {
                el.style.backgroundColor = el.getAttribute('data-swatch');
            });

            simulationGrid.appendChild(itemDiv);
        });
    }

    function updateSliderBackgrounds(hue, saturation, lightness) {
        const saturationSlider = document.getElementById('saturationSlider');
        const lightnessSlider = document.getElementById('lightnessSlider');

        // Update saturation slider background
        saturationSlider.style.background = `hsl(${hue}, ${saturation}%, ${lightness}%)`;

        // Update lightness slider background
        lightnessSlider.style.background = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
    }

    // Event listeners
    [hueInput, saturationInput, lightnessInput, harmonySelect].forEach(element => {
        element.addEventListener('input', updateColorsAndPreview);
    });

    // Reset button functionality
    const resetBtn = document.getElementById('resetBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', async function() {
            if (!confirm('Are you sure you want to reset branding to default values? This will reload the page.')) {
                return;
            }

            try {
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
                const response = await fetch(webopsPage().urlReset, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'Content-Type': 'application/json',
                    },
                });

                if (response.ok) {
                    window.location.reload();
                } else {
                    alert('Failed to reset branding settings');
                }
            } catch (error) {
                console.error('Error resetting branding:', error);
                alert('An error occurred while resetting branding settings');
            }
        });
    }

    // Initial update
    updateColorsAndPreview();
});
