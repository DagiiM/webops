"""
Webhook models for WebOps.

"Database Models" section
Architecture: Webhook configuration, delivery tracking, automated deployments
"""

from django.db import models
from django.contrib.auth.models import User
from apps.core.common.models import BaseModel
from apps.core.security.encryption import encrypt_field, decrypt_field, is_encrypted


class Webhook(BaseModel):
    """
    Webhook configuration for automated deployments.

    Supports GitHub push events, manual triggers, and other webhook sources.
    Each webhook has a unique secret for security validation.

    SECURITY: Webhook secrets are encrypted at rest using Fernet symmetric encryption.
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
        'deployments.BaseDeployment',
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
    # SECURITY FIX: Store encrypted webhook secret
    # Note: Field is longer to accommodate encrypted data (Fernet tokens are ~140 bytes)
    _secret_encrypted = models.CharField(
        max_length=256,
        unique=True,
        db_column='secret',
        help_text='Encrypted webhook secret for request validation'
    )
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
            models.Index(fields=['_secret_encrypted']),
            models.Index(fields=['deployment', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.name} → {self.deployment.name}"

    @property
    def secret(self) -> str:
        """
        Get decrypted webhook secret.

        Returns:
            Decrypted secret string

        Raises:
            ValueError: If encryption key is not configured
        """
        if not self._secret_encrypted:
            return ''

        # Check if already encrypted - if not, it's legacy unencrypted data
        if not is_encrypted(self._secret_encrypted):
            # Legacy unencrypted secret - return as-is and log warning
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Webhook {self.id} has unencrypted secret. "
                "Run data migration to encrypt."
            )
            return self._secret_encrypted

        return decrypt_field(self._secret_encrypted)

    @secret.setter
    def secret(self, value: str) -> None:
        """
        Set webhook secret with automatic encryption.

        Args:
            value: Plain text webhook secret
        """
        if value:
            self._secret_encrypted = encrypt_field(value)
        else:
            self._secret_encrypted = ''


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