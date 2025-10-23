"""
Tests for branding domain.
"""

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from apps.core.branding.models import BrandingSettings
from apps.core.branding.services import BrandingService


class BrandingSettingsTests(TestCase):
    """Test BrandingSettings model."""

    def setUp(self):
        """Set up test data."""
        self.settings = BrandingSettings.get_settings()

    def test_singleton_pattern(self):
        """Test that only one BrandingSettings instance exists."""
        settings2 = BrandingSettings.get_settings()
        self.assertEqual(self.settings.pk, settings2.pk)

    def test_hsl_to_hex_conversion(self):
        """Test HSL to hex color conversion."""
        # Test blue
        hex_color = BrandingService.hsl_to_hex(210, 80, 50)
        self.assertEqual(hex_color, '#3399ff')

    def test_color_palette_generation(self):
        """Test color palette generation."""
        palette = BrandingService.generate_color_palette(210, 80, 50, 'monochromatic')
        self.assertIn('primary', palette)
        self.assertIn('secondary', palette)
        self.assertIn('success', palette)

    def test_wcag_contrast_validation(self):
        """Test WCAG contrast ratio validation."""
        # Test high contrast (black on white)
        results = BrandingService.validate_accessibility('#000000', '#ffffff')
        self.assertTrue(results['primary_aa_white'])
        self.assertTrue(results['primary_aaa_white'])

    def test_css_variable_generation(self):
        """Test CSS variable generation."""
        css_vars = BrandingService.generate_css_variables(self.settings)
        self.assertIn('--webops-hue-primary:', css_vars)
        self.assertIn('--webops-primary-400:', css_vars)
        self.assertIn('--webops-font-family-primary:', css_vars)

    def test_theme_presets(self):
        """Test theme preset application."""
        forest_preset = BrandingService.apply_theme_preset('forest')
        self.assertIn('primary_hue', forest_preset)
        self.assertEqual(forest_preset['primary_hue'], 142)

    def test_save_updates_colors(self):
        """Test that saving updates generated colors."""
        self.settings.primary_hue = 120  # Green
        self.settings.primary_saturation = 80
        self.settings.primary_lightness = 50
        self.settings.save()

        # Check that primary_color was updated
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.primary_color, '#00cc66')


class BrandingFormTests(TestCase):
    """Test BrandingSettingsForm."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_superuser=True
        )
        self.settings = BrandingSettings.get_settings()

    def test_form_valid_data(self):
        """Test form with valid data."""
        form_data = {
            'site_name': 'Test Site',
            'primary_hue': 200,
            'primary_saturation': 70,
            'primary_lightness': 50,
            'color_harmony': 'monochromatic',
        }
        form = BrandingSettingsForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_invalid_hue(self):
        """Test form with invalid hue value."""
        form_data = {
            'site_name': 'Test Site',
            'primary_hue': 400,  # Invalid: > 360
            'primary_saturation': 70,
            'primary_lightness': 50,
        }
        form = BrandingSettingsForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_logo_upload(self):
        """Test logo file upload validation."""
        # Valid small PNG
        logo = SimpleUploadedFile(
            "logo.png",
            b'\x89PNG\r\n\x1a\n' + b'\x00' * 100,  # Small PNG
            content_type="image/png"
        )
        form_data = {
            'site_name': 'Test Site',
            'primary_hue': 200,
            'primary_saturation': 70,
            'primary_lightness': 50,
        }
        form = BrandingSettingsForm(data=form_data, files={'logo': logo})
        self.assertTrue(form.is_valid())

    def test_logo_too_large(self):
        """Test logo file size validation."""
        # Create a large file (over 2MB)
        large_logo = SimpleUploadedFile(
            "large.png",
            b'\x89PNG\r\n\x1a\n' + b'\x00' * (3 * 1024 * 1024),  # 3MB
            content_type="image/png"
        )
        form_data = {
            'site_name': 'Test Site',
            'primary_hue': 200,
            'primary_saturation': 70,
            'primary_lightness': 50,
        }
        form = BrandingSettingsForm(data=form_data, files={'logo': large_logo})
        self.assertFalse(form.is_valid())
        self.assertIn('Logo file size must be under 2MB', str(form.errors))