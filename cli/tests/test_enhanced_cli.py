"""Tests for enhanced WebOps CLI functionality.

This module tests the improved error handling, progress indicators,
and enhanced admin/system commands.
"""

import os
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch
from typing import Any, Dict

import pytest
from click.testing import CliRunner

from webops_cli.admin import admin, AdminManager
from webops_cli.errors import (
    ErrorHandler,
    WebOpsError,
    ConfigurationError,
    ConnectionError,
    PermissionError,
    ServiceError,
    validate_configuration,
    require_root_privileges
)
from webops_cli.progress import ProgressManager, StatusDisplay
from webops_cli.system import system, SystemMonitor


class TestErrorHandler(unittest.TestCase):
    """Test cases for the ErrorHandler class."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
    
    def test_identify_connection_error(self) -> None:
        """Test identification of connection errors."""
        error_message = "Connection refused to localhost:8000"
        error_type = self.error_handler.identify_error_type(error_message)
        self.assertEqual(error_type, "connection_refused")
    
    def test_identify_authentication_error(self) -> None:
        """Test identification of authentication errors."""
        error_message = "401 Unauthorized: Invalid token"
        error_type = self.error_handler.identify_error_type(error_message)
        self.assertEqual(error_type, "authentication_failed")
    
    def test_identify_permission_error(self) -> None:
        """Test identification of permission errors."""
        error_message = "Permission denied: Access forbidden"
        error_type = self.error_handler.identify_error_type(error_message)
        self.assertEqual(error_type, "permission_denied")
    
    def test_get_suggestions_for_known_error(self) -> None:
        """Test getting suggestions for known error types."""
        error_message = "Connection refused"
        suggestions = self.error_handler.get_suggestions(error_message)
        self.assertIn("Check if the WebOps control panel is running", suggestions)
    
    def test_get_generic_suggestions_for_unknown_error(self) -> None:
        """Test getting generic suggestions for unknown errors."""
        error_message = "Some unknown error occurred"
        suggestions = self.error_handler.get_suggestions(error_message)
        self.assertIn("Check the WebOps documentation for troubleshooting guides", suggestions)
    
    @patch('webops_cli.errors.console')
    def test_display_error_with_suggestions(self, mock_console: Mock) -> None:
        """Test displaying error with suggestions."""
        error = WebOpsError("Test error", ["Suggestion 1", "Suggestion 2"])
        self.error_handler.display_error(error, "Test context")
        mock_console.print.assert_called()
    
    @patch('webops_cli.errors.console')
    def test_display_error_without_suggestions(self, mock_console: Mock) -> None:
        """Test displaying error without suggestions."""
        error = Exception("Test error")
        self.error_handler.display_error(error, show_suggestions=False)
        mock_console.print.assert_called()


class TestWebOpsErrors(unittest.TestCase):
    """Test cases for WebOps custom exceptions."""
    
    def test_webops_error_with_suggestions(self) -> None:
        """Test WebOpsError with suggestions."""
        suggestions = ["Fix this", "Try that"]
        error = WebOpsError("Test message", suggestions)
        self.assertEqual(error.message, "Test message")
        self.assertEqual(error.suggestions, suggestions)
    
    def test_webops_error_without_suggestions(self) -> None:
        """Test WebOpsError without suggestions."""
        error = WebOpsError("Test message")
        self.assertEqual(error.message, "Test message")
        self.assertEqual(error.suggestions, [])
    
    def test_configuration_error_inheritance(self) -> None:
        """Test ConfigurationError inherits from WebOpsError."""
        error = ConfigurationError("Config error")
        self.assertIsInstance(error, WebOpsError)
    
    def test_connection_error_inheritance(self) -> None:
        """Test ConnectionError inherits from WebOpsError."""
        error = ConnectionError("Connection error")
        self.assertIsInstance(error, WebOpsError)


class TestProgressManager(unittest.TestCase):
    """Test cases for the ProgressManager class."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.progress_manager = ProgressManager()
    
    @patch('webops_cli.progress.console')
    def test_spinner_context_manager(self, mock_console: Mock) -> None:
        """Test spinner context manager."""
        mock_status = Mock()
        mock_console.status.return_value = mock_status
        
        with self.progress_manager.spinner("Test message") as status:
            self.assertEqual(status, mock_status)
    
    def test_show_health_check_progress(self) -> None:
        """Test health check progress display."""
        checks = {
            "test_check_1": lambda: True,
            "test_check_2": lambda: False,
            "test_check_3": lambda: True
        }
        
        with patch('webops_cli.progress.time.sleep'):  # Speed up test
            results = self.progress_manager.show_health_check_progress(checks)
        
        self.assertEqual(len(results), 3)
        self.assertTrue(results["test_check_1"])
        self.assertFalse(results["test_check_2"])
        self.assertTrue(results["test_check_3"])
    
    def test_show_health_check_progress_with_exception(self) -> None:
        """Test health check progress with exception in check function."""
        def failing_check() -> bool:
            raise Exception("Check failed")
        
        checks = {
            "failing_check": failing_check,
            "passing_check": lambda: True
        }
        
        with patch('webops_cli.progress.time.sleep'):  # Speed up test
            results = self.progress_manager.show_health_check_progress(checks)
        
        self.assertFalse(results["failing_check"])
        self.assertTrue(results["passing_check"])


