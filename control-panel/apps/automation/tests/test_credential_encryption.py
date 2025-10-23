"""
Tests for credential encryption functionality.
"""

import pytest
from django.test import TestCase
from django.contrib.auth.models import User

from apps.automation.models import DataSourceCredential


class DataSourceCredentialTest(TestCase):
    """Test the DataSourceCredential model with focus on encryption."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_encrypt_sensitive_fields_on_save(self):
        """Test that sensitive fields are encrypted on save."""
        credentials = {
            'api_key': 'secret-api-key',
            'token': 'secret-token',
            'username': 'testuser',  # Not sensitive
            'url': 'https://api.example.com'  # Not sensitive
        }
        
        credential = DataSourceCredential.objects.create(
            user=self.user,
            provider=DataSourceCredential.Provider.CUSTOM,
            name='Test Credential',
            credentials=credentials
        )
        
        # Refresh from database
        credential.refresh_from_db()
        
        # Check that sensitive fields are encrypted
        stored_creds = credential.credentials
        self.assertNotEqual(stored_creds['api_key'], 'secret-api-key')
        self.assertNotEqual(stored_creds['token'], 'secret-token')
        
        # Non-sensitive fields should remain unchanged
        self.assertEqual(stored_creds['username'], 'testuser')
        self.assertEqual(stored_creds['url'], 'https://api.example.com')
    
    def test_get_credentials_decrypts_sensitive_fields(self):
        """Test that get_credentials decrypts sensitive fields."""
        credentials = {
            'api_key': 'secret-api-key',
            'token': 'secret-token',
            'username': 'testuser',
            'url': 'https://api.example.com'
        }
        
        credential = DataSourceCredential.objects.create(
            user=self.user,
            provider=DataSourceCredential.Provider.CUSTOM,
            name='Test Credential',
            credentials=credentials
        )
        
        # Get decrypted credentials
        decrypted_creds = credential.get_credentials()
        
        # All fields should be decrypted
        self.assertEqual(decrypted_creds['api_key'], 'secret-api-key')
        self.assertEqual(decrypted_creds['token'], 'secret-token')
        self.assertEqual(decrypted_creds['username'], 'testuser')
        self.assertEqual(decrypted_creds['url'], 'https://api.example.com')
    
    def test_update_credentials_reencrypts(self):
        """Test that updating credentials re-encrypts them."""
        # Create credential
        credentials = {
            'api_key': 'secret-api-key',
            'username': 'testuser'
        }
        
        credential = DataSourceCredential.objects.create(
            user=self.user,
            provider=DataSourceCredential.Provider.CUSTOM,
            name='Test Credential',
            credentials=credentials
        )
        
        # Update credentials
        new_credentials = {
            'api_key': 'new-secret-key',
            'token': 'new-token',
            'username': 'testuser'
        }
        
        credential.credentials = new_credentials
        credential.save()
        
        # Refresh from database
        credential.refresh_from_db()
        
        # Check that new sensitive fields are encrypted
        stored_creds = credential.credentials
        self.assertNotEqual(stored_creds['api_key'], 'new-secret-key')
        self.assertNotEqual(stored_creds['token'], 'new-token')
        
        # Get decrypted credentials
        decrypted_creds = credential.get_credentials()
        self.assertEqual(decrypted_creds['api_key'], 'new-secret-key')
        self.assertEqual(decrypted_creds['token'], 'new-token')
    
    def test_empty_credentials_handling(self):
        """Test handling of empty credentials."""
        credential = DataSourceCredential.objects.create(
            user=self.user,
            provider=DataSourceCredential.Provider.CUSTOM,
            name='Empty Credential',
            credentials={}
        )
        
        decrypted_creds = credential.get_credentials()
        self.assertEqual(decrypted_creds, {})
    
    def test_none_values_handling(self):
        """Test handling of None values in credentials."""
        credentials = {
            'api_key': None,
            'token': 'some-token',
            'username': 'testuser'
        }
        
        credential = DataSourceCredential.objects.create(
            user=self.user,
            provider=DataSourceCredential.Provider.CUSTOM,
            name='Test Credential',
            credentials=credentials
        )
        
        # None values should remain None
        decrypted_creds = credential.get_credentials()
        self.assertIsNone(decrypted_creds['api_key'])
        self.assertEqual(decrypted_creds['token'], 'some-token')
        self.assertEqual(decrypted_creds['username'], 'testuser')
    
    def test_various_sensitive_field_patterns(self):
        """Test that various sensitive field patterns are detected."""
        credentials = {
            'api_key': 'secret-api-key',
            'access_token': 'secret-access-token',
            'refresh_token': 'secret-refresh-token',
            'private_key': 'secret-private-key',
            'password': 'secret-password',
            'secret': 'secret-value',
            'client_secret': 'secret-client-secret',
            'public_key': 'public-key-value',  # Not sensitive
            'description': 'A description'  # Not sensitive
        }
        
        credential = DataSourceCredential.objects.create(
            user=self.user,
            provider=DataSourceCredential.Provider.CUSTOM,
            name='Test Credential',
            credentials=credentials
        )
        
        # Check that only sensitive fields are encrypted
        stored_creds = credential.credentials
        self.assertNotEqual(stored_creds['api_key'], 'secret-api-key')
        self.assertNotEqual(stored_creds['access_token'], 'secret-access-token')
        self.assertNotEqual(stored_creds['refresh_token'], 'secret-refresh-token')
        self.assertNotEqual(stored_creds['private_key'], 'secret-private-key')
        self.assertNotEqual(stored_creds['password'], 'secret-password')
        self.assertNotEqual(stored_creds['secret'], 'secret-value')
        self.assertNotEqual(stored_creds['client_secret'], 'secret-client-secret')
        
        # Non-sensitive fields should remain unchanged
        self.assertEqual(stored_creds['public_key'], 'public-key-value')
        self.assertEqual(stored_creds['description'], 'A description')
        
        # Get decrypted credentials
        decrypted_creds = credential.get_credentials()
        self.assertEqual(decrypted_creds['api_key'], 'secret-api-key')
        self.assertEqual(decrypted_creds['access_token'], 'secret-access-token')
        self.assertEqual(decrypted_creds['refresh_token'], 'secret-refresh-token')
        self.assertEqual(decrypted_creds['private_key'], 'secret-private-key')
        self.assertEqual(decrypted_creds['password'], 'secret-password')
        self.assertEqual(decrypted_creds['secret'], 'secret-value')
        self.assertEqual(decrypted_creds['client_secret'], 'secret-client-secret')
        self.assertEqual(decrypted_creds['public_key'], 'public-key-value')
        self.assertEqual(decrypted_creds['description'], 'A description')
    
    def test_non_string_values(self):
        """Test handling of non-string values in credentials."""
        credentials = {
            'api_key': 12345,  # Integer
            'token': True,  # Boolean
            'secret': ['item1', 'item2'],  # List
            'username': 'testuser'  # String
        }
        
        credential = DataSourceCredential.objects.create(
            user=self.user,
            provider=DataSourceCredential.Provider.CUSTOM,
            name='Test Credential',
            credentials=credentials
        )
        
        # Get decrypted credentials
        decrypted_creds = credential.get_credentials()
        
        # Non-string sensitive values should be converted to strings during encryption
        # and converted back when decrypted
        self.assertEqual(decrypted_creds['api_key'], '12345')
        self.assertEqual(decrypted_creds['token'], 'True')
        self.assertEqual(decrypted_creds['secret'], "['item1', 'item2']")
        self.assertEqual(decrypted_creds['username'], 'testuser')