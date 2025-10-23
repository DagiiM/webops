"""Comprehensive test suite for WebOps CLI security features.

This module tests all security-related functionality including validation,
encryption, RBAC, and logging to ensure compliance with SOC 2 and ISO 27001.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from webops_cli.validators import InputValidator, ValidationError
from webops_cli.encryption import SecureConfig, EncryptionError, PasswordManager
from webops_cli.security_logging import SecurityLogger, SecurityEventType, get_security_logger
from webops_cli.enhanced_api import EnhancedWebOpsAPIClient, RBACError, Role, Permission
from webops_cli.config import Config


class TestInputValidation(unittest.TestCase):
    """Test input validation and sanitization."""
    
    def test_validate_deployment_name_valid(self):
        """Test valid deployment names."""
        valid_names = [
            "myapp",
            "my-app",
            "app123",
            "test-app-123",
            "a"  # Minimum length
        ]
        
        for name in valid_names:
            with self.subTest(name=name):
                result = InputValidator.validate_deployment_name(name)
                self.assertEqual(result, name)
    
    def test_validate_deployment_name_invalid(self):
        """Test invalid deployment names."""
        invalid_names = [
            "",  # Empty
            "a" * 65,  # Too long
            "-app",  # Starts with hyphen
            "app-",  # Ends with hyphen
            "app--name",  # Double hyphen
            "app_name",  # Underscore
            "app.name",  # Dot
            "app name",  # Space
            "www",  # Reserved
            "admin",  # Reserved
            "root",  # Reserved
        ]
        
        for name in invalid_names:
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    InputValidator.validate_deployment_name(name)
    
    def test_validate_git_url_valid(self):
        """Test valid Git URLs."""
        valid_urls = [
            "https://github.com/user/repo.git",
            "http://github.com/user/repo.git",
            "git@github.com:user/repo.git",
            "ssh://git@github.com/user/repo.git",
        ]
        
        for url in valid_urls:
            with self.subTest(url=url):
                result = InputValidator.validate_git_url(url)
                self.assertEqual(result, url)
    
    def test_validate_git_url_invalid(self):
        """Test invalid Git URLs."""
        invalid_urls = [
            "",  # Empty
            "not-a-url",
            "file:///etc/passwd",  # Local file
            "ftp://example.com/repo.git",  # FTP protocol
            "ldap://example.com",  # LDAP protocol
            "../../../etc/passwd",  # Directory traversal
            "a" * 2049,  # Too long
        ]
        
        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValidationError):
                    InputValidator.validate_git_url(url)
    
    def test_validate_api_token_valid(self):
        """Test valid API tokens."""
        valid_tokens = [
            "a" * 10,  # Minimum length
            "abcd1234efgh5678",
            "token-with-hyphens_and_underscores",
            "a" * 1024,  # Maximum length
        ]
        
        for token in valid_tokens:
            with self.subTest(token=token):
                result = InputValidator.validate_api_token(token)
                self.assertEqual(result, token)
    
    def test_validate_api_token_invalid(self):
        """Test invalid API tokens."""
        invalid_tokens = [
            "",  # Empty
            "a" * 9,  # Too short
            "a" * 1025,  # Too long
            "token with spaces",
            "token@with#special",
        ]
        
        for token in invalid_tokens:
            with self.subTest(token=token):
                with self.assertRaises(ValidationError):
                    InputValidator.validate_api_token(token)
    
    def test_sanitize_custom_env_vars(self):
        """Test environment variable sanitization."""
        valid_env_vars = [
            "KEY=value",
            "API_KEY=secret123",
            "DB_HOST=localhost",
            "DEBUG=True"
        ]
        
        result = InputValidator.sanitize_custom_env_vars(valid_env_vars)
        expected = {
            "KEY": "value",
            "API_KEY": "secret123",
            "DB_HOST": "localhost",
            "DEBUG": "True"
        }
        self.assertEqual(result, expected)
    
    def test_sanitize_custom_env_vars_invalid(self):
        """Test invalid environment variable format."""
        invalid_env_vars = [
            "INVALID_NO_EQUALS",
            "KEY=",
            "=VALUE",
            "KEY VALUE",
            "1INVALID=value"  # Starts with number
        ]
        
        for env_var in invalid_env_vars:
            with self.subTest(env_var=env_var):
                with self.assertRaises(ValidationError):
                    InputValidator.sanitize_custom_env_vars([env_var])


class TestEncryption(unittest.TestCase):
    """Test encryption and decryption functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.encryption_key_file = Path(self.temp_dir) / ".encryption_key"
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_encrypt_decrypt_value(self):
        """Test basic encryption and decryption."""
        secure_config = SecureConfig()
        original_value = "sensitive_token_123"
        
        # Encrypt
        encrypted = secure_config.encrypt_value(original_value)
        self.assertNotEqual(encrypted, original_value)
        self.assertIsInstance(encrypted, str)
        
        # Decrypt
        decrypted = secure_config.decrypt_value(encrypted)
        self.assertEqual(decrypted, original_value)
    
    def test_encrypt_dict_values(self):
        """Test encrypting dictionary values."""
        secure_config = SecureConfig()
        data = {
            "url": "https://example.com",
            "token": "secret_token",
            "password": "secret_password",
            "normal_value": "not_secret"
        }
        
        encrypted = secure_config.encrypt_dict_values(data, ["token", "password"])
        
        # Check that sensitive values are encrypted
        self.assertNotEqual(encrypted["token"], "secret_token")
        self.assertNotEqual(encrypted["password"], "secret_password")
        
        # Check that non-sensitive values are not encrypted
        self.assertEqual(encrypted["url"], "https://example.com")
        self.assertEqual(encrypted["normal_value"], "not_secret")
    
    def test_decrypt_dict_values(self):
        """Test decrypting dictionary values."""
        secure_config = SecureConfig()
        data = {
            "url": "https://example.com",
            "token": "secret_token",
            "password": "secret_password"
        }
        
        # Encrypt first
        encrypted = secure_config.encrypt_dict_values(data, ["token", "password"])
        
        # Then decrypt
        decrypted = secure_config.decrypt_dict_values(encrypted, ["token", "password"])
        
        # Check that all values are restored
        self.assertEqual(decrypted["url"], "https://example.com")
        self.assertEqual(decrypted["token"], "secret_token")
        self.assertEqual(decrypted["password"], "secret_password")
    
    def test_is_encrypted(self):
        """Test encryption detection."""
        secure_config = SecureConfig()
        
        # Unencrypted value
        self.assertFalse(secure_config.is_encrypted("plain_text"))
        
        # Encrypted value
        encrypted = secure_config.encrypt_value("secret")
        self.assertTrue(secure_config.is_encrypted(encrypted))
    
    def test_password_generation(self):
        """Test secure password generation."""
        password = PasswordManager.generate_secure_password(16)
        
        # Check length
        self.assertEqual(len(password), 16)
        
        # Check for required character types
        self.assertTrue(any(c.isupper() for c in password))
        self.assertTrue(any(c.islower() for c in password))
        self.assertTrue(any(c.isdigit() for c in password))
        self.assertTrue(any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password))
    
    def test_password_validation(self):
        """Test password strength validation."""
        # Strong password
        strong_password = "StrongP@ssw0rd123"
        result = PasswordManager.validate_password_strength(strong_password)
        self.assertTrue(result['valid'])
        self.assertEqual(result['score'], 5)
        
        # Weak password
        weak_password = "weak"
        result = PasswordManager.validate_password_strength(weak_password)
        self.assertFalse(result['valid'])
        self.assertLess(result['score'], 5)
        self.assertTrue(len(result['issues']) > 0)


