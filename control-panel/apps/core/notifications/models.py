"""
Notification models for WebOps.

"Database Models" section
Architecture: Notification channels, delivery tracking, event filtering
"""

from django.db import models
from django.contrib.auth.models import User


class BaseModel(models.Model):
    """Abstract base model with common fields for all models."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class NotificationChannel(BaseModel):
    """
    Configuration for notification channels.

    Supports email, webhook, and custom SMTP notifications
    with flexible event filtering.
    """

    class ChannelType(models.TextChoices):
        EMAIL = 'email', 'Email'
        WEBHOOK = 'webhook', 'Webhook'
        SMTP = 'smtp', 'Custom SMTP'

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
    config = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    notification_count = models.IntegerField(default=0)
    last_notification = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    # Event filters
    notify_on_deploy_success = models.BooleanField(default=True)
    notify_on_deploy_failure = models.BooleanField(default=True)
    notify_on_deploy_start = models.BooleanField(default=False)
    notify_on_health_check_fail = models.BooleanField(default=True)
    notify_on_resource_warning = models.BooleanField(default=False)

    class Meta:
        db_table = 'core_notification_channel'
        verbose_name = 'Notification Channel'
        verbose_name_plural = 'Notification Channels'
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['channel_type', 'is_active']),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.channel_type})"


class NotificationLog(BaseModel):
    """
    Record of notification delivery attempts and responses.

    Tracks each notification for debugging and audit purposes.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    channel = models.ForeignKey(
        NotificationChannel,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    event_type = models.CharField(max_length=50)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = 'core_notification_log'
        verbose_name = 'Notification Log'
        verbose_name_plural = 'Notification Logs'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.channel.name} - {self.status} at {self.created_at}"