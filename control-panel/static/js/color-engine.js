/**
 * WebOps Color Engine
 * 
 * Vanilla JavaScript color manipulation, palette generation, and accessibility validation.
 * Provides HSL-based color generation with WCAG compliance checking.
 * 
 * @author Douglas Mutethia <support@ifinsta.com>
 * @version 1.0.0
 */

class WebOpsColorEngine {
    /**
     * Initialize the color engine with default settings.
     */
    constructor() {
        this.colorHarmonySchemes = {
            monochromatic: 'Monochromatic',
            complementary: 'Complementary', 
            triadic: 'Triadic',
            analogous: 'Analogous',
            split_complementary: 'Split Complementary'
        };
        
        this.wcagLevels = {
            AA_NORMAL: 4.5,
            AA_LARGE: 3.0,
            AAA_NORMAL: 7.0,
            AAA_LARGE: 4.5
        };
    }

    /**
     * Convert HSL values to hex color.
     * 
     * @param {number} h - Hue (0-360)
     * @param {number} s - Saturation (0-100)
     * @param {number} l - Lightness (0-100)
     * @returns {string} Hex color string (#RRGGBB)
     */
    hslToHex(h, s, l) {
        // Normalize values
        h = h / 360;
        s = s / 100;
        l = l / 100;

        const hueToRgb = (p, q, t) => {
            if (t < 0) t += 1;
            if (t > 1) t -= 1;
            if (t < 1/6) return p + (q - p) * 6 * t;
            if (t < 1/2) return q;
            if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
            return p;
        };

        let r, g, b;

        if (s === 0) {
            r = g = b = l; // achromatic
        } else {
            const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
            const p = 2 * l - q;
            r = hueToRgb(p, q, h + 1/3);
            g = hueToRgb(p, q, h);
            b = hueToRgb(p, q, h - 1/3);
        }

        // Convert to hex
        const toHex = (c) => {
            const hex = Math.round(c * 255).toString(16);
            return hex.length === 1 ? '0' + hex : hex;
        };

        return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
    }

    /**
     * Convert hex color to HSL values.
     * 
     * @param {string} hex - Hex color string (#RRGGBB)
     * @returns {Object} HSL object {h, s, l}
     */
    hexToHsl(hex) {
        // Remove # if present
        hex = hex.replace('#', '');
        
        // Convert to RGB
        const r = parseInt(hex.substr(0, 2), 16) / 255;
        const g = parseInt(hex.substr(2, 2), 16) / 255;
        const b = parseInt(hex.substr(4, 2), 16) / 255;

        const max = Math.max(r, g, b);
        const min = Math.min(r, g, b);
        let h, s, l = (max + min) / 2;

        if (max === min) {
            h = s = 0; // achromatic
        } else {
            const d = max - min;
            s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
            
            switch (max) {
                case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                case g: h = (b - r) / d + 2; break;
                case b: h = (r - g) / d + 4; break;
            }
            h /= 6;
        }

        return {
            h: Math.round(h * 360),
            s: Math.round(s * 100),
            l: Math.round(l * 100)
        };
    }

    /**
     * Generate a color scale with multiple lightness variants.
     * 
     * @param {number} hue - Base hue (0-360)
     * @param {number} saturation - Base saturation (0-100)
     * @param {number} baseLightness - Base lightness (0-100)
     * @returns {Object} Color scale object with shade names as keys
     */
    generateColorScale(hue, saturation, baseLightness) {
        const scale = {};
        const lightnessValues = [95, 85, 75, 65, baseLightness, 45, 35, 25, 15];
        const shadeNames = ['50', '100', '200', '300', '400', '500', '600', '700', '800'];

        for (let i = 0; i < lightnessValues.length; i++) {
            scale[shadeNames[i]] = this.hslToHex(hue, saturation, lightnessValues[i]);
        }

        return scale;
    }