class TestRBAC(unittest.TestCase):
    """Test role-based access control."""
    
    def test_role_validation(self):
        """Test role validation."""
        # Valid roles
        for role in Role.all_roles():
            self.assertTrue(Role.is_valid_role(role))
        
        # Invalid role
        self.assertFalse(Role.is_valid_role("invalid_role"))
    
    def test_rbac_manager_admin(self):
        """Test RBAC manager for admin role."""
        rbac = RBACManager(Role.ADMIN)
        
        # Admin should have all permissions
        for permission in Permission.all_permissions():
            self.assertTrue(rbac.check_permission(permission))
    
    def test_rbac_manager_developer(self):
        """Test RBAC manager for developer role."""
        rbac = RBACManager(Role.DEVELOPER)
        
        # Developer should have deployment permissions
        self.assertTrue(rbac.check_permission(Permission.DEPLOYMENT_CREATE))
        self.assertTrue(rbac.check_permission(Permission.DEPLOYMENT_READ))
        self.assertTrue(rbac.check_permission(Permission.DEPLOYMENT_UPDATE))
        self.assertTrue(rbac.check_permission(Permission.DEPLOYMENT_DELETE))
        
        # Developer should not have system admin permissions
        self.assertFalse(rbac.check_permission(Permission.SYSTEM_ADMIN))
    
    def test_rbac_manager_viewer(self):
        """Test RBAC manager for viewer role."""
        rbac = RBACManager(Role.VIEWER)
        
        # Viewer should have read permissions
        self.assertTrue(rbac.check_permission(Permission.DEPLOYMENT_READ))
        self.assertTrue(rbac.check_permission(Permission.DATABASE_READ))
        
        # Viewer should not have write permissions
        self.assertFalse(rbac.check_permission(Permission.DEPLOYMENT_CREATE))
        self.assertFalse(rbac.check_permission(Permission.DEPLOYMENT_DELETE))
    
    def test_require_permission_success(self):
        """Test successful permission requirement."""
        rbac = RBACManager(Role.DEVELOPER)
        
        # Should not raise exception for allowed permission
        rbac.require_permission(Permission.DEPLOYMENT_READ)
    
    def test_require_permission_failure(self):
        """Test failed permission requirement."""
        rbac = RBACManager(Role.VIEWER)
        
        # Should raise exception for denied permission
        with self.assertRaises(RBACError):
            rbac.require_permission(Permission.DEPLOYMENT_CREATE)
    
    def test_invalid_role(self):
        """Test invalid role initialization."""
        with self.assertRaises(RBACError):
            RBACManager("invalid_role")


