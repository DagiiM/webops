"""
Authentication forms for WebOps.

Reference: CLAUDE.md "Django App Structure" section
Modern, forward-facing authentication with enhanced security.
"""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
from apps.core.models import BrandingSettings
import re


class WebOpsLoginForm(AuthenticationForm):
    """Enhanced login form with better styling."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Enter your username',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Enter your password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'webops-checkbox'
        })
    )


class WebOpsRegistrationForm(UserCreationForm):
    """User registration form with email and enhanced validation."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'webops-input',
            'placeholder': 'your.email@example.com'
        })
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Choose a username'
        }),
        help_text='Letters, numbers, and @/./+/-/_ only.'
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Create a strong password'
        }),
        help_text='Minimum 8 characters, must include letters and numbers.'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Confirm your password'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        """Ensure email is unique."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        return email

    def clean_username(self):
        """Validate username format."""
        username = self.cleaned_data.get('username')

        # Check for reserved usernames
        reserved = ['admin', 'root', 'webops', 'administrator', 'system', 'api', 'www']
        if username.lower() in reserved:
            raise ValidationError('This username is reserved.')

        # Check length
        if len(username) < 3:
            raise ValidationError('Username must be at least 3 characters.')

        # Check for valid characters
        if not re.match(r'^[\w.@+-]+$', username):
            raise ValidationError('Username contains invalid characters.')

        return username

    def clean_password1(self):
        """Enhanced password validation."""
        password = self.cleaned_data.get('password1')

        if len(password) < 8:
            raise ValidationError('Password must be at least 8 characters.')

        if not re.search(r'[A-Za-z]', password):
            raise ValidationError('Password must contain at least one letter.')

        if not re.search(r'\d', password):
            raise ValidationError('Password must contain at least one number.')

        # Check for common passwords
        common_passwords = ['password', '12345678', 'qwerty', 'admin123']
        if password.lower() in common_passwords:
            raise ValidationError('This password is too common.')

        return password


class WebOpsPasswordResetForm(PasswordResetForm):
    """Password reset request form."""

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Enter your email address'
        })
    )


class WebOpsSetPasswordForm(SetPasswordForm):
    """Set new password form."""

    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Enter new password'
        })
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Confirm new password'
        })
    )


class TwoFactorSetupForm(forms.Form):
    """Form for setting up 2FA."""

    verification_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': '000000',
            'maxlength': '6',
            'pattern': '[0-9]{6}',
            'autocomplete': 'off'
        }),
        help_text='Enter the 6-digit code from your authenticator app'
    )


class TwoFactorVerifyForm(forms.Form):
    """Form for verifying 2FA code during login."""

    code = forms.CharField(
        max_length=6,
        min_length=6,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': '000000',
            'maxlength': '6',
            'pattern': '[0-9]{6}',
            'autocomplete': 'off',
            'autofocus': True
        }),
        label='Verification Code'
    )
    backup_code = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': 'Or enter backup code'
        }),
        label='Backup Code (optional)'
    )
    
    def clean(self):
        """Ensure at least one of code or backup_code is provided."""
        cleaned_data = super().clean()
        code = cleaned_data.get('code')
        backup_code = cleaned_data.get('backup_code')
        
        if not code and not backup_code:
            raise ValidationError('Please enter either a verification code or a backup code.')
        
        if code and backup_code:
            raise ValidationError('Please enter either a verification code OR a backup code, not both.')
        
        return cleaned_data


