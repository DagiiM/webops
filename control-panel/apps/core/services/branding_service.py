"""
Branding Service for WebOps.

Handles color generation, theme management, and CSS variable generation
for the branding system. Extracted from BrandingSettings model to follow
proper separation of concerns.
"""

from typing import Dict, Tuple


class BrandingService:
    """
    Service for branding and theme management.

    Provides utilities for:
    - HSL to hex color conversion
    - Color palette generation
    - WCAG accessibility validation
    - CSS variable generation
    - Theme preset application
    """

    # Theme presets configuration
    THEME_PRESETS = {
        'forest': {
            'primary_hue': 142,      # Forest green
            'primary_saturation': 71,
            'primary_lightness': 45,
            'color_harmony': 'analogous',
            'supports_dark_mode': True,
            'accent_color': '#8B5A2B',  # Earth brown
            'header_bg_color': '#2D5016',  # Dark forest green
        },
        'ocean': {
            'primary_hue': 200,      # Ocean blue
            'primary_saturation': 85,
            'primary_lightness': 50,
            'color_harmony': 'complementary',
            'supports_dark_mode': True,
            'accent_color': '#20B2AA',  # Light sea green
            'header_bg_color': '#1E3A8A',  # Deep ocean blue
        },
        'dark': {
            'primary_hue': 220,      # Cool blue-gray
            'primary_saturation': 25,
            'primary_lightness': 65,
            'color_harmony': 'monochromatic',
            'supports_dark_mode': True,
            'accent_color': '#10B981',  # Emerald green
            'header_bg_color': '#111827',  # Very dark gray
        },
        'premium': {
            'primary_hue': 260,      # Royal purple
            'primary_saturation': 95,
            'primary_lightness': 40,
            'color_harmony': 'triadic',
            'supports_dark_mode': True,
            'accent_color': '#F59E0B',  # Gold accent
            'header_bg_color': '#1F2937',  # Dark gray
            'enforce_wcag_aaa': True,  # High contrast requirement
        }
    }

    @staticmethod
    def hsl_to_hex(h: int, s: int, l: int) -> str:
        """
        Convert HSL values to hex color.

        Args:
            h: Hue (0-360 degrees)
            s: Saturation (0-100%)
            l: Lightness (0-100%)

        Returns:
            Hex color string (e.g., '#3b82f6')
        """
        # Normalize values
        h = h / 360.0
        s = s / 100.0
        l = l / 100.0

        def hue_to_rgb(p: float, q: float, t: float) -> float:
            if t < 0:
                t += 1
            if t > 1:
                t -= 1
            if t < 1/6:
                return p + (q - p) * 6 * t
            if t < 1/2:
                return q
            if t < 2/3:
                return p + (q - p) * (2/3 - t) * 6
            return p

        if s == 0:
            r = g = b = l  # achromatic
        else:
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)

        # Convert to hex
        r_hex = format(int(r * 255), '02x')
        g_hex = format(int(g * 255), '02x')
        b_hex = format(int(b * 255), '02x')

        return f'#{r_hex}{g_hex}{b_hex}'

    @staticmethod
    def generate_color_scale(hue: int, saturation: int, base_lightness: int) -> Dict[str, str]:
        """
        Generate a color scale with multiple lightness variants.

        Args:
            hue: Base hue (0-360)
            saturation: Base saturation (0-100)
            base_lightness: Base lightness (0-100)

        Returns:
            Dictionary with shade names ('50' to '800') mapped to hex colors
        """
        scale = {}

        # Generate 9 shades from very light to very dark
        lightness_values = [95, 85, 75, 65, base_lightness, 45, 35, 25, 15]
        shade_names = ['50', '100', '200', '300', '400', '500', '600', '700', '800']

        for i, lightness in enumerate(lightness_values):
            scale[shade_names[i]] = BrandingService.hsl_to_hex(hue, saturation, lightness)

        return scale

    @staticmethod
    def generate_color_palette(primary_hue: int, primary_saturation: int,
                              primary_lightness: int, color_harmony: str) -> Dict[str, Dict[str, str]]:
        """
        Generate complete color palette based on harmony scheme.

        Args:
            primary_hue: Primary color hue
            primary_saturation: Primary color saturation
            primary_lightness: Primary color lightness
            color_harmony: Harmony scheme ('monochromatic', 'complementary', 'triadic', 'analogous', 'split_complementary')

        Returns:
            Dictionary of color scales for different palette colors
        """
        palette = {
            'primary': BrandingService.generate_color_scale(
                primary_hue,
                primary_saturation,
                primary_lightness
            ),
            'secondary': BrandingService.generate_color_scale(
                primary_hue,
                primary_saturation,
                max(20, primary_lightness - 25)
            )
        }

        # Add harmony colors based on scheme
        if color_harmony == 'complementary':
            comp_hue = (primary_hue + 180) % 360
            palette['complementary'] = BrandingService.generate_color_scale(
                comp_hue, primary_saturation, primary_lightness
            )
        elif color_harmony == 'triadic':
            palette['triadic_1'] = BrandingService.generate_color_scale(
                (primary_hue + 120) % 360,
                primary_saturation,
                primary_lightness
            )
            palette['triadic_2'] = BrandingService.generate_color_scale(
                (primary_hue + 240) % 360,
                primary_saturation,
                primary_lightness
            )
        elif color_harmony == 'analogous':
            palette['analogous_1'] = BrandingService.generate_color_scale(
                (primary_hue + 30) % 360,
                primary_saturation,
                primary_lightness
            )
            palette['analogous_2'] = BrandingService.generate_color_scale(
                (primary_hue - 30) % 360,
                primary_saturation,
                primary_lightness
            )

        # Add semantic colors
        palette['success'] = BrandingService.generate_color_scale(142, 71, 45)  # Green
        palette['warning'] = BrandingService.generate_color_scale(38, 92, 50)   # Orange
        palette['error'] = BrandingService.generate_color_scale(0, 84, 60)      # Red
        palette['info'] = BrandingService.generate_color_scale(200, 98, 39)     # Light blue

        # Add neutral grays
        palette['neutral'] = BrandingService.generate_color_scale(220, 13, 50)  # Gray scale

        return palette

    @staticmethod
    def get_contrast_ratio(color1: str, color2: str) -> float:
        """
        Calculate WCAG contrast ratio between two colors.

        Args:
            color1: First hex color (e.g., '#3b82f6')
            color2: Second hex color (e.g., '#ffffff')

        Returns:
            Contrast ratio (1.0 to 21.0)
        """
        def get_luminance(hex_color: str) -> float:
            # Remove # and convert to RGB
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

            # Convert to relative luminance
            def to_linear(c: int) -> float:
                c = c / 255.0
                return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

            r_lin = to_linear(r)
            g_lin = to_linear(g)
            b_lin = to_linear(b)

            return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

        lum1 = get_luminance(color1)
        lum2 = get_luminance(color2)

        # Ensure lighter color is numerator
        if lum1 < lum2:
            lum1, lum2 = lum2, lum1

        return (lum1 + 0.05) / (lum2 + 0.05)

    @staticmethod
    def validate_accessibility(primary_color: str, secondary_color: str) -> Dict[str, bool]:
        """
        Validate color accessibility against WCAG standards.

        Args:
            primary_color: Primary hex color
            secondary_color: Secondary hex color

        Returns:
            Dictionary of WCAG compliance results
        """
        results = {}

        # Test primary color against white and black backgrounds
        primary_vs_white = BrandingService.get_contrast_ratio(primary_color, '#ffffff')
        primary_vs_black = BrandingService.get_contrast_ratio(primary_color, '#000000')

        results['primary_aa_white'] = primary_vs_white >= 4.5
        results['primary_aaa_white'] = primary_vs_white >= 7.0
        results['primary_aa_black'] = primary_vs_black >= 4.5
        results['primary_aaa_black'] = primary_vs_black >= 7.0

        # Test secondary color
        secondary_vs_white = BrandingService.get_contrast_ratio(secondary_color, '#ffffff')
        secondary_vs_black = BrandingService.get_contrast_ratio(secondary_color, '#000000')

        results['secondary_aa_white'] = secondary_vs_white >= 4.5
        results['secondary_aaa_white'] = secondary_vs_white >= 7.0
        results['secondary_aa_black'] = secondary_vs_black >= 4.5
        results['secondary_aaa_black'] = secondary_vs_black >= 7.0

        return results

    @staticmethod
    def generate_css_variables(settings) -> str:
        """
        Generate comprehensive CSS variables for all design system tokens.

        Args:
            settings: BrandingSettings model instance

        Returns:
            CSS string with all custom properties for the design system
        """
        css_vars = []

        # Core theme parameters
        css_vars.extend([
            f"  --webops-hue-primary: {settings.primary_hue};",
            f"  --webops-sat-primary: {settings.primary_saturation}%;",
            f"  --webops-light-primary: {settings.primary_lightness}%;",
        ])

        # Primary color system
        primary_variants = BrandingService.generate_color_scale(
            settings.primary_hue,
            settings.primary_saturation,
            settings.primary_lightness
        )

        for variant, color in primary_variants.items():
            css_vars.append(f"  --webops-primary-{variant}: {color};")

        # Primary color with alpha variants
        css_vars.extend([
            f"  --webops-primary-alpha-10: hsla({settings.primary_hue}, {settings.primary_saturation}%, {settings.primary_lightness}%, 0.1);",
            f"  --webops-primary-alpha-20: hsla({settings.primary_hue}, {settings.primary_saturation}%, {settings.primary_lightness}%, 0.2);",
            f"  --webops-primary-alpha-50: hsla({settings.primary_hue}, {settings.primary_saturation}%, {settings.primary_lightness}%, 0.5);",
        ])

        # Semantic status colors
        css_vars.extend([
            "  --webops-warning: #f59e0b;",
            "  --webops-warning-light: #fbbf24;",
            "  --webops-warning-dark: #d97706;",
            "  --webops-error: #ef4444;",
            "  --webops-error-light: #f87171;",
            "  --webops-error-dark: #dc2626;",
            "  --webops-info: #3b82f6;",
            "  --webops-info-light: #60a5fa;",
            "  --webops-info-dark: #2563eb;",
            f"  --webops-accent: {settings.accent_color};",
        ])

        # Neutral grayscale system
        css_vars.extend([
            "  --webops-neutral-50: #f9fafb;",
            "  --webops-neutral-100: #f3f4f6;",
            "  --webops-neutral-200: #e5e7eb;",
            "  --webops-neutral-300: #d1d5db;",
            "  --webops-neutral-400: #9ca3af;",
            "  --webops-neutral-500: #6b7280;",
            "  --webops-neutral-600: #4b5563;",
            "  --webops-neutral-700: #374151;",
            "  --webops-neutral-800: #1f2937;",
            "  --webops-neutral-900: #111827;",
        ])

        # Typography system
        css_vars.extend([
            f"  --webops-font-family-primary: {settings.font_family_primary};",
            f"  --webops-font-family-mono: {settings.font_family_mono};",
            f"  --webops-font-size-base: {settings.font_size_base}rem;",
            f"  --webops-font-weight-normal: {settings.font_weight_normal};",
            f"  --webops-font-weight-medium: {settings.font_weight_medium};",
            f"  --webops-font-weight-bold: {settings.font_weight_bold};",
            f"  --webops-line-height-tight: {settings.line_height_tight};",
            f"  --webops-line-height-normal: {settings.line_height_normal};",
            f"  --webops-line-height-relaxed: {settings.line_height_relaxed};",
        ])

        # Font size scale
        font_sizes = {
            'xs': settings.font_size_base * 0.75,
            'sm': settings.font_size_base * 0.875,
            'base': settings.font_size_base,
            'lg': settings.font_size_base * 1.125,
            'xl': settings.font_size_base * 1.25,
            '2xl': settings.font_size_base * 1.5,
            '3xl': settings.font_size_base * 1.875,
            '4xl': settings.font_size_base * 2.25,
        }

        for size, value in font_sizes.items():
            css_vars.append(f"  --webops-font-size-{size}: {value}rem;")

        # Spacing system
        css_vars.extend([
            f"  --webops-spacing-base: {settings.spacing_base_unit}px;",
            f"  --webops-container-padding-desktop: {settings.container_padding_desktop}px;",
            f"  --webops-container-padding-mobile: {settings.container_padding_mobile}px;",
            f"  --webops-component-spacing-compact: {settings.component_spacing_compact}px;",
            f"  --webops-component-spacing-normal: {settings.component_spacing_normal}px;",
            f"  --webops-component-spacing-relaxed: {settings.component_spacing_relaxed}px;",
        ])

        # Generate spacing scale
        spacing_scale = {}
        for i in range(0, 17):  # 0 to 16
            if i == 0:
                spacing_scale[i] = 0
            elif i <= 4:
                spacing_scale[i] = i * settings.spacing_base_unit
            else:
                spacing_scale[i] = (i * settings.spacing_base_unit) + ((i - 4) * settings.spacing_base_unit)

        for scale, value in spacing_scale.items():
            css_vars.append(f"  --webops-spacing-{scale}: {value}px;")

        # Border radius system
        css_vars.extend([
            f"  --webops-radius-small: {settings.border_radius_small}px;",
            f"  --webops-radius-medium: {settings.border_radius_medium}px;",
            f"  --webops-radius-large: {settings.border_radius_large}px;",
            "  --webops-radius-full: 9999px;",
        ])

        # Shadow system
        shadow_opacity = settings.shadow_intensity / 100.0

        css_vars.extend([
            f"  --webops-shadow-small: 0 1px {settings.shadow_blur_small}px rgba(0, 0, 0, {shadow_opacity * 0.1});",
            f"  --webops-shadow-medium: 0 4px {settings.shadow_blur_medium}px rgba(0, 0, 0, {shadow_opacity * 0.15});",
            f"  --webops-shadow-large: 0 10px {settings.shadow_blur_large}px rgba(0, 0, 0, {shadow_opacity * 0.2});",
        ])

        # Themed shadows
        if settings.enable_themed_shadows:
            css_vars.extend([
                f"  --webops-shadow-primary: 0 4px {settings.shadow_blur_medium}px hsla({settings.primary_hue}, {settings.primary_saturation}%, {settings.primary_lightness}%, 0.3);",
                f"  --webops-shadow-accent: 0 4px {settings.shadow_blur_medium}px hsla(142, 76%, 36%, 0.3);",
            ])

        # Animation system
        css_vars.extend([
            f"  --webops-duration-fast: {settings.animation_duration_fast}ms;",
            f"  --webops-duration-normal: {settings.animation_duration_normal}ms;",
            f"  --webops-duration-slow: {settings.animation_duration_slow}ms;",
            f"  --webops-easing: {settings.animation_easing};",
        ])

        # Layout dimensions
        css_vars.extend([
            f"  --webops-header-height-desktop: {settings.header_height_desktop}px;",
            f"  --webops-header-height-mobile: {settings.header_height_mobile}px;",
            f"  --webops-sidebar-width-desktop: {settings.sidebar_width_desktop}px;",
            f"  --webops-sidebar-width-collapsed: {settings.sidebar_width_collapsed}px;",
            f"  --webops-content-max-width: {settings.content_max_width}px;",
        ])

        # Component dimensions
        css_vars.extend([
            f"  --webops-input-height-small: {settings.input_height_small}px;",
            f"  --webops-input-height-medium: {settings.input_height_medium}px;",
            f"  --webops-input-height-large: {settings.input_height_large}px;",
            f"  --webops-button-height-small: {settings.button_height_small}px;",
            f"  --webops-button-height-medium: {settings.button_height_medium}px;",
            f"  --webops-button-height-large: {settings.button_height_large}px;",
        ])

        # Interactive states
        css_vars.extend([
            f"  --webops-hover-opacity: {settings.hover_opacity};",
            f"  --webops-hover-scale: {settings.hover_scale};",
            f"  --webops-focus-ring-width: {settings.focus_ring_width}px;",
            f"  --webops-focus-ring-offset: {settings.focus_ring_offset}px;",
            f"  --webops-active-scale: {settings.active_scale};",
        ])

        # Responsive breakpoints
        css_vars.extend([
            "  --webops-breakpoint-sm: 640px;",
            "  --webops-breakpoint-md: 768px;",
            "  --webops-breakpoint-lg: 1024px;",
            "  --webops-breakpoint-xl: 1280px;",
            "  --webops-breakpoint-2xl: 1536px;",
        ])

        # Reduced motion support
        reduced_motion_css = ""
        if settings.respect_reduced_motion:
            reduced_motion_css = """
@media (prefers-reduced-motion: reduce) {
  :root {
    --webops-duration-fast: 0ms;
    --webops-duration-normal: 0ms;
    --webops-duration-slow: 0ms;
    --webops-hover-scale: 1;
    --webops-active-scale: 1;
  }
}"""

        # Combine all CSS variables
        css_content = f"""/* WebOps Design System - Auto-generated from BrandingSettings */
:root {{
{chr(10).join(css_vars)}
}}

{reduced_motion_css}"""

        return css_content

    @staticmethod
    def apply_theme_preset(preset_name: str) -> Dict[str, any]:
        """
        Get configuration for a theme preset.

        Args:
            preset_name: Name of the preset ('forest', 'ocean', 'dark', 'premium')

        Returns:
            Dictionary of theme settings to apply
        """
        return BrandingService.THEME_PRESETS.get(preset_name, {})