"""
Authentication models for WebOps.

Contains models for Two-Factor Authentication (2FA) using TOTP
and User Preferences for persistent settings storage.
Compatible with Google Authenticator, Authy, and other authenticator apps.
"""

from django.db import models
from django.contrib.auth.models import User

from apps.core.common.models import BaseModel


class TwoFactorAuth(BaseModel):
    """
    Two-Factor Authentication settings for users.

    Inherits from BaseModel to get:
    - created_at, updated_at: Timestamp tracking
    - Soft-delete functionality (is_deleted, deleted_at, deleted_by)
    - Notification dispatch (send_notification, notify_*)

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
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'core_two_factor_auth'
        verbose_name = '2FA Setting'
        verbose_name_plural = '2FA Settings'

    def __str__(self) -> str:
        status = "enabled" if self.is_enabled else "disabled"
        return f"{self.user.username} - 2FA {status}"


class UserPreferences(BaseModel):
    """
    User preferences and settings for the WebOps control panel.

    Inherits from BaseModel to get:
    - created_at, updated_at: Timestamp tracking
    - Soft-delete functionality (is_deleted, deleted_at, deleted_by)
    - Notification dispatch (send_notification, notify_*)

    Stores all user-specific preferences including appearance, language,
    notifications, privacy settings, and other customization options.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='preferences'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # APPEARANCE SETTINGS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    theme = models.CharField(
        max_length=20,
        default='system',
        choices=[
            ('system', 'System Default'),
            ('light', 'Light'),
            ('dark', 'Dark'),
        ],
        help_text='Preferred theme for the interface'
    )
    
    animations_enabled = models.BooleanField(
        default=True,
        help_text='Enable UI animations and transitions'
    )
    
    compact_view = models.BooleanField(
        default=False,
        help_text='Use compact spacing for UI elements'
    )
    
    font_size = models.CharField(
        max_length=20,
        default='medium',
        choices=[
            ('small', 'Small'),
            ('medium', 'Medium'),
            ('large', 'Large'),
            ('extra_large', 'Extra Large'),
        ],
        help_text='Preferred font size for the interface'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # LANGUAGE & REGIONAL SETTINGS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    interface_language = models.CharField(
        max_length=10,
        default='en',
        choices=[
            ('en', 'English'),
            ('es', 'Spanish'),
            ('fr', 'French'),
            ('de', 'German'),
            ('it', 'Italian'),
            ('pt', 'Portuguese'),
            ('ru', 'Russian'),
            ('zh', 'Chinese'),
            ('ja', 'Japanese'),
        ],
        help_text='Preferred interface language'
    )
    
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        help_text='User timezone for displaying dates and times'
    )
    
    date_format = models.CharField(
        max_length=20,
        default='YYYY-MM-DD',
        choices=[
            ('YYYY-MM-DD', 'ISO (2023-12-25)'),
            ('MM/DD/YYYY', 'US (12/25/2023)'),
            ('DD/MM/YYYY', 'European (25/12/2023)'),
            ('DD.MM.YYYY', 'German (25.12.2023)'),
        ],
        help_text='Preferred date format'
    )
    
    time_format = models.CharField(
        max_length=10,
        default='24h',
        choices=[
            ('12h', '12-hour (3:00 PM)'),
            ('24h', '24-hour (15:00)'),
        ],
        help_text='Preferred time format'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # NOTIFICATION SETTINGS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    email_notifications_enabled = models.BooleanField(
        default=True,
        help_text='Receive email notifications'
    )
    
    browser_notifications_enabled = models.BooleanField(
        default=True,
        help_text='Receive browser push notifications'
    )
    
    deployment_notifications = models.BooleanField(
        default=True,
        help_text='Notifications for deployment events'
    )
    
    security_notifications = models.BooleanField(
        default=True,
        help_text='Notifications for security events'
    )
    
    system_notifications = models.BooleanField(
        default=True,
        help_text='Notifications for system updates and maintenance'
    )
    
    notification_frequency = models.CharField(
        max_length=20,
        default='immediate',
        choices=[
            ('immediate', 'Immediate'),
            ('hourly', 'Hourly Digest'),
            ('daily', 'Daily Digest'),
            ('weekly', 'Weekly Digest'),
        ],
        help_text='Frequency of email notifications'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # PRIVACY SETTINGS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    activity_tracking = models.BooleanField(
        default=True,
        help_text='Track user activity for analytics and improvements'
    )
    
    personalized_recommendations = models.BooleanField(
        default=True,
        help_text='Show personalized recommendations based on usage patterns'
    )
    
    third_party_integrations = models.BooleanField(
        default=False,
        help_text='Allow third-party integrations and services'
    )
    
    analytics_sharing = models.BooleanField(
        default=False,
        help_text='Share anonymous usage data for product improvement'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # DASHBOARD SETTINGS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    dashboard_layout = models.CharField(
        max_length=20,
        default='grid',
        choices=[
            ('grid', 'Grid Layout'),
            ('list', 'List Layout'),
            ('compact', 'Compact Layout'),
        ],
        help_text='Preferred dashboard layout'
    )
    
    default_dashboard_tab = models.CharField(
        max_length=20,
        default='overview',
        choices=[
            ('overview', 'Overview'),
            ('deployments', 'Deployments'),
            ('databases', 'Databases'),
            ('services', 'Services'),
        ],
        help_text='Default tab to show on dashboard'
    )
    
    items_per_page = models.IntegerField(
        default=20,
        choices=[
            (10, '10 items'),
            (20, '20 items'),
            (50, '50 items'),
            (100, '100 items'),
        ],
        help_text='Number of items to display per page in lists'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # SECURITY SETTINGS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    session_timeout = models.IntegerField(
        default=24,
        choices=[
            (1, '1 hour'),
            (8, '8 hours'),
            (24, '24 hours'),
            (168, '1 week'),
            (720, '30 days'),
        ],
        help_text='Session timeout in hours'
    )
    
    require_2fa_for_sensitive = models.BooleanField(
        default=False,
        help_text='Require 2FA for sensitive operations'
    )
    
    login_notifications = models.BooleanField(
        default=True,
        help_text='Receive notifications for new login attempts'
    )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # DEVELOPER SETTINGS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    show_advanced_options = models.BooleanField(
        default=False,
        help_text='Show advanced technical options in the interface'
    )
    
    debug_mode = models.BooleanField(
        default=False,
        help_text='Enable debug information and developer tools'
    )
    
    beta_features = models.BooleanField(
        default=False,
        help_text='Enable beta features and experimental functionality'
    )

    class Meta:
        db_table = 'core_user_preferences'
        verbose_name = 'User Preferences'
        verbose_name_plural = 'User Preferences'

    def __str__(self) -> str:
        return f"{self.user.username} - Preferences"

    def save(self, *args, **kwargs):
        """Create user preferences if they don't exist."""
        if not self.pk and not UserPreferences.objects.filter(user=self.user).exists():
            # This is a new preference object, save normally
            super().save(*args, **kwargs)
        else:
            # Update existing preferences
            super().save(*args, **kwargs)

    @classmethod
    def get_preferences(cls, user):
        """Get or create user preferences for the given user."""
        preferences, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'theme': 'system',
                'animations_enabled': True,
                'compact_view': False,
                'font_size': 'medium',
                'interface_language': 'en',
                'timezone': 'UTC',
                'date_format': 'YYYY-MM-DD',
                'time_format': '24h',
                'email_notifications_enabled': True,
                'browser_notifications_enabled': True,
                'deployment_notifications': True,
                'security_notifications': True,
                'system_notifications': True,
                'notification_frequency': 'immediate',
                'activity_tracking': True,
                'personalized_recommendations': True,
                'third_party_integrations': False,
                'analytics_sharing': False,
                'dashboard_layout': 'grid',
                'default_dashboard_tab': 'overview',
                'items_per_page': 20,
                'session_timeout': 24,
                'require_2fa_for_sensitive': False,
                'login_notifications': True,
                'show_advanced_options': False,
                'debug_mode': False,
                'beta_features': False,
            }
        )
        return preferences

    def to_dict(self):
        """Convert preferences to dictionary for API responses."""
        return {
            'theme': self.theme,
            'animations_enabled': self.animations_enabled,
            'compact_view': self.compact_view,
            'font_size': self.font_size,
            'interface_language': self.interface_language,
            'timezone': self.timezone,
            'date_format': self.date_format,
            'time_format': self.time_format,
            'email_notifications_enabled': self.email_notifications_enabled,
            'browser_notifications_enabled': self.browser_notifications_enabled,
            'deployment_notifications': self.deployment_notifications,
            'security_notifications': self.security_notifications,
            'system_notifications': self.system_notifications,
            'notification_frequency': self.notification_frequency,
            'activity_tracking': self.activity_tracking,
            'personalized_recommendations': self.personalized_recommendations,
            'third_party_integrations': self.third_party_integrations,
            'analytics_sharing': self.analytics_sharing,
            'dashboard_layout': self.dashboard_layout,
            'default_dashboard_tab': self.default_dashboard_tab,
            'items_per_page': self.items_per_page,
            'session_timeout': self.session_timeout,
            'require_2fa_for_sensitive': self.require_2fa_for_sensitive,
            'login_notifications': self.login_notifications,
            'show_advanced_options': self.show_advanced_options,
            'debug_mode': self.debug_mode,
            'beta_features': self.beta_features,
        }

    def update_from_dict(self, data):
        """Update preferences from a dictionary."""
        updatable_fields = [
            'theme', 'animations_enabled', 'compact_view', 'font_size',
            'interface_language', 'timezone', 'date_format', 'time_format',
            'email_notifications_enabled', 'browser_notifications_enabled',
            'deployment_notifications', 'security_notifications', 'system_notifications',
            'notification_frequency', 'activity_tracking', 'personalized_recommendations',
            'third_party_integrations', 'analytics_sharing', 'dashboard_layout',
            'default_dashboard_tab', 'items_per_page', 'session_timeout',
            'require_2fa_for_sensitive', 'login_notifications',
            'show_advanced_options', 'debug_mode', 'beta_features'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(self, field, data[field])
        
        self.save()