    /**
     * Generate color palette based on harmony scheme.
     * 
     * @param {number} baseHue - Base hue (0-360)
     * @param {number} baseSaturation - Base saturation (0-100)
     * @param {number} baseLightness - Base lightness (0-100)
     * @param {string} harmonyScheme - Color harmony scheme
     * @returns {Object} Complete color palette
     */
    generateColorPalette(baseHue, baseSaturation, baseLightness, harmonyScheme = 'monochromatic') {
        const palette = {
            primary: this.generateColorScale(baseHue, baseSaturation, baseLightness),
            secondary: this.generateColorScale(baseHue, baseSaturation, Math.max(20, baseLightness - 25))
        };

        // Add harmony colors based on scheme
        switch (harmonyScheme) {
            case 'complementary':
                const compHue = (baseHue + 180) % 360;
                palette.complementary = this.generateColorScale(compHue, baseSaturation, baseLightness);
                break;
                
            case 'triadic':
                palette.triadic_1 = this.generateColorScale((baseHue + 120) % 360, baseSaturation, baseLightness);
                palette.triadic_2 = this.generateColorScale((baseHue + 240) % 360, baseSaturation, baseLightness);
                break;
                
            case 'analogous':
                palette.analogous_1 = this.generateColorScale((baseHue + 30) % 360, baseSaturation, baseLightness);
                palette.analogous_2 = this.generateColorScale((baseHue - 30 + 360) % 360, baseSaturation, baseLightness);
                break;
                
            case 'split_complementary':
                palette.split_comp_1 = this.generateColorScale((baseHue + 150) % 360, baseSaturation, baseLightness);
                palette.split_comp_2 = this.generateColorScale((baseHue + 210) % 360, baseSaturation, baseLightness);
                break;
        }

        // Add semantic colors
        palette.success = this.generateColorScale(142, 71, 45);  // Green
        palette.warning = this.generateColorScale(38, 92, 50);   // Orange
        palette.error = this.generateColorScale(0, 84, 60);      // Red
        palette.info = this.generateColorScale(200, 98, 39);     // Light blue

        // Add neutral grays
        palette.neutral = this.generateColorScale(220, 13, 50);

        return palette;
    }

    /**
     * Calculate relative luminance of a color.
     * 
     * @param {string} hexColor - Hex color string
     * @returns {number} Relative luminance (0-1)
     */
    getLuminance(hexColor) {
        // Remove # and convert to RGB
        hexColor = hexColor.replace('#', '');
        const r = parseInt(hexColor.substr(0, 2), 16);
        const g = parseInt(hexColor.substr(2, 2), 16);
        const b = parseInt(hexColor.substr(4, 2), 16);

        // Convert to relative luminance
        const toLinear = (c) => {
            c = c / 255;
            return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        };

        const rLin = toLinear(r);
        const gLin = toLinear(g);
        const bLin = toLinear(b);

        return 0.2126 * rLin + 0.7152 * gLin + 0.0722 * bLin;
    }

    /**
     * Calculate WCAG contrast ratio between two colors.
     * 
     * @param {string} color1 - First hex color
     * @param {string} color2 - Second hex color
     * @returns {number} Contrast ratio (1-21)
     */
    getContrastRatio(color1, color2) {
        const lum1 = this.getLuminance(color1);
        const lum2 = this.getLuminance(color2);

        // Ensure lighter color is numerator
        const lighter = Math.max(lum1, lum2);
        const darker = Math.min(lum1, lum2);

        return (lighter + 0.05) / (darker + 0.05);
    }

    /**
     * Validate color accessibility against WCAG standards.
     * 
     * @param {string} foreground - Foreground color hex
     * @param {string} background - Background color hex
     * @returns {Object} Accessibility validation results
     */
    validateAccessibility(foreground, background) {
        const ratio = this.getContrastRatio(foreground, background);

        return {
            ratio: Math.round(ratio * 100) / 100,
            aa_normal: ratio >= this.wcagLevels.AA_NORMAL,
            aa_large: ratio >= this.wcagLevels.AA_LARGE,
            aaa_normal: ratio >= this.wcagLevels.AAA_NORMAL,
            aaa_large: ratio >= this.wcagLevels.AAA_LARGE,
            grade: this.getAccessibilityGrade(ratio)
        };
    }

    /**
     * Get accessibility grade based on contrast ratio.
     * 
     * @param {number} ratio - Contrast ratio
     * @returns {string} Accessibility grade (AAA, AA, or Fail)
     */
    getAccessibilityGrade(ratio) {
        if (ratio >= this.wcagLevels.AAA_NORMAL) return 'AAA';
        if (ratio >= this.wcagLevels.AA_NORMAL) return 'AA';
        return 'Fail';
    }

