"""
Integration tests for WebOps domains.

These tests verify that the different domains work together correctly.
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
import json

# Import from new domain locations
from apps.core.branding.models import BrandingSettings
from apps.core.branding.services import BrandingService
from apps.core.integrations.models import GitHubConnection
from apps.core.integrations.services.github import GitHubIntegrationService
from apps.core.webhooks.models import Webhook, WebhookDelivery
from apps.core.webhooks.services import WebhookService
from apps.core.notifications.models import NotificationChannel, NotificationLog
from apps.core.notifications.services import NotificationService
from apps.core.common.utils.encryption import encrypt_value, decrypt_value


class DomainIntegrationTests(TestCase):
    """Test integration between different domains."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.factory = RequestFactory()

    def test_branding_and_integrations_integration(self):
        """Test integration between branding and integrations domains."""
        # Create branding settings
        settings = BrandingSettings.get_settings()
        settings.site_name = 'Test Site'
        settings.save()

        # Create GitHub connection
        github_service = GitHubIntegrationService()
        with patch.object(github_service, 'validate_token', return_value=(True, {'id': 12345, 'login': 'testuser'})):
            connection = github_service.save_connection_with_pat(self.user, 'test_token')
        
        # Verify both domains work together
        self.assertEqual(settings.site_name, 'Test Site')
        self.assertEqual(connection.username, 'testuser')
        self.assertEqual(connection.user, self.user)

    def test_integrations_and_webhooks_integration(self):
        """Test integration between integrations and webhooks domains."""
        # Create GitHub connection
        github_service = GitHubIntegrationService()
        with patch.object(github_service, 'validate_token', return_value=(True, {'id': 12345, 'login': 'testuser'})):
            connection = github_service.save_connection_with_pat(self.user, 'test_token')
        
        # Create webhook
        webhook_service = WebhookService()
        from apps.deployments.models import BaseDeployment
        deployment = BaseDeployment.objects.create(
            name='Test Deployment',
            deployed_by=self.user
        )
        webhook = webhook_service.create_webhook(
            user=self.user,
            deployment=deployment,
            name='Test Webhook',
            trigger_event=Webhook.TriggerEvent.PUSH
        )
        
        # Verify both domains work together
        self.assertEqual(connection.user, self.user)
        self.assertEqual(webhook.user, self.user)
        self.assertEqual(webhook.deployment, deployment)

    def test_webhooks_and_notifications_integration(self):
        """Test integration between webhooks and notifications domains."""
        # Create notification channel
        notification_service = NotificationService()
        channel = notification_service.create_channel(
            user=self.user,
            name='Test Channel',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'test@example.com'}
        )
        
        # Create webhook
        webhook_service = WebhookService()
        from apps.deployments.models import BaseDeployment
        deployment = BaseDeployment.objects.create(
            name='Test Deployment',
            deployed_by=self.user
        )
        webhook = webhook_service.create_webhook(
            user=self.user,
            deployment=deployment,
            name='Test Webhook',
            trigger_event=Webhook.TriggerEvent.PUSH
        )
        
        # Process webhook (this would normally trigger notifications)
        payload = {'ref': 'refs/heads/main', 'commits': [{'message': 'Test commit'}]}
        
        # Create a signature
        import hmac
        import hashlib
        payload_json = json.dumps(payload, separators=(",", ":"))
        mac = hmac.new(webhook.secret.encode('utf-8'), msg=payload_json.encode('utf-8'), digestmod=hashlib.sha256)
        signature = f"sha256={mac.hexdigest()}"
        
        with patch('apps.core.webhooks.services.get_background_processor') as mock_processor:
            mock_handle = MagicMock()
            mock_handle.id = 'test-task-id'
            mock_processor.return_value.submit.return_value = mock_handle
            
            success, message = webhook_service.process_github_webhook(webhook, payload, signature)
            self.assertTrue(success)
        
        # Verify both domains work together
        self.assertEqual(channel.user, self.user)
        self.assertEqual(webhook.user, self.user)
        self.assertTrue(success)

    def test_all_domains_integration(self):
        """Test integration between all domains."""
        # Set up branding
        settings = BrandingSettings.get_settings()
        settings.site_name = 'Test Site'
        settings.save()
        
        # Create GitHub connection
        github_service = GitHubIntegrationService()
        with patch.object(github_service, 'validate_token', return_value=(True, {'id': 12345, 'login': 'testuser'})):
            connection = github_service.save_connection_with_pat(self.user, 'test_token')
        
        # Create notification channel
        notification_service = NotificationService()
        channel = notification_service.create_channel(
            user=self.user,
            name='Test Channel',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'test@example.com'}
        )
        
        # Create webhook
        webhook_service = WebhookService()
        from apps.deployments.models import BaseDeployment
        deployment = BaseDeployment.objects.create(
            name='Test Deployment',
            deployed_by=self.user
        )
        webhook = webhook_service.create_webhook(
            user=self.user,
            deployment=deployment,
            name='Test Webhook',
            trigger_event=Webhook.TriggerEvent.PUSH
        )
        
        # Verify all domains work together
        self.assertEqual(settings.site_name, 'Test Site')
        self.assertEqual(connection.user, self.user)
        self.assertEqual(channel.user, self.user)
        self.assertEqual(webhook.user, self.user)
        self.assertEqual(webhook.deployment, deployment)

    def test_encryption_across_domains(self):
        """Test that encryption works consistently across domains."""
        # Test encryption and decryption
        original_value = 'test_password'
        encrypted = encrypt_value(original_value)
        decrypted = decrypt_value(encrypted)
        
        self.assertEqual(original_value, decrypted)
        self.assertNotEqual(original_value, encrypted)
        
        # Test that encrypted values can be stored and retrieved
        github_service = GitHubIntegrationService()
        with patch.object(github_service, 'validate_token', return_value=(True, {'id': 12345, 'login': 'testuser'})):
            connection = github_service.save_connection_with_pat(self.user, 'test_token')
        
        # Retrieve the access token
        retrieved_token = github_service.get_access_token(self.user)
        self.assertEqual(retrieved_token, 'test_token')

    def test_notification_after_webhook(self):
        """Test that notifications are sent after webhook processing."""
        # Create notification channel
        notification_service = NotificationService()
        channel = notification_service.create_channel(
            user=self.user,
            name='Test Channel',
            channel_type=NotificationChannel.ChannelType.EMAIL,
            config={'email': 'test@example.com'}
        )
        
        # Create webhook
        webhook_service = WebhookService()
        from apps.deployments.models import BaseDeployment
        deployment = BaseDeployment.objects.create(
            name='Test Deployment',
            deployed_by=self.user
        )
        webhook = webhook_service.create_webhook(
            user=self.user,
            deployment=deployment,
            name='Test Webhook',
            trigger_event=Webhook.TriggerEvent.PUSH
        )
        
        # Process webhook
        payload = {'ref': 'refs/heads/main', 'commits': [{'message': 'Test commit'}]}
        
        # Create a signature
        import hmac
        import hashlib
        payload_json = json.dumps(payload, separators=(",", ":"))
        mac = hmac.new(webhook.secret.encode('utf-8'), msg=payload_json.encode('utf-8'), digestmod=hashlib.sha256)
        signature = f"sha256={mac.hexdigest()}"
        
        with patch('apps.core.webhooks.services.get_background_processor') as mock_processor:
            mock_handle = MagicMock()
            mock_handle.id = 'test-task-id'
            mock_processor.return_value.submit.return_value = mock_handle
            
            # Process webhook
            success, message = webhook_service.process_github_webhook(webhook, payload, signature)
            self.assertTrue(success)
            
            # Send notification about deployment
            notification_service.notify_deployment_event(
                user=self.user,
                deployment_name='Test Deployment',
                event_type='deploy_success',
                status='Success',
                details='Deployment completed successfully'
            )
            
            # Verify notification log was created
            self.assertTrue(NotificationLog.objects.exists())