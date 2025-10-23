"""
Tests for Google integration service.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from apps.core.integrations.models import GoogleConnection
from apps.core.integrations.services.google import GoogleIntegrationService


class GoogleIntegrationServiceTests(TestCase):
    """Test GoogleIntegrationService."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = GoogleIntegrationService()

    @patch('apps.core.integrations.services.google.requests.get')
    def test_get_user_info_success(self, mock_get):
        """Test successful user info retrieval."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'sub': '123456789',
            'email': 'test@example.com',
            'name': 'Test User',
            'picture': 'https://example.com/avatar.jpg'
        }
        mock_get.return_value = mock_response

        # Test getting user info
        user_info = self.service.get_user_info('test_token')
        
        self.assertIsNotNone(user_info)
        self.assertEqual(user_info['email'], 'test@example.com')
        self.assertEqual(user_info['name'], 'Test User')

    @patch('apps.core.integrations.services.google.requests.get')
    def test_get_user_info_failure(self, mock_get):
        """Test failed user info retrieval."""
        # Mock failed API response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        # Test getting user info
        user_info = self.service.get_user_info('invalid_token')
        
        self.assertIsNone(user_info)

    @patch('apps.core.integrations.services.google.requests.post')
    def test_exchange_code_for_token_success(self, mock_post):
        """Test successful code exchange for token."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'id_token': 'test_id_token',
            'expires_in': 3600,
            'scope': 'openid email profile'
        }
        mock_post.return_value = mock_response

        # Test code exchange
        token_data = self.service.exchange_code_for_token('test_code', 'http://example.com/callback')
        
        self.assertIsNotNone(token_data)
        self.assertEqual(token_data['access_token'], 'test_access_token')
        self.assertEqual(token_data['refresh_token'], 'test_refresh_token')

    @patch('apps.core.integrations.services.google.requests.post')
    def test_exchange_code_for_token_failure(self, mock_post):
        """Test failed code exchange for token."""
        # Mock failed API response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {'error': 'invalid_grant'}
        mock_post.return_value = mock_response

        # Test code exchange
        token_data = self.service.exchange_code_for_token('invalid_code', 'http://example.com/callback')
        
        self.assertIsNone(token_data)

    @patch('apps.core.integrations.services.google.requests.get')
    def test_save_connection_success(self, mock_get):
        """Test successful connection saving."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'sub': '123456789',
            'email': 'test@example.com',
            'name': 'Test User',
            'picture': 'https://example.com/avatar.jpg'
        }
        mock_get.return_value = mock_response

        # Test saving connection
        token_data = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'id_token': 'test_id_token',
            'expires_in': 3600,
            'scope': 'openid email profile'
        }
        user_info = {
            'sub': '123456789',
            'email': 'test@example.com',
            'name': 'Test User'
        }
        
        connection = self.service.save_connection(self.user, token_data, user_info)
        
        self.assertIsNotNone(connection)
        self.assertEqual(connection.email, 'test@example.com')
        self.assertEqual(connection.name, 'Test User')
        self.assertEqual(connection.google_user_id, '123456789')
        self.assertTrue(connection.is_valid)

    def test_get_connection(self):
        """Test getting user's Google connection."""
        # Create a connection
        connection = GoogleConnection.objects.create(
            user=self.user,
            google_user_id='123456789',
            email='test@example.com',
            name='Test User',
            access_token='encrypted_token'
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
        """Test disconnecting Google account."""
        # Create a connection
        GoogleConnection.objects.create(
            user=self.user,
            google_user_id='123456789',
            email='test@example.com',
            name='Test User',
            access_token='encrypted_token'
        )

        # Test disconnecting
        success = self.service.disconnect(self.user)
        
        self.assertTrue(success)
        self.assertFalse(GoogleConnection.objects.filter(user=self.user).exists())

    def test_disconnect_none(self):
        """Test disconnecting non-existent connection."""
        # Test disconnecting for user without connection
        success = self.service.disconnect(self.user)
        
        self.assertFalse(success)

    @patch('apps.core.integrations.services.google.requests.get')
    def test_test_connection_success(self, mock_get):
        """Test successful connection test."""
        # Create a connection
        GoogleConnection.objects.create(
            user=self.user,
            google_user_id='123456789',
            email='test@example.com',
            name='Test User',
            access_token='encrypted_token'
        )

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'sub': '123456789',
            'email': 'test@example.com',
            'name': 'Test User',
        }
        mock_get.return_value = mock_response

        # Test connection
        is_valid, message = self.service.test_connection(self.user)
        
        self.assertTrue(is_valid)
        self.assertIn('test@example.com', message)

    @patch('apps.core.integrations.services.google.requests.get')
    def test_test_connection_failure(self, mock_get):
        """Test failed connection test."""
        # Create a connection
        GoogleConnection.objects.create(
            user=self.user,
            google_user_id='123456789',
            email='test@example.com',
            name='Test User',
            access_token='encrypted_token'
        )

        # Mock failed API response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        # Test connection
        is_valid, message = self.service.test_connection(self.user)
        
        self.assertFalse(is_valid)
        self.assertIn('Failed', message)

    def test_test_connection_none(self):
        """Test connection test for user without connection."""
        # Test connection for user without one
        is_valid, message = self.service.test_connection(self.user)
        
        self.assertFalse(is_valid)
        self.assertIn('No Google access token', message)

    @patch('apps.core.integrations.services.google.requests.post')
    def test_test_oauth_config_success(self, mock_post):
        """Test successful OAuth config test."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {'error': 'invalid_grant'}
        mock_post.return_value = mock_response

        # Test OAuth config
        is_valid, message = self.service.test_oauth_config()
        
        self.assertTrue(is_valid)
        self.assertIn('valid', message)

    @patch('apps.core.integrations.services.google.requests.post')
    def test_test_oauth_config_invalid_client(self, mock_post):
        """Test OAuth config test with invalid client."""
        # Mock API response for invalid client
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {'error': 'invalid_client'}
        mock_post.return_value = mock_response

        # Test OAuth config
        is_valid, message = self.service.test_oauth_config()
        
        self.assertFalse(is_valid)
        self.assertIn('Invalid', message)

    @patch('apps.core.integrations.services.google.requests.post')
    def test_test_oauth_config_request_exception(self, mock_post):
        """Test OAuth config test with request exception."""
        # Mock request exception
        mock_post.side_effect = Exception("Connection error")

        # Test OAuth config
        is_valid, message = self.service.test_oauth_config()
        
        self.assertFalse(is_valid)
        self.assertIn('Failed to connect', message)