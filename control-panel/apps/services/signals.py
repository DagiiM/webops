"""
Signal handlers for the services app.

Automatically creates user notifications when alerts are created and
integrates the monitoring system with the notification bell.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from typing import Optional

from .models import Alert
from apps.core.notifications.models import UserNotification


def get_notification_type_for_alert(alert: Alert) -> str:
    """
    Map alert severity to notification type.

    Args:
        alert: Alert instance

    Returns:
        Notification type (success/error/warning/info)
    """
    severity_mapping = {
        Alert.Severity.INFO: UserNotification.NotificationType.INFO,
        Alert.Severity.WARNING: UserNotification.NotificationType.WARNING,
        Alert.Severity.ERROR: UserNotification.NotificationType.ERROR,
        Alert.Severity.CRITICAL: UserNotification.NotificationType.ERROR,
    }
    return severity_mapping.get(alert.severity, UserNotification.NotificationType.INFO)


def get_action_url_for_alert(alert: Alert) -> str:
    """
    Generate action URL for an alert.

    Args:
        alert: Alert instance

    Returns:
        URL to navigate to when notification is clicked
    """
    if alert.deployment:
        # Link to appropriate deployment detail page based on deployment type
        try:
            # Check if it's an LLM deployment
            if hasattr(alert.deployment, 'llmdeployment'):
                return f"/deployments/llm/{alert.deployment.id}/"
            else:
                return f"/deployments/{alert.deployment.id}/"
        except Exception:
            # Fallback to standard deployment URL
            return f"/deployments/{alert.deployment.id}/"

    # Default to alerts list page
    return "/services/alerts/"


def get_users_to_notify(alert: Alert) -> list:
    """
    Determine which users should be notified about an alert.

    Args:
        alert: Alert instance

    Returns:
        List of User instances to notify
    """
    users_to_notify = []

    # If alert is related to a specific deployment, notify the deployment owner
    if alert.deployment and alert.deployment.deployed_by:
        users_to_notify.append(alert.deployment.deployed_by)

    # For critical system alerts, notify all superusers
    if alert.severity == Alert.Severity.CRITICAL:
        superusers = User.objects.filter(is_superuser=True, is_active=True)
        for superuser in superusers:
            if superuser not in users_to_notify:
                users_to_notify.append(superuser)

    # For deployment-specific alerts, also notify staff users
    if alert.deployment and alert.alert_type in [
        Alert.AlertType.DEPLOYMENT_FAILED,
        Alert.AlertType.SERVICE_DOWN
    ]:
        staff_users = User.objects.filter(is_staff=True, is_active=True)
        for staff_user in staff_users:
            if staff_user not in users_to_notify:
                users_to_notify.append(staff_user)

    # If no users found, notify all superusers as fallback
    if not users_to_notify:
        users_to_notify = list(User.objects.filter(is_superuser=True, is_active=True))

    return users_to_notify


@receiver(post_save, sender=Alert)
def create_notification_for_alert(sender, instance: Alert, created: bool, **kwargs):
    """
    Automatically create user notifications when an alert is created.

    This signal handler creates in-app notifications that appear in the
    notification bell for all relevant users when a new alert is created.

    Args:
        sender: Alert model class
        instance: Alert instance that was saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    # Only create notifications for new alerts
    if not created:
        return

    alert = instance

    # Get users to notify
    users = get_users_to_notify(alert)

    if not users:
        return

    # Determine notification properties
    notification_type = get_notification_type_for_alert(alert)
    action_url = get_action_url_for_alert(alert)

    # Create notification title based on alert type
    title_templates = {
        Alert.AlertType.CPU_HIGH: "High CPU Usage Alert",
        Alert.AlertType.MEMORY_HIGH: "High Memory Usage Alert",
        Alert.AlertType.DISK_HIGH: "High Disk Usage Alert",
        Alert.AlertType.SERVICE_DOWN: "Service Down Alert",
        Alert.AlertType.DEPLOYMENT_FAILED: "Deployment Failed Alert",
        Alert.AlertType.SSL_EXPIRING: "SSL Certificate Expiring",
        Alert.AlertType.DATABASE_ERROR: "Database Error Alert",
    }

    notification_title = title_templates.get(alert.alert_type, alert.title)

    # Mark critical alerts as important
    is_important = alert.severity in [Alert.Severity.CRITICAL, Alert.Severity.ERROR]

    # Create metadata
    metadata = {
        'alert_id': alert.id,
        'alert_type': alert.alert_type,
        'severity': alert.severity,
        **alert.metadata  # Include alert's metadata
    }

    # Create notifications for all users
    for user in users:
        UserNotification.create_for_user(
            user=user,
            title=notification_title,
            message=alert.message,
            notification_type=notification_type,
            action_url=action_url,
            action_text="View Alert",
            related_object=alert,
            is_important=is_important,
            **metadata
        )


