"""
Trash Manager - Utility for integrating trash functionality throughout WebOps
"""
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import TrashItem
from .utils import validate_trash_item_data, generate_trash_item_metadata

User = get_user_model()


class TrashManager:
    """
    Main utility class for trash operations throughout the WebOps platform
    """

    @staticmethod
    def move_to_trash(item_name, item_type, original_path, deleted_by=None,
                     size=None, metadata=None, retention_days=None):
        """
        Move an item to trash with full validation and metadata generation

        Args:
            item_name (str): Display name of the item
            item_type (str): Type of item (deployment, database, file, etc.)
            original_path (str): Original path or identifier
            deleted_by (User): User who deleted the item
            size (int): Size in bytes (optional)
            metadata (dict): Additional metadata (optional)
            retention_days (int): Days to keep item (optional, uses default if not provided)

        Returns:
            TrashItem: The created trash item

        Raises:
            ValidationError: If data is invalid
        """
        # Prepare data
        data = {
            'item_name': item_name,
            'item_type': item_type,
            'original_path': original_path,
            'size': size,
            'metadata': metadata or {}
        }

        # Validate data
        validated_data = validate_trash_item_data(data)

        # Get retention days from settings or use provided value
        if retention_days is None:
            try:
                from .models import TrashSettings
                settings = TrashSettings.objects.get(pk=1)
                retention_days = settings.default_retention_days
            except TrashSettings.DoesNotExist:
                retention_days = 30  # Default fallback

        # Create trash item
        trash_item = TrashItem.objects.create(
            item_name=validated_data['item_name'],
            item_type=validated_data['item_type'],
            original_path=validated_data['original_path'],
            deleted_by=deleted_by,
            size=validated_data.get('size'),
            metadata=validated_data.get('metadata', {}),
            retention_days=retention_days
        )

        return trash_item

    @staticmethod
    def move_deployment_to_trash(deployment, deleted_by):
        """Move a deployment to trash"""
        metadata = {
            'deployment_id': deployment.id,
            'git_url': deployment.git_url,
            'branch': deployment.branch,
            'port': deployment.port,
            'status': deployment.status,
            'created_at': deployment.created_at.isoformat() if deployment.created_at else None,
        }

        return TrashManager.move_to_trash(
            item_name=f"Deployment: {deployment.name}",
            item_type='deployment',
            original_path=f"/deployments/{deployment.id}/",
            deleted_by=deleted_by,
            size=None,  # Could calculate deployment size if needed
            metadata=metadata
        )

    @staticmethod
    def move_database_to_trash(database, deleted_by):
        """Move a database to trash"""
        metadata = {
            'database_id': database.id,
            'db_type': database.db_type,
            'db_name': database.db_name,
            'username': database.username,
            'host': database.host,
            'port': database.port,
            'created_at': database.created_at.isoformat() if database.created_at else None,
        }

        return TrashManager.move_to_trash(
            item_name=f"Database: {database.db_name}",
            item_type='database',
            original_path=f"/databases/{database.id}/",
            deleted_by=deleted_by,
            size=None,  # Database size would need to be calculated separately
            metadata=metadata
        )

    @staticmethod
    def move_file_to_trash(file_path, original_name=None, deleted_by=None, item_type=None):
        """Move a file or directory to trash"""
        import os

        if not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")

        # Determine item type if not provided
        if item_type is None:
            from .utils import get_item_type_from_path
            item_type = get_item_type_from_path(file_path)

        # Generate metadata
        metadata = generate_trash_item_metadata(file_path, item_type)

        # Calculate size
        if os.path.isfile(file_path):
            size = os.path.getsize(file_path)
        else:
            from .utils import calculate_directory_size
            size = calculate_directory_size(file_path)

        # Use original name or filename
        item_name = original_name or os.path.basename(file_path)

        return TrashManager.move_to_trash(
            item_name=item_name,
            item_type=item_type,
            original_path=file_path,
            deleted_by=deleted_by,
            size=size,
            metadata=metadata
        )

    @staticmethod
    def get_user_trash_stats(user):
        """Get comprehensive trash statistics for a user"""
        from .utils import get_trash_statistics
        return get_trash_statistics(user)

    @staticmethod
    def cleanup_expired_items(user=None):
        """
        Clean up expired items for a specific user or all users (admin only)
        Returns number of items cleaned up
        """
        from .models import TrashOperation

        if user:
            # Clean up specific user's expired items
            expired_items = TrashItem.objects.filter(
                deleted_by=user,
                is_restored=False,
                is_permanently_deleted=False,
                auto_delete_at__lte=timezone.now()
            )
        else:
            # Clean up all expired items (admin function)
            expired_items = TrashItem.objects.filter(
                is_restored=False,
                is_permanently_deleted=False,
                auto_delete_at__lte=timezone.now()
            )

        count = 0
        for item in expired_items:
            item.permanent_delete()
            count += 1

        # Log the cleanup operation
        if count > 0:
            TrashOperation.objects.create(
                operation='auto_cleanup',
                performed_by=user,
                items_count=count,
                details={'auto_cleanup': True}
            )

        return count

    @staticmethod
    def empty_user_trash(user):
        """Empty entire trash for a user"""
        from .models import TrashOperation

        items = TrashItem.objects.filter(
            deleted_by=user,
            is_restored=False,
            is_permanently_deleted=False
        )

        count = items.count()
        if count == 0:
            return 0

        # Permanently delete all items
        for item in items:
            item.permanent_delete(user=user)

        # Log the operation
        TrashOperation.objects.create(
            operation='empty_trash',
            performed_by=user,
            items_count=count
        )

        return count

    @staticmethod
    def restore_item(item_id, user):
        """Restore a specific item"""
        item = TrashItem.objects.get(
            id=item_id,
            deleted_by=user,
            is_restored=False,
            is_permanently_deleted=False
        )

        item.restore(user=user)
        return item

    @staticmethod
    def get_items_expiring_soon(user, days=3):
        """Get items expiring within specified days"""
        return TrashItem.objects.filter(
            deleted_by=user,
            is_restored=False,
            is_permanently_deleted=False,
            auto_delete_at__lte=timezone.now() + timezone.timedelta(days=days)
        ).order_by('auto_delete_at')


# Convenience functions for common operations
def move_to_trash(item_name, item_type, original_path, deleted_by=None, **kwargs):
    """Convenience function to move any item to trash"""
    return TrashManager.move_to_trash(
        item_name=item_name,
        item_type=item_type,
        original_path=original_path,
        deleted_by=deleted_by,
        **kwargs
    )


def move_file_to_trash(file_path, deleted_by=None, **kwargs):
    """Convenience function to move a file to trash"""
    return TrashManager.move_file_to_trash(
        file_path=file_path,
        deleted_by=deleted_by,
        **kwargs
    )


def get_trash_stats(user):
    """Convenience function to get user trash statistics"""
    return TrashManager.get_user_trash_stats(user)


def cleanup_expired_items(user=None):
    """Convenience function to cleanup expired items"""
    return TrashManager.cleanup_expired_items(user)


def empty_trash(user):
    """Convenience function to empty user trash"""
    return TrashManager.empty_user_trash(user)
