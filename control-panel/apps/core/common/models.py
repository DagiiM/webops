"""
Common base models for WebOps core app.

This module contains abstract base models and common configuration models
used across all core app domains.
"""

from django.db import models
from django.utils import timezone
from .mixins import Trashable, Notifiable


class BaseModel(Trashable, Notifiable, models.Model):
    """
    Abstract base model with common fields for all models.

    Inherits from:
    - Trashable: Provides soft-delete functionality
    - Notifiable: Provides notification dispatch functionality
    - models.Model: Django base model

    All models inheriting from BaseModel automatically get:
    - created_at, updated_at: Timestamp tracking
    - is_deleted, deleted_at, deleted_by: Soft-delete support
    - send_notification(), notify_*(): Notification methods
    """

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class Configuration(BaseModel):
    """Dynamic configuration settings stored in database."""

    class ConfigType(models.TextChoices):
        OAUTH = 'oauth', 'OAuth Configuration'
        INTEGRATION = 'integration', 'Integration Settings'
        SYSTEM = 'system', 'System Settings'
        NOTIFICATION = 'notification', 'Notification Settings'
        SECURITY = 'security', 'Security Settings'

    key = models.CharField(
        max_length=100,
        unique=True,
        help_text='Configuration key (e.g., google_oauth_client_id)'
    )
    value = models.TextField(
        blank=True,
        help_text='Configuration value (encrypted for sensitive data)'
    )
    config_type = models.CharField(
        max_length=20,
        choices=ConfigType.choices,
        default=ConfigType.SYSTEM,
        help_text='Type of configuration'
    )
    is_sensitive = models.BooleanField(
        default=False,
        help_text='Whether this value should be encrypted'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this configuration is active'
    )
    description = models.TextField(
        blank=True,
        help_text='Description of what this configuration does'
    )
    default_value = models.TextField(
        blank=True,
        help_text='Default value if not set'
    )

    class Meta:
        db_table = 'core_configuration'
        verbose_name = 'Configuration'
        verbose_name_plural = 'Configurations'
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['config_type', 'is_active']),
        ]

    def __str__(self) -> str:
        return f"{self.key} ({self.config_type})"

    def get_value(self) -> str:
        """Get the configuration value, decrypting if necessary."""
        if self.is_sensitive and self.value:
            from apps.core.security.services import EncryptionService
            encryption_service = EncryptionService()
            try:
                return encryption_service.decrypt(self.value)
            except Exception:
                return self.default_value
        return self.value or self.default_value

    def set_value(self, value: str) -> None:
        """Set the configuration value, encrypting if necessary."""
        if self.is_sensitive and value:
            from apps.core.security.services import EncryptionService
            encryption_service = EncryptionService()
            self.value = encryption_service.encrypt(value)
        else:
            self.value = value

    @classmethod
    def get_config(cls, key: str, default: str = '') -> str:
        """Get a configuration value by key."""
        try:
            config = cls.objects.get(key=key, is_active=True)
            return config.get_value()
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_config(cls, key: str, value: str, config_type: str = ConfigType.SYSTEM,
                   is_sensitive: bool = False, description: str = '') -> 'Configuration':
        """Set a configuration value by key."""
        config, created = cls.objects.get_or_create(
            key=key,
            defaults={
                'value': '',
                'config_type': config_type,
                'is_sensitive': is_sensitive,
                'description': description,
            }
        )
        config.set_value(value)
        config.save()
        return config


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
