"""
Common model mixins for WebOps.

This module provides reusable mixins that can be added to Django models
to provide consistent behavior across the application.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from typing import Optional, Dict, Any


class Trashable(models.Model):
    """
    Mixin for soft-delete functionality.

    Adds fields and methods to support moving items to trash instead of
    permanently deleting them. Works with the TrashItem model to track
    deleted items for potential restoration.

    Usage:
        class MyModel(Trashable, models.Model):
            name = models.CharField(max_length=100)

        # Soft delete
        obj.soft_delete(user=request.user)

        # Check if deleted
        if obj.is_deleted:
            print("This item is in trash")

        # Restore from trash
        obj.restore(user=request.user)
    """

    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this item has been moved to trash"
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this item was moved to trash"
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_deleted",
        help_text="User who moved this item to trash"
    )

    class Meta:
        abstract = True

    def soft_delete(self, user: Optional[Any] = None, **kwargs) -> bool:
        """
        Soft delete this object by marking it as deleted and creating a TrashItem entry.

        Args:
            user: The user performing the deletion
            **kwargs: Additional metadata to store in TrashItem

        Returns:
            True if deletion was successful, False otherwise
        """
        if self.is_deleted:
            return False

        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])

        # Create TrashItem entry
        from apps.trash.trash_manager import TrashManager

        item_type = f"{self._meta.app_label}.{self._meta.model_name}"
        item_name = str(self)

        # Build metadata
        metadata = {
            'model': self._meta.label,
            'pk': self.pk,
            **kwargs
        }

        # Add any custom metadata from the model
        if hasattr(self, 'get_trash_metadata'):
            metadata.update(self.get_trash_metadata())

        TrashManager.move_to_trash(
            item_type=item_type,
            item_name=item_name,
            metadata=metadata,
            deleted_by=user
        )

        return True

    def restore(self, user: Optional[Any] = None) -> bool:
        """
        Restore this object from trash.

        Args:
            user: The user performing the restoration

        Returns:
            True if restoration was successful, False otherwise
        """
        if not self.is_deleted:
            return False

        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])

        # Update TrashItem entry
        from apps.trash.models import TrashItem

        item_type = f"{self._meta.app_label}.{self._meta.model_name}"

        try:
            trash_item = TrashItem.objects.filter(
                item_type=item_type,
                metadata__pk=self.pk,
                is_restored=False
            ).first()

            if trash_item:
                trash_item.restore(user=user)
        except Exception:
            pass  # TrashItem update is optional

        return True

    def hard_delete(self, *args, **kwargs) -> tuple:
        """
        Permanently delete this object, bypassing soft delete.

        Returns:
            Tuple of (number of objects deleted, dictionary with details)
        """
        return super().delete(*args, **kwargs)

    def delete(self, using=None, keep_parents=False, soft: bool = True, user: Optional[Any] = None):
        """
        Override default delete to use soft delete by default.

        Args:
            using: Database alias
            keep_parents: Whether to keep parent objects (for multi-table inheritance)
            soft: If True, perform soft delete; if False, hard delete
            user: User performing the deletion

        Returns:
            For soft delete: True/False success
            For hard delete: Tuple of (number deleted, details dict)
        """
        if soft:
            return self.soft_delete(user=user)
        else:
            return super().delete(using=using, keep_parents=keep_parents)


class Notifiable(models.Model):
    """
    Mixin for notification dispatch functionality.

    Adds methods to send notifications related to this model instance.
    Works with the NotificationChannel and NotificationLog models to
    dispatch notifications through configured channels.

    Usage:
        class MyModel(Notifiable, models.Model):
            name = models.CharField(max_length=100)

        # Send notification
        obj.send_notification(
            event_type='deployment.created',
            subject='New Deployment',
            message='Deployment was created successfully'
        )

        # With custom context
        obj.send_notification(
            event_type='deployment.failed',
            subject='Deployment Failed',
            message='Deployment failed to build',
            context={'error': 'Build error message'}
        )
    """

    class Meta:
        abstract = True

    def send_notification(
        self,
        event_type: str,
        subject: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        user: Optional[Any] = None
    ) -> bool:
        """
        Send notification for this model instance.

        Args:
            event_type: Type of event (e.g., 'deployment.created', 'database.failed')
            subject: Notification subject line
            message: Notification message body
            context: Additional context data for the notification
            user: User associated with this notification

        Returns:
            True if notification was sent successfully, False otherwise
        """
        from apps.core.notifications.services import NotificationService
        from apps.core.notifications.models import NotificationChannel

        # Build notification context
        notification_context = {
            'model': self._meta.label,
            'model_name': self._meta.verbose_name,
            'object_id': self.pk,
            'object_str': str(self),
        }

        if context:
            notification_context.update(context)

        # Add custom context from the model
        if hasattr(self, 'get_notification_context'):
            notification_context.update(self.get_notification_context())

        # Get notification service
        service = NotificationService()

        # Find active channels that match this event type
        channels = NotificationChannel.objects.filter(
            is_active=True
        )

        # Filter channels by event type
        matching_channels = []
        for channel in channels:
            if channel.events and event_type in channel.events:
                matching_channels.append(channel)

        # Send notification through each matching channel
        success = False
        for channel in matching_channels:
            try:
                result = service.send_notification(
                    channel=channel,
                    event_type=event_type,
                    subject=subject,
                    message=message,
                    metadata=notification_context
                )
                if result:
                    success = True
            except Exception:
                continue  # Continue trying other channels

        return success

    def notify_created(self, user: Optional[Any] = None) -> bool:
        """
        Send notification when this object is created.

        Args:
            user: User who created the object

        Returns:
            True if notification was sent successfully
        """
        event_type = f"{self._meta.app_label}.{self._meta.model_name}.created"
        subject = f"{self._meta.verbose_name} Created"
        message = f"A new {self._meta.verbose_name} '{self}' was created."

        return self.send_notification(
            event_type=event_type,
            subject=subject,
            message=message,
            user=user
        )

    def notify_updated(self, user: Optional[Any] = None, fields: Optional[list] = None) -> bool:
        """
        Send notification when this object is updated.

        Args:
            user: User who updated the object
            fields: List of fields that were updated

        Returns:
            True if notification was sent successfully
        """
        event_type = f"{self._meta.app_label}.{self._meta.model_name}.updated"
        subject = f"{self._meta.verbose_name} Updated"
        message = f"{self._meta.verbose_name} '{self}' was updated."

        context = {}
        if fields:
            context['updated_fields'] = fields

        return self.send_notification(
            event_type=event_type,
            subject=subject,
            message=message,
            context=context,
            user=user
        )

    def notify_deleted(self, user: Optional[Any] = None) -> bool:
        """
        Send notification when this object is deleted.

        Args:
            user: User who deleted the object

        Returns:
            True if notification was sent successfully
        """
        event_type = f"{self._meta.app_label}.{self._meta.model_name}.deleted"
        subject = f"{self._meta.verbose_name} Deleted"
        message = f"{self._meta.verbose_name} '{self}' was deleted."

        return self.send_notification(
            event_type=event_type,
            subject=subject,
            message=message,
            user=user
        )

    def notify_status_change(
        self,
        old_status: str,
        new_status: str,
        user: Optional[Any] = None
    ) -> bool:
        """
        Send notification when this object's status changes.

        Args:
            old_status: Previous status value
            new_status: New status value
            user: User who changed the status

        Returns:
            True if notification was sent successfully
        """
        event_type = f"{self._meta.app_label}.{self._meta.model_name}.status_changed"
        subject = f"{self._meta.verbose_name} Status Changed"
        message = f"{self._meta.verbose_name} '{self}' status changed from {old_status} to {new_status}."

        return self.send_notification(
            event_type=event_type,
            subject=subject,
            message=message,
            context={
                'old_status': old_status,
                'new_status': new_status
            },
            user=user
        )
