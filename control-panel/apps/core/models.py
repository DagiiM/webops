"""
Core models for WebOps.

Reference: CLAUDE.md "Database Models" section
Architecture: Base models, 2FA, security tracking, GitHub integration
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class BaseModel(models.Model):
    """Abstract base model with common fields for all models."""

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class TwoFactorAuth(models.Model):
    """
    Two-Factor Authentication settings for users.

    Uses TOTP (Time-based One-Time Password) - compatible with
    Google Authenticator, Authy, Microsoft Authenticator, etc.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='two_factor'
    )
    secret = models.CharField(max_length=32, unique=True)
    is_enabled = models.BooleanField(default=False)
    backup_codes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'core_two_factor_auth'
        verbose_name = '2FA Setting'
        verbose_name_plural = '2FA Settings'

    def __str__(self) -> str:
        status = "enabled" if self.is_enabled else "disabled"
        return f"{self.user.username} - 2FA {status}"


class GitHubConnection(models.Model):
    """GitHub OAuth connection for deploying private repositories."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='github_connection'
    )
    github_user_id = models.IntegerField(unique=True)
    username = models.CharField(max_length=100)
    access_token = models.CharField(max_length=255)  # Encrypted
    refresh_token = models.CharField(max_length=255, blank=True)  # Encrypted
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    last_synced = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'core_github_connection'
        verbose_name = 'GitHub Connection'
        verbose_name_plural = 'GitHub Connections'

    def __str__(self) -> str:
        return f"{self.user.username} → GitHub @{self.username}"


class HuggingFaceConnection(models.Model):
    """Hugging Face API token connection for deploying models and accessing private repos."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='huggingface_connection'
    )
    username = models.CharField(max_length=100)
    access_token = models.CharField(max_length=500)  # Encrypted (Hugging Face tokens are longer)
    token_type = models.CharField(
        max_length=20,
        choices=[
            ('read', 'Read-only'),
            ('write', 'Write'),
            ('fine-grained', 'Fine-grained'),
        ],
        default='read'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_synced = models.DateTimeField(null=True, blank=True)
    is_valid = models.BooleanField(default=True)
    last_validation_error = models.TextField(blank=True)

    class Meta:
        db_table = 'core_huggingface_connection'
        verbose_name = 'Hugging Face Connection'
        verbose_name_plural = 'Hugging Face Connections'

    def __str__(self) -> str:
        return f"{self.user.username} → Hugging Face @{self.username}"


class SecurityAuditLog(BaseModel):
    """Security audit log for all security-relevant events."""

    class EventType(models.TextChoices):
        LOGIN_SUCCESS = 'login_success', 'Login Success'
        LOGIN_FAILED = 'login_failed', 'Login Failed'
        LOGOUT = 'logout', 'Logout'
        PASSWORD_CHANGE = 'password_change', 'Password Changed'
        TFA_ENABLED = '2fa_enabled', '2FA Enabled'
        TFA_DISABLED = '2fa_disabled', '2FA Disabled'
        TFA_SUCCESS = '2fa_success', '2FA Success'
        TFA_FAILED = '2fa_failed', '2FA Failed'
        TOKEN_CREATED = 'token_created', 'API Token Created'
        TOKEN_REVOKED = 'token_revoked', 'API Token Revoked'
        DEPLOYMENT_CREATED = 'deployment_created', 'Deployment Created'
        DEPLOYMENT_DELETED = 'deployment_deleted', 'Deployment Deleted'
        DATABASE_ACCESSED = 'database_accessed', 'Database Credentials Accessed'
        SUSPICIOUS_ACTIVITY = 'suspicious_activity', 'Suspicious Activity'
        UNAUTHORIZED_ACCESS = 'unauthorized_access', 'Unauthorized Access Attempt'

    class Severity(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'
        CRITICAL = 'critical', 'Critical'

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_logs'
    )
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.INFO)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'core_security_audit_log'
        verbose_name = 'Security Audit Log'
        verbose_name_plural = 'Security Audit Logs'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['event_type']),
            models.Index(fields=['severity']),
        ]

    def __str__(self) -> str:
        user_str = self.user.username if self.user else "Anonymous"
        return f"[{self.severity.upper()}] {user_str} - {self.event_type}"