class TestSecurityLogging(unittest.TestCase):
    """Test security logging functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.logger = SecurityLogger(Path(self.temp_dir))
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_log_authentication(self):
        """Test authentication logging."""
        self.logger.log_authentication(
            user="testuser",
            success=True,
            method="token"
        )
        
        # Check that log file was created
        self.assertTrue(self.logger.security_log_file.exists())
        self.assertTrue(self.logger.audit_log_file.exists())
        
        # Check log content
        with open(self.logger.security_log_file, 'r') as f:
            log_entry = json.loads(f.read().strip())
        
        self.assertEqual(log_entry['event_type'], 'authentication')
        self.assertEqual(log_entry['user'], 'testuser')
        self.assertEqual(log_entry['result'], 'SUCCESS')
        self.assertEqual(log_entry['details']['method'], 'token')
    
    def test_log_authorization(self):
        """Test authorization logging."""
        self.logger.log_authorization(
            user="testuser",
            action="read",
            resource="deployment:myapp",
            granted=True
        )
        
        # Check log content
        with open(self.logger.security_log_file, 'r') as f:
            log_entry = json.loads(f.read().strip())
        
        self.assertEqual(log_entry['event_type'], 'authorization')
        self.assertEqual(log_entry['user'], 'testuser')
        self.assertEqual(log_entry['action'], 'read')
        self.assertEqual(log_entry['resource'], 'deployment:myapp')
        self.assertEqual(log_entry['result'], 'GRANTED')
    
    def test_log_configuration_change(self):
        """Test configuration change logging."""
        self.logger.log_configuration_change(
            user="testuser",
            setting="token",
            old_value="old_token",
            new_value="new_token"
        )
        
        # Check log content
        with open(self.logger.security_log_file, 'r') as f:
            log_entry = json.loads(f.read().strip())
        
        self.assertEqual(log_entry['event_type'], 'configuration_change')
        self.assertEqual(log_entry['user'], 'testuser')
        self.assertEqual(log_entry['details']['setting'], 'token')
        # Sensitive values should be masked
        self.assertEqual(log_entry['details']['old_value'], '***MASKED***')
        self.assertEqual(log_entry['details']['new_value'], '***MASKED***')
    
    def test_log_security_violation(self):
        """Test security violation logging."""
        self.logger.log_security_violation(
            user="testuser",
            violation_type="invalid_input",
            description="SQL injection attempt detected",
            severity="HIGH"
        )
        
        # Check log content
        with open(self.logger.security_log_file, 'r') as f:
            log_entry = json.loads(f.read().strip())
        
        self.assertEqual(log_entry['event_type'], 'security_violation')
        self.assertEqual(log_entry['user'], 'testuser')
        self.assertEqual(log_entry['details']['violation_type'], 'invalid_input')
        self.assertEqual(log_entry['details']['description'], 'SQL injection attempt detected')
        self.assertEqual(log_entry['severity'], 'HIGH')
    
    def test_log_file_permissions(self):
        """Test that log files have correct permissions."""
        self.logger.log_authentication(
            user="testuser",
            success=True
        )
        
        # Check file permissions (should be 600)
        stat_info = self.logger.security_log_file.stat()
        file_mode = oct(stat_info.st_mode)[-3:]
        self.assertEqual(file_mode, "600")


class TestEnhancedAPIClient(unittest.TestCase):
    """Test enhanced API client security features."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_url = "https://api.example.com"
        self.token = "test_token_12345"
        self.client = EnhancedWebOpsAPIClient(
            base_url=self.base_url,
            token=self.token,
            user_role=Role.DEVELOPER
        )
    
    def tearDown(self):
        """Clean up test environment."""
        self.client.close()
    
    @patch('webops_cli.enhanced_api.requests.Session.request')
    def test_rbac_permission_check(self, mock_request):
        """Test RBAC permission checking."""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        # Should succeed for allowed permission
        self.client.get_status()
        
        # Verify request was made
        mock_request.assert_called_once()
    
    def test_rbac_permission_denied(self):
        """Test RBAC permission denial."""
        # Create client with viewer role (limited permissions)
        client = EnhancedWebOpsAPIClient(
            base_url=self.base_url,
            token=self.token,
            user_role=Role.VIEWER
        )
        
        try:
            # Should fail for admin-only permission
            with self.assertRaises(RBACError):
                client._request('POST', '/api/admin/', Permission.SYSTEM_ADMIN)
        finally:
            client.close()
    
    def test_input_validation_in_api_calls(self):
        """Test that API calls validate inputs."""
        with self.assertRaises(ValidationError):
            self.client.get_deployment("")  # Empty name should fail
        
        with self.assertRaises(ValidationError):
            self.client.get_deployment("invalid name with spaces")  # Invalid format
    
    @patch('webops_cli.enhanced_api.requests.Session.request')
    def test_security_logging_in_api_calls(self, mock_request):
        """Test that API calls are logged."""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"id": 1, "name": "test"}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        # Make API call
        self.client.get_deployment("test-app")
        
        # Verify that logging occurred
        mock_request.assert_called_once()
        
        # Check that the request was made with correct parameters
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'GET')
        self.assertIn('/api/deployments/test-app/', args[1])