    /**
     * Simulate color blindness for accessibility testing.
     * 
     * @param {string} hexColor - Original hex color
     * @param {string} type - Type of color blindness (protanopia, deuteranopia, tritanopia)
     * @returns {string} Simulated hex color
     */
    simulateColorBlindness(hexColor, type) {
        // Convert hex to RGB
        hexColor = hexColor.replace('#', '');
        let r = parseInt(hexColor.substr(0, 2), 16) / 255;
        let g = parseInt(hexColor.substr(2, 2), 16) / 255;
        let b = parseInt(hexColor.substr(4, 2), 16) / 255;

        // Apply color blindness transformation matrices
        let newR, newG, newB;

        switch (type) {
            case 'protanopia': // Red-blind
                newR = 0.567 * r + 0.433 * g;
                newG = 0.558 * r + 0.442 * g;
                newB = 0.242 * g + 0.758 * b;
                break;
                
            case 'deuteranopia': // Green-blind
                newR = 0.625 * r + 0.375 * g;
                newG = 0.7 * r + 0.3 * g;
                newB = 0.3 * g + 0.7 * b;
                break;
                
            case 'tritanopia': // Blue-blind
                newR = 0.95 * r + 0.05 * g;
                newG = 0.433 * g + 0.567 * b;
                newB = 0.475 * g + 0.525 * b;
                break;
                
            default:
                return hexColor;
        }

        // Convert back to hex
        const toHex = (c) => {
            const hex = Math.round(Math.max(0, Math.min(255, c * 255))).toString(16);
            return hex.length === 1 ? '0' + hex : hex;
        };

        return `#${toHex(newR)}${toHex(newG)}${toHex(newB)}`;
    }

    /**
     * Validates WCAG accessibility compliance for a color palette
     * @param {Object} palette - Color palette object
     * @param {boolean} enforceAA - Whether to enforce WCAG AA compliance
     * @param {boolean} enforceAAA - Whether to enforce WCAG AAA compliance
     * @returns {Object} Accessibility validation report
     */
    validatePaletteAccessibility(palette, enforceAA = true, enforceAAA = false) {
        const report = {
            overall: 'pass',
            issues: [],
            warnings: [],
            recommendations: [],
            contrasts: {}
        };

        const minContrastAA = 4.5;
        const minContrastAAA = 7.0;
        const minContrastLargeAA = 3.0;
        const minContrastLargeAAA = 4.5;

        const backgrounds = ['#ffffff', '#000000'];
        const testColors = [
            { name: 'Primary', color: palette.primary?.['500'] },
            { name: 'Secondary', color: palette.secondary?.['500'] },
            { name: 'Success', color: palette.success?.['500'] },
            { name: 'Warning', color: palette.warning?.['500'] },
            { name: 'Error', color: palette.error?.['500'] },
            { name: 'Info', color: palette.info?.['500'] }
        ];

        testColors.forEach(({ name, color }) => {
            if (!color) return;

            report.contrasts[name] = {};

            backgrounds.forEach(bg => {
                const bgName = bg === '#ffffff' ? 'white' : 'black';
                const contrast = this.getContrastRatio(color, bg);
                
                report.contrasts[name][bgName] = {
                    ratio: contrast,
                    aa: contrast >= minContrastAA,
                    aaa: contrast >= minContrastAAA,
                    aaLarge: contrast >= minContrastLargeAA,
                    aaaLarge: contrast >= minContrastLargeAAA
                };

                // Check compliance
                if (enforceAA && contrast < minContrastAA) {
                    report.issues.push({
                        type: 'contrast',
                        severity: 'error',
                        color: name,
                        background: bgName,
                        ratio: contrast,
                        required: minContrastAA,
                        standard: 'WCAG AA'
                    });
                    report.overall = 'fail';
                }

                if (enforceAAA && contrast < minContrastAAA) {
                    report.issues.push({
                        type: 'contrast',
                        severity: 'error',
                        color: name,
                        background: bgName,
                        ratio: contrast,
                        required: minContrastAAA,
                        standard: 'WCAG AAA'
                    });
                    report.overall = 'fail';
                }

                // Add warnings for borderline cases
                if (contrast >= minContrastAA && contrast < minContrastAAA) {
                    report.warnings.push({
                        type: 'contrast',
                        severity: 'warning',
                        color: name,
                        background: bgName,
                        ratio: contrast,
                        message: 'Meets AA but not AAA standards'
                    });
                }
            });
        });

        // Add recommendations
        if (report.issues.length > 0) {
            report.recommendations.push('Consider adjusting color lightness to improve contrast ratios');
            report.recommendations.push('Test with actual text content and font sizes');
            report.recommendations.push('Consider providing alternative high-contrast theme');
        }

        if (report.warnings.length > 0) {
            report.recommendations.push('Consider enhancing contrast for better accessibility');
        }

        return report;
    }

