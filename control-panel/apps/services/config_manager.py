"""
Configuration Management Service for centralized settings.

"Configuration Management"
Architecture: Database-backed configuration with validation and defaults

This module provides:
- Centralized configuration storage
- Type-safe configuration access
- Configuration validation
- Default value handling
- Configuration change tracking
"""

from typing import Dict, Any, Optional, List, Union, Tuple
import logging
from django.core.cache import cache
from django.utils import timezone

from apps.core.common.models import Configuration

logger = logging.getLogger(__name__)


class ConfigurationManager:
    """
    Centralized configuration management service.

    Provides type-safe access to configuration values stored in the database
    with caching, validation, and change tracking.
    """

    # Cache timeout in seconds (5 minutes)
    CACHE_TIMEOUT = 300

    # Configuration schema with defaults and validation
    CONFIG_SCHEMA = {
        # Service monitoring
        'monitoring.metrics_interval': {
            'type': int,
            'default': 300,  # 5 minutes
            'min': 60,
            'max': 3600,
            'description': 'Interval for collecting system metrics (seconds)'
        },
        'monitoring.health_check_interval': {
            'type': int,
            'default': 120,  # 2 minutes
            'min': 30,
            'max': 600,
            'description': 'Interval for service health checks (seconds)'
        },
        'monitoring.alert_threshold_cpu': {
            'type': float,
            'default': 80.0,
            'min': 50.0,
            'max': 95.0,
            'description': 'CPU usage threshold for alerts (%)'
        },
        'monitoring.alert_threshold_memory': {
            'type': float,
            'default': 85.0,
            'min': 50.0,
            'max': 95.0,
            'description': 'Memory usage threshold for alerts (%)'
        },
        'monitoring.alert_threshold_disk': {
            'type': float,
            'default': 90.0,
            'min': 70.0,
            'max': 99.0,
            'description': 'Disk usage threshold for alerts (%)'
        },

        # Restart policies
        'restart_policy.default_max_restarts': {
            'type': int,
            'default': 3,
            'min': 1,
            'max': 10,
            'description': 'Default maximum restart attempts'
        },
        'restart_policy.default_time_window': {
            'type': int,
            'default': 15,
            'min': 5,
            'max': 60,
            'description': 'Default time window for restart attempts (minutes)'
        },
        'restart_policy.default_cooldown': {
            'type': int,
            'default': 5,
            'min': 1,
            'max': 30,
            'description': 'Default cooldown period after max restarts (minutes)'
        },

        # Celery worker management
        'celery.min_workers': {
            'type': int,
            'default': 2,
            'min': 1,
            'max': 10,
            'description': 'Minimum number of Celery workers'
        },
        'celery.auto_restart_workers': {
            'type': bool,
            'default': True,
            'description': 'Automatically restart failed Celery workers'
        },
        'celery.worker_health_check_interval': {
            'type': int,
            'default': 600,  # 10 minutes
            'min': 300,
            'max': 1800,
            'description': 'Interval for Celery worker health checks (seconds)'
        },

        # Background processing
        'background.processor': {
            'type': str,
            'default': 'celery',
            'choices': ['celery', 'memory'],
            'description': 'Active background processor for async tasks (celery or memory)'
        },

        # Data retention
        'data_retention.metrics_days': {
            'type': int,
            'default': 7,
            'min': 1,
            'max': 90,
            'description': 'Days to retain metrics data'
        },
        'data_retention.logs_days': {
            'type': int,
            'default': 30,
            'min': 7,
            'max': 365,
            'description': 'Days to retain log data'
        },
        'data_retention.health_checks_days': {
            'type': int,
            'default': 30,
            'min': 7,
            'max': 90,
            'description': 'Days to retain health check data'
        },

        # System services
        'system.nginx_reload_timeout': {
            'type': int,
            'default': 10,
            'min': 5,
            'max': 60,
            'description': 'Timeout for Nginx reload operations (seconds)'
        },
        'system.service_start_timeout': {
            'type': int,
            'default': 30,
            'min': 10,
            'max': 300,
            'description': 'Timeout for service start operations (seconds)'
        },
    }

    def __init__(self):
        self._cache_prefix = 'config:'

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.

        Args:
            key: Configuration key (e.g., 'monitoring.metrics_interval')
            default: Default value if not found

        Returns:
            Configuration value with proper type
        """
        # Check cache first
        cache_key = f"{self._cache_prefix}{key}"
        cached_value = cache.get(cache_key)
        if cached_value is not None:
            return cached_value

        # Get schema for this key
        schema = self.CONFIG_SCHEMA.get(key)

        # Get from database
        try:
            config = Configuration.objects.get(key=key, is_active=True)
            value = config.get_value()

            # Convert to correct type
            if schema:
                value = self._convert_type(value, schema['type'])
                # Validate against constraints
                value = self._validate_value(value, schema)
        except Configuration.DoesNotExist:
            # Use default from schema or provided default
            if schema:
                value = schema['default']
            else:
                value = default

        # Cache the value
        cache.set(cache_key, value, self.CACHE_TIMEOUT)

        return value

    def set(self, key: str, value: Any, config_type: str = Configuration.ConfigType.SYSTEM) -> bool:
        """
        Set configuration value.

        Args:
            key: Configuration key
            value: Value to set
            config_type: Type of configuration

        Returns:
            True if successful
        """
        try:
            # Validate against schema if exists
            schema = self.CONFIG_SCHEMA.get(key)
            if schema:
                value = self._validate_value(value, schema)

            # Convert to string for storage
            value_str = str(value)

            # Get or create configuration
            config, created = Configuration.objects.get_or_create(
                key=key,
                defaults={
                    'value': '',
                    'config_type': config_type,
                    'is_sensitive': False,
                    'description': schema['description'] if schema else ''
                }
            )

            config.set_value(value_str)
            config.save()

            # Invalidate cache
            cache_key = f"{self._cache_prefix}{key}"
            cache.delete(cache_key)

            logger.info(f"Configuration updated: {key} = {value}")

            return True

        except Exception as e:
            logger.error(f"Failed to set configuration {key}: {e}")
            return False

    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration values.

        Returns:
            Dict of all configuration key-value pairs
        """
        config_dict = {}

        # Load all from schema
        for key, schema in self.CONFIG_SCHEMA.items():
            config_dict[key] = self.get(key)

        return config_dict

    def get_by_category(self, category: str) -> Dict[str, Any]:
        """
        Get all configuration values for a category.

        Args:
            category: Category prefix (e.g., 'monitoring', 'celery')

        Returns:
            Dict of configuration values in this category
        """
        result = {}
        for key in self.CONFIG_SCHEMA.keys():
            if key.startswith(f"{category}."):
                result[key] = self.get(key)
        return result

    def reset_to_default(self, key: str) -> bool:
        """
        Reset configuration to default value.

        Args:
            key: Configuration key

        Returns:
            True if successful
        """
        schema = self.CONFIG_SCHEMA.get(key)
        if not schema:
            return False

        return self.set(key, schema['default'])

    def reset_all_to_defaults(self) -> int:
        """
        Reset all configurations to default values.

        Returns:
            Number of configurations reset
        """
        count = 0
        for key in self.CONFIG_SCHEMA.keys():
            if self.reset_to_default(key):
                count += 1
        return count

    def validate_all(self) -> Dict[str, List[str]]:
        """
        Validate all configuration values.

        Returns:
            Dict of validation errors by key
        """
        errors = {}

        for key in self.CONFIG_SCHEMA.keys():
            value = self.get(key)
            schema = self.CONFIG_SCHEMA[key]

            try:
                self._validate_value(value, schema)
            except ValueError as e:
                errors[key] = [str(e)]

        return errors

    def export_config(self) -> Dict[str, Any]:
        """
        Export all configuration for backup.

        Returns:
            Dict with all configuration data
        """
        return {
            'timestamp': timezone.now().isoformat(),
            'config': self.get_all(),
            'schema': self.CONFIG_SCHEMA
        }

    def import_config(self, config_data: Dict[str, Any]) -> Tuple[int, List[str]]:
        """
        Import configuration from backup.

        Args:
            config_data: Configuration data dict

        Returns:
            Tuple of (count imported, list of errors)
        """
        count = 0
        errors = []

        config = config_data.get('config', {})

        for key, value in config.items():
            try:
                if self.set(key, value):
                    count += 1
            except Exception as e:
                errors.append(f"Failed to import {key}: {e}")

        return count, errors

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _convert_type(self, value: str, target_type: type) -> Any:
        """Convert string value to target type."""
        if target_type == bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        elif target_type == int:
            return int(value)
        elif target_type == float:
            return float(value)
        else:
            return value

    def _validate_value(self, value: Any, schema: Dict[str, Any]) -> Any:
        """Validate value against schema constraints."""
        # Type check
        expected_type = schema['type']
        if not isinstance(value, expected_type):
            try:
                value = expected_type(value)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid type for {value}, expected {expected_type.__name__}")

        # Min/max validation for numeric types
        if expected_type in (int, float):
            if 'min' in schema and value < schema['min']:
                raise ValueError(f"Value {value} is below minimum {schema['min']}")
            if 'max' in schema and value > schema['max']:
                raise ValueError(f"Value {value} is above maximum {schema['max']}")

        # Choices validation for enumerated string settings
        if expected_type == str and 'choices' in schema:
            if value not in schema['choices']:
                raise ValueError(f"Invalid value '{value}'. Allowed: {', '.join(schema['choices'])}")

        return value


# Singleton instance
config_manager = ConfigurationManager()
