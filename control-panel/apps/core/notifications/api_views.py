"""
API views for user notifications.

Provides REST API endpoints for the notification bell/center in the UI.
"""

from typing import Dict, Any
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.utils import timezone
from django.db.models import Q
from .models import UserNotification


@require_GET
@login_required
def get_notifications(request) -> JsonResponse:
    """
    Get current user's notifications.

    Query Parameters:
        unread_only (bool): If true, only return unread notifications
        limit (int): Maximum number of notifications to return (default: 50)
        offset (int): Offset for pagination (default: 0)
        type (str): Filter by notification type (success/error/warning/info)

    Returns:
        JSON response with notifications list and metadata
    """
    user = request.user

    # Build query
    queryset = UserNotification.objects.filter(user=user, is_deleted=False)

    # Filter by read status
    if request.GET.get('unread_only') == 'true':
        queryset = queryset.filter(is_read=False)

    # Filter by type
    notification_type = request.GET.get('type')
    if notification_type:
        queryset = queryset.filter(notification_type=notification_type)

    # Pagination
    try:
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
    except (ValueError, TypeError):
        limit = 50
        offset = 0

    # Limit to reasonable bounds
    limit = min(limit, 100)

    # Get total counts
    total_count = queryset.count()
    unread_count = UserNotification.objects.filter(
        user=user,
        is_deleted=False,
        is_read=False
    ).count()

    # Get paginated notifications
    notifications = queryset[offset:offset + limit]

    # Serialize notifications
    notifications_data = []
    for notification in notifications:
        notifications_data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'read': notification.is_read,
            'read_at': notification.read_at.isoformat() if notification.read_at else None,
            'timestamp': notification.created_at.isoformat(),
            'action_url': notification.action_url,
            'action_text': notification.action_text,
            'is_important': notification.is_important,
            'metadata': notification.metadata,
            'related_object_type': notification.related_object_type,
            'related_object_id': notification.related_object_id,
        })

    return JsonResponse({
        'success': True,
        'notifications': notifications_data,
        'total_count': total_count,
        'unread_count': unread_count,
        'has_more': (offset + limit) < total_count,
    })


@require_POST
@login_required
def mark_as_read(request, notification_id: int) -> JsonResponse:
    """
    Mark a notification as read.

    Args:
        notification_id: ID of the notification to mark as read

    Returns:
        JSON response with success status
    """
    try:
        notification = UserNotification.objects.get(
            id=notification_id,
            user=request.user,
            is_deleted=False
        )
        notification.mark_as_read()

        return JsonResponse({
            'success': True,
            'message': 'Notification marked as read',
            'notification_id': notification_id
        })
    except UserNotification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notification not found'
        }, status=404)


@require_POST
@login_required
def mark_all_as_read(request) -> JsonResponse:
    """
    Mark all user's notifications as read.

    Returns:
        JSON response with number of notifications marked as read
    """
    updated_count = UserNotification.objects.filter(
        user=request.user,
        is_read=False,
        is_deleted=False
    ).update(
        is_read=True,
        read_at=timezone.now()
    )

    return JsonResponse({
        'success': True,
        'message': f'{updated_count} notifications marked as read',
        'count': updated_count
    })


@require_POST
@login_required
def delete_notification(request, notification_id: int) -> JsonResponse:
    """
    Delete a notification (soft delete).

    Args:
        notification_id: ID of the notification to delete

    Returns:
        JSON response with success status
    """
    try:
        notification = UserNotification.objects.get(
            id=notification_id,
            user=request.user,
            is_deleted=False
        )
        notification.soft_delete(user=request.user)

        return JsonResponse({
            'success': True,
            'message': 'Notification deleted',
            'notification_id': notification_id
        })
    except UserNotification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notification not found'
        }, status=404)


@require_POST
@login_required
def clear_all_notifications(request) -> JsonResponse:
    """
    Clear all user's notifications (soft delete).

    Returns:
        JSON response with number of notifications cleared
    """
    notifications = UserNotification.objects.filter(
        user=request.user,
        is_deleted=False
    )

    count = notifications.count()

    # Soft delete all notifications
    for notification in notifications:
        notification.soft_delete(user=request.user)

    return JsonResponse({
        'success': True,
        'message': f'{count} notifications cleared',
        'count': count
    })


@require_GET
@login_required
def get_unread_count(request) -> JsonResponse:
    """
    Get count of unread notifications for the current user.

    Returns:
        JSON response with unread count
    """
    unread_count = UserNotification.objects.filter(
        user=request.user,
        is_read=False,
        is_deleted=False
    ).count()

    return JsonResponse({
        'success': True,
        'unread_count': unread_count
    })


@require_GET
@login_required
def get_notification_detail(request, notification_id: int) -> JsonResponse:
    """
    Get details of a specific notification.

    Args:
        notification_id: ID of the notification

    Returns:
        JSON response with notification details
    """
    try:
        notification = UserNotification.objects.get(
            id=notification_id,
            user=request.user,
            is_deleted=False
        )

        # Automatically mark as read when viewed
        if not notification.is_read:
            notification.mark_as_read()

        # Get related object info if exists
        related_object = notification.get_related_object()
        related_object_info = None
        if related_object:
            related_object_info = {
                'type': notification.related_object_type,
                'id': notification.related_object_id,
                'str': str(related_object)
            }

        return JsonResponse({
            'success': True,
            'notification': {
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'type': notification.notification_type,
                'read': notification.is_read,
                'read_at': notification.read_at.isoformat() if notification.read_at else None,
                'timestamp': notification.created_at.isoformat(),
                'action_url': notification.action_url,
                'action_text': notification.action_text,
                'is_important': notification.is_important,
                'metadata': notification.metadata,
                'related_object': related_object_info,
            }
        })
    except UserNotification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notification not found'
        }, status=404)
