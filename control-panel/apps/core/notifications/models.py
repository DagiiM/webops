"""
Notification models for WebOps.

"Database Models" section
Architecture: Notification channels, delivery tracking, event filtering
"""

from django.db import models
from django.contrib.auth.models import User
from apps.core.common.models import BaseModel


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


class UserNotification(BaseModel):
    """
    In-app notifications for users.

    These notifications appear in the notification bell/center in the UI.
    Provides a persistent record of user-facing notifications with read tracking.

    Inherits from BaseModel to get:
    - created_at, updated_at: Timestamp tracking
    - Soft-delete functionality (is_deleted, deleted_at, deleted_by)
    - Notification dispatch (send_notification, notify_*)
    """

    class NotificationType(models.TextChoices):
        SUCCESS = 'success', 'Success'
        ERROR = 'error', 'Error'
        WARNING = 'warning', 'Warning'
        INFO = 'info', 'Info'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text='User who receives this notification'
    )
    title = models.CharField(
        max_length=200,
        help_text='Notification title/headline'
    )
    message = models.TextField(
        help_text='Detailed notification message'
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.INFO,
        help_text='Type of notification (affects icon and color)'
    )

    # Read tracking
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Whether the user has read this notification'
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the notification was read'
    )

    # Related object tracking (generic relation alternative)
    related_object_type = models.CharField(
        max_length=50,
        blank=True,
        help_text='Type of related object (e.g., "deployment", "alert", "database")'
    )
    related_object_id = models.IntegerField(
        null=True,
        blank=True,
        help_text='ID of the related object'
    )

    # Action/navigation
    action_url = models.CharField(
        max_length=500,
        blank=True,
        help_text='URL to navigate to when notification is clicked'
    )
    action_text = models.CharField(
        max_length=100,
        blank=True,
        default='View',
        help_text='Text for the action button'
    )

    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional notification metadata'
    )

    # Priority/importance
    is_important = models.BooleanField(
        default=False,
        help_text='High-priority notification (shown prominently)'
    )

    class Meta:
        db_table = 'core_user_notification'
        verbose_name = 'User Notification'
        verbose_name_plural = 'User Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
            models.Index(fields=['related_object_type', 'related_object_id']),
        ]

    def __str__(self) -> str:
        read_status = "read" if self.is_read else "unread"
        return f"{self.user.username} - {self.title} ({read_status})"

    def mark_as_read(self) -> None:
        """Mark this notification as read."""
        if not self.is_read:
            self.is_read = True
            from django.utils import timezone
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def get_related_object(self):
        """
        Get the related object if it exists.

        Returns:
            The related model instance or None
        """
        if not self.related_object_type or not self.related_object_id:
            return None

        try:
            from django.apps import apps
            model = apps.get_model(self.related_object_type)
            return model.objects.get(pk=self.related_object_id)
        except Exception:
            return None

    @classmethod
    def create_for_user(
        cls,
        user: User,
        title: str,
        message: str,
        notification_type: str = NotificationType.INFO,
        action_url: str = '',
        action_text: str = 'View',
        related_object=None,
        is_important: bool = False,
        **metadata
    ) -> 'UserNotification':
        """
        Create a notification for a user.

        Args:
            user: User to notify
            title: Notification title
            message: Notification message
            notification_type: Type of notification (success/error/warning/info)
            action_url: URL for action button
            action_text: Text for action button
            related_object: Related model instance (optional)
            is_important: Whether this is a high-priority notification
            **metadata: Additional metadata

        Returns:
            Created UserNotification instance
        """
        notification = cls(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url,
            action_text=action_text,
            is_important=is_important,
            metadata=metadata
        )

        # Set related object if provided
        if related_object:
            notification.related_object_type = f"{related_object._meta.app_label}.{related_object._meta.model_name}"
            notification.related_object_id = related_object.pk

        notification.save()
        return notification

    @classmethod
    def create_for_users(
        cls,
        users,
        title: str,
        message: str,
        **kwargs
    ) -> list:
        """
        Create notifications for multiple users.

        Args:
            users: QuerySet or list of User instances
            title: Notification title
            message: Notification message
            **kwargs: Additional arguments passed to create_for_user

        Returns:
            List of created UserNotification instances
        """
        notifications = []
        for user in users:
            notification = cls.create_for_user(
                user=user,
                title=title,
                message=message,
                **kwargs
            )
            notifications.append(notification)
        return notifications