class BrandingSettingsForm(forms.ModelForm):
    """
    Comprehensive branding settings form with organized sections for
    theme presets, identity, colors, typography, spacing, shadows, animations, and layout.
    """

    # ═══════════════════════════════════════════════════════════════════════════════
    # THEME PRESETS
    # ═══════════════════════════════════════════════════════════════════════════════

    theme_preset = forms.ChoiceField(
        choices=[
            ('custom', 'Custom Theme'),
            ('forest', 'Forest Theme'),
            ('ocean', 'Ocean Theme'),
            ('dark', 'Dark Theme'),
            ('premium', 'Premium/High Contrast Theme'),
        ],
        initial='custom',
        widget=forms.Select(attrs={
            'class': 'webops-input',
            'id': 'id_theme_preset'
        }),
        help_text='Choose a preset theme or customize your own'
    )

    # ═══════════════════════════════════════════════════════════════════════════════
    # SITE IDENTITY
    # ═══════════════════════════════════════════════════════════════════════════════

    site_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': 'WebOps'
        }),
        help_text='The name displayed in the browser title and header'
    )
    logo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'webops-file-input',
            'accept': 'image/png,image/jpeg,image/svg+xml'
        }),
        help_text='Logo image (recommended: 200x50px, PNG with transparency)'
    )
    favicon = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'webops-file-input',
            'accept': 'image/png,image/x-icon'
        }),
        help_text='Favicon (recommended: 32x32px or 64x64px, PNG/ICO)'
    )

    # ═══════════════════════════════════════════════════════════════════════════════
    # HSL COLOR SYSTEM
    # ═══════════════════════════════════════════════════════════════════════════════

    primary_hue = forms.IntegerField(
        min_value=0,
        max_value=360,
        initial=220,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input webops-hsl-input',
            'id': 'id_primary_hue',
            'data-hsl-component': 'hue'
        }),
        help_text='Primary color hue (0-360°)'
    )
    primary_saturation = forms.IntegerField(
        min_value=0,
        max_value=100,
        initial=85,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input webops-hsl-input',
            'id': 'id_primary_saturation',
            'data-hsl-component': 'saturation'
        }),
        help_text='Primary color saturation (0-100%)'
    )
    primary_lightness = forms.IntegerField(
        min_value=0,
        max_value=100,
        initial=50,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input webops-hsl-input',
            'id': 'id_primary_lightness',
            'data-hsl-component': 'lightness'
        }),
        help_text='Primary color lightness (0-100%)'
    )

    # ═══════════════════════════════════════════════════════════════════════════════
    # COLOR HARMONY & ACCESSIBILITY
    # ═══════════════════════════════════════════════════════════════════════════════

    color_harmony = forms.ChoiceField(
        choices=[
            ('monochromatic', 'Monochromatic'),
            ('complementary', 'Complementary'),
            ('triadic', 'Triadic'),
            ('analogous', 'Analogous'),
            ('split_complementary', 'Split Complementary'),
        ],
        initial='monochromatic',
        widget=forms.Select(attrs={
            'class': 'webops-input',
            'id': 'id_color_harmony'
        }),
        help_text='Color harmony scheme for palette generation'
    )

    # Accessibility settings
    enforce_wcag_aa = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'webops-checkbox',
            'id': 'id_enforce_wcag_aa'
        }),
        help_text='Enforce WCAG AA contrast requirements (4.5:1)'
    )
    enforce_wcag_aaa = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'webops-checkbox',
            'id': 'id_enforce_wcag_aaa'
        }),
        help_text='Enforce WCAG AAA contrast requirements (7:1)'
    )
    supports_dark_mode = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'webops-checkbox',
            'id': 'id_supports_dark_mode'
        }),
        help_text='Generate dark mode color variants'
    )

    # ═══════════════════════════════════════════════════════════════════════════════
    # GENERATED COLORS (Read-only preview)
    # ═══════════════════════════════════════════════════════════════════════════════

    primary_color = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'webops-input webops-generated-color',
            'type': 'color',
            'readonly': True,
            'id': 'id_primary_color'
        }),
        help_text='Auto-generated from HSL values'
    )
    secondary_color = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'webops-input webops-generated-color',
            'type': 'color',
            'readonly': True,
            'id': 'id_secondary_color'
        }),
        help_text='Auto-generated from HSL values'
    )
    accent_color = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'webops-input webops-generated-color',
            'type': 'color',
            'readonly': True,
            'id': 'id_accent_color'
        }),
        help_text='Auto-generated from HSL values'
    )
    header_bg_color = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'webops-input webops-generated-color',
            'type': 'color',
            'readonly': True,
            'id': 'id_header_bg_color'
        }),
        help_text='Auto-generated from HSL values'
    )

    # ═══════════════════════════════════════════════════════════════════════════════
    # TYPOGRAPHY SYSTEM
    # ═══════════════════════════════════════════════════════════════════════════════

    # Font families
    font_family_primary = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
        }),
        help_text='Primary font family for UI text'
    )
    font_family_mono = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'webops-input',
            'placeholder': '"JetBrains Mono", "Fira Code", Consolas, monospace'
        }),
        help_text='Monospace font family for code and technical text'
    )

    # Base font size
    font_size_base = forms.FloatField(
        min_value=0.75,
        max_value=2.0,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'step': '0.125',
            'min': '0.75',
            'max': '2.0'
        }),
        help_text='Base font size multiplier (1.0 = 16px, 1.125 = 18px)'
    )

    # Font weights
    font_weight_normal = forms.IntegerField(
        min_value=100,
        max_value=900,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'step': '100',
            'min': '100',
            'max': '900'
        }),
        help_text='Normal text weight (100-900)'
    )
    font_weight_medium = forms.IntegerField(
        min_value=100,
        max_value=900,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'step': '100',
            'min': '100',
            'max': '900'
        }),
        help_text='Medium text weight (100-900)'
    )
    font_weight_bold = forms.IntegerField(
        min_value=100,
        max_value=900,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'step': '100',
            'min': '100',
            'max': '900'
        }),
        help_text='Bold text weight (100-900)'
    )

    # Line heights
    line_height_tight = forms.FloatField(
        min_value=1.0,
        max_value=3.0,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'step': '0.125',
            'min': '1.0',
            'max': '3.0'
        }),
        help_text='Tight line height for headings'
    )
    line_height_normal = forms.FloatField(
        min_value=1.0,
        max_value=3.0,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'step': '0.125',
            'min': '1.0',
            'max': '3.0'
        }),
        help_text='Normal line height for body text'
    )
    line_height_relaxed = forms.FloatField(
        min_value=1.0,
        max_value=3.0,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'step': '0.125',
            'min': '1.0',
            'max': '3.0'
        }),
        help_text='Relaxed line height for long-form content'
    )

    # ═══════════════════════════════════════════════════════════════════════════════
    # SPACING SYSTEM
    # ═══════════════════════════════════════════════════════════════════════════════

    # Base spacing unit
    spacing_base_unit = forms.IntegerField(
        min_value=2,
        max_value=16,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '2',
            'max': '16'
        }),
        help_text='Base spacing unit in pixels (typically 4px or 8px)'
    )

    # Container padding
    container_padding_desktop = forms.IntegerField(
        min_value=8,
        max_value=64,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '8',
            'max': '64'
        }),
        help_text='Container padding for desktop (px)'
    )
    container_padding_mobile = forms.IntegerField(
        min_value=8,
        max_value=32,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '8',
            'max': '32'
        }),
        help_text='Container padding for mobile (px)'
    )

    # Component spacing
    component_spacing_compact = forms.IntegerField(
        min_value=4,
        max_value=32,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '4',
            'max': '32'
        }),
        help_text='Compact spacing between components (px)'
    )
    component_spacing_normal = forms.IntegerField(
        min_value=8,
        max_value=64,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '8',
            'max': '64'
        }),
        help_text='Normal spacing between components (px)'
    )
    component_spacing_relaxed = forms.IntegerField(
        min_value=16,
        max_value=128,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '16',
            'max': '128'
        }),
        help_text='Relaxed spacing between components (px)'
    )

    # ═══════════════════════════════════════════════════════════════════════════════
    # BORDER RADIUS SYSTEM
    # ═══════════════════════════════════════════════════════════════════════════════

    border_radius_small = forms.IntegerField(
        min_value=0,
        max_value=16,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '0',
            'max': '16'
        }),
        help_text='Small border radius (px)'
    )
    border_radius_medium = forms.IntegerField(
        min_value=0,
        max_value=32,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '0',
            'max': '32'
        }),
        help_text='Medium border radius (px)'
    )
    border_radius_large = forms.IntegerField(
        min_value=0,
        max_value=64,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '0',
            'max': '64'
        }),
        help_text='Large border radius (px)'
    )

    # ═══════════════════════════════════════════════════════════════════════════════
    # SHADOW SYSTEM
    # ═══════════════════════════════════════════════════════════════════════════════

    # Shadow intensity
    shadow_intensity = forms.IntegerField(
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '0',
            'max': '100'
        }),
        help_text='Shadow intensity percentage (0-100)'
    )

    # Shadow blur amounts
    shadow_blur_small = forms.IntegerField(
        min_value=0,
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '0',
            'max': '20'
        }),
        help_text='Small shadow blur amount (px)'
    )
    shadow_blur_medium = forms.IntegerField(
        min_value=0,
        max_value=40,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '0',
            'max': '40'
        }),
        help_text='Medium shadow blur amount (px)'
    )
    shadow_blur_large = forms.IntegerField(
        min_value=0,
        max_value=60,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '0',
            'max': '60'
        }),
        help_text='Large shadow blur amount (px)'
    )

    # Enable themed shadows
    enable_themed_shadows = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'webops-checkbox'
        }),
        help_text='Use primary color for accent shadows'
    )

    # ═══════════════════════════════════════════════════════════════════════════════
    # ANIMATION SYSTEM
    # ═══════════════════════════════════════════════════════════════════════════════

    # Animation durations
    animation_duration_fast = forms.IntegerField(
        min_value=50,
        max_value=500,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '50',
            'max': '500'
        }),
        help_text='Fast animation duration (ms)'
    )
    animation_duration_normal = forms.IntegerField(
        min_value=100,
        max_value=1000,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '100',
            'max': '1000'
        }),
        help_text='Normal animation duration (ms)'
    )
    animation_duration_slow = forms.IntegerField(
        min_value=200,
        max_value=2000,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '200',
            'max': '2000'
        }),
        help_text='Slow animation duration (ms)'
    )

    # Animation easing
    animation_easing = forms.ChoiceField(
        choices=[
            ('linear', 'Linear'),
            ('ease', 'Ease'),
            ('ease-in', 'Ease In'),
            ('ease-out', 'Ease Out'),
            ('ease-in-out', 'Ease In Out'),
            ('cubic-bezier(0.4, 0, 0.2, 1)', 'Material Design'),
            ('cubic-bezier(0.68, -0.55, 0.265, 1.55)', 'Bounce'),
        ],
        widget=forms.Select(attrs={
            'class': 'webops-input'
        }),
        help_text='Animation easing function'
    )

    # Reduce motion preference
    respect_reduced_motion = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'webops-checkbox'
        }),
        help_text='Respect user preference for reduced motion'
    )

    # ═══════════════════════════════════════════════════════════════════════════════
    # LAYOUT DIMENSIONS
    # ═══════════════════════════════════════════════════════════════════════════════

    # Header dimensions
    header_height_desktop = forms.IntegerField(
        min_value=40,
        max_value=120,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '40',
            'max': '120'
        }),
        help_text='Header height on desktop (px)'
    )
    header_height_mobile = forms.IntegerField(
        min_value=40,
        max_value=80,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '40',
            'max': '80'
        }),
        help_text='Header height on mobile (px)'
    )

    # Sidebar dimensions
    sidebar_width_desktop = forms.IntegerField(
        min_value=200,
        max_value=400,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '200',
            'max': '400'
        }),
        help_text='Sidebar width on desktop (px)'
    )
    sidebar_width_collapsed = forms.IntegerField(
        min_value=48,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '48',
            'max': '100'
        }),
        help_text='Collapsed sidebar width (px)'
    )

    # Content constraints
    content_max_width = forms.IntegerField(
        min_value=800,
        max_value=2000,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '800',
            'max': '2000'
        }),
        help_text='Maximum content width (px)'
    )

    # Component heights
    input_height_small = forms.IntegerField(
        min_value=24,
        max_value=48,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '24',
            'max': '48'
        }),
        help_text='Small input height (px)'
    )
    input_height_medium = forms.IntegerField(
        min_value=32,
        max_value=56,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '32',
            'max': '56'
        }),
        help_text='Medium input height (px)'
    )
    input_height_large = forms.IntegerField(
        min_value=40,
        max_value=64,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '40',
            'max': '64'
        }),
        help_text='Large input height (px)'
    )

    button_height_small = forms.IntegerField(
        min_value=24,
        max_value=48,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '24',
            'max': '48'
        }),
        help_text='Small button height (px)'
    )
    button_height_medium = forms.IntegerField(
        min_value=32,
        max_value=56,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '32',
            'max': '56'
        }),
        help_text='Medium button height (px)'
    )
    button_height_large = forms.IntegerField(
        min_value=40,
        max_value=64,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '40',
            'max': '64'
        }),
        help_text='Large button height (px)'
    )

    # ═══════════════════════════════════════════════════════════════════════════════
    # INTERACTIVE STATES
    # ═══════════════════════════════════════════════════════════════════════════════

    # Hover effects
    hover_opacity = forms.FloatField(
        min_value=0.1,
        max_value=1.0,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'step': '0.1',
            'min': '0.1',
            'max': '1.0'
        }),
        help_text='Opacity for hover states (0.1-1.0)'
    )
    hover_scale = forms.FloatField(
        min_value=0.9,
        max_value=1.2,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'step': '0.01',
            'min': '0.9',
            'max': '1.2'
        }),
        help_text='Scale transform for hover states (0.9-1.2)'
    )

    # Focus effects
    focus_ring_width = forms.IntegerField(
        min_value=1,
        max_value=8,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '1',
            'max': '8'
        }),
        help_text='Focus ring width (px)'
    )
    focus_ring_offset = forms.IntegerField(
        min_value=0,
        max_value=8,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'min': '0',
            'max': '8'
        }),
        help_text='Focus ring offset (px)'
    )

    # Active/pressed effects
    active_scale = forms.FloatField(
        min_value=0.8,
        max_value=1.0,
        widget=forms.NumberInput(attrs={
            'class': 'webops-input',
            'step': '0.01',
            'min': '0.8',
            'max': '1.0'
        }),
        help_text='Scale transform for active/pressed states (0.8-1.0)'
    )

    class Meta:
        model = BrandingSettings
        fields = [
            # Theme presets
            'theme_preset',
            
            # Site identity
            'site_name', 'logo', 'favicon',
            
            # HSL color system
            'primary_hue', 'primary_saturation', 'primary_lightness',
            
            # Color harmony & accessibility
            'color_harmony', 'enforce_wcag_aa', 'enforce_wcag_aaa', 'supports_dark_mode',
            
            # Generated colors (read-only)
            'primary_color', 'secondary_color', 'accent_color', 'header_bg_color',
            
            # Typography system
            'font_family_primary', 'font_family_mono', 'font_size_base',
            'font_weight_normal', 'font_weight_medium', 'font_weight_bold',
            'line_height_tight', 'line_height_normal', 'line_height_relaxed',
            
            # Spacing system
            'spacing_base_unit', 'container_padding_desktop', 'container_padding_mobile',
            'component_spacing_compact', 'component_spacing_normal', 'component_spacing_relaxed',
            
            # Border radius system
            'border_radius_small', 'border_radius_medium', 'border_radius_large',
            
            # Shadow system
            'shadow_intensity', 'shadow_blur_small', 'shadow_blur_medium', 'shadow_blur_large',
            'enable_themed_shadows',
            
            # Animation system
            'animation_duration_fast', 'animation_duration_normal', 'animation_duration_slow',
            'animation_easing', 'respect_reduced_motion',
            
            # Layout dimensions
            'header_height_desktop', 'header_height_mobile',
            'sidebar_width_desktop', 'sidebar_width_collapsed', 'content_max_width',
            'input_height_small', 'input_height_medium', 'input_height_large',
            'button_height_small', 'button_height_medium', 'button_height_large',
            
            # Interactive states
            'hover_opacity', 'hover_scale', 'focus_ring_width', 'focus_ring_offset', 'active_scale',
        ]

    def clean_logo(self):
        """Validate logo file size and dimensions."""
        logo = self.cleaned_data.get('logo')
        if logo:
            # Check file size (max 2MB)
            if logo.size > 2 * 1024 * 1024:
                raise ValidationError('Logo file size must be under 2MB')
        return logo

    def clean_favicon(self):
        """Validate favicon file size."""
        favicon = self.cleaned_data.get('favicon')
        if favicon:
            # Check file size (max 500KB)
            if favicon.size > 500 * 1024:
                raise ValidationError('Favicon file size must be under 500KB')
        return favicon

    def clean_primary_color(self):
        """Validate hex color format."""
        color = self.cleaned_data.get('primary_color')
        if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
            raise ValidationError('Invalid hex color format. Use #RRGGBB')
        return color

    def clean_secondary_color(self):
        """Validate hex color format."""
        color = self.cleaned_data.get('secondary_color')
        if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
            raise ValidationError('Invalid hex color format. Use #RRGGBB')
        return color

    def clean_accent_color(self):
        """Validate hex color format."""
        color = self.cleaned_data.get('accent_color')
        if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
            raise ValidationError('Invalid hex color format. Use #RRGGBB')
        return color

    def clean_header_bg_color(self):
        """Validate hex color format."""
        color = self.cleaned_data.get('header_bg_color')
        if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
            raise ValidationError('Invalid hex color format. Use #RRGGBB')
        return color

    class Meta:
        model = BrandingSettings
        fields = [
            'theme_preset', 'site_name', 'logo', 'favicon', 'primary_hue', 'primary_saturation',
            'primary_lightness', 'color_harmony', 'enforce_wcag_aa', 'enforce_wcag_aaa',
            'supports_dark_mode', 'primary_color', 'secondary_color', 'accent_color',
            'header_bg_color'
        ]


