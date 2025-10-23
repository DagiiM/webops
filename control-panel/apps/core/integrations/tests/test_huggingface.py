"""
Tests for Hugging Face integration service.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from apps.core.integrations.models import HuggingFaceConnection
from apps.core.integrations.services.huggingface import HuggingFaceIntegrationService


class HuggingFaceIntegrationServiceTests(TestCase):
    """Test HuggingFaceIntegrationService."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = HuggingFaceIntegrationService()

    @patch('apps.core.integrations.services.huggingface.requests.get')
    def test_validate_token_success(self, mock_get):
        """Test successful token validation."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'name': 'Test User',
            'id': 'testuser',
            'type': 'user'
        }
        mock_get.return_value = mock_response

        # Test token validation
        is_valid, user_data = self.service.validate_token('test_token')
        
        self.assertTrue(is_valid)
        self.assertEqual(user_data['name'], 'Test User')

    @patch('apps.core.integrations.services.huggingface.requests.get')
    def test_validate_token_failure(self, mock_get):
        """Test failed token validation."""
        # Mock failed API response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        # Test token validation
        is_valid, user_data = self.service.validate_token('invalid_token')
        
        self.assertFalse(is_valid)
        self.assertIsNone(user_data)

    @patch('apps.core.integrations.services.huggingface.requests.get')
    def test_save_connection_success(self, mock_get):
        """Test successful connection saving."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'name': 'Test User',
            'id': 'testuser',
            'type': 'user'
        }
        mock_get.return_value = mock_response

        # Test saving connection
        connection = self.service.save_connection(
            self.user, 
            'test_token', 
            'read'
        )
        
        self.assertIsNotNone(connection)
        self.assertEqual(connection.username, 'Test User')
        self.assertEqual(connection.token_type, 'read')
        self.assertTrue(connection.is_valid)

    @patch('apps.core.integrations.services.huggingface.requests.get')
    def test_save_connection_failure(self, mock_get):
        """Test failed connection saving."""
        # Mock failed API response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        # Test saving connection
        connection = self.service.save_connection(
            self.user, 
            'invalid_token', 
            'read'
        )
        
        self.assertIsNone(connection)

    def test_get_connection(self):
        """Test getting user's Hugging Face connection."""
        # Create a connection
        connection = HuggingFaceConnection.objects.create(
            user=self.user,
            username='testuser',
            access_token='encrypted_token',
            token_type='read'
        )

        # Test getting connection
        result = self.service.get_connection(self.user)
        
        self.assertEqual(result, connection)

    def test_get_connection_none(self):
        """Test getting non-existent connection."""
        # Test getting connection for user without one
        result = self.service.get_connection(self.user)
        
        self.assertIsNone(result)

    def test_disconnect(self):
        """Test disconnecting Hugging Face account."""
        # Create a connection
        HuggingFaceConnection.objects.create(
            user=self.user,
            username='testuser',
            access_token='encrypted_token',
            token_type='read'
        )

        # Test disconnecting
        success = self.service.disconnect(self.user)
        
        self.assertTrue(success)
        self.assertFalse(HuggingFaceConnection.objects.filter(user=self.user).exists())

    def test_disconnect_none(self):
        """Test disconnecting non-existent connection."""
        # Test disconnecting for user without connection
        success = self.service.disconnect(self.user)
        
        self.assertFalse(success)

    @patch('apps.core.integrations.services.huggingface.requests.get')
    def test_test_connection_success(self, mock_get):
        """Test successful connection test."""
        # Create a connection
        HuggingFaceConnection.objects.create(
            user=self.user,
            username='testuser',
            access_token='encrypted_token',
            token_type='read'
        )

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'name': 'Test User',
            'id': 'testuser',
        }
        mock_get.return_value = mock_response

        # Test connection
        is_valid, message = self.service.test_connection(self.user)
        
        self.assertTrue(is_valid)
        self.assertIn('Test User', message)

    @patch('apps.core.integrations.services.huggingface.requests.get')
    def test_test_connection_failure(self, mock_get):
        """Test failed connection test."""
        # Create a connection
        HuggingFaceConnection.objects.create(
            user=self.user,
            username='testuser',
            access_token='encrypted_token',
            token_type='read'
        )

        # Mock failed API response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        # Test connection
        is_valid, message = self.service.test_connection(self.user)
        
        self.assertFalse(is_valid)
        self.assertIn('Invalid', message)

    def test_test_connection_none(self):
        """Test connection test for user without connection."""
        # Test connection for user without one
        is_valid, message = self.service.test_connection(self.user)
        
        self.assertFalse(is_valid)
        self.assertIn('No Hugging Face connection', message)

    @patch('apps.core.integrations.services.huggingface.requests.get')
    def test_list_user_models(self, mock_get):
        """Test listing user models."""
        # Create a connection
        HuggingFaceConnection.objects.create(
            user=self.user,
            username='testuser',
            access_token='encrypted_token',
            token_type='read'
        )

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'id': 'model1', 'name': 'Test Model 1'},
            {'id': 'model2', 'name': 'Test Model 2'}
        ]
        mock_get.return_value = mock_response

        # Test listing models
        models = self.service.list_user_models(self.user)
        
        self.assertIsNotNone(models)
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]['id'], 'model1')

    def test_list_user_models_no_connection(self):
        """Test listing models without connection."""
        # Test listing models for user without connection
        models = self.service.list_user_models(self.user)
        
        self.assertIsNone(models)