class SystemHealthCheck(BaseModel):
    """System health check results and metrics."""

    cpu_percent = models.FloatField()
    memory_percent = models.FloatField()
    memory_used_mb = models.IntegerField()
    memory_total_mb = models.IntegerField()
    disk_percent = models.FloatField()
    disk_used_gb = models.FloatField()
    disk_total_gb = models.FloatField()
    active_deployments = models.IntegerField()
    failed_deployments = models.IntegerField()
    is_healthy = models.BooleanField(default=True)
    issues = models.JSONField(default=list)

    class Meta:
        db_table = 'core_system_health_check'
        verbose_name = 'System Health Check'
        verbose_name_plural = 'System Health Checks'


class SSLCertificate(BaseModel):
    """SSL Certificate tracking for Let's Encrypt."""

    domain = models.CharField(max_length=255, unique=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)
    last_renewal_attempt = models.DateTimeField(null=True, blank=True)
    renewal_failed_count = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('expiring_soon', 'Expiring Soon'),
            ('expired', 'Expired'),
            ('renewal_failed', 'Renewal Failed'),
        ],
        default='active'
    )

    class Meta:
        db_table = 'core_ssl_certificate'
        verbose_name = 'SSL Certificate'
        verbose_name_plural = 'SSL Certificates'

    def __str__(self) -> str:
        return f"{self.domain} - {self.status}"


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
        if not self.pk and BrandingSettings.objects.exists():
            # Update existing instance instead of creating new
            existing = BrandingSettings.objects.first()
            self.pk = existing.pk
        
        # Apply theme preset if selected
        if self.theme_preset != 'custom':
            self._apply_theme_preset()
        
        # Generate hex colors from HSL values
        self._generate_hex_colors()
        
        # Generate complete color palette
        self._generate_color_palette()
        
        super().save(*args, **kwargs)

    def _apply_theme_preset(self) -> None:
        """Apply predefined theme preset values."""
        theme_presets = {
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
        
        if self.theme_preset in theme_presets:
            preset = theme_presets[self.theme_preset]
            
            # Apply HSL values
            self.primary_hue = preset['primary_hue']
            self.primary_saturation = preset['primary_saturation']
            self.primary_lightness = preset['primary_lightness']
            self.color_harmony = preset['color_harmony']
            self.supports_dark_mode = preset['supports_dark_mode']
            
            # Apply direct color values
            self.accent_color = preset['accent_color']
            self.header_bg_color = preset['header_bg_color']
            
            # Apply accessibility settings for premium theme
            if 'enforce_wcag_aaa' in preset:
                self.enforce_wcag_aaa = preset['enforce_wcag_aaa']

    def _generate_hex_colors(self) -> None:
        """Generate hex colors from HSL values."""
        # Convert HSL to hex for primary color
        self.primary_color = self._hsl_to_hex(
            self.primary_hue, 
            self.primary_saturation, 
            self.primary_lightness
        )
        
        # Generate secondary color (darker variant)
        self.secondary_color = self._hsl_to_hex(
            self.primary_hue,
            self.primary_saturation,
            max(20, self.primary_lightness - 25)
        )

    def _generate_color_palette(self) -> None:
        """Generate complete color palette based on harmony scheme."""
        palette = {
            'primary': self._generate_color_scale(
                self.primary_hue, 
                self.primary_saturation, 
                self.primary_lightness
            ),
            'secondary': self._generate_color_scale(
                self.primary_hue,
                self.primary_saturation,
                max(20, self.primary_lightness - 25)
            )
        }
        
        # Add harmony colors based on scheme
        if self.color_harmony == 'complementary':
            comp_hue = (self.primary_hue + 180) % 360
            palette['complementary'] = self._generate_color_scale(
                comp_hue, self.primary_saturation, self.primary_lightness
            )
        elif self.color_harmony == 'triadic':
            palette['triadic_1'] = self._generate_color_scale(
                (self.primary_hue + 120) % 360, 
                self.primary_saturation, 
                self.primary_lightness
            )
            palette['triadic_2'] = self._generate_color_scale(
                (self.primary_hue + 240) % 360, 
                self.primary_saturation, 
                self.primary_lightness
            )
        elif self.color_harmony == 'analogous':
            palette['analogous_1'] = self._generate_color_scale(
                (self.primary_hue + 30) % 360, 
                self.primary_saturation, 
                self.primary_lightness
            )
            palette['analogous_2'] = self._generate_color_scale(
                (self.primary_hue - 30) % 360, 
                self.primary_saturation, 
                self.primary_lightness
            )
        
        # Add semantic colors
        palette['success'] = self._generate_color_scale(142, 71, 45)  # Green
        palette['warning'] = self._generate_color_scale(38, 92, 50)   # Orange
        palette['error'] = self._generate_color_scale(0, 84, 60)      # Red
        palette['info'] = self._generate_color_scale(200, 98, 39)     # Light blue
        
        # Add neutral grays
        palette['neutral'] = self._generate_color_scale(220, 13, 50)  # Gray scale
        
        self.generated_palette = palette

    def _generate_color_scale(self, hue: int, saturation: int, base_lightness: int) -> dict[str, str]:
        """Generate a color scale with multiple lightness variants."""
        scale = {}
        
        # Generate 9 shades from very light to very dark
        lightness_values = [95, 85, 75, 65, base_lightness, 45, 35, 25, 15]
        shade_names = ['50', '100', '200', '300', '400', '500', '600', '700', '800']
        
        for i, lightness in enumerate(lightness_values):
            scale[shade_names[i]] = self._hsl_to_hex(hue, saturation, lightness)
        
        return scale

    def _hsl_to_hex(self, h: int, s: int, l: int) -> str:
        """Convert HSL values to hex color."""
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

    def get_contrast_ratio(self, color1: str, color2: str) -> float:
        """Calculate WCAG contrast ratio between two colors."""
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

    def validate_accessibility(self) -> dict[str, bool]:
        """Validate color accessibility against WCAG standards."""
        results = {}
        
        # Test primary color against white and black backgrounds
        primary_vs_white = self.get_contrast_ratio(self.primary_color, '#ffffff')
        primary_vs_black = self.get_contrast_ratio(self.primary_color, '#000000')
        
        results['primary_aa_white'] = primary_vs_white >= 4.5
        results['primary_aaa_white'] = primary_vs_white >= 7.0
        results['primary_aa_black'] = primary_vs_black >= 4.5
        results['primary_aaa_black'] = primary_vs_black >= 7.0
        
        # Test secondary color
        secondary_vs_white = self.get_contrast_ratio(self.secondary_color, '#ffffff')
        secondary_vs_black = self.get_contrast_ratio(self.secondary_color, '#000000')
        
        results['secondary_aa_white'] = secondary_vs_white >= 4.5
        results['secondary_aaa_white'] = secondary_vs_white >= 7.0
        results['secondary_aa_black'] = secondary_vs_black >= 4.5
        results['secondary_aaa_black'] = secondary_vs_black >= 7.0
        
        return results

    def generate_css_variables(self) -> str:
        """
        Generate comprehensive CSS variables for all design system tokens.
        
        Returns:
            CSS string with all custom properties for the design system.
        """
        css_vars = []
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # CORE THEME PARAMETERS
        # ═══════════════════════════════════════════════════════════════════════════════
        css_vars.extend([
            f"  --webops-hue-primary: {self.primary_hue};",
            f"  --webops-sat-primary: {self.primary_saturation}%;",
            f"  --webops-light-primary: {self.primary_lightness}%;",
        ])
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # PRIMARY COLOR SYSTEM
        # ═══════════════════════════════════════════════════════════════════════════════
        # Generate primary color variants
        primary_variants = self._generate_color_scale(
            self.primary_hue, 
            self.primary_saturation, 
            self.primary_lightness
        )
        
        for variant, color in primary_variants.items():
            css_vars.append(f"  --webops-primary-{variant}: {color};")
        
        # Primary color with alpha variants
        css_vars.extend([
            f"  --webops-primary-alpha-10: hsla({self.primary_hue}, {self.primary_saturation}%, {self.primary_lightness}%, 0.1);",
            f"  --webops-primary-alpha-20: hsla({self.primary_hue}, {self.primary_saturation}%, {self.primary_lightness}%, 0.2);",
            f"  --webops-primary-alpha-50: hsla({self.primary_hue}, {self.primary_saturation}%, {self.primary_lightness}%, 0.5);",
        ])
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # SEMANTIC STATUS COLORS
        # ═══════════════════════════════════════════════════════════════════════════════
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
            f"  --webops-accent: {self.accent_color};",
        ])
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # NEUTRAL GRAYSCALE SYSTEM
        # ═══════════════════════════════════════════════════════════════════════════════
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
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # TYPOGRAPHY SYSTEM
        # ═══════════════════════════════════════════════════════════════════════════════
        css_vars.extend([
            f"  --webops-font-family-primary: {self.font_family_primary};",
            f"  --webops-font-family-mono: {self.font_family_mono};",
            f"  --webops-font-size-base: {self.font_size_base}rem;",
            f"  --webops-font-weight-normal: {self.font_weight_normal};",
            f"  --webops-font-weight-medium: {self.font_weight_medium};",
            f"  --webops-font-weight-bold: {self.font_weight_bold};",
            f"  --webops-line-height-tight: {self.line_height_tight};",
            f"  --webops-line-height-normal: {self.line_height_normal};",
            f"  --webops-line-height-relaxed: {self.line_height_relaxed};",
        ])
        
        # Font size scale (calculated from base)
        font_sizes = {
            'xs': self.font_size_base * 0.75,
            'sm': self.font_size_base * 0.875,
            'base': self.font_size_base,
            'lg': self.font_size_base * 1.125,
            'xl': self.font_size_base * 1.25,
            '2xl': self.font_size_base * 1.5,
            '3xl': self.font_size_base * 1.875,
            '4xl': self.font_size_base * 2.25,
        }
        
        for size, value in font_sizes.items():
            css_vars.append(f"  --webops-font-size-{size}: {value}rem;")
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # SPACING SYSTEM
        # ═══════════════════════════════════════════════════════════════════════════════
        css_vars.extend([
            f"  --webops-spacing-base: {self.spacing_base_unit}px;",
            f"  --webops-container-padding-desktop: {self.container_padding_desktop}px;",
            f"  --webops-container-padding-mobile: {self.container_padding_mobile}px;",
            f"  --webops-component-spacing-compact: {self.component_spacing_compact}px;",
            f"  --webops-component-spacing-normal: {self.component_spacing_normal}px;",
            f"  --webops-component-spacing-relaxed: {self.component_spacing_relaxed}px;",
        ])
        
        # Generate spacing scale
        spacing_scale = {}
        for i in range(0, 17):  # 0 to 16
            if i == 0:
                spacing_scale[i] = 0
            elif i <= 4:
                spacing_scale[i] = i * self.spacing_base_unit
            else:
                spacing_scale[i] = (i * self.spacing_base_unit) + ((i - 4) * self.spacing_base_unit)
        
        for scale, value in spacing_scale.items():
            css_vars.append(f"  --webops-spacing-{scale}: {value}px;")
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # BORDER RADIUS SYSTEM
        # ═══════════════════════════════════════════════════════════════════════════════
        css_vars.extend([
            f"  --webops-radius-small: {self.border_radius_small}px;",
            f"  --webops-radius-medium: {self.border_radius_medium}px;",
            f"  --webops-radius-large: {self.border_radius_large}px;",
            "  --webops-radius-full: 9999px;",
        ])
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # SHADOW SYSTEM
        # ═══════════════════════════════════════════════════════════════════════════════
        shadow_opacity = self.shadow_intensity / 100.0
        
        css_vars.extend([
            f"  --webops-shadow-small: 0 1px {self.shadow_blur_small}px rgba(0, 0, 0, {shadow_opacity * 0.1});",
            f"  --webops-shadow-medium: 0 4px {self.shadow_blur_medium}px rgba(0, 0, 0, {shadow_opacity * 0.15});",
            f"  --webops-shadow-large: 0 10px {self.shadow_blur_large}px rgba(0, 0, 0, {shadow_opacity * 0.2});",
        ])
        
        # Themed shadows (if enabled)
        if self.enable_themed_shadows:
            css_vars.extend([
                f"  --webops-shadow-primary: 0 4px {self.shadow_blur_medium}px hsla({self.primary_hue}, {self.primary_saturation}%, {self.primary_lightness}%, 0.3);",
                f"  --webops-shadow-accent: 0 4px {self.shadow_blur_medium}px hsla(142, 76%, 36%, 0.3);",
            ])
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # ANIMATION SYSTEM
        # ═══════════════════════════════════════════════════════════════════════════════
        css_vars.extend([
            f"  --webops-duration-fast: {self.animation_duration_fast}ms;",
            f"  --webops-duration-normal: {self.animation_duration_normal}ms;",
            f"  --webops-duration-slow: {self.animation_duration_slow}ms;",
            f"  --webops-easing: {self.animation_easing};",
        ])
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # LAYOUT DIMENSIONS
        # ═══════════════════════════════════════════════════════════════════════════════
        css_vars.extend([
            f"  --webops-header-height-desktop: {self.header_height_desktop}px;",
            f"  --webops-header-height-mobile: {self.header_height_mobile}px;",
            f"  --webops-sidebar-width-desktop: {self.sidebar_width_desktop}px;",
            f"  --webops-sidebar-width-collapsed: {self.sidebar_width_collapsed}px;",
            f"  --webops-content-max-width: {self.content_max_width}px;",
        ])
        
        # Component dimensions
        css_vars.extend([
            f"  --webops-input-height-small: {self.input_height_small}px;",
            f"  --webops-input-height-medium: {self.input_height_medium}px;",
            f"  --webops-input-height-large: {self.input_height_large}px;",
            f"  --webops-button-height-small: {self.button_height_small}px;",
            f"  --webops-button-height-medium: {self.button_height_medium}px;",
            f"  --webops-button-height-large: {self.button_height_large}px;",
        ])
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # INTERACTIVE STATES
        # ═══════════════════════════════════════════════════════════════════════════════
        css_vars.extend([
            f"  --webops-hover-opacity: {self.hover_opacity};",
            f"  --webops-hover-scale: {self.hover_scale};",
            f"  --webops-focus-ring-width: {self.focus_ring_width}px;",
            f"  --webops-focus-ring-offset: {self.focus_ring_offset}px;",
            f"  --webops-active-scale: {self.active_scale};",
        ])
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # RESPONSIVE BREAKPOINTS
        # ═══════════════════════════════════════════════════════════════════════════════
        css_vars.extend([
            "  --webops-breakpoint-sm: 640px;",
            "  --webops-breakpoint-md: 768px;",
            "  --webops-breakpoint-lg: 1024px;",
            "  --webops-breakpoint-xl: 1280px;",
            "  --webops-breakpoint-2xl: 1536px;",
        ])
        
        # Reduced motion support
        reduced_motion_css = ""
        if self.respect_reduced_motion:
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

    @classmethod
    def get_settings(cls):
        """Get or create the singleton branding settings instance."""
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings


class Webhook(BaseModel):
    """
    Webhook configuration for automated deployments.

    Supports GitHub push events, manual triggers, and other webhook sources.
    Each webhook has a unique secret for security validation.
    """

    class TriggerEvent(models.TextChoices):
        PUSH = 'push', 'Push to Branch'
        PULL_REQUEST = 'pull_request', 'Pull Request'
        RELEASE = 'release', 'Release Created'
        MANUAL = 'manual', 'Manual Trigger'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        FAILED = 'failed', 'Failed'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='webhooks'
    )
    deployment = models.ForeignKey(
        'deployments.Deployment',
        on_delete=models.CASCADE,
        related_name='webhooks'
    )
    name = models.CharField(max_length=100)
    trigger_event = models.CharField(
        max_length=20,
        choices=TriggerEvent.choices,
        default=TriggerEvent.PUSH
    )
    branch_filter = models.CharField(
        max_length=100,
        blank=True,
        help_text='Only trigger for specific branch (empty = all branches)'
    )
    secret = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    last_triggered = models.DateTimeField(null=True, blank=True)
    trigger_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        db_table = 'core_webhook'
        verbose_name = 'Webhook'
        verbose_name_plural = 'Webhooks'
        indexes = [
            models.Index(fields=['secret']),
            models.Index(fields=['deployment', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.name} → {self.deployment.name}"


class WebhookDelivery(BaseModel):
    """
    Record of webhook delivery attempts and responses.

    Tracks each webhook trigger for debugging and audit purposes.
    """

    class Status(models.TextChoices):
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        PENDING = 'pending', 'Pending'

    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name='deliveries'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    payload = models.JSONField(default=dict)
    response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    triggered_by = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'core_webhook_delivery'
        verbose_name = 'Webhook Delivery'
        verbose_name_plural = 'Webhook Deliveries'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.webhook.name} - {self.status} at {self.created_at}"


class NotificationChannel(BaseModel):
    """
    Notification channel configuration for deployment alerts.

    Supports email, webhook, and other notification types.
    Each channel can be configured with specific events to monitor.
    """

    class ChannelType(models.TextChoices):
        EMAIL = 'email', 'Email'
        WEBHOOK = 'webhook', 'Webhook URL'
        SMTP = 'smtp', 'SMTP Email'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        FAILED = 'failed', 'Failed'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notification_channels'
    )
    name = models.CharField(max_length=100)
    channel_type = models.CharField(
        max_length=20,
        choices=ChannelType.choices,
        default=ChannelType.EMAIL
    )
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    # Channel-specific configuration
    config = models.JSONField(
        default=dict,
        help_text='Channel configuration (email address, webhook URL, SMTP settings, etc.)'
    )

    # Event filters
    notify_on_deploy_success = models.BooleanField(default=True)
    notify_on_deploy_failure = models.BooleanField(default=True)
    notify_on_deploy_start = models.BooleanField(default=False)
    notify_on_health_check_fail = models.BooleanField(default=True)
    notify_on_resource_warning = models.BooleanField(default=False)

    # Delivery tracking
    last_notification = models.DateTimeField(null=True, blank=True)
    notification_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        db_table = 'core_notification_channel'
        verbose_name = 'Notification Channel'
        verbose_name_plural = 'Notification Channels'
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_active', 'status']),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.channel_type})"


class NotificationLog(BaseModel):
    """
    Log of sent notifications for audit and debugging.
    """

    class Status(models.TextChoices):
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        PENDING = 'pending', 'Pending'

    channel = models.ForeignKey(
        NotificationChannel,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    event_type = models.CharField(max_length=50)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'core_notification_log'
        verbose_name = 'Notification Log'
        verbose_name_plural = 'Notification Logs'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.channel.name} - {self.event_type} ({self.status})"