# ==================================
# Webhook and Notification Forms
# ==================================

from apps.core.models import Webhook, NotificationChannel
from apps.deployments.models import Deployment


class WebhookForm(forms.ModelForm):
    """Form for creating and editing webhooks."""

    deployment = forms.ModelChoiceField(
        queryset=Deployment.objects.all(),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select webops-input',
        })
    )

    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input webops-input',
            'placeholder': 'My Auto-Deploy Webhook',
        })
    )

    trigger_event = forms.ChoiceField(
        choices=Webhook.TriggerEvent.choices,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select webops-input',
        })
    )

    branch_filter = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input webops-input',
            'placeholder': 'main (leave empty for all branches)',
        })
    )

    class Meta:
        model = Webhook
        fields = ['name', 'deployment', 'trigger_event', 'branch_filter']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['deployment'].queryset = Deployment.objects.filter(deployed_by=user)


class NotificationChannelForm(forms.ModelForm):
    """Form for creating and editing notification channels."""

    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input webops-input',
            'placeholder': 'My Email Notifications',
        })
    )

    channel_type = forms.ChoiceField(
        choices=NotificationChannel.ChannelType.choices,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select webops-input',
            'id': 'id_channel_type',
        })
    )

    # Email configuration
    email_address = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-input webops-input channel-config email-config',
            'placeholder': 'your.email@example.com',
        })
    )

    # Webhook configuration
    webhook_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-input webops-input channel-config webhook-config',
            'placeholder': 'https://your-webhook-endpoint.com/webhook',
        })
    )

    notify_on_deploy_success = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox webops-checkbox'})
    )

    notify_on_deploy_failure = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox webops-checkbox'})
    )

    notify_on_deploy_start = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox webops-checkbox'})
    )

    notify_on_health_check_fail = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox webops-checkbox'})
    )

    notify_on_resource_warning = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox webops-checkbox'})
    )

    class Meta:
        model = NotificationChannel
        fields = [
            'name',
            'channel_type',
            'notify_on_deploy_success',
            'notify_on_deploy_failure',
            'notify_on_deploy_start',
            'notify_on_health_check_fail',
            'notify_on_resource_warning',
        ]

    def clean(self):
        cleaned_data = super().clean()
        channel_type = cleaned_data.get('channel_type')
        email_address = cleaned_data.get('email_address')
        webhook_url = cleaned_data.get('webhook_url')

        # Validate based on channel type
        if channel_type == NotificationChannel.ChannelType.EMAIL:
            if not email_address:
                raise ValidationError('Email address is required for email notifications.')
        elif channel_type == NotificationChannel.ChannelType.WEBHOOK:
            if not webhook_url:
                raise ValidationError('Webhook URL is required for webhook notifications.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Build config based on channel type
        channel_type = self.cleaned_data.get('channel_type')
        config = {}

        if channel_type == NotificationChannel.ChannelType.EMAIL:
            config['email'] = self.cleaned_data.get('email_address')
        elif channel_type == NotificationChannel.ChannelType.WEBHOOK:
            config['webhook_url'] = self.cleaned_data.get('webhook_url')

        instance.config = config

        if commit:
            instance.save()

        return instance
