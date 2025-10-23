from django.utils import timezone
from django.core.exceptions import ValidationError
import os
import json
from typing import Dict, Any, Optional


def get_client_ip(request) -> Optional[str]:
    """
    Get the client IP address from the request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format
    """
    if not size_bytes:
        return "0 B"

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def validate_trash_item_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and clean trash item data
    """
    required_fields = ['item_name', 'item_type', 'original_path']

    for field in required_fields:
        if field not in data or not data[field]:
            raise ValidationError(f"Field '{field}' is required")

    # Validate item_type
    valid_types = [
        'deployment', 'database', 'file', 'directory', 'backup',
        'configuration', 'log', 'template', 'script', 'other'
    ]

    if data['item_type'] not in valid_types:
        raise ValidationError(f"Invalid item_type. Must be one of: {', '.join(valid_types)}")

    # Clean metadata
    if 'metadata' in data and data['metadata']:
        data['metadata'] = clean_metadata(data['metadata'])

    return data


def clean_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean metadata by removing sensitive information
    """
    if not isinstance(metadata, dict):
        return {}

    cleaned = {}
    sensitive_keys = [
        'password', 'secret', 'key', 'token', 'credential',
        'auth', 'private', 'api_key', 'access_token'
    ]

    for key, value in metadata.items():
        key_lower = key.lower()
        if not any(sensitive in key_lower for sensitive in sensitive_keys):
            # Convert non-serializable objects to strings
            try:
                json.dumps(value)
                cleaned[key] = value
            except (TypeError, ValueError):
                cleaned[key] = str(value)

    return cleaned


def calculate_directory_size(path: str) -> int:
    """
    Calculate total size of a directory
    """
    total_size = 0

    if not os.path.exists(path):
        return 0

    if os.path.isfile(path):
        return os.path.getsize(path)

    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            try:
                total_size += os.path.getsize(filepath)
            except (OSError, FileNotFoundError):
                # Skip files that can't be accessed
                continue

    return total_size


def get_item_type_from_path(path: str) -> str:
    """
    Determine item type based on file path or extension
    """
    if not path:
        return 'other'

    path_lower = path.lower()

    # File type detection
    if path_lower.endswith(('.py', '.js', '.php', '.rb', '.go', '.rs', '.java')):
        return 'script'
    elif path_lower.endswith(('.yml', '.yaml', '.json', '.xml', '.ini', '.conf')):
        return 'configuration'
    elif path_lower.endswith(('.log', '.txt', '.md', '.rst')):
        return 'log'
    elif path_lower.endswith(('.sql', '.db', '.sqlite', '.sqlite3')):
        return 'database'
    elif path_lower.endswith(('.tar.gz', '.zip', '.rar', '.7z', '.tar')):
        return 'backup'
    elif path_lower.endswith(('.html', '.htm', '.css', '.scss', '.js')):
        return 'file'
    elif os.path.isdir(path):
        return 'directory'

    return 'file'


def create_trash_item(item_name: str, item_type: str, original_path: str,
                     deleted_by=None, size: int = None, metadata: Dict = None) -> 'TrashItem':
    """
    Helper function to create a trash item with validation
    """
    from .models import TrashItem

    data = {
        'item_name': item_name,
        'item_type': item_type,
        'original_path': original_path,
        'size': size,
        'metadata': metadata or {}
    }

    # Validate data
    validated_data = validate_trash_item_data(data)

    # Create trash item
    trash_item = TrashItem.objects.create(
        item_name=validated_data['item_name'],
        item_type=validated_data['item_type'],
        original_path=validated_data['original_path'],
        deleted_by=deleted_by,
        size=validated_data.get('size'),
        metadata=validated_data.get('metadata', {})
    )

    return trash_item


def get_trash_statistics(user) -> Dict[str, Any]:
    """
    Get comprehensive trash statistics for a user
    """
    from .models import TrashItem

    base_queryset = TrashItem.objects.filter(deleted_by=user)

    # Current trash items
    current_items = base_queryset.filter(
        is_restored=False,
        is_permanently_deleted=False
    )

    # Recently restored items
    restored_items = base_queryset.filter(
        is_restored=True,
        restored_at__gte=timezone.now() - timezone.timedelta(days=7)
    )

    # Recently permanently deleted items
    deleted_items = base_queryset.filter(
        is_permanently_deleted=True,
        permanently_deleted_at__gte=timezone.now() - timezone.timedelta(days=7)
    )

    return {
        'current': {
            'total_items': current_items.count(),
            'total_size': current_items.aggregate(Sum('size'))['size__sum'] or 0,
            'by_type': current_items.values('item_type').annotate(count=Count('id')).order_by('-count'),
            'expiring_soon': current_items.filter(
                auto_delete_at__lte=timezone.now() + timezone.timedelta(days=3)
            ).count(),
            'expired': current_items.filter(auto_delete_at__lte=timezone.now()).count(),
        },
        'recent_activity': {
            'restored_count': restored_items.count(),
            'deleted_count': deleted_items.count(),
        },
        'trends': {
            'items_deleted_last_7_days': base_queryset.filter(
                deleted_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).count(),
            'items_deleted_last_30_days': base_queryset.filter(
                deleted_at__gte=timezone.now() - timezone.timedelta(days=30)
            ).count(),
        }
    }


