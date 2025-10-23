"""
Test suite for BrandingService.

Tests color conversion, palette generation, and accessibility validation.
"""

from django.test import TestCase

from apps.core.branding.services import BrandingService


class BrandingServiceColorTests(TestCase):
    """Test color conversion and manipulation."""

    def test_hsl_to_hex_blue(self):
        """Test HSL to hex conversion for blue."""
        # HSL(217, 91%, 60%) = #3b82f6 (Tailwind blue-500)
        result = BrandingService.hsl_to_hex(217, 91, 60)
        self.assertEqual(result.lower(), '#3b82f6')

    def test_hsl_to_hex_red(self):
        """Test HSL to hex conversion for red."""
        # HSL(0, 100%, 50%) = #ff0000 (pure red)
        result = BrandingService.hsl_to_hex(0, 100, 50)
        self.assertEqual(result.lower(), '#ff0000')

    def test_hsl_to_hex_green(self):
        """Test HSL to hex conversion for green."""
        # HSL(120, 100%, 50%) = #00ff00 (pure green)
        result = BrandingService.hsl_to_hex(120, 100, 50)
        self.assertEqual(result.lower(), '#00ff00')

    def test_hsl_to_hex_black(self):
        """Test HSL to hex conversion for black."""
        # HSL(0, 0%, 0%) = #000000 (black)
        result = BrandingService.hsl_to_hex(0, 0, 0)
        self.assertEqual(result.lower(), '#000000')

    def test_hsl_to_hex_white(self):
        """Test HSL to hex conversion for white."""
        # HSL(0, 0%, 100%) = #ffffff (white)
        result = BrandingService.hsl_to_hex(0, 0, 100)
        self.assertEqual(result.lower(), '#ffffff')

    def test_hsl_to_hex_gray(self):
        """Test HSL to hex conversion for gray."""
        # HSL(0, 0%, 50%) = #808080 (gray)
        result = BrandingService.hsl_to_hex(0, 0, 50)
        self.assertEqual(result.lower(), '#808080')


class BrandingServiceScaleTests(TestCase):
    """Test color scale generation."""

    def test_generate_color_scale(self):
        """Test generating a color scale."""
        scale = BrandingService.generate_color_scale(217, 91, 60)

        # Should return 9 shades
        self.assertEqual(len(scale), 9)

        # Should have keys 50-900
        expected_keys = ['50', '100', '200', '300', '400', '500', '600', '700', '800', '900']
        for key in expected_keys:
            self.assertIn(key, scale)

        # Each value should be a valid hex color
        for color in scale.values():
            self.assertTrue(color.startswith('#'))
            self.assertEqual(len(color), 7)

    def test_generate_color_scale_500_is_base(self):
        """Test that shade 500 matches the input color."""
        hue, sat, light = 217, 91, 60
        scale = BrandingService.generate_color_scale(hue, sat, light)

        base_color = BrandingService.hsl_to_hex(hue, sat, light)
        self.assertEqual(scale['500'].lower(), base_color.lower())

    def test_generate_color_scale_progression(self):
        """Test that scale progresses from light to dark."""
        scale = BrandingService.generate_color_scale(217, 91, 60)

        # Convert hex to RGB for comparison
        def hex_to_brightness(hex_color):
            """Calculate perceived brightness of hex color."""
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return (r * 299 + g * 587 + b * 114) / 1000

        # Brightness should decrease from 50 to 900
        brightness_50 = hex_to_brightness(scale['50'])
        brightness_900 = hex_to_brightness(scale['900'])

        self.assertGreater(brightness_50, brightness_900)


class BrandingServicePaletteTests(TestCase):
    """Test color palette generation."""

    def test_generate_analogous_palette(self):
        """Test analogous color harmony."""
        palette = BrandingService.generate_color_palette(
            hue=217,
            saturation=91,
            lightness=60,
            harmony='analogous'
        )

        self.assertIn('primary', palette)
        self.assertIn('secondary', palette)
        self.assertIn('accent', palette)

        # Each color should have a full scale
        for color_name in ['primary', 'secondary', 'accent']:
            self.assertEqual(len(palette[color_name]), 9)

    def test_generate_complementary_palette(self):
        """Test complementary color harmony."""
        palette = BrandingService.generate_color_palette(
            hue=217,
            saturation=91,
            lightness=60,
            harmony='complementary'
        )

        self.assertIn('primary', palette)
        self.assertIn('secondary', palette)

    def test_generate_triadic_palette(self):
        """Test triadic color harmony."""
        palette = BrandingService.generate_color_palette(
            hue=217,
            saturation=91,
            lightness=60,
            harmony='triadic'
        )

        self.assertIn('primary', palette)
        self.assertIn('secondary', palette)
        self.assertIn('accent', palette)

    def test_generate_monochromatic_palette(self):
        """Test monochromatic color harmony."""
        palette = BrandingService.generate_color_palette(
            hue=217,
            saturation=91,
            lightness=60,
            harmony='monochromatic'
        )

        self.assertIn('primary', palette)
        # Monochromatic uses same hue for all colors


