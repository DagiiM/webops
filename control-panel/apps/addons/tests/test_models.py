"""
Tests for addon models.

Tests SystemAddon, Addon, and AddonExecution models including:
- Model creation and validation
- Status transitions
- Health tracking
- Execution history
- Metrics calculation
"""

import time
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.addons.models import SystemAddon, Addon, AddonExecution

User = get_user_model()


class TestSystemAddonModel(TestCase):
    """Tests for SystemAddon model."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_system_addon(self):
        """Test creating a system addon."""
        addon = SystemAddon.objects.create(
            name='postgresql',
            display_name='PostgreSQL',
            version='14.0.0',
            status='not_installed',
            health='unknown',
            category='database',
            description='PostgreSQL database',
            script_path='/path/to/postgresql.sh',
            enabled=True,
            installed_by=self.user,
        )

        self.assertEqual(addon.name, 'postgresql')
        self.assertEqual(addon.display_name, 'PostgreSQL')
        self.assertEqual(addon.status, 'not_installed')
        self.assertEqual(addon.health, 'unknown')
        self.assertTrue(addon.enabled)

    def test_system_addon_unique_name(self):
        """Test that addon names must be unique."""
        SystemAddon.objects.create(
            name='postgresql',
            display_name='PostgreSQL',
            script_path='/path/to/postgresql.sh',
            installed_by=self.user,
        )

        with self.assertRaises(IntegrityError):
            SystemAddon.objects.create(
                name='postgresql',  # Duplicate name
                display_name='PostgreSQL 2',
                script_path='/path/to/postgresql2.sh',
                installed_by=self.user,
            )

    def test_mark_installing(self):
        """Test marking addon as installing."""
        addon = SystemAddon.objects.create(
            name='test-addon',
            display_name='Test Addon',
            script_path='/path/to/test.sh',
            installed_by=self.user,
        )

        self.assertEqual(addon.status, 'not_installed')

        addon.mark_installing(self.user)

        self.assertEqual(addon.status, 'installing')
        self.assertEqual(addon.installed_by, self.user)

    def test_mark_installed(self):
        """Test marking addon as installed."""
        addon = SystemAddon.objects.create(
            name='test-addon',
            display_name='Test Addon',
            script_path='/path/to/test.sh',
            status='installing',
            installed_by=self.user,
        )

        addon.mark_installed(version='14.0.0')

        self.assertEqual(addon.status, 'installed')
        self.assertEqual(addon.version, '14.0.0')
        self.assertIsNotNone(addon.installed_at)
        self.assertEqual(addon.health, 'healthy')

    def test_mark_failed(self):
        """Test marking addon installation as failed."""
        addon = SystemAddon.objects.create(
            name='test-addon',
            display_name='Test Addon',
            script_path='/path/to/test.sh',
            status='installing',
            installed_by=self.user,
        )

        error_msg = 'Installation failed: connection timeout'
        addon.mark_failed(error_msg)

        self.assertEqual(addon.status, 'failed')
        self.assertEqual(addon.last_error, error_msg)
        self.assertEqual(addon.health, 'unhealthy')

    def test_mark_uninstalling(self):
        """Test marking addon as uninstalling."""
        addon = SystemAddon.objects.create(
            name='test-addon',
            display_name='Test Addon',
            script_path='/path/to/test.sh',
            status='installed',
            installed_by=self.user,
        )

        addon.mark_uninstalling()

        self.assertEqual(addon.status, 'uninstalling')

    def test_mark_uninstalled(self):
        """Test marking addon as uninstalled."""
        addon = SystemAddon.objects.create(
            name='test-addon',
            display_name='Test Addon',
            script_path='/path/to/test.sh',
            status='uninstalling',
            installed_by=self.user,
        )

        addon.mark_uninstalled()

        self.assertEqual(addon.status, 'not_installed')
        self.assertEqual(addon.health, 'unknown')

    def test_update_health(self):
        """Test updating addon health status."""
        addon = SystemAddon.objects.create(
            name='test-addon',
            display_name='Test Addon',
            script_path='/path/to/test.sh',
            status='installed',
            installed_by=self.user,
        )

        addon.update_health('degraded')

        self.assertEqual(addon.health, 'degraded')
        self.assertEqual(addon.status, 'degraded')

    def test_increment_metrics_via_mark_installed(self):
        """Test that success count increments on install."""
        addon = SystemAddon.objects.create(
            name='test-addon',
            display_name='Test Addon',
            script_path='/path/to/test.sh',
            status='installing',
            installed_by=self.user,
        )

        initial_count = addon.success_count
        addon.mark_installed(version='1.0.0')

        self.assertEqual(addon.success_count, initial_count + 1)
        self.assertIsNotNone(addon.last_success_at)

    def test_system_addon_str(self):
        """Test string representation."""
        addon = SystemAddon.objects.create(
            name='test-addon',
            display_name='Test Addon',
            script_path='/path/to/test.sh',
            status='installed',
            installed_by=self.user,
        )

        self.assertEqual(str(addon), 'Test Addon (installed)')

    def test_system_addon_config_json_field(self):
        """Test that config stores JSON data correctly."""
        addon = SystemAddon.objects.create(
            name='test-addon',
            display_name='Test Addon',
            script_path='/path/to/test.sh',
            installed_by=self.user,
        )

        config = {
            'port': 5432,
            'max_connections': 100,
            'shared_buffers': '256MB',
        }

        addon.config = config
        addon.save()
        addon.refresh_from_db()

        self.assertEqual(addon.config, config)
        self.assertEqual(addon.config['port'], 5432)


class TestAddonModel(TestCase):
    """Tests for application Addon model."""

    def test_create_application_addon(self):
        """Test creating an application addon."""
        addon = Addon.objects.create(
            name='test-unique-addon-create',
            version='1.0.0',
            description='Test addon for creation',
            enabled=True,
        )

        self.assertEqual(addon.name, 'test-unique-addon-create')
        self.assertEqual(addon.version, '1.0.0')
        self.assertTrue(addon.enabled)

    def test_addon_default_values(self):
        """Test default values for addon fields."""
        addon = Addon.objects.create(
            name='test-unique-addon-defaults',
            version='1.0.0',
        )

        self.assertTrue(addon.enabled)  # Default
        self.assertEqual(addon.success_count, 0)
        self.assertEqual(addon.failure_count, 0)

    def test_addon_unique_name(self):
        """Test that addon names must be unique."""
        Addon.objects.create(name='test-unique-addon-duplicate', version='1.0.0')

        with self.assertRaises(IntegrityError):
            Addon.objects.create(name='test-unique-addon-duplicate', version='2.0.0')

    def test_addon_str(self):
        """Test string representation."""
        addon = Addon.objects.create(
            name='test-unique-addon-str',
            version='1.0.0',
        )

        self.assertEqual(str(addon), 'test-unique-addon-str (1.0.0)')


class TestAddonExecutionModel(TestCase):
    """Tests for AddonExecution model."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.addon = SystemAddon.objects.create(
            name='test-addon',
            display_name='Test Addon',
            script_path='/path/to/test.sh',
            installed_by=self.user,
        )

    def test_create_addon_execution(self):
        """Test creating an addon execution record."""
        execution = AddonExecution.objects.create(
            system_addon=self.addon,
            operation='install',
            status='running',
            requested_by=self.user,
            input_data={'config': {'port': 5432}},
            celery_task_id='task-123',
        )

        self.assertEqual(execution.system_addon, self.addon)
        self.assertEqual(execution.operation, 'install')
        self.assertEqual(execution.status, 'running')
        self.assertEqual(execution.requested_by, self.user)
        self.assertIsNotNone(execution.started_at)
        self.assertIsNone(execution.completed_at)

    def test_execution_mark_success(self):
        """Test marking execution as successful."""
        execution = AddonExecution.objects.create(
            system_addon=self.addon,
            operation='install',
            status='running',
            requested_by=self.user,
        )

        output_data = {'version': '14.0.0', 'port': 5432}
        execution.mark_success(output_data)

        self.assertEqual(execution.status, 'success')
        self.assertIsNotNone(execution.completed_at)
        self.assertEqual(execution.output_data, output_data)
        self.assertIsNotNone(execution.duration_ms)
        self.assertGreaterEqual(execution.duration_ms, 0)  # Can be 0 for very fast operations

    def test_execution_mark_failed(self):
        """Test marking execution as failed."""
        execution = AddonExecution.objects.create(
            system_addon=self.addon,
            operation='install',
            status='running',
            requested_by=self.user,
        )

        error_msg = 'Installation failed: connection timeout'
        execution.mark_failed(error_msg)

        self.assertEqual(execution.status, 'failed')
        self.assertEqual(execution.error_message, error_msg)
        self.assertIsNotNone(execution.completed_at)
        self.assertIsNotNone(execution.duration_ms)

    def test_execution_duration_calculation(self):
        """Test that duration is calculated correctly."""
        execution = AddonExecution.objects.create(
            system_addon=self.addon,
            operation='install',
            status='running',
            requested_by=self.user,
        )

        # Simulate some time passing
        time.sleep(0.1)  # 100ms

        execution.mark_success({'success': True})

        self.assertGreaterEqual(execution.duration_ms, 100)
        self.assertLess(execution.duration_ms, 1000)  # Should be well under 1 second

    def test_execution_str(self):
        """Test string representation."""
        execution = AddonExecution.objects.create(
            system_addon=self.addon,
            operation='install',
            status='success',
            requested_by=self.user,
        )

        expected = f'test-addon - install (success)'
        self.assertEqual(str(execution), expected)

    def test_execution_ordering(self):
        """Test that executions are ordered by started_at descending."""
        # Create multiple executions
        exec1 = AddonExecution.objects.create(
            system_addon=self.addon,
            operation='install',
            status='success',
            requested_by=self.user,
        )

        # Small delay to ensure different timestamps
        time.sleep(0.01)

        exec2 = AddonExecution.objects.create(
            system_addon=self.addon,
            operation='configure',
            status='success',
            requested_by=self.user,
        )

        # Get all executions
        executions = list(AddonExecution.objects.all())

        # Most recent should be first
        self.assertEqual(executions[0], exec2)
        self.assertEqual(executions[1], exec1)

    def test_execution_updates_addon_statistics(self):
        """Test that successful execution updates addon statistics."""
        initial_success_count = self.addon.success_count

        execution = AddonExecution.objects.create(
            system_addon=self.addon,
            operation='install',
            status='running',
            requested_by=self.user,
        )

        execution.mark_success({'version': '1.0.0'})

        # Refresh addon from database
        self.addon.refresh_from_db()

        self.assertEqual(self.addon.success_count, initial_success_count + 1)
        self.assertIsNotNone(self.addon.last_success_at)
        self.assertEqual(self.addon.last_duration_ms, execution.duration_ms)


class TestAddonMetrics(TestCase):
    """Tests for addon metrics and statistics."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.addon = SystemAddon.objects.create(
            name='test-addon',
            display_name='Test Addon',
            script_path='/path/to/test.sh',
            installed_by=self.user,
        )

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        self.addon.success_count = 8
        self.addon.failure_count = 2
        self.addon.save()

        total = self.addon.success_count + self.addon.failure_count
        success_rate = (self.addon.success_count / total * 100) if total > 0 else 0

        self.assertEqual(success_rate, 80.0)

    def test_zero_runs_success_rate(self):
        """Test success rate with zero runs."""
        self.assertEqual(self.addon.success_count, 0)
        self.assertEqual(self.addon.failure_count, 0)

        total = self.addon.success_count + self.addon.failure_count
        success_rate = (self.addon.success_count / total * 100) if total > 0 else 0

        self.assertEqual(success_rate, 0.0)