@receiver(post_save, sender=Alert)
def send_external_notifications_for_critical_alerts(sender, instance: Alert, created: bool, **kwargs):
    """
    Send external notifications (email/webhook) for critical alerts.

    This handler uses the NotificationService to send alerts through
    configured notification channels for critical/error severity alerts.

    Args:
        sender: Alert model class
        instance: Alert instance that was saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    # Only process new critical or error alerts
    if not created:
        return

    alert = instance

    # Only send external notifications for critical/error alerts
    if alert.severity not in [Alert.Severity.CRITICAL, Alert.Severity.ERROR]:
        return

    try:
        from apps.core.notifications.models import NotificationChannel
        from apps.core.notifications.services import NotificationService

        service = NotificationService()

        # Determine event type based on alert type
        event_type_mapping = {
            Alert.AlertType.SERVICE_DOWN: 'health_check_fail',
            Alert.AlertType.DEPLOYMENT_FAILED: 'deploy_failure',
            Alert.AlertType.CPU_HIGH: 'resource_warning',
            Alert.AlertType.MEMORY_HIGH: 'resource_warning',
            Alert.AlertType.DISK_HIGH: 'resource_warning',
        }

        event_type = event_type_mapping.get(alert.alert_type, 'alert_created')

        # Get all active channels
        channels = NotificationChannel.objects.filter(is_active=True)

        # Send notification through each appropriate channel
        for channel in channels:
            # Check if channel should receive this type of notification
            should_send = False

            if event_type == 'health_check_fail' and channel.notify_on_health_check_fail:
                should_send = True
            elif event_type == 'deploy_failure' and channel.notify_on_deploy_failure:
                should_send = True
            elif event_type == 'resource_warning' and channel.notify_on_resource_warning:
                should_send = True

            if should_send:
                service.send_notification(
                    channel=channel,
                    event_type=event_type,
                    subject=f"[{alert.get_severity_display()}] {alert.title}",
                    message=alert.message,
                    metadata={
                        'alert_id': alert.id,
                        'alert_type': alert.alert_type,
                        'severity': alert.severity,
                        'deployment_name': alert.deployment.name if alert.deployment else None,
                        **alert.metadata
                    }
                )
    except Exception as e:
        # Log error but don't fail the alert creation
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send external notification for alert {alert.id}: {e}")


@receiver(post_save, sender=UserNotification)
def broadcast_notification_to_websocket(sender, instance: UserNotification, created: bool, **kwargs):
    """
    Broadcast new notifications to WebSocket clients in real-time.

    This signal handler sends notifications through Django Channels
    to connected WebSocket clients for instant delivery.

    Args:
        sender: UserNotification model class
        instance: UserNotification instance that was saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    # Only broadcast new notifications
    if not created:
        return

    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        notification = instance
        channel_layer = get_channel_layer()

        if channel_layer is None:
            # Channel layer not configured, skip WebSocket broadcast
            return

        # Serialize notification data
        notification_data = {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'read': notification.is_read,
            'timestamp': notification.created_at.isoformat(),
            'action_url': notification.action_url,
            'action_text': notification.action_text,
            'is_important': notification.is_important,
            'metadata': notification.metadata,
        }

        # Send to the user's notification group
        group_name = f'notifications_user_{notification.user.id}'

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_new',
                'notification': notification_data
            }
        )

    except Exception as e:
        # Log error but don't fail the notification creation
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to broadcast notification {notification.id} via WebSocket: {e}")
