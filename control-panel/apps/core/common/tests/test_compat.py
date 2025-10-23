"""
Tests for backward compatibility layer.
"""

from django.test import TestCase
from unittest.mock import patch

# Test importing from the old paths
from apps.core.branding.models import BrandingSettings
from apps.core.models import (
    GitHubConnection,
    HuggingFaceConnection,
    GoogleConnection,
    Webhook,
    WebhookDelivery,
    NotificationChannel,
    NotificationLog,
)

from apps.core.forms import (
    BrandingSettingsForm,
    WebhookForm,
    NotificationChannelForm,
)

from apps.core.utils import (
    generate_password,
    generate_secret_key,
    encrypt_value,
    decrypt_value,
    encrypt_password,
    decrypt_password,
    generate_port,
    validate_repo_url,
    get_client_ip,
    validate_domain_name,
    sanitize_deployment_name,
    format_bytes,
    format_uptime,
)

from apps.core.branding.services import BrandingService as BrandingServiceCompat
from apps.core.integrations.services import (
    GitHubIntegrationService as GitHubIntegrationServiceCompat,
    HuggingFaceIntegrationService as HuggingFaceIntegrationServiceCompat,
    GoogleIntegrationService as GoogleIntegrationServiceCompat,
)
from apps.core.webhooks.services import WebhookService as WebhookServiceCompat
from apps.core.notifications.services import NotificationService as NotificationServiceCompat


class BackwardCompatibilityTests(TestCase):
    """Test backward compatibility layer."""

    def test_models_import(self):
        """Test that models can be imported from old paths."""
        # Test that the classes are available
        self.assertTrue(callable(BrandingSettings))
        self.assertTrue(callable(GitHubConnection))
        self.assertTrue(callable(HuggingFaceConnection))
        self.assertTrue(callable(GoogleConnection))
        self.assertTrue(callable(Webhook))
        self.assertTrue(callable(WebhookDelivery))
        self.assertTrue(callable(NotificationChannel))
        self.assertTrue(callable(NotificationLog))

    def test_forms_import(self):
        """Test that forms can be imported from old paths."""
        # Test that the forms are available
        self.assertTrue(callable(BrandingSettingsForm))
        self.assertTrue(callable(WebhookForm))
        self.assertTrue(callable(NotificationChannelForm))

    def test_utils_import(self):
        """Test that utilities can be imported from old paths."""
        # Test that the utility functions are available
        self.assertTrue(callable(generate_password))
        self.assertTrue(callable(generate_secret_key))
        self.assertTrue(callable(encrypt_value))
        self.assertTrue(callable(decrypt_value))
        self.assertTrue(callable(encrypt_password))
        self.assertTrue(callable(decrypt_password))
        self.assertTrue(callable(generate_port))
        self.assertTrue(callable(validate_repo_url))
        self.assertTrue(callable(get_client_ip))
        self.assertTrue(callable(validate_domain_name))
        self.assertTrue(callable(sanitize_deployment_name))
        self.assertTrue(callable(format_bytes))
        self.assertTrue(callable(format_uptime))

    def test_encryption_aliases(self):
        """Test that encryption aliases work correctly."""
        # Test that the aliases point to the same functions
        self.assertEqual(encrypt_password, encrypt_value)
        self.assertEqual(decrypt_password, decrypt_value)

    def test_services_import(self):
        """Test that services can be imported from old paths."""
        # Test that the services are available
        self.assertTrue(callable(BrandingServiceCompat))
        self.assertTrue(callable(GitHubIntegrationServiceCompat))
        self.assertTrue(callable(HuggingFaceIntegrationServiceCompat))
        self.assertTrue(callable(GoogleIntegrationServiceCompat))
        self.assertTrue(callable(WebhookServiceCompat))
        self.assertTrue(callable(NotificationServiceCompat))

    @patch('apps.core.common.utils.encryption.settings')
    def test_encryption_functions_work(self, mock_settings):
        """Test that encryption functions work through the compatibility layer."""
        mock_settings.ENCRYPTION_KEY = 'test-key-for-encryption-32-chars'
        
        # Test encryption
        original_value = 'test_password'
        encrypted = encrypt_value(original_value)
        decrypted = decrypt_value(encrypted)
        
        self.assertEqual(original_value, decrypted)
        
        # Test aliases
        encrypted_alias = encrypt_password(original_value)
        decrypted_alias = decrypt_password(encrypted_alias)
        
        self.assertEqual(original_value, decrypted_alias)
        self.assertEqual(encrypted, encrypted_alias)
        self.assertEqual(decrypted, decrypted_alias)

    def test_utility_functions_work(self):
        """Test that utility functions work through the compatibility layer."""
        # Test password generation
        password = generate_password()
        self.assertIsInstance(password, str)
        self.assertGreaterEqual(len(password), 12)
        
        # Test secret key generation
        key = generate_secret_key()
        self.assertIsInstance(key, str)
        self.assertEqual(len(key), 50)
        
        # Test port generation
        used_ports = {8001, 8002, 8003}
        port = generate_port(used_ports)
        self.assertNotIn(port, used_ports)
        self.assertGreaterEqual(port, 8001)
        self.assertLessEqual(port, 9000)
        
        # Test URL validation
        valid_url = 'https://github.com/user/repo'
        self.assertTrue(validate_repo_url(valid_url))
        
        invalid_url = 'http://github.com/user/repo'
        self.assertFalse(validate_repo_url(invalid_url))
        
        # Test domain validation
        valid_domain = 'example.com'
        self.assertTrue(validate_domain_name(valid_domain))
        
        invalid_domain = '-example.com'
        self.assertFalse(validate_domain_name(invalid_domain))
        
        # Test deployment name sanitization
        name = 'My App'
        sanitized = sanitize_deployment_name(name)
        self.assertEqual(sanitized, 'my-app')
        
        # Test formatting functions
        bytes_value = 1024
        formatted = format_bytes(bytes_value)
        self.assertEqual(formatted, '1.0 KB')
        
        uptime = 3600
        formatted = format_uptime(uptime)
        self.assertEqual(formatted, '1h 0m')