class BrandingServiceAccessibilityTests(TestCase):
    """Test WCAG accessibility validation."""

    def test_get_contrast_ratio_high_contrast(self):
        """Test contrast ratio for high contrast colors."""
        # Black on white should have high contrast (21:1)
        ratio = BrandingService.get_contrast_ratio('#000000', '#ffffff')
        self.assertGreater(ratio, 20)

    def test_get_contrast_ratio_low_contrast(self):
        """Test contrast ratio for low contrast colors."""
        # Similar colors should have low contrast
        ratio = BrandingService.get_contrast_ratio('#cccccc', '#d0d0d0')
        self.assertLess(ratio, 2)

    def test_get_contrast_ratio_symmetry(self):
        """Test that contrast ratio is symmetric."""
        ratio1 = BrandingService.get_contrast_ratio('#000000', '#ffffff')
        ratio2 = BrandingService.get_contrast_ratio('#ffffff', '#000000')
        self.assertAlmostEqual(ratio1, ratio2, places=2)

    def test_validate_accessibility_pass_aa(self):
        """Test that high contrast passes WCAG AA."""
        result = BrandingService.validate_accessibility(
            foreground='#000000',
            background='#ffffff',
            level='AA'
        )

        self.assertTrue(result['passes_normal'])
        self.assertTrue(result['passes_large'])

    def test_validate_accessibility_fail_aa(self):
        """Test that low contrast fails WCAG AA."""
        result = BrandingService.validate_accessibility(
            foreground='#cccccc',
            background='#d0d0d0',
            level='AA'
        )

        self.assertFalse(result['passes_normal'])
        self.assertFalse(result['passes_large'])

    def test_validate_accessibility_aaa(self):
        """Test WCAG AAA validation."""
        # Black on white passes AAA
        result = BrandingService.validate_accessibility(
            foreground='#000000',
            background='#ffffff',
            level='AAA'
        )

        self.assertTrue(result['passes_normal'])
        self.assertTrue(result['passes_large'])


class BrandingServiceCSSTests(TestCase):
    """Test CSS variable generation."""

    def test_generate_css_variables_structure(self):
        """Test CSS variables generation structure."""
        # Create mock branding settings
        class MockBranding:
            primary_hue = 217
            primary_saturation = 91
            primary_lightness = 60
            color_harmony = 'analogous'
            font_family_base = 'Inter, sans-serif'
            font_size_base = 16

        css = BrandingService.generate_css_variables(MockBranding())

        # Should contain CSS custom properties
        self.assertIn('--primary-', css)
        self.assertIn(':root', css)

    def test_generate_css_variables_valid_css(self):
        """Test that generated CSS is valid."""
        class MockBranding:
            primary_hue = 217
            primary_saturation = 91
            primary_lightness = 60
            color_harmony = 'analogous'
            font_family_base = 'Inter, sans-serif'
            font_size_base = 16

        css = BrandingService.generate_css_variables(MockBranding())

        # Should have proper CSS structure
        self.assertTrue(css.strip().startswith(':root'))
        self.assertIn('{', css)
        self.assertIn('}', css)


class BrandingServiceThemePresetTests(TestCase):
    """Test theme preset application."""

    def test_apply_theme_preset_modern(self):
        """Test applying modern theme preset."""
        preset = BrandingService.apply_theme_preset('modern')

        self.assertIn('primary_hue', preset)
        self.assertIn('primary_saturation', preset)
        self.assertIn('primary_lightness', preset)

    def test_apply_theme_preset_classic(self):
        """Test applying classic theme preset."""
        preset = BrandingService.apply_theme_preset('classic')

        self.assertIsInstance(preset, dict)
        self.assertIn('primary_hue', preset)

    def test_apply_theme_preset_invalid(self):
        """Test applying invalid theme preset."""
        # Should return empty dict or raise error
        preset = BrandingService.apply_theme_preset('invalid')
        self.assertIsInstance(preset, dict)