    /**
     * Generates accessibility-compliant text colors for backgrounds
     * @param {string} backgroundColor - Background color hex
     * @param {boolean} enforceAAA - Whether to enforce AAA compliance
     * @returns {Object} Text color recommendations
     */
    getAccessibleTextColors(backgroundColor, enforceAAA = false) {
        const minContrast = enforceAAA ? 7.0 : 4.5;
        const whiteContrast = this.getContrastRatio('#ffffff', backgroundColor);
        const blackContrast = this.getContrastRatio('#000000', backgroundColor);

        const result = {
            primary: whiteContrast >= blackContrast ? '#ffffff' : '#000000',
            white: {
                color: '#ffffff',
                contrast: whiteContrast,
                compliant: whiteContrast >= minContrast
            },
            black: {
                color: '#000000',
                contrast: blackContrast,
                compliant: blackContrast >= minContrast
            },
            recommended: null
        };

        // If neither white nor black is compliant, generate a compliant color
        if (!result.white.compliant && !result.black.compliant) {
            const hsl = this.hexToHsl(backgroundColor);
            if (hsl) {
                // Try lighter version
                const lighterColor = this.hslToHex(hsl.h, hsl.s, Math.min(100, hsl.l + 30));
                const lighterContrast = this.getContrastRatio(lighterColor, backgroundColor);
                
                // Try darker version
                const darkerColor = this.hslToHex(hsl.h, hsl.s, Math.max(0, hsl.l - 30));
                const darkerContrast = this.getContrastRatio(darkerColor, backgroundColor);

                if (lighterContrast >= minContrast) {
                    result.recommended = {
                        color: lighterColor,
                        contrast: lighterContrast,
                        type: 'lighter'
                    };
                } else if (darkerContrast >= minContrast) {
                    result.recommended = {
                        color: darkerColor,
                        contrast: darkerContrast,
                        type: 'darker'
                    };
                }
            }
        }

        return result;
    }

    /**
     * Generates a comprehensive accessibility report for color blindness
     * @param {Object} palette - Color palette object
     * @returns {Object} Color blindness simulation report
     */
    generateColorBlindnessReport(palette) {
        const types = ['protanopia', 'deuteranopia', 'tritanopia'];
        const report = {
            simulations: {},
            issues: [],
            recommendations: []
        };

        const testColors = [
            { name: 'primary', color: palette.primary?.['500'] },
            { name: 'secondary', color: palette.secondary?.['500'] },
            { name: 'success', color: palette.success?.['500'] },
            { name: 'warning', color: palette.warning?.['500'] },
            { name: 'error', color: palette.error?.['500'] },
            { name: 'info', color: palette.info?.['500'] }
        ];

        types.forEach(type => {
            report.simulations[type] = {};
            
            testColors.forEach(({ name, color }) => {
                if (!color) return;
                
                const simulatedColor = this.simulateColorBlindness(color, type);
                report.simulations[type][name] = {
                    original: color,
                    simulated: simulatedColor,
                    changed: color.toLowerCase() !== simulatedColor.toLowerCase()
                };

                // Check if critical colors become too similar
                if (name === 'success' || name === 'error') {
                    const otherCritical = name === 'success' ? 'error' : 'success';
                    const otherColor = testColors.find(c => c.name === otherCritical)?.color;
                    
                    if (otherColor) {
                        const otherSimulated = this.simulateColorBlindness(otherColor, type);
                        const originalDiff = this.getColorDifference(color, otherColor);
                        const simulatedDiff = this.getColorDifference(simulatedColor, otherSimulated);
                        
                        if (simulatedDiff < originalDiff * 0.5) {
                            report.issues.push({
                                type: 'similarity',
                                colorBlindnessType: type,
                                colors: [name, otherCritical],
                                originalDifference: originalDiff,
                                simulatedDifference: simulatedDiff,
                                severity: 'high'
                            });
                        }
                    }
                }
            });
        });

        // Generate recommendations
        if (report.issues.length > 0) {
            report.recommendations.push('Consider using patterns, icons, or text labels in addition to color');
            report.recommendations.push('Ensure sufficient contrast between critical state colors');
            report.recommendations.push('Test with color blindness simulation tools');
        }

        report.recommendations.push('Use textures or patterns for data visualization');
        report.recommendations.push('Provide alternative color schemes for color blind users');

        return report;
    }

