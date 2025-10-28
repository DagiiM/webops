"""
Branding models for WebOps.

"Database Models" section
Architecture: Branding settings, theme management, design system
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class BrandingSettings(models.Model):
    """
    Branding and theming settings for the WebOps control panel.
    
    Supports HSL-based color generation with accessibility compliance,
    theme presets, and comprehensive design system management including
    typography, spacing, shadows, animations, and layout controls.
    """

    # ═══════════════════════════════════════════════════════════════════════════════
    # SITE IDENTITY
    # ═══════════════════════════════════════════════════════════════════════════════
    
    site_name = models.CharField(
        max_length=100,
        default='WebOps',
        help_text='Name displayed in browser title and header'
    )
    logo = models.ImageField(
        upload_to='branding/logos/',
        null=True,
        blank=True,
        help_text='Logo image (recommended: 200x50px, PNG with transparency)'
    )
    favicon = models.ImageField(
        upload_to='branding/favicons/',
        null=True,
        blank=True,
        help_text='Favicon (recommended: 32x32px or 64x64px, PNG/ICO)'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # HSL COLOR SYSTEM (Primary color generation)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    primary_hue = models.IntegerField(
        default=217,  # Blue hue for #3b82f6
        help_text='Primary color hue (0-360 degrees)'
    )
    primary_saturation = models.IntegerField(
        default=91,  # Saturation percentage for #3b82f6
        help_text='Primary color saturation (0-100%)'
    )
    primary_lightness = models.IntegerField(
        default=60,  # Lightness percentage for #3b82f6
        help_text='Primary color lightness (0-100%)'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # GENERATED COLORS (Auto-calculated from HSL values)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    primary_color = models.CharField(
        max_length=7,
        default='#3b82f6',
        help_text='Primary brand color (hex format: #RRGGBB) - auto-generated from HSL'
    )
    secondary_color = models.CharField(
        max_length=7,
        default='#1e40af',
        help_text='Secondary brand color (hex format: #RRGGBB) - auto-generated'
    )
    accent_color = models.CharField(
        max_length=7,
        default='#10b981',
        help_text='Accent color for success states (hex format: #RRGGBB)'
    )
    header_bg_color = models.CharField(
        max_length=7,
        default='#1f2937',
        help_text='Header background color (hex format: #RRGGBB)'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # COLOR HARMONY & PALETTE GENERATION
    # ═══════════════════════════════════════════════════════════════════════════════
    
    color_harmony = models.CharField(
        max_length=20,
        default='monochromatic',
        choices=[
            ('monochromatic', 'Monochromatic'),
            ('complementary', 'Complementary'),
            ('triadic', 'Triadic'),
            ('analogous', 'Analogous'),
            ('split_complementary', 'Split Complementary'),
        ],
        help_text='Color harmony scheme for palette generation'
    )
    
    # Auto-generated palette storage
    generated_palette = models.JSONField(
        default=dict,
        blank=True,
        help_text='Auto-generated color palette with semantic names and variants'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # ACCESSIBILITY COMPLIANCE
    # ═══════════════════════════════════════════════════════════════════════════════
    
    enforce_wcag_aa = models.BooleanField(
        default=True,
        help_text='Enforce WCAG AA contrast ratios (4.5:1 for normal text)'
    )
    enforce_wcag_aaa = models.BooleanField(
        default=False,
        help_text='Enforce WCAG AAA contrast ratios (7:1 for normal text)'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # THEME FEATURES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    supports_dark_mode = models.BooleanField(
        default=True,
        help_text='Generate dark mode color variants'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # THEME PRESETS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    theme_preset = models.CharField(
        max_length=20,
        default='custom',
        choices=[
            ('custom', 'Custom'),
            ('forest', 'Forest Theme'),
            ('ocean', 'Ocean Theme'),
            ('dark', 'Dark Theme'),
            ('premium', 'Premium/High Contrast'),
        ],
        help_text='Predefined theme preset or custom configuration'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # TYPOGRAPHY SYSTEM
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Font families
    font_family_primary = models.CharField(
        max_length=200,
        default='"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        help_text='Primary font family for UI text'
    )
    font_family_mono = models.CharField(
        max_length=200,
        default='"JetBrains Mono", "Fira Code", Consolas, "Liberation Mono", Menlo, Courier, monospace',
        help_text='Monospace font family for code and technical text'
    )
    
    # Base font size (rem multiplier)
    font_size_base = models.FloatField(
        default=1.0,
        help_text='Base font size multiplier (1.0 = 16px, 1.125 = 18px)'
    )
    
    # Font weight preferences
    font_weight_normal = models.IntegerField(
        default=400,
        help_text='Normal text weight (300-900)'
    )
    font_weight_medium = models.IntegerField(
        default=500,
        help_text='Medium text weight (300-900)'
    )
    font_weight_bold = models.IntegerField(
        default=700,
        help_text='Bold text weight (300-900)'
    )
    
    # Line height preferences
    line_height_tight = models.FloatField(
        default=1.25,
        help_text='Tight line height for headings'
    )
    line_height_normal = models.FloatField(
        default=1.5,
        help_text='Normal line height for body text'
    )
    line_height_relaxed = models.FloatField(
        default=1.625,
        help_text='Relaxed line height for long-form content'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # SPACING SYSTEM
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Base spacing unit (in pixels)
    spacing_base_unit = models.IntegerField(
        default=8,
        help_text='Base spacing unit in pixels (typically 4px or 8px)'
    )
    
    # Container padding
    container_padding_desktop = models.IntegerField(
        default=24,
        help_text='Container padding for desktop (px)'
    )
    container_padding_mobile = models.IntegerField(
        default=16,
        help_text='Container padding for mobile (px)'
    )
    
    # Component spacing
    component_spacing_compact = models.IntegerField(
        default=12,
        help_text='Compact spacing between components (px)'
    )
    component_spacing_normal = models.IntegerField(
        default=24,
        help_text='Normal spacing between components (px)'
    )
    component_spacing_relaxed = models.IntegerField(
        default=48,
        help_text='Relaxed spacing between components (px)'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # BORDER RADIUS SYSTEM
    # ═══════════════════════════════════════════════════════════════════════════════
    
    border_radius_small = models.IntegerField(
        default=4,
        help_text='Small border radius (px)'
    )
    border_radius_medium = models.IntegerField(
        default=8,
        help_text='Medium border radius (px)'
    )
    border_radius_large = models.IntegerField(
        default=16,
        help_text='Large border radius (px)'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # SHADOW SYSTEM
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Shadow intensity (0-100)
    shadow_intensity = models.IntegerField(
        default=10,
        help_text='Shadow intensity percentage (0-100)'
    )
    
    # Shadow blur amounts
    shadow_blur_small = models.IntegerField(
        default=6,
        help_text='Small shadow blur amount (px)'
    )
    shadow_blur_medium = models.IntegerField(
        default=15,
        help_text='Medium shadow blur amount (px)'
    )
    shadow_blur_large = models.IntegerField(
        default=25,
        help_text='Large shadow blur amount (px)'
    )
    
    # Enable themed shadows (using primary color)
    enable_themed_shadows = models.BooleanField(
        default=True,
        help_text='Use primary color for accent shadows'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # ANIMATION SYSTEM
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Animation durations (in milliseconds)
    animation_duration_fast = models.IntegerField(
        default=150,
        help_text='Fast animation duration (ms)'
    )
    animation_duration_normal = models.IntegerField(
        default=200,
        help_text='Normal animation duration (ms)'
    )
    animation_duration_slow = models.IntegerField(
        default=300,
        help_text='Slow animation duration (ms)'
    )
    
    # Animation easing
    animation_easing = models.CharField(
        max_length=50,
        default='cubic-bezier(0.4, 0, 0.2, 1)',
        choices=[
            ('linear', 'Linear'),
            ('ease', 'Ease'),
            ('ease-in', 'Ease In'),
            ('ease-out', 'Ease Out'),
            ('ease-in-out', 'Ease In Out'),
            ('cubic-bezier(0.4, 0, 0.2, 1)', 'Material Design'),
            ('cubic-bezier(0.68, -0.55, 0.265, 1.55)', 'Bounce'),
        ],
        help_text='Animation easing function'
    )
    
    # Reduce motion preference
    respect_reduced_motion = models.BooleanField(
        default=True,
        help_text='Respect user preference for reduced motion'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # LAYOUT DIMENSIONS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Header dimensions
    header_height_desktop = models.IntegerField(
        default=64,
        help_text='Header height on desktop (px)'
    )
    header_height_mobile = models.IntegerField(
        default=56,
        help_text='Header height on mobile (px)'
    )
    
    # Sidebar dimensions
    sidebar_width_desktop = models.IntegerField(
        default=256,
        help_text='Sidebar width on desktop (px)'
    )
    sidebar_width_collapsed = models.IntegerField(
        default=64,
        help_text='Collapsed sidebar width (px)'
    )
    
    # Content constraints
    content_max_width = models.IntegerField(
        default=1280,
        help_text='Maximum content width (px)'
    )
    
    # Component heights
    input_height_small = models.IntegerField(
        default=32,
        help_text='Small input height (px)'
    )
    input_height_medium = models.IntegerField(
        default=40,
        help_text='Medium input height (px)'
    )
    input_height_large = models.IntegerField(
        default=48,
        help_text='Large input height (px)'
    )
    
    button_height_small = models.IntegerField(
        default=32,
        help_text='Small button height (px)'
    )
    button_height_medium = models.IntegerField(
        default=40,
        help_text='Medium button height (px)'
    )
    button_height_large = models.IntegerField(
        default=48,
        help_text='Large button height (px)'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # INTERACTIVE STATES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Hover effects
    hover_opacity = models.FloatField(
        default=0.8,
        help_text='Opacity for hover states (0.0-1.0)'
    )
    hover_scale = models.FloatField(
        default=1.02,
        help_text='Scale transform for hover states (0.5-2.0)'
    )
    
    # Focus effects
    focus_ring_width = models.IntegerField(
        default=2,
        help_text='Focus ring width (px)'
    )
    focus_ring_offset = models.IntegerField(
        default=2,
        help_text='Focus ring offset (px)'
    )
    
    # Active/pressed effects
    active_scale = models.FloatField(
        default=0.98,
        help_text='Scale transform for active/pressed states (0.5-2.0)'
    )
    
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_branding_settings'
        verbose_name = 'Branding Settings'
        verbose_name_plural = 'Branding Settings'

    def __str__(self) -> str:
        return f"Branding: {self.site_name}"

    def save(self, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern) and generate color palette."""
        from apps.core.branding.services import BrandingService

        if not self.pk and BrandingSettings.objects.exists():
            # Update existing instance instead of creating new
            existing = BrandingSettings.objects.first()
            self.pk = existing.pk

        # Apply theme preset if selected (delegate to service)
        if self.theme_preset != 'custom':
            preset = BrandingService.apply_theme_preset(self.theme_preset)
            if preset:
                for key, value in preset.items():
                    if hasattr(self, key):
                        setattr(self, key, value)

        # Generate hex colors from HSL values (delegate to service)
        self.primary_color = BrandingService.hsl_to_hex(
            self.primary_hue,
            self.primary_saturation,
            self.primary_lightness
        )

        self.secondary_color = BrandingService.hsl_to_hex(
            self.primary_hue,
            self.primary_saturation,
            max(20, self.primary_lightness - 25)
        )

        # Generate complete color palette (delegate to service)
        self.generated_palette = BrandingService.generate_color_palette(
            self.primary_hue,
            self.primary_saturation,
            self.primary_lightness,
            self.color_harmony
        )

        super().save(*args, **kwargs)

    # Deprecated internal methods - kept for backward compatibility but delegate to service
    def _apply_theme_preset(self) -> None:
        """DEPRECATED: Use BrandingService.apply_theme_preset() directly.

        This method will be removed in version 2.0.

        Deprecated since: 1.0.7
        Removal planned: 2.0.0
        """
        import warnings
        warnings.warn(
            "_apply_theme_preset() is deprecated and will be removed in version 2.0. "
            "Use BrandingService.apply_theme_preset() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        from apps.core.branding.services import BrandingService
        preset = BrandingService.apply_theme_preset(self.theme_preset)
        if preset:
            for key, value in preset.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    def _generate_hex_colors(self) -> None:
        """DEPRECATED: Use BrandingService.hsl_to_hex() directly.

        This method will be removed in version 2.0.

        Deprecated since: 1.0.7
        Removal planned: 2.0.0
        """
        import warnings
        warnings.warn(
            "_generate_hex_colors() is deprecated and will be removed in version 2.0. "
            "Use BrandingService.hsl_to_hex() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        from apps.core.branding.services import BrandingService
        self.primary_color = BrandingService.hsl_to_hex(
            self.primary_hue,
            self.primary_saturation,
            self.primary_lightness
        )
        self.secondary_color = BrandingService.hsl_to_hex(
            self.primary_hue,
            self.primary_saturation,
            max(20, self.primary_lightness - 25)
        )

    def _generate_color_palette(self) -> None:
        """DEPRECATED: Use BrandingService.generate_color_palette() directly."""
        from apps.core.branding.services import BrandingService
        self.generated_palette = BrandingService.generate_color_palette(
            self.primary_hue,
            self.primary_saturation,
            self.primary_lightness,
            self.color_harmony
        )

    def _generate_color_scale(self, hue: int, saturation: int, base_lightness: int) -> dict[str, str]:
        """DEPRECATED: Use BrandingService.generate_color_scale() directly."""
        from apps.core.branding.services import BrandingService
        return BrandingService.generate_color_scale(hue, saturation, base_lightness)

    def _hsl_to_hex(self, h: int, s: int, l: int) -> str:
        """DEPRECATED: Use BrandingService.hsl_to_hex() directly."""
        from apps.core.branding.services import BrandingService
        return BrandingService.hsl_to_hex(h, s, l)

    def get_contrast_ratio(self, color1: str, color2: str) -> float:
        """Calculate WCAG contrast ratio between two colors. Delegates to BrandingService."""
        from apps.core.branding.services import BrandingService
        return BrandingService.get_contrast_ratio(color1, color2)

    def validate_accessibility(self) -> dict[str, bool]:
        """Validate color accessibility against WCAG standards. Delegates to BrandingService."""
        from apps.core.branding.services import BrandingService
        return BrandingService.validate_accessibility(self.primary_color, self.secondary_color)

    def generate_css_variables(self) -> str:
        """
        Generate comprehensive CSS variables for all design system tokens.
        Delegates to BrandingService.

        Returns:
            CSS string with all custom properties for the design system.
        """
        from apps.core.branding.services import BrandingService
        return BrandingService.generate_css_variables(self)

    @classmethod
    def get_settings(cls):
        """Get or create the singleton branding settings instance."""
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings