"""
Tests for database views.
"""

import json
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch, MagicMock
from apps.databases.views import (
    DatabaseListView, DatabaseDetailView, DatabaseCreateView,
    DatabaseUpdateView, DatabaseDeleteView, DatabaseCredentialsView
)
from apps.databases.models import Database
from apps.core.utils import encrypt_password, decrypt_password


class DatabaseViewTest(TestCase):
    """Test cases for database views."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a test database
        self.test_db = Database.objects.create(
            name='test_db',
            db_type='postgresql',
            host='localhost',
            port=5432,
            username='test_user',
            password=encrypt_password('test_password'),
            database_name='test_db'
        )

    def test_database_list_view(self):
        """Test database list view."""
        # Create request
        request = self.factory.get(reverse('databases:list'))
        request.user = self.user
        
        # Get response
        response = DatabaseListView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test_db')

    def test_database_detail_view(self):
        """Test database detail view."""
        # Create request
        request = self.factory.get(reverse('databases:detail', args=[self.test_db.id]))
        request.user = self.user
        
        # Get response
        response = DatabaseDetailView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test_db')
        self.assertContains(response, 'test_user')
        self.assertContains(response, 'localhost')
        self.assertContains(response, '5432')

    @patch('apps.databases.views.DatabaseService')
    def test_database_create_view_get(self, mock_db_service):
        """Test database create view (GET)."""
        # Create request
        request = self.factory.get(reverse('databases:create'))
        request.user = self.user
        
        # Get response
        response = DatabaseCreateView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Database')

    @patch('apps.databases.views.DatabaseService')
    def test_database_create_view_post_valid(self, mock_db_service):
        """Test database create view (POST) with valid data."""
        # Mock DatabaseService methods
        mock_db_service.create_database.return_value = (True, "Database created successfully")
        mock_db_service.create_user.return_value = (True, "User created successfully")
        mock_db_service.grant_privileges.return_value = (True, "Privileges granted successfully")
        
        # Create request
        form_data = {
            'name': 'new_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'new_user',
            'password': 'new_password',
            'database_name': 'new_db'
        }
        request = self.factory.post(reverse('databases:create'), data=form_data)
        request.user = self.user
        
        # Get response
        response = DatabaseCreateView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 302)  # Redirect after successful creation
        self.assertEqual(response.url, reverse('databases:list'))
        
        # Verify DatabaseService methods were called
        mock_db_service.create_database.assert_called_once_with('new_db')
        mock_db_service.create_user.assert_called_once_with('new_user', 'new_password')
        mock_db_service.grant_privileges.assert_called_once_with('new_db', 'new_user')

    @patch('apps.databases.views.DatabaseService')
    def test_database_create_view_post_invalid(self, mock_db_service):
        """Test database create view (POST) with invalid data."""
        # Mock DatabaseService methods
        mock_db_service.create_database.return_value = (False, "Database already exists")
        
        # Create request with invalid data
        form_data = {
            'name': 'invalid@name',  # Invalid characters
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'new_user',
            'password': 'new_password',
            'database_name': 'new_db'
        }
        request = self.factory.post(reverse('databases:create'), data=form_data)
        request.user = self.user
        
        # Get response
        response = DatabaseCreateView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 200)  # Form is redisplayed
        self.assertContains(response, 'Create Database')
        
        # Verify DatabaseService methods were not called
        mock_db_service.create_database.assert_not_called()
        mock_db_service.create_user.assert_not_called()
        mock_db_service.grant_privileges.assert_not_called()

    def test_database_update_view_get(self):
        """Test database update view (GET)."""
        # Create request
        request = self.factory.get(reverse('databases:update', args=[self.test_db.id]))
        request.user = self.user
        
        # Get response
        response = DatabaseUpdateView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test_db')
        self.assertContains(response, 'Update Database')

    @patch('apps.databases.views.DatabaseService')
    def test_database_update_view_post_valid(self, mock_db_service):
        """Test database update view (POST) with valid data."""
        # Mock DatabaseService methods
        mock_db_service.create_database.return_value = (True, "Database created successfully")
        mock_db_service.create_user.return_value = (True, "User created successfully")
        mock_db_service.grant_privileges.return_value = (True, "Privileges granted successfully")
        
        # Create request
        form_data = {
            'name': 'updated_db',
            'db_type': 'postgresql',
            'host': 'updated_host',
            'port': 5433,
            'username': 'updated_user',
            'password': 'updated_password',
            'database_name': 'updated_db'
        }
        request = self.factory.post(reverse('databases:update', args=[self.test_db.id]), data=form_data)
        request.user = self.user
        
        # Get response
        response = DatabaseUpdateView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 302)  # Redirect after successful update
        self.assertEqual(response.url, reverse('databases:list'))
        
        # Verify DatabaseService methods were called
        mock_db_service.create_database.assert_called_once_with('updated_db')
        mock_db_service.create_user.assert_called_once_with('updated_user', 'updated_password')
        mock_db_service.grant_privileges.assert_called_once_with('updated_db', 'updated_user')

    @patch('apps.databases.views.DatabaseService')
    def test_database_update_view_post_invalid(self, mock_db_service):
        """Test database update view (POST) with invalid data."""
        # Mock DatabaseService methods
        mock_db_service.create_database.return_value = (False, "Database already exists")
        
        # Create request with invalid data
        form_data = {
            'name': 'invalid@name',  # Invalid characters
            'db_type': 'postgresql',
            'host': 'updated_host',
            'port': 5433,
            'username': 'updated_user',
            'password': 'updated_password',
            'database_name': 'updated_db'
        }
        request = self.factory.post(reverse('databases:update', args=[self.test_db.id]), data=form_data)
        request.user = self.user
        
        # Get response
        response = DatabaseUpdateView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 200)  # Form is redisplayed
        self.assertContains(response, 'Update Database')
        
        # Verify DatabaseService methods were not called
        mock_db_service.create_database.assert_not_called()
        mock_db_service.create_user.assert_not_called()
        mock_db_service.grant_privileges.assert_not_called()

    def test_database_delete_view_get(self):
        """Test database delete view (GET)."""
        # Create request
        request = self.factory.get(reverse('databases:delete', args=[self.test_db.id]))
        request.user = self.user
        
        # Get response
        response = DatabaseDeleteView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test_db')
        self.assertContains(response, 'Delete Database')

    @patch('apps.databases.views.DatabaseService')
    def test_database_delete_view_post_confirm(self, mock_db_service):
        """Test database delete view (POST) with confirmation."""
        # Mock DatabaseService methods
        mock_db_service.delete_database.return_value = (True, "Database deleted successfully")
        mock_db_service.delete_user.return_value = (True, "User deleted successfully")
        
        # Create request with confirmation
        form_data = {
            'confirm': 'yes'
        }
        request = self.factory.post(reverse('databases:delete', args=[self.test_db.id]), data=form_data)
        request.user = self.user
        
        # Get response
        response = DatabaseDeleteView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 302)  # Redirect after successful deletion
        self.assertEqual(response.url, reverse('databases:list'))
        
        # Verify DatabaseService methods were called
        mock_db_service.delete_database.assert_called_once_with('test_db')
        mock_db_service.delete_user.assert_called_once_with('test_user')

    @patch('apps.databases.views.DatabaseService')
    def test_database_delete_view_post_no_confirm(self, mock_db_service):
        """Test database delete view (POST) without confirmation."""
        # Create request without confirmation
        form_data = {
            'confirm': 'no'
        }
        request = self.factory.post(reverse('databases:delete', args=[self.test_db.id]), data=form_data)
        request.user = self.user
        
        # Get response
        response = DatabaseDeleteView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 200)  # Form is redisplayed
        self.assertContains(response, 'Delete Database')
        
        # Verify DatabaseService methods were not called
        mock_db_service.delete_database.assert_not_called()
        mock_db_service.delete_user.assert_not_called()

    @patch('apps.databases.views.DatabaseService')
    def test_database_credentials_view_html(self, mock_db_service):
        """Test database credentials view (HTML)."""
        # Mock DatabaseService.get_connection_string
        mock_db_service.get_connection_string.return_value = "postgresql://test_user:test_password@localhost:5432/test_db"
        
        # Create request
        request = self.factory.get(reverse('databases:credentials', args=[self.test_db.id]))
        request.user = self.user
        
        # Get response
        response = DatabaseCredentialsView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test_db')
        self.assertContains(response, 'test_user')
        self.assertContains(response, 'test_password')
        self.assertContains(response, 'postgresql://test_user:test_password@localhost:5432/test_db')
        
        # Verify DatabaseService method was called
        mock_db_service.get_connection_string.assert_called_once()

    @patch('apps.databases.views.DatabaseService')
    def test_database_credentials_view_json(self, mock_db_service):
        """Test database credentials view (JSON)."""
        # Mock DatabaseService.get_connection_string
        mock_db_service.get_connection_string.return_value = "postgresql://test_user:test_password@localhost:5432/test_db"
        
        # Create request with HTTP header for JSON
        request = self.factory.get(
            reverse('databases:credentials', args=[self.test_db.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        request.user = self.user
        
        # Get response
        response = DatabaseCredentialsView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        
        # Parse JSON response
        response_data = json.loads(response.content)
        
        # Check JSON response
        self.assertEqual(response_data['name'], 'test_db')
        self.assertEqual(response_data['username'], 'test_user')
        self.assertEqual(response_data['password'], 'test_password')
        self.assertEqual(response_data['host'], 'localhost')
        self.assertEqual(response_data['port'], 5432)
        self.assertEqual(response_data['connection_string'], 'postgresql://test_user:test_password@localhost:5432/test_db')
        
        # Verify DatabaseService method was called
        mock_db_service.get_connection_string.assert_called_once()

    @patch('apps.databases.views.DatabaseService')
    def test_database_credentials_view_masked(self, mock_db_service):
        """Test database credentials view with masked password."""
        # Mock DatabaseService.get_connection_string
        mock_db_service.get_connection_string.return_value = "postgresql://test_user:****@localhost:5432/test_db"
        
        # Create request
        request = self.factory.get(reverse('databases:credentials', args=[self.test_db.id]))
        request.user = self.user
        
        # Get response
        response = DatabaseCredentialsView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test_db')
        self.assertContains(response, 'test_user')
        self.assertNotContains(response, 'test_password')  # Password should be masked
        self.assertContains(response, 'postgresql://test_user:****@localhost:5432/test_db')
        
        # Verify DatabaseService method was called with decrypted=False
        mock_db_service.get_connection_string.assert_called_once_with(self.test_db, decrypted=False)

    @patch('apps.databases.views.logger')
    def test_database_credentials_view_logging(self, mock_logger):
        """Test database credentials view logging."""
        # Create request
        request = self.factory.get(reverse('databases:credentials', args=[self.test_db.id]))
        request.user = self.user
        
        # Get response
        response = DatabaseCredentialsView.as_view()(request)
        
        # Verify logger was called
        mock_logger.info.assert_called_once_with(
            "Database credentials accessed",
            extra={
                'user_id': self.user.id,
                'username': self.user.username,
                'database_id': self.test_db.id,
                'database_name': 'test_db',
                'timestamp': mock_logger.info.call_args[0]['extra']['timestamp']
            }
        )

    def test_database_views_require_login(self):
        """Test that database views require login."""
        # Create request without user
        request = self.factory.get(reverse('databases:list'))
        
        # Get response
        response = DatabaseListView.as_view()(request)
        
        # Check response
        self.assertEqual(response.status_code, 302)  # Redirect to login
        self.assertIn(reverse('login'), response.url)