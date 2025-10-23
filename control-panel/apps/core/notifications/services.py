"""
Notification services for deployment alerts.

"Security Best Practices" section
Architecture: Email notifications, webhook alerts, SMTP configuration
"""

import logging
import requests
from typing import Dict, Any, Optional, Tuple
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings

from apps.core.notifications.models import NotificationChannel, NotificationLog

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications about deployment events."""

    def create_channel(
        self,
        user: User,
        name: str,
        channel_type: str,
        config: Dict[str, Any],
        **event_filters,
    ) -> NotificationChannel:
        """
        Create a new notification channel.

        Args:
            user: Channel owner
            name: Channel name
            channel_type: Type of notification channel
            config: Channel configuration
            **event_filters: Boolean filters for events

        Returns:
            Created notification channel
        """
        channel = NotificationChannel.objects.create(
            user=user,
            name=name,
            channel_type=channel_type,
            config=config,
            notify_on_deploy_success=event_filters.get("notify_on_deploy_success", True),
            notify_on_deploy_failure=event_filters.get("notify_on_deploy_failure", True),
            notify_on_deploy_start=event_filters.get("notify_on_deploy_start", False),
            notify_on_health_check_fail=event_filters.get(
                "notify_on_health_check_fail", True
            ),
            notify_on_resource_warning=event_filters.get(
                "notify_on_resource_warning", False
            ),
        )

        logger.info(f"Notification channel created: {channel.name} by {user.username}")
        return channel

    def send_notification(
        self,
        channel: NotificationChannel,
        event_type: str,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send notification through configured channel.

        Args:
            channel: Notification channel
            event_type: Type of event
            subject: Notification subject
            message: Notification message
            metadata: Optional metadata

        Returns:
            True if notification sent successfully
        """
        if not channel.is_active:
            logger.info(f"Skipping notification: Channel {channel.id} is not active")
            return False

        # Create notification log
        log = NotificationLog.objects.create(
            channel=channel,
            event_type=event_type,
            subject=subject,
            message=message,
            metadata=metadata or {},
            status=NotificationLog.Status.PENDING,
        )

        try:
            if channel.channel_type == NotificationChannel.ChannelType.EMAIL:
                success = self._send_email(channel, subject, message)
            elif channel.channel_type == NotificationChannel.ChannelType.WEBHOOK:
                success = self._send_webhook(channel, event_type, subject, message, metadata)
            elif channel.channel_type == NotificationChannel.ChannelType.SMTP:
                success = self._send_smtp_email(channel, subject, message)
            else:
                logger.error(f"Unknown channel type: {channel.channel_type}")
                success = False

            if success:
                log.status = NotificationLog.Status.SENT
                channel.last_notification = timezone.now()
                channel.notification_count += 1
                channel.status = NotificationChannel.Status.ACTIVE
                channel.save()
            else:
                log.status = NotificationLog.Status.FAILED

            log.save()
            return success

        except Exception as e:
            logger.error(f"Notification error: {e}")
            log.status = NotificationLog.Status.FAILED
            log.error_message = str(e)
            log.save()

            channel.status = NotificationChannel.Status.FAILED
            channel.last_error = str(e)
            channel.save()

            return False

    def _send_email(
        self, channel: NotificationChannel, subject: str, message: str
    ) -> bool:
        """Send email notification using Django's default email backend."""
        try:
            email_address = channel.config.get("email")
            if not email_address:
                logger.error("Email address not configured in channel")
                return False

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email_address],
                fail_silently=False,
            )

            logger.info(f"Email sent to {email_address}")
            return True

        except Exception as e:
            logger.error(f"Email send error: {e}")
            return False

    def _send_webhook(
        self,
        channel: NotificationChannel,
        event_type: str,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]],
    ) -> bool:
        """Send webhook notification to configured URL."""
        try:
            webhook_url = channel.config.get("webhook_url")
            if not webhook_url:
                logger.error("Webhook URL not configured in channel")
                return False

            payload = {
                "event_type": event_type,
                "subject": subject,
                "message": message,
                "metadata": metadata or {},
                "timestamp": timezone.now().isoformat(),
            }

            response = requests.post(
                webhook_url, json=payload, timeout=10, headers={"Content-Type": "application/json"}
            )

            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Webhook sent to {webhook_url}")
                return True
            else:
                logger.error(f"Webhook failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Webhook send error: {e}")
            return False

    def _send_smtp_email(
        self, channel: NotificationChannel, subject: str, message: str
    ) -> bool:
        """Send email using custom SMTP configuration."""
        try:
            import smtplib
            from email.mime.text import MIMEText

            smtp_config = channel.config
            server = smtplib.SMTP(smtp_config.get("host"), smtp_config.get("port", 587))
            server.starttls()
            server.login(smtp_config.get("username"), smtp_config.get("password"))

            msg = MIMEText(message)
            msg["Subject"] = subject
            msg["From"] = smtp_config.get("from_email")
            msg["To"] = smtp_config.get("to_email")

            server.send_message(msg)
            server.quit()

            logger.info(f"SMTP email sent to {smtp_config.get('to_email')}")
            return True

        except Exception as e:
            logger.error(f"SMTP send error: {e}")
            return False

    def notify_deployment_event(
        self, user: User, deployment_name: str, event_type: str, status: str, details: str = ""
    ):
        """
        Send notifications for deployment events.

        Args:
            user: Deployment owner
            deployment_name: Name of deployment
            event_type: Type of deployment event
            status: Deployment status
            details: Additional details
        """
        # Get all active channels for user
        channels = NotificationChannel.objects.filter(user=user, is_active=True)

        for channel in channels:
            # Check event filters
            should_notify = False
            if event_type == "deploy_start" and channel.notify_on_deploy_start:
                should_notify = True
            elif event_type == "deploy_success" and channel.notify_on_deploy_success:
                should_notify = True
            elif event_type == "deploy_failure" and channel.notify_on_deploy_failure:
                should_notify = True
            elif (
                event_type == "health_check_fail"
                and channel.notify_on_health_check_fail
            ):
                should_notify = True
            elif (
                event_type == "resource_warning"
                and channel.notify_on_resource_warning
            ):
                should_notify = True

            if should_notify:
                subject = f"WebOps: {deployment_name} - {event_type.replace('_', ' ').title()}"
                message = f"Deployment: {deployment_name}\nStatus: {status}\n\n{details}"

                self.send_notification(
                    channel,
                    event_type,
                    subject,
                    message,
                    metadata={"deployment": deployment_name, "status": status},
                )

    def list_user_channels(self, user: User) -> list:
        """List all notification channels for a user."""
        channels = NotificationChannel.objects.filter(user=user)

        return [
            {
                "id": channel.id,
                "name": channel.name,
                "channel_type": channel.channel_type,
                "is_active": channel.is_active,
                "status": channel.status,
                "notification_count": channel.notification_count,
                "last_notification": channel.last_notification,
                "created_at": channel.created_at,
            }
            for channel in channels
        ]

    def toggle_channel(self, channel: NotificationChannel) -> bool:
        """Toggle notification channel active status."""
        channel.is_active = not channel.is_active
        if channel.is_active:
            channel.status = NotificationChannel.Status.ACTIVE
        else:
            channel.status = NotificationChannel.Status.PAUSED
        channel.save()

        logger.info(
            f"Channel {channel.id} {'activated' if channel.is_active else 'paused'}"
        )

        return channel.is_active

    def delete_channel(self, channel: NotificationChannel) -> bool:
        """Delete a notification channel."""
        channel_id = channel.id
        channel.delete()
        logger.info(f"Channel {channel_id} deleted")
        return True

    def test_channel(self, channel: NotificationChannel) -> Tuple[bool, str]:
        """
        Test notification channel by sending a test message.

        Returns:
            Tuple of (success, message)
        """
        try:
            success = self.send_notification(
                channel,
                "test",
                "WebOps Test Notification",
                "This is a test notification from WebOps. If you received this, your notification channel is working correctly!",
                metadata={"test": True},
            )

            if success:
                return True, "Test notification sent successfully"
            else:
                return False, "Failed to send test notification"

        except Exception as e:
            return False, f"Error: {str(e)}"