class TestStatusDisplay(unittest.TestCase):
    """Test cases for the StatusDisplay class."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.status_display = StatusDisplay()
    
    @patch('webops_cli.progress.console')
    def test_show_service_status(self, mock_console: Mock) -> None:
        """Test service status display."""
        services = {
            "webops-web": {
                "status": "active",
                "uptime": "2 days",
                "memory": "128MB",
                "cpu": "5%"
            },
            "webops-celery": {
                "status": "inactive",
                "uptime": "N/A",
                "memory": "N/A",
                "cpu": "N/A"
            }
        }
        
        self.status_display.show_service_status(services)
        mock_console.print.assert_called()
    
    @patch('webops_cli.progress.console')
    def test_show_deployment_status(self, mock_console: Mock) -> None:
        """Test deployment status display."""
        deployments = {
            "my-app": {
                "status": "running",
                "version": "v1.2.3",
                "url": "https://my-app.example.com",
                "last_updated": "2024-01-15 10:30:00"
            }
        }
        
        self.status_display.show_deployment_status(deployments)
        mock_console.print.assert_called()
    
    @patch('webops_cli.progress.console')
    def test_show_system_metrics(self, mock_console: Mock) -> None:
        """Test system metrics display."""
        metrics = {
            "cpu_percent": 45.2,
            "memory_percent": 67.8,
            "disk_percent": 23.1,
            "load_average": [0.8, 0.9, 1.1],
            "connections": 42
        }
        
        self.status_display.show_system_metrics(metrics)
        mock_console.print.assert_called()


class TestAdminManager(unittest.TestCase):
    """Test cases for the AdminManager class."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.admin_manager = AdminManager()
    
    @patch('os.geteuid')
    def test_check_root_privileges_as_root(self, mock_geteuid: Mock) -> None:
        """Test root privilege check when running as root."""
        mock_geteuid.return_value = 0
        self.assertTrue(self.admin_manager.check_root_privileges())
    
    @patch('os.geteuid')
    def test_check_root_privileges_as_user(self, mock_geteuid: Mock) -> None:
        """Test root privilege check when running as regular user."""
        mock_geteuid.return_value = 1000
        self.assertFalse(self.admin_manager.check_root_privileges())
    
    @patch('subprocess.run')
    def test_run_as_webops_user_success(self, mock_run: Mock) -> None:
        """Test successful command execution as webops user."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Command output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        with patch('webops_cli.admin.show_progress'):
            result = self.admin_manager.run_as_webops_user("echo test")
        
        self.assertEqual(result, mock_result)
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_run_as_webops_user_failure(self, mock_run: Mock) -> None:
        """Test failed command execution as webops user."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "test command")
        
        with patch('webops_cli.admin.show_progress'):
            with self.assertRaises(subprocess.CalledProcessError):
                self.admin_manager.run_as_webops_user("false")


class TestSystemMonitor(unittest.TestCase):
    """Test cases for the SystemMonitor class."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.system_monitor = SystemMonitor()
        # Mock the webops directory to avoid permission issues
        self.system_monitor.webops_dir = Path("/tmp/test_webops")
        self.system_monitor.control_panel_dir = self.system_monitor.webops_dir / "control-panel"
    
    @patch('subprocess.run')
    def test_check_service_status_active(self, mock_run: Mock) -> None:
        """Test service status check for active service."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "active (running) since..."
        mock_run.return_value = mock_result
        
        result = self.system_monitor.check_service_status("test-service")
        self.assertEqual(result["name"], "test-service")
        self.assertTrue(result["active"])
        self.assertEqual(result["status"], "active")
    
    @patch('subprocess.run')
    def test_check_service_status_inactive(self, mock_run: Mock) -> None:
        """Test service status check for inactive service."""
        mock_result = Mock()
        mock_result.returncode = 3  # systemctl returns 3 for inactive services
        mock_result.stdout = "inactive (dead)"
        mock_run.return_value = mock_result
        
        result = self.system_monitor.check_service_status("test-service")
        self.assertEqual(result["name"], "test-service")
        self.assertFalse(result["active"])
        self.assertEqual(result["status"], "inactive")
    
    @patch('subprocess.run')
    def test_check_disk_usage_normal(self, mock_run: Mock) -> None:
        """Test disk usage check with normal usage."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1       100G   50G   45G  53% /"
        mock_run.return_value = mock_result
        
        result = self.system_monitor.check_disk_usage()
        self.assertIn("system", result)
        self.assertEqual(result["system"]["total"], "100G")
        self.assertEqual(result["system"]["used"], "50G")
    
    @patch('subprocess.run')
    def test_check_disk_usage_high(self, mock_run: Mock) -> None:
        """Test disk usage check with high usage."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1       100G   95G    5G  95% /"
        mock_run.return_value = mock_result
        
        result = self.system_monitor.check_disk_usage()
        self.assertIn("system", result)
        self.assertEqual(result["system"]["usage_percent"], "95%")


