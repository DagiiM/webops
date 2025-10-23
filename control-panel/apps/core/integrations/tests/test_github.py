"""
Tests for GitHub integration service.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from apps.core.integrations.models import GitHubConnection
from apps.core.integrations.services.github import GitHubIntegrationService


class GitHubIntegrationServiceTests(TestCase):
    """Test GitHubIntegrationService."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = GitHubIntegrationService()

    @patch('apps.core.integrations.services.github.requests.get')
    def test_validate_token_success(self, mock_get):
        """Test successful token validation."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 12345,
            'login': 'testuser',
            'name': 'Test User'
        }
        mock_get.return_value = mock_response

        # Test token validation
        is_valid, user_data = self.service.validate_token('test_token')
        
        self.assertTrue(is_valid)
        self.assertEqual(user_data['login'], 'testuser')

    @patch('apps.core.integrations.services.github.requests.get')
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

    @patch('apps.core.integrations.services.github.requests.get')
    def test_save_connection_with_pat(self, mock_get):
        """Test saving connection with Personal Access Token."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 12345,
            'login': 'testuser',
            'name': 'Test User'
        }
        mock_get.return_value = mock_response

        # Test saving connection
        connection = self.service.save_connection_with_pat(self.user, 'test_token')
        
        self.assertIsNotNone(connection)
        self.assertEqual(connection.username, 'testuser')
        self.assertEqual(connection.github_user_id, 12345)

    def test_get_connection(self):
        """Test getting user's GitHub connection."""
        # Create a connection
        connection = GitHubConnection.objects.create(
            user=self.user,
            github_user_id=12345,
            username='testuser',
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
        """Test disconnecting GitHub account."""
        # Create a connection
        GitHubConnection.objects.create(
            user=self.user,
            github_user_id=12345,
            username='testuser',
            access_token='encrypted_token'
        )

        # Test disconnecting
        success = self.service.disconnect(self.user)
        
        self.assertTrue(success)
        self.assertFalse(GitHubConnection.objects.filter(user=self.user).exists())

    def test_disconnect_none(self):
        """Test disconnecting non-existent connection."""
        # Test disconnecting for user without connection
        success = self.service.disconnect(self.user)
        
        self.assertFalse(success)

    @patch('apps.core.integrations.services.github.requests.get')
    def test_test_connection_success(self, mock_get):
        """Test successful connection test."""
        # Create a connection
        GitHubConnection.objects.create(
            user=self.user,
            github_user_id=12345,
            username='testuser',
            access_token='encrypted_token'
        )

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 12345,
            'login': 'testuser',
        }
        mock_get.return_value = mock_response

        # Test connection
        is_valid, message = self.service.test_connection(self.user)
        
        self.assertTrue(is_valid)
        self.assertIn('testuser', message)

    @patch('apps.core.integrations.services.github.requests.get')
    def test_test_connection_failure(self, mock_get):
        """Test failed connection test."""
        # Create a connection
        GitHubConnection.objects.create(
            user=self.user,
            github_user_id=12345,
            username='testuser',
            access_token='encrypted_token'
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
        self.assertIn('No GitHub connection', message)

    @patch('apps.core.integrations.services.github.requests.post')
    def test_exchange_code_for_token_success(self, mock_post):
        """Test successful code exchange for token."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'token_type': 'bearer',
            'scope': 'repo,user'
        }
        mock_post.return_value = mock_response

        # Test code exchange
        token_data = self.service.exchange_code_for_token('test_code', 'http://example.com/callback')
        
        self.assertIsNotNone(token_data)
        self.assertEqual(token_data['access_token'], 'test_access_token')

    @patch('apps.core.integrations.services.github.requests.post')
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