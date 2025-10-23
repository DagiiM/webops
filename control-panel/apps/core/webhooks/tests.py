"""
Tests for webhooks domain.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
import json
import hmac
import hashlib
from apps.core.webhooks.models import Webhook, WebhookDelivery
from apps.core.webhooks.services import WebhookService
from apps.deployments.models import BaseDeployment


class WebhookServiceTests(TestCase):
    """Test WebhookService."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = WebhookService()
        
        # Create a mock deployment
        self.deployment = BaseDeployment.objects.create(
            name='Test Deployment',
            deployed_by=self.user
        )

    def test_generate_secret(self):
        """Test secret generation."""
        secret = WebhookService.generate_secret()
        
        self.assertEqual(len(secret), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in secret))

    def test_create_webhook(self):
        """Test webhook creation."""
        webhook = self.service.create_webhook(
            user=self.user,
            deployment=self.deployment,
            name='Test Webhook',
            trigger_event=Webhook.TriggerEvent.PUSH,
            branch_filter='main'
        )
        
        self.assertEqual(webhook.name, 'Test Webhook')
        self.assertEqual(webhook.user, self.user)
        self.assertEqual(webhook.deployment, self.deployment)
        self.assertEqual(webhook.trigger_event, Webhook.TriggerEvent.PUSH)
        self.assertEqual(webhook.branch_filter, 'main')
        self.assertTrue(webhook.is_active)
        self.assertEqual(len(webhook.secret), 64)

    def test_validate_github_signature_valid(self):
        """Test valid GitHub signature validation."""
        secret = 'test_secret'
        payload = b'{"test": "payload"}'
        
        # Create a valid signature
        mac = hmac.new(secret.encode('utf-8'), msg=payload, digestmod=hashlib.sha256)
        signature = f"sha256={mac.hexdigest()}"
        
        result = self.service.validate_github_signature(payload, signature, secret)
        self.assertTrue(result)

    def test_validate_github_signature_invalid(self):
        """Test invalid GitHub signature validation."""
        secret = 'test_secret'
        payload = b'{"test": "payload"}'
        
        # Create an invalid signature
        signature = 'sha256=invalid_signature'
        
        result = self.service.validate_github_signature(payload, signature, secret)
        self.assertFalse(result)

    def test_validate_github_signature_missing(self):
        """Test missing GitHub signature."""
        secret = 'test_secret'
        payload = b'{"test": "payload"}'
        
        result = self.service.validate_github_signature(payload, '', secret)
        self.assertFalse(result)

    def test_get_webhook_url(self):
        """Test webhook URL generation."""
        webhook = Webhook.objects.create(
            user=self.user,
            deployment=self.deployment,
            name='Test Webhook',
            secret='test_secret'
        )
        
        url = self.service.get_webhook_url(webhook)
        self.assertEqual(url, 'http://localhost:8000/webhooks/test_secret/')

    def test_list_user_webhooks(self):
        """Test listing user webhooks."""
        # Create webhooks
        webhook1 = Webhook.objects.create(
            user=self.user,
            deployment=self.deployment,
            name='Webhook 1',
            secret='secret1'
        )
        webhook2 = Webhook.objects.create(
            user=self.user,
            deployment=self.deployment,
            name='Webhook 2',
            secret='secret2'
        )
        
        webhooks = self.service.list_user_webhooks(self.user)
        
        self.assertEqual(len(webhooks), 2)
        self.assertEqual(webhooks[0]['name'], 'Webhook 2')  # Ordered by -created_at
        self.assertEqual(webhooks[1]['name'], 'Webhook 1')

    def test_toggle_webhook(self):
        """Test toggling webhook status."""
        webhook = Webhook.objects.create(
            user=self.user,
            deployment=self.deployment,
            name='Test Webhook',
            secret='test_secret',
            is_active=True
        )
        
        # Deactivate webhook
        is_active = self.service.toggle_webhook(webhook)
        self.assertFalse(is_active)
        self.assertEqual(webhook.status, Webhook.Status.PAUSED)
        
        # Reactivate webhook
        is_active = self.service.toggle_webhook(webhook)
        self.assertTrue(is_active)
        self.assertEqual(webhook.status, Webhook.Status.ACTIVE)

    def test_delete_webhook(self):
        """Test webhook deletion."""
        webhook = Webhook.objects.create(
            user=self.user,
            deployment=self.deployment,
            name='Test Webhook',
            secret='test_secret'
        )
        
        result = self.service.delete_webhook(webhook)
        self.assertTrue(result)
        self.assertFalse(Webhook.objects.filter(id=webhook.id).exists())

    def test_get_recent_deliveries(self):
        """Test getting recent webhook deliveries."""
        webhook = Webhook.objects.create(
            user=self.user,
            deployment=self.deployment,
            name='Test Webhook',
            secret='test_secret'
        )
        
        # Create delivery records
        delivery1 = WebhookDelivery.objects.create(
            webhook=webhook,
            status=WebhookDelivery.Status.SUCCESS,
            payload={'ref': 'refs/heads/main', 'commits': [{'message': 'Commit 1'}]},
            triggered_by='GitHub push to main'
        )
        delivery2 = WebhookDelivery.objects.create(
            webhook=webhook,
            status=WebhookDelivery.Status.FAILED,
            payload={'ref': 'refs/heads/main', 'commits': [{'message': 'Commit 2'}]},
            triggered_by='GitHub push to main',
            error_message='Test error'
        )
        
        deliveries = self.service.get_recent_deliveries(webhook)
        
        self.assertEqual(len(deliveries), 2)
        self.assertEqual(deliveries[0]['status'], 'FAILED')
        self.assertEqual(deliveries[1]['status'], 'SUCCESS')
        self.assertEqual(deliveries[0]['payload_summary']['commits'], 1)
        self.assertEqual(deliveries[1]['payload_summary']['ref'], 'refs/heads/main')

    @patch('apps.core.webhooks.services.get_background_processor')
    @patch('apps.core.webhooks.services.ServiceManager')
    def test_process_github_webhook_success(self, mock_service_manager, mock_processor):
        """Test successful GitHub webhook processing."""
        webhook = Webhook.objects.create(
            user=self.user,
            deployment=self.deployment,
            name='Test Webhook',
            secret='test_secret',
            is_active=True
        )
        
        # Mock the background processor
        mock_handle = MagicMock()
        mock_handle.id = 'test-task-id'
        mock_processor.return_value.submit.return_value = mock_handle
        
        # Create a valid signature
        payload = {'ref': 'refs/heads/main', 'commits': [{'message': 'Test commit'}]}
        payload_json = json.dumps(payload, separators=(",", ":"))
        mac = hmac.new(webhook.secret.encode('utf-8'), msg=payload_json.encode('utf-8'), digestmod=hashlib.sha256)
        signature = f"sha256={mac.hexdigest()}"
        
        success, message = self.service.process_github_webhook(webhook, payload, signature)
        
        self.assertTrue(success)
        self.assertIn('Deployment triggered for branch main', message)
        
        # Check that a delivery record was created
        delivery = WebhookDelivery.objects.get(webhook=webhook)
        self.assertEqual(delivery.status, WebhookDelivery.Status.SUCCESS)
        self.assertEqual(delivery.response['task_id'], 'test-task-id')
        
        # Check webhook was updated
        webhook.refresh_from_db()
        self.assertEqual(webhook.trigger_count, 1)
        self.assertIsNotNone(webhook.last_triggered)

    @patch('apps.core.webhooks.services.get_background_processor')
    def test_process_github_webhook_invalid_signature(self, mock_processor):
        """Test GitHub webhook processing with invalid signature."""
        webhook = Webhook.objects.create(
            user=self.user,
            deployment=self.deployment,
            name='Test Webhook',
            secret='test_secret',
            is_active=True
        )
        
        payload = {'ref': 'refs/heads/main', 'commits': [{'message': 'Test commit'}]}
        signature = 'sha256=invalid_signature'
        
        success, message = self.service.process_github_webhook(webhook, payload, signature)
        
        self.assertFalse(success)
        self.assertIn('Invalid signature', message)

    @patch('apps.core.webhooks.services.get_background_processor')
    def test_process_github_webhook_inactive(self, mock_processor):
        """Test GitHub webhook processing for inactive webhook."""
        webhook = Webhook.objects.create(
            user=self.user,
            deployment=self.deployment,
            name='Test Webhook',
            secret='test_secret',
            is_active=False
        )
        
        payload = {'ref': 'refs/heads/main', 'commits': [{'message': 'Test commit'}]}
        
        # Create a valid signature
        payload_json = json.dumps(payload, separators=(",", ":"))
        mac = hmac.new(webhook.secret.encode('utf-8'), msg=payload_json.encode('utf-8'), digestmod=hashlib.sha256)
        signature = f"sha256={mac.hexdigest()}"
        
        success, message = self.service.process_github_webhook(webhook, payload, signature)
        
        self.assertFalse(success)
        self.assertIn('Webhook is paused', message)

    @patch('apps.core.webhooks.services.get_background_processor')
    def test_process_github_webhook_branch_filter(self, mock_processor):
        """Test GitHub webhook processing with branch filter."""
        webhook = Webhook.objects.create(
            user=self.user,
            deployment=self.deployment,
            name='Test Webhook',
            secret='test_secret',
            is_active=True,
            branch_filter='main'
        )
        
        # Payload with different branch
        payload = {'ref': 'refs/heads/develop', 'commits': [{'message': 'Test commit'}]}
        
        # Create a valid signature
        payload_json = json.dumps(payload, separators=(",", ":"))
        mac = hmac.new(webhook.secret.encode('utf-8'), msg=payload_json.encode('utf-8'), digestmod=hashlib.sha256)
        signature = f"sha256={mac.hexdigest()}"
        
        success, message = self.service.process_github_webhook(webhook, payload, signature)
        
        self.assertFalse(success)
        self.assertIn("Branch develop doesn't match filter", message)