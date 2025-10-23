"""
Tests for notifications domain.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.core import mail
from unittest.mock import patch, MagicMock
import json

from apps.core.notifications.models import NotificationChannel, NotificationLog
from apps.core.notifications.services import NotificationService


class NotificationServiceTests(TestCase):
    """Test NotificationService."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = NotificationService()

    def test_create_channel_email(self):
        """Test creating email notification channel."""
        channel = self.service.create_channel(
            user=self.user,
            name='Email Notifications',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'test@example.com'},
            notify_on_deploy_success=True,
            notify_on_deploy_failure=True,
            notify_on_deploy_start=False,
        )
        
        self.assertEqual(channel.name, 'Email Notifications')
        self.assertEqual(channel.user, self.user)
        self.assertEqual(channel.channel_type, NotificationChannel.ChannelType.EMAIL)
        self.assertEqual(channel.config['email'], 'test@example.com')
        self.assertTrue(channel.notify_on_deploy_success)
        self.assertTrue(channel.notify_on_deploy_failure)
        self.assertFalse(channel.notify_on_deploy_start)

    def test_create_channel_webhook(self):
        """Test creating webhook notification channel."""
        channel = self.service.create_channel(
            user=self.user,
            name='Webhook Notifications',
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            config={'webhook_url': 'https://example.com/webhook'},
        )
        
        self.assertEqual(channel.name, 'Webhook Notifications')
        self.assertEqual(channel.channel_type, NotificationChannel.ChannelType.WEBHOOK)
        self.assertEqual(channel.config['webhook_url'], 'https://example.com/webhook')

    @patch('apps.core.notifications.services.send_mail')
    def test_send_email_notification(self, mock_send_mail):
        """Test sending email notification."""
        channel = NotificationChannel.objects.create(
            user=self.user,
            name='Email Notifications',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'test@example.com'},
            is_active=True
        )
        
        # Mock successful email sending
        mock_send_mail.return_value = True
        
        success = self.service.send_notification(
            channel,
            'deploy_success',
            'Test Deployment',
            'Deployment completed successfully'
        )
        
        self.assertTrue(success)
        mock_send_mail.assert_called_once()
        
        # Check notification log
        log = NotificationLog.objects.get(channel=channel)
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.event_type, 'deploy_success')
        self.assertEqual(log.subject, 'Test Deployment')

    @patch('apps.core.notifications.services.send_mail')
    def test_send_email_notification_failure(self, mock_send_mail):
        """Test failed email notification."""
        channel = NotificationChannel.objects.create(
            user=self.user,
            name='Email Notifications',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'test@example.com'},
            is_active=True
        )
        
        # Mock failed email sending
        mock_send_mail.side_effect = Exception("SMTP error")
        
        success = self.service.send_notification(
            channel,
            'deploy_success',
            'Test Deployment',
            'Deployment completed successfully'
        )
        
        self.assertFalse(success)
        
        # Check notification log
        log = NotificationLog.objects.get(channel=channel)
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn('SMTP error', log.error_message)

    @patch('apps.core.notifications.services.requests.post')
    def test_send_webhook_notification(self, mock_post):
        """Test sending webhook notification."""
        channel = NotificationChannel.objects.create(
            user=self.user,
            name='Webhook Notifications',
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            config={'webhook_url': 'https://example.com/webhook'},
            is_active=True
        )
        
        # Mock successful webhook response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        success = self.service.send_notification(
            channel,
            'deploy_success',
            'Test Deployment',
            'Deployment completed successfully',
            metadata={'deployment_id': 123}
        )
        
        self.assertTrue(success)
        mock_post.assert_called_once()
        
        # Check notification log
        log = NotificationLog.objects.get(channel=channel)
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.event_type, 'deploy_success')
        self.assertEqual(log.metadata['deployment_id'], 123)

    @patch('apps.core.notifications.services.requests.post')
    def test_send_webhook_notification_failure(self, mock_post):
        """Test failed webhook notification."""
        channel = NotificationChannel.objects.create(
            user=self.user,
            name='Webhook Notifications',
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            config={'webhook_url': 'https://example.com/webhook'},
            is_active=True
        )
        
        # Mock failed webhook response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        
        success = self.service.send_notification(
            channel,
            'deploy_success',
            'Test Deployment',
            'Deployment completed successfully'
        )
        
        self.assertFalse(success)
        
        # Check notification log
        log = NotificationLog.objects.get(channel=channel)
        self.assertEqual(log.status, NotificationLog.Status.FAILED)

    def test_send_notification_inactive_channel(self):
        """Test sending notification to inactive channel."""
        channel = NotificationChannel.objects.create(
            user=self.user,
            name='Email Notifications',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'test@example.com'},
            is_active=False
        )
        
        success = self.service.send_notification(
            channel,
            'deploy_success',
            'Test Deployment',
            'Deployment completed successfully'
        )
        
        self.assertFalse(success)
        
        # No notification log should be created
        self.assertFalse(NotificationLog.objects.exists())

    def test_notify_deployment_event(self):
        """Test notifying deployment event."""
        # Create channels with different event filters
        success_channel = NotificationChannel.objects.create(
            user=self.user,
            name='Success Channel',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'success@example.com'},
            is_active=True,
            notify_on_deploy_success=True,
            notify_on_deploy_failure=False
        )
        
        failure_channel = NotificationChannel.objects.create(
            user=self.user,
            name='Failure Channel',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'failure@example.com'},
            is_active=True,
            notify_on_deploy_success=False,
            notify_on_deploy_failure=True
        )
        
        with patch('apps.core.notifications.services.send_mail') as mock_send_mail:
            # Mock successful email sending
            mock_send_mail.return_value = True
            
            # Notify success event
            self.service.notify_deployment_event(
                user=self.user,
                deployment_name='Test App',
                event_type='deploy_success',
                status='Success',
                details='Deployment completed successfully'
            )
            
            # Only success channel should be notified
            self.assertEqual(mock_send_mail.call_count, 1)
            self.assertEqual(mock_send_mail.call_args[1]['recipient_list'], ['success@example.com'])

    def test_list_user_channels(self):
        """Test listing user notification channels."""
        # Create channels
        channel1 = NotificationChannel.objects.create(
            user=self.user,
            name='Channel 1',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'test1@example.com'}
        )
        channel2 = NotificationChannel.objects.create(
            user=self.user,
            name='Channel 2',
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            config={'webhook_url': 'https://example.com/webhook'}
        )
        
        # Create channel for another user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        other_channel = NotificationChannel.objects.create(
            user=other_user,
            name='Other Channel',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'other@example.com'}
        )
        
        # List channels for user
        channels = self.service.list_user_channels(self.user)
        
        self.assertEqual(len(channels), 2)
        channel_names = [c['name'] for c in channels]
        self.assertIn('Channel 1', channel_names)
        self.assertIn('Channel 2', channel_names)
        self.assertNotIn('Other Channel', channel_names)

    def test_toggle_channel(self):
        """Test toggling notification channel status."""
        channel = NotificationChannel.objects.create(
            user=self.user,
            name='Test Channel',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'test@example.com'},
            is_active=True
        )
        
        # Deactivate channel
        is_active = self.service.toggle_channel(channel)
        self.assertFalse(is_active)
        self.assertEqual(channel.status, NotificationChannel.Status.PAUSED)
        
        # Reactivate channel
        is_active = self.service.toggle_channel(channel)
        self.assertTrue(is_active)
        self.assertEqual(channel.status, NotificationChannel.Status.ACTIVE)

    def test_delete_channel(self):
        """Test deleting notification channel."""
        channel = NotificationChannel.objects.create(
            user=self.user,
            name='Test Channel',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'test@example.com'}
        )
        
        result = self.service.delete_channel(channel)
        self.assertTrue(result)
        self.assertFalse(NotificationChannel.objects.filter(id=channel.id).exists())

    @patch('apps.core.notifications.services.send_mail')
    def test_test_channel(self, mock_send_mail):
        """Test testing notification channel."""
        channel = NotificationChannel.objects.create(
            user=self.user,
            name='Test Channel',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'test@example.com'},
            is_active=True
        )
        
        # Mock successful email sending
        mock_send_mail.return_value = True
        
        success, message = self.service.test_channel(channel)
        
        self.assertTrue(success)
        self.assertIn('Test notification sent successfully', message)
        mock_send_mail.assert_called_once()
        
        # Check notification log
        log = NotificationLog.objects.get(channel=channel)
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.event_type, 'test')
        self.assertIn('test notification', log.message.lower())

    @patch('apps.core.notifications.services.send_mail')
    def test_test_channel_failure(self, mock_send_mail):
        """Test testing notification channel with failure."""
        channel = NotificationChannel.objects.create(
            user=self.user,
            name='Test Channel',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'test@example.com'},
            is_active=True
        )
        
        # Mock failed email sending
        mock_send_mail.side_effect = Exception("SMTP error")
        
        success, message = self.service.test_channel(channel)
        
        self.assertFalse(success)
        self.assertIn('Failed to send test notification', message)