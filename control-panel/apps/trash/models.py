from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
import json

class TrashItem(models.Model):
    """
    Model to store soft-deleted items in the recycle bin.
    Tracks all necessary metadata for restoration and audit purposes.
    """

    # Item identification
    original_path = models.CharField(
        max_length=500,
        help_text="Original path or identifier of the deleted item"
    )
    item_type = models.CharField(
        max_length=50,
        help_text="Type of item (deployment, database, file, etc.)"
    )
    item_name = models.CharField(
        max_length=200,
        help_text="Display name of the deleted item"
    )

    # Ownership and tracking
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who deleted this item"
    )
    deleted_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the item was moved to trash"
    )

    # Item details
    size = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Size of the item in bytes (for files/databases)"
    )
    metadata = models.JSONField(
        default=dict,
        help_text="Additional item-specific metadata for restoration"
    )

    # Status tracking
    is_restored = models.BooleanField(
        default=False,
        help_text="Whether this item has been restored"
    )
    restored_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the item was restored"
    )
    restored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='restored_trash_items',
        help_text="User who restored this item"
    )

    # Permanent deletion tracking
    is_permanently_deleted = models.BooleanField(
        default=False,
        help_text="Whether this item has been permanently deleted"
    )
    permanently_deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the item was permanently deleted"
    )
    permanently_deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='permanently_deleted_trash_items',
        help_text="User who permanently deleted this item"
    )

    # Retention and cleanup
    retention_days = models.IntegerField(
        default=30,
        help_text="Days to keep this item before auto-deletion"
    )
    auto_delete_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this item should be automatically deleted"
    )

    class Meta:
        verbose_name = "Trash Item"
        verbose_name_plural = "Trash Items"
        ordering = ['-deleted_at']
        indexes = [
            models.Index(fields=['item_type', 'deleted_at']),
            models.Index(fields=['deleted_by', 'deleted_at']),
            models.Index(fields=['is_restored', 'deleted_at']),
            models.Index(fields=['auto_delete_at']),
        ]

    def __str__(self):
        return f"{self.item_name} ({self.item_type}) - {self.deleted_at.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        # Set auto-delete timestamp if not set
        if not self.auto_delete_at:
            self.auto_delete_at = self.deleted_at + timezone.timedelta(days=self.retention_days)

        super().save(*args, **kwargs)

    def restore(self, user=None):
        """Mark item as restored"""
        self.is_restored = True
        self.restored_at = timezone.now()
        if user:
            self.restored_by = user
        self.save()

    def permanent_delete(self, user=None):
        """Mark item as permanently deleted"""
        self.is_permanently_deleted = True
        self.permanently_deleted_at = timezone.now()
        if user:
            self.permanently_deleted_by = user
        self.save()

    def is_expired(self):
        """Check if item should be auto-deleted"""
        if self.auto_delete_at:
            return timezone.now() > self.auto_delete_at
        return False

    def days_until_expiry(self):
        """Get days until auto-deletion"""
        if self.auto_delete_at:
            remaining = self.auto_delete_at - timezone.now()
            return max(0, remaining.days)
        return 0

    def get_size_display(self):
        """Get human-readable size"""
        if not self.size:
            return "Unknown"

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if self.size < 1024.0:
                return f"{self.size:.1f} {unit}"
            self.size /= 1024.0
        return f"{self.size:.1f} PB"

    def get_metadata_display(self):
        """Get formatted metadata for display"""
        if not self.metadata:
            return "No additional metadata"

        # Filter out sensitive information
        display_metadata = {}
        for key, value in self.metadata.items():
            if not any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token']):
                display_metadata[key] = value

        return json.dumps(display_metadata, indent=2) if display_metadata else "No displayable metadata"


class TrashSettings(models.Model):
    """
    Global settings for trash functionality
    """

    # Retention settings
    default_retention_days = models.IntegerField(
        default=30,
        help_text="Default days to keep items in trash"
    )
    max_retention_days = models.IntegerField(
        default=90,
        help_text="Maximum days items can be kept in trash"
    )

    # Size limits
    max_trash_size_gb = models.IntegerField(
        default=10,
        help_text="Maximum total size of trash in GB"
    )

    # Auto-cleanup settings
    enable_auto_cleanup = models.BooleanField(
        default=True,
        help_text="Enable automatic cleanup of expired items"
    )
    cleanup_schedule_hours = models.IntegerField(
        default=24,
        help_text="Hours between automatic cleanup runs"
    )

    # Notification settings
    notify_before_deletion_days = models.IntegerField(
        default=7,
        help_text="Days before deletion to send notification"
    )

    class Meta:
        verbose_name = "Trash Settings"
        verbose_name_plural = "Trash Settings"

    def __str__(self):
        return "Global Trash Settings"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and TrashSettings.objects.exists():
            raise ValidationError("Only one TrashSettings instance is allowed")
        super().save(*args, **kwargs)


class TrashOperation(models.Model):
    """
    Audit trail for all trash operations
    """

    OPERATION_CHOICES = [
        ('delete', 'Item Deleted'),
        ('restore', 'Item Restored'),
        ('permanent_delete', 'Item Permanently Deleted'),
        ('bulk_delete', 'Bulk Delete'),
        ('bulk_restore', 'Bulk Restore'),
        ('bulk_permanent_delete', 'Bulk Permanent Delete'),
        ('auto_cleanup', 'Auto Cleanup'),
        ('empty_trash', 'Empty Trash'),
    ]

    # Operation details
    operation = models.CharField(
        max_length=25,
        choices=OPERATION_CHOICES,
        help_text="Type of operation performed"
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        help_text="User who performed the operation"
    )
    performed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the operation was performed"
    )

    # Items affected
    items_affected = models.ManyToManyField(
        TrashItem,
        related_name='operations',
        help_text="Trash items affected by this operation"
    )
    items_count = models.IntegerField(
        help_text="Number of items affected"
    )

    # Additional details
    details = models.JSONField(
        default=dict,
        help_text="Additional operation details"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the user"
    )

    class Meta:
        verbose_name = "Trash Operation"
        verbose_name_plural = "Trash Operations"
        ordering = ['-performed_at']
        indexes = [
            models.Index(fields=['operation', 'performed_at']),
            models.Index(fields=['performed_by', 'performed_at']),
        ]

    def __str__(self):
        return f"{self.operation} by {self.performed_by} at {self.performed_at}"