    /**
     * Calculates perceptual color difference
     * @param {string} color1 - First hex color
     * @param {string} color2 - Second hex color
     * @returns {number} Color difference value
     */
    getColorDifference(color1, color2) {
        const hsl1 = this.hexToHsl(color1);
        const hsl2 = this.hexToHsl(color2);
        
        if (!hsl1 || !hsl2) return 0;

        // Simple HSL distance calculation
        const deltaH = Math.abs(hsl1.h - hsl2.h);
        const deltaS = Math.abs(hsl1.s - hsl2.s);
        const deltaL = Math.abs(hsl1.l - hsl2.l);

        return Math.sqrt(deltaH * deltaH + deltaS * deltaS + deltaL * deltaL);
    }

    /**
     * Generate CSS custom properties from color palette.
     * 
     * @param {Object} palette - Color palette object
     * @returns {string} CSS custom properties string
     */
    generateCSSVariables(palette) {
        let css = ':root {\n';

        for (const [colorName, colorScale] of Object.entries(palette)) {
            if (typeof colorScale === 'object') {
                for (const [shade, hexValue] of Object.entries(colorScale)) {
                    css += `  --webops-color-${colorName}-${shade}: ${hexValue};\n`;
                }
            }
        }

        css += '}\n';
        return css;
    }

    /**
     * Get optimal text color (black or white) for a background.
     * 
     * @param {string} backgroundColor - Background hex color
     * @returns {string} Optimal text color (#000000 or #ffffff)
     */
    getOptimalTextColor(backgroundColor) {
        const whiteContrast = this.getContrastRatio(backgroundColor, '#ffffff');
        const blackContrast = this.getContrastRatio(backgroundColor, '#000000');
        
        return whiteContrast > blackContrast ? '#ffffff' : '#000000';
    }

    /**
     * Adjust color lightness to meet WCAG contrast requirements.
     * 
     * @param {string} color - Hex color to adjust
     * @param {string} background - Background hex color
     * @param {number} targetRatio - Target contrast ratio (default: 4.5)
     * @returns {string} Adjusted hex color
     */
    adjustForContrast(color, background, targetRatio = 4.5) {
        const hsl = this.hexToHsl(color);
        let { h, s, l } = hsl;
        
        // Try adjusting lightness in both directions
        const originalRatio = this.getContrastRatio(color, background);
        
        if (originalRatio >= targetRatio) {
            return color; // Already meets requirements
        }
        
        // Determine if we need to go lighter or darker
        const backgroundLum = this.getLuminance(background);
        const shouldGoDarker = backgroundLum > 0.5;
        
        let step = shouldGoDarker ? -5 : 5;
        let attempts = 0;
        const maxAttempts = 20;
        
        while (attempts < maxAttempts) {
            l = Math.max(0, Math.min(100, l + step));
            const adjustedColor = this.hslToHex(h, s, l);
            const newRatio = this.getContrastRatio(adjustedColor, background);
            
            if (newRatio >= targetRatio) {
                return adjustedColor;
            }
            
            attempts++;
        }
        
        // If we can't meet the ratio, return the best attempt
        return this.hslToHex(h, s, l);
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebOpsColorEngine;
} else if (typeof window !== 'undefined') {
    window.WebOpsColorEngine = WebOpsColorEngine;
}