class TestConfigSecurity(unittest.TestCase):
    """Test configuration security features."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / ".webops"
        self.config_file = self.config_dir / "config.json"
        
        # Patch config directory
        with patch('webops_cli.config.Path.home') as mock_home:
            mock_home.return_value = Path(self.temp_dir)
            self.config = Config()
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_encrypted_config_storage(self):
        """Test that sensitive config values are encrypted."""
        # Set sensitive values
        self.config.set('url', 'https://example.com')
        self.config.set('token', 'secret_token_123')
        
        # Load raw config file
        with open(self.config_file, 'r') as f:
            raw_config = json.load(f)
        
        # Check that token is encrypted
        self.assertNotEqual(raw_config['token'], 'secret_token_123')
        self.assertTrue(len(raw_config['token']) > len('secret_token_123'))
        
        # Check that URL is not encrypted
        self.assertEqual(raw_config['url'], 'https://example.com')
    
    def test_decrypted_config_loading(self):
        """Test that encrypted values are decrypted when loading."""
        # Set sensitive values
        self.config.set('url', 'https://example.com')
        self.config.set('token', 'secret_token_123')
        
        # Create new config instance (simulates restart)
        with patch('webops_cli.config.Path.home') as mock_home:
            mock_home.return_value = Path(self.temp_dir)
            new_config = Config()
        
        # Check that values are properly decrypted
        self.assertEqual(new_config.get('url'), 'https://example.com')
        self.assertEqual(new_config.get('token'), 'secret_token_123')
    
    def test_config_file_permissions(self):
        """Test that config files have correct permissions."""
        # Set a value to create the file
        self.config.set('test', 'value')
        
        # Check file permissions (should be 600)
        stat_info = self.config_file.stat()
        file_mode = oct(stat_info.st_mode)[-3:]
        self.assertEqual(file_mode, "600")
        
        # Check directory permissions (should be 700)
        stat_info = self.config_dir.stat()
        dir_mode = oct(stat_info.st_mode)[-3:]
        self.assertEqual(dir_mode, "700")


class TestSecurityIntegration(unittest.TestCase):
    """Integration tests for security features."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Patch home directory
        self.home_patcher = patch('webops_cli.config.Path.home')
        mock_home = self.home_patcher.start()
        mock_home.return_value = Path(self.temp_dir)
        
        # Patch security logger directory
        self.logger_patcher = patch('webops_cli.security_logging.Path.home')
        mock_logger_home = self.logger_patcher.start()
        mock_logger_home.return_value = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        self.home_patcher.stop()
        self.logger_patcher.stop()
        
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_end_to_end_security_flow(self):
        """Test complete security flow from config to API call."""
        # 1. Configure CLI with encrypted storage
        config = Config()
        config.set('url', 'https://api.example.com')
        config.set('token', 'secret_token_123')
        config.set('role', 'developer')
        
        # 2. Create enhanced API client
        client = EnhancedWebOpsAPIClient(
            base_url=config.get_url(),
            token=config.get_token(),
            user_role=config.get('role')
        )
        
        try:
            # 3. Verify RBAC setup
            self.assertTrue(client.rbac.check_permission(Permission.DEPLOYMENT_READ))
            self.assertFalse(client.rbac.check_permission(Permission.SYSTEM_ADMIN))
            
            # 4. Verify security logging is active
            security_logger = get_security_logger()
            self.assertTrue(security_logger.security_log_file.parent.exists())
            
        finally:
            client.close()
    
    def test_security_violation_logging(self):
        """Test that security violations are properly logged."""
        security_logger = get_security_logger()
        
        # Simulate security violation
        security_logger.log_security_violation(
            user="testuser",
            violation_type="invalid_input",
            description="Malicious input detected",
            severity="HIGH"
        )
        
        # Verify log entry
        with open(security_logger.security_log_file, 'r') as f:
            log_entry = json.loads(f.read().strip())
        
        self.assertEqual(log_entry['event_type'], 'security_violation')
        self.assertEqual(log_entry['severity'], 'HIGH')
        self.assertEqual(log_entry['details']['violation_type'], 'invalid_input')


if __name__ == '__main__':
    unittest.main()