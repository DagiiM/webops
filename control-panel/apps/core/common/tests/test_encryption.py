"""
Tests for encryption utilities.
"""

from django.test import TestCase
from unittest.mock import patch
from apps.core.common.utils.encryption import (
    generate_password,
    generate_secret_key,
    encrypt_value,
    decrypt_value
)


class EncryptionUtilsTests(TestCase):
    """Test encryption utility functions."""

    def test_generate_password_default_length(self):
        """Test password generation with default length."""
        password = generate_password()
        
        self.assertEqual(len(password), 32)
        self.assertTrue(any(c.isupper() for c in password))
        self.assertTrue(any(c.islower() for c in password))
        self.assertTrue(any(c.isdigit() for c in password))
        self.assertTrue(any(c in "!@#$%^&*" for c in password))

    def test_generate_password_custom_length(self):
        """Test password generation with custom length."""
        password = generate_password(20)
        
        self.assertEqual(len(password), 20)

    def test_generate_password_minimum_length(self):
        """Test password generation with length below minimum."""
        password = generate_password(5)
        
        self.assertEqual(len(password), 12)  # Should be minimum of 12

    def test_generate_secret_key(self):
        """Test secret key generation."""
        key = generate_secret_key()
        
        self.assertEqual(len(key), 50)
        self.assertTrue(any(c.isupper() for c in key))
        self.assertTrue(any(c.islower() for c in key))
        self.assertTrue(any(c.isdigit() for c in key))
        self.assertTrue(any(c in "!@#$%^&*(-_=+)" for c in key))

    @patch('apps.core.common.utils.encryption.settings')
    def test_encrypt_value(self, mock_settings):
        """Test value encryption."""
        mock_settings.ENCRYPTION_KEY = 'test-key-for-encryption-32-chars'
        
        value = 'test_password'
        encrypted = encrypt_value(value)
        
        self.assertNotEqual(encrypted, value)
        self.assertIsInstance(encrypted, str)

    @patch('apps.core.common.utils.encryption.settings')
    def test_encrypt_decrypt_value(self, mock_settings):
        """Test value encryption and decryption."""
        mock_settings.ENCRYPTION_KEY = 'test-key-for-encryption-32-chars'
        
        original_value = 'test_password'
        encrypted = encrypt_value(original_value)
        decrypted = decrypt_value(encrypted)
        
        self.assertEqual(original_value, decrypted)

    @patch('apps.core.common.utils.encryption.settings')
    def test_encrypt_value_no_key(self, mock_settings):
        """Test encryption without configured key."""
        mock_settings.ENCRYPTION_KEY = None
        
        with self.assertRaises(ValueError) as context:
            encrypt_value('test_value')
        
        self.assertIn('ENCRYPTION_KEY not configured', str(context.exception))

    @patch('apps.core.common.utils.encryption.settings')
    def test_decrypt_value_no_key(self, mock_settings):
        """Test decryption without configured key."""
        mock_settings.ENCRYPTION_KEY = None
        
        with self.assertRaises(ValueError) as context:
            decrypt_value('encrypted_value')
        
        self.assertIn('ENCRYPTION_KEY not configured', str(context.exception))