def check_trash_limits(user, new_item_size: int = 0) -> Dict[str, Any]:
    """
    Check if adding a new item would exceed trash limits
    """
    from .models import TrashItem, TrashSettings

    try:
        settings = TrashSettings.objects.get(pk=1)
    except TrashSettings.DoesNotExist:
        # Use default limits if no settings configured
        settings = TrashSettings()

    current_items = TrashItem.objects.filter(
        deleted_by=user,
        is_restored=False,
        is_permanently_deleted=False
    )

    current_size = current_items.aggregate(Sum('size'))['size__sum'] or 0
    max_size_bytes = settings.max_trash_size_gb * 1024 * 1024 * 1024

    projected_size = current_size + new_item_size

    return {
        'current_size': current_size,
        'current_size_formatted': format_file_size(current_size),
        'max_size': max_size_bytes,
        'max_size_formatted': format_file_size(max_size_bytes),
        'projected_size': projected_size,
        'projected_size_formatted': format_file_size(projected_size),
        'would_exceed': projected_size > max_size_bytes,
        'available_space': max_size_bytes - current_size,
        'available_space_formatted': format_file_size(max_size_bytes - current_size),
    }


def get_retention_info(item) -> Dict[str, Any]:
    """
    Get retention information for a trash item
    """
    now = timezone.now()

    return {
        'deleted_at': item.deleted_at,
        'auto_delete_at': item.auto_delete_at,
        'retention_days': item.retention_days,
        'days_remaining': max(0, (item.auto_delete_at - now).days) if item.auto_delete_at else 0,
        'is_expired': item.is_expired(),
        'expires_in_days': max(0, (item.auto_delete_at - now).days) if item.auto_delete_at else None,
        'expiry_status': get_expiry_status(item),
    }


def get_expiry_status(item) -> str:
    """
    Get human-readable expiry status for an item
    """
    if item.is_restored:
        return 'restored'
    if item.is_permanently_deleted:
        return 'permanently_deleted'

    if not item.auto_delete_at:
        return 'no_expiry'

    now = timezone.now()
    days_remaining = (item.auto_delete_at - now).days

    if days_remaining < 0:
        return 'expired'
    elif days_remaining <= 1:
        return 'expires_today'
    elif days_remaining <= 3:
        return 'expires_soon'
    else:
        return 'active'


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage
    """
    import re

    # Remove or replace problematic characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)

    # Limit length
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:195] + ext

    return filename.strip()


def generate_trash_item_metadata(item_path: str, item_type: str) -> Dict[str, Any]:
    """
    Generate metadata for different types of items
    """
    metadata = {
        'original_path': item_path,
        'item_type': item_type,
        'generated_at': timezone.now().isoformat(),
    }

    if os.path.exists(item_path):
        stat = os.stat(item_path)
        metadata.update({
            'file_size': stat.st_size,
            'modified_time': stat.st_mtime,
            'accessed_time': stat.st_access_time,
            'created_time': stat.st_ctime,
            'permissions': oct(stat.st_mode),
        })

        if os.path.isfile(item_path):
            metadata.update({
                'mime_type': get_mime_type(item_path),
                'encoding': get_file_encoding(item_path),
            })

    return metadata


def get_mime_type(file_path: str) -> str:
    """
    Get MIME type of a file
    """
    import mimetypes
    mime_type, encoding = mimetypes.guess_type(file_path)
    return mime_type or 'application/octet-stream'


def get_file_encoding(file_path: str) -> str:
    """
    Attempt to detect file encoding
    """
    try:
        import chardet

        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)  # Read first 10KB for detection
            result = chardet.detect(raw_data)
            return result.get('encoding', 'utf-8')
    except Exception:
        return 'utf-8'


def export_trash_data(user, format: str = 'json') -> str:
    """
    Export trash data for backup or migration
    """
    from .models import TrashItem

    items = TrashItem.objects.filter(
        deleted_by=user,
        is_restored=False,
        is_permanently_deleted=False
    ).values(
        'id', 'item_name', 'item_type', 'original_path',
        'deleted_at', 'size', 'metadata', 'retention_days'
    )

    if format.lower() == 'json':
        return json.dumps(list(items), indent=2, default=str)
    elif format.lower() == 'csv':
        import csv
        import io

        output = io.StringIO()
        fieldnames = ['id', 'item_name', 'item_type', 'original_path',
                     'deleted_at', 'size', 'metadata', 'retention_days']
        writer = csv.DictWriter(output, fieldnames=fieldnames)

        writer.writeheader()
        for item in items:
            # Convert metadata dict to string for CSV
            item = item.copy()
            item['metadata'] = json.dumps(item['metadata'], default=str)
            writer.writerow(item)

        return output.getvalue()

    return json.dumps(list(items), indent=2, default=str)


def import_trash_data(user, data: str, format: str = 'json') -> int:
    """
    Import trash data from backup
    """
    from .models import TrashItem

    imported_count = 0

    try:
        if format.lower() == 'json':
            items_data = json.loads(data)
        else:
            raise ValueError(f"Unsupported import format: {format}")

        for item_data in items_data:
            # Create new trash item
            TrashItem.objects.create(
                item_name=item_data['item_name'],
                item_type=item_data['item_type'],
                original_path=item_data['original_path'],
                deleted_by=user,
                deleted_at=item_data.get('deleted_at'),
                size=item_data.get('size'),
                metadata=item_data.get('metadata', {}),
                retention_days=item_data.get('retention_days', 30)
            )
            imported_count += 1

    except Exception as e:
        raise ValidationError(f"Failed to import trash data: {str(e)}")

    return imported_count
