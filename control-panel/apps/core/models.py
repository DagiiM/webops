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
    Branding configuration for the WebOps control panel.

    Singleton model - only one instance should exist.
    Stores customizable branding elements like site name, logo, colors.
    """

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
    primary_color = models.CharField(
        max_length=7,
        default='#3b82f6',
        help_text='Primary brand color (hex format: #RRGGBB)'
    )
    secondary_color = models.CharField(
        max_length=7,
        default='#1e40af',
        help_text='Secondary brand color (hex format: #RRGGBB)'
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
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_branding_settings'
        verbose_name = 'Branding Settings'
        verbose_name_plural = 'Branding Settings'

    def __str__(self) -> str:
        return f"Branding: {self.site_name}"

    def save(self, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)."""
        if not self.pk and BrandingSettings.objects.exists():
            # Update existing instance instead of creating new
            existing = BrandingSettings.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)

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