class TestCLICommands(unittest.TestCase):
    """Test cases for CLI commands."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()
    
    @patch('webops_cli.admin.require_root_privileges')
    @patch('webops_cli.admin.AdminManager')
    def test_admin_status_command(self, mock_admin_manager: Mock, mock_require_root: Mock) -> None:
        """Test admin status command."""
        mock_manager = Mock()
        mock_manager.get_system_status.return_value = {
            "webops-web": {"status": "active", "info": "Running"}
        }
        mock_admin_manager.return_value = mock_manager
        
        result = self.runner.invoke(admin, ['status'])
        self.assertEqual(result.exit_code, 0)
    
    @patch('webops_cli.admin.require_root_privileges')
    @patch('webops_cli.admin.AdminManager')
    def test_admin_run_command(self, mock_admin_manager: Mock, mock_require_root: Mock) -> None:
        """Test admin run command."""
        mock_manager = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Command output"
        mock_result.stderr = ""
        mock_manager.run_as_webops_user.return_value = mock_result
        mock_admin_manager.return_value = mock_manager
        
        result = self.runner.invoke(admin, ['run', 'echo test'])
        self.assertEqual(result.exit_code, 0)
    
    @patch('webops_cli.system.SystemMonitor')
    def test_system_health_command(self, mock_system_monitor: Mock) -> None:
        """Test system health command."""
        mock_monitor = Mock()
        mock_monitor.run_comprehensive_health_check.return_value = {
            "checks": {"Database": True, "Celery": False},
            "health_score": 50.0,
            "status": "warning",
            "timestamp": 1640995200.0
        }
        mock_system_monitor.return_value = mock_monitor
        
        result = self.runner.invoke(system, ['health'])
        self.assertEqual(result.exit_code, 0)


class TestConfigurationValidation(unittest.TestCase):
    """Test cases for configuration validation."""
    
    @patch('os.path.exists')
    def test_validate_configuration_not_configured(self, mock_exists: Mock) -> None:
        """Test configuration validation when not configured."""
        mock_exists.return_value = False
        
        with self.assertRaises(ConfigurationError):
            validate_configuration()
    
    @patch('os.path.exists')
    @patch('builtins.open', create=True)
    def test_validate_configuration_invalid_url(self, mock_open: Mock, mock_exists: Mock) -> None:
        """Test configuration validation with invalid URL."""
        mock_exists.return_value = True
        mock_file = Mock()
        mock_file.read.return_value = '{"url": "invalid-url", "token": "valid-token-12345"}'
        mock_open.return_value.__enter__.return_value = mock_file
        
        with self.assertRaises(ConfigurationError):
            validate_configuration()
    
    @patch('os.path.exists')
    @patch('builtins.open', create=True)
    def test_validate_configuration_invalid_token(self, mock_open: Mock, mock_exists: Mock) -> None:
        """Test configuration validation with invalid token."""
        mock_exists.return_value = True
        mock_file = Mock()
        mock_file.read.return_value = '{"url": "https://webops.example.com", "token": "short"}'
        mock_open.return_value.__enter__.return_value = mock_file
        
        with self.assertRaises(ConfigurationError):
            validate_configuration()
    
    @patch('os.path.exists')
    @patch('builtins.open', create=True)
    def test_validate_configuration_valid(self, mock_open: Mock, mock_exists: Mock) -> None:
        """Test configuration validation with valid configuration."""
        mock_exists.return_value = True
        mock_file = Mock()
        mock_file.read.return_value = '{"url": "https://webops.example.com", "token": "valid-token-12345"}'
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Should not raise any exception
        validate_configuration()


class TestPrivilegeRequirement(unittest.TestCase):
    """Test cases for privilege requirement checks."""
    
    @patch('os.geteuid')
    def test_require_root_privileges_as_root(self, mock_geteuid: Mock) -> None:
        """Test privilege requirement when running as root."""
        mock_geteuid.return_value = 0
        
        # Should not raise any exception
        require_root_privileges("test operation")
    
    @patch('os.geteuid')
    def test_require_root_privileges_as_user(self, mock_geteuid: Mock) -> None:
        """Test privilege requirement when running as regular user."""
        mock_geteuid.return_value = 1000
        
        with self.assertRaises(PermissionError):
            require_root_privileges("test operation")


if __name__ == '__main__':
    unittest.main()