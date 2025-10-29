"""Enhanced configuration management for WebOps CLI with validation and backup."""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Self, List

from .encryption import SecureConfig, EncryptionError


class ConfigError(Exception):
    """Configuration-related errors."""
    pass


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""
    pass


class ConfigBackupError(ConfigError):
    """Raised when backup operations fail."""
    pass


class Config:
    """Manages CLI configuration with encryption, validation, and backup."""

    # Configuration schema for validation
    CONFIG_SCHEMA = {
        'url': {'type': str, 'required': False, 'validator': 'validate_url'},
        'token': {'type': str, 'required': False, 'validator': 'validate_token'},
        'role': {'type': str, 'required': False, 'choices': ['admin', 'developer', 'viewer']},
        'timeout': {'type': int, 'required': False, 'min': 5, 'max': 300, 'default': 30},
        'verify_ssl': {'type': bool, 'required': False, 'default': True},
        'retries': {'type': int, 'required': False, 'min': 0, 'max': 10, 'default': 3},
        'backup_count': {'type': int, 'required': False, 'min': 1, 'max': 50, 'default': 5}
    }

    def __init__(self: Self) -> None:
        """Initialize configuration manager."""
        self.config_dir = Path.home() / ".webops"
        self.config_file = self.config_dir / "config.json"
        self.backup_dir = self.config_dir / "backups"
        self._ensure_directories()
        self.secure_config = SecureConfig()
        self._sensitive_keys = ['token', 'password', 'secret', 'key']

    def _ensure_directories(self: Self) -> None:
        """Create config directories with proper permissions."""
        # Create main config directory
        self.config_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.config_dir, 0o700)
        
        # Create backup directory
        self.backup_dir.mkdir(exist_ok=True)
        os.chmod(self.backup_dir, 0o700)

    def _validate_config_schema(self: Self, config: Dict[str, Any]) -> None:
        """Validate configuration against schema.
        
        Args:
            config: Configuration dictionary to validate.
            
        Raises:
            ConfigValidationError: If validation fails.
        """
        errors = []
        
        for key, schema in self.CONFIG_SCHEMA.items():
            value = config.get(key)
            
            # Check required fields
            if schema['required'] and value is None:
                errors.append(f"Required field '{key}' is missing")
                continue
            
            # Skip validation if value is None and field is not required
            if value is None:
                continue
            
            # Type validation
            if not isinstance(value, schema['type']):
                errors.append(f"Field '{key}' must be of type {schema['type'].__name__}")
                continue
            
            # Choice validation
            if 'choices' in schema and value not in schema['choices']:
                errors.append(f"Field '{key}' must be one of: {', '.join(schema['choices'])}")
            
            # Range validation
            if 'min' in schema and value < schema['min']:
                errors.append(f"Field '{key}' must be >= {schema['min']}")
            if 'max' in schema and value > schema['max']:
                errors.append(f"Field '{key}' must be <= {schema['max']}")
            
            # Custom validation
            if 'validator' in schema:
                validator = getattr(self, schema['validator'], None)
                if validator and not validator(value):
                    errors.append(f"Field '{key}' failed validation")
        
        if errors:
            raise ConfigValidationError(f"Configuration validation failed: {'; '.join(errors)}")

    def validate_url(self: Self, url: str) -> bool:
        """Validate URL format.
        
        Args:
            url: URL to validate.
            
        Returns:
            True if valid, False otherwise.
        """
        if not isinstance(url, str):
            return False
        return url.startswith(('http://', 'https://'))

    def validate_token(self: Self, token: str) -> bool:
        """Validate API token format.
        
        Args:
            token: Token to validate.
            
        Returns:
            True if valid, False otherwise.
        """
        if not isinstance(token, str):
            return False
        # Basic validation - token should be reasonably long
        return len(token) >= 10

    def _create_backup(self: Self) -> None:
        """Create a backup of the current configuration."""
        if not self.config_file.exists():
            return
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = self.backup_dir / f"config_{timestamp}.json"
            
            # Copy current config to backup
            shutil.copy2(self.config_file, backup_file)
            
            # Set restrictive permissions on backup
            os.chmod(backup_file, 0o600)
            
            # Clean up old backups if count exceeds limit
            self._cleanup_old_backups()
            
        except Exception as e:
            raise ConfigBackupError(f"Failed to create backup: {e}")

    def _cleanup_old_backups(self: Self) -> None:
        """Remove old backup files beyond the configured limit."""
        try:
            backup_files = sorted(
                self.backup_dir.glob("config_*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            max_backups = self.get('backup_count', 5)
            for old_backup in backup_files[max_backups:]:
                old_backup.unlink()
                
        except Exception:
            # Don't fail on backup cleanup errors
            pass

    def restore_from_backup(self: Self, backup_timestamp: Optional[str] = None) -> None:
        """Restore configuration from backup.
        
        Args:
            backup_timestamp: Optional backup timestamp to restore from.
                            If None, restores from the most recent backup.
        
        Raises:
            ConfigError: If no backup exists or restoration fails.
        """
        if backup_timestamp:
            backup_file = self.backup_dir / f"config_{backup_timestamp}.json"
        else:
            # Find most recent backup
            backup_files = list(self.backup_dir.glob("config_*.json"))
            if not backup_files:
                raise ConfigError("No backup files found")
            
            backup_file = max(backup_files, key=lambda x: x.stat().st_mtime)
        
        if not backup_file.exists():
            raise ConfigError(f"Backup file not found: {backup_file}")
        
        try:
            # Create backup of current config before restoring
            if self.config_file.exists():
                self._create_backup()
            
            # Restore from backup
            shutil.copy2(backup_file, self.config_file)
            os.chmod(self.config_file, 0o600)
            
        except Exception as e:
            raise ConfigError(f"Failed to restore from backup: {e}")

    def load(self: Self, validate: bool = True) -> Dict[str, Any]:
        """Load configuration from file with optional validation.
        
        Args:
            validate: Whether to validate the configuration schema.
            
        Returns:
            Dictionary containing configuration data.
            
        Raises:
            ConfigError: If loading fails.
        """
        if not self.config_file.exists():
            return {}

        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            # Decrypt sensitive values
            decrypted_config = self.secure_config.decrypt_dict_values(config, self._sensitive_keys)
            
            # Apply defaults for missing optional fields
            for key, schema in self.CONFIG_SCHEMA.items():
                if key not in decrypted_config and 'default' in schema:
                    decrypted_config[key] = schema['default']
            
            # Validate configuration if requested
            if validate:
                self._validate_config_schema(decrypted_config)
            
            return decrypted_config
            
        except (json.JSONDecodeError, IOError) as e:
            # Try to restore from backup if current config is corrupted
            if isinstance(e, json.JSONDecodeError):
                try:
                    self.restore_from_backup()
                    return self.load(validate=validate)
                except ConfigError:
                    pass  # Fall through to original error
            
            raise ConfigError(f"Failed to load configuration: {e}")
        
        except EncryptionError as e:
            raise ConfigError(f"Failed to decrypt configuration: {e}")

    def save(self: Self, config: Dict[str, Any], create_backup: bool = True) -> None:
        """Save configuration to file with encryption and validation.
        
        Args:
            config: Configuration dictionary to save.
            create_backup: Whether to create a backup before saving.
            
        Raises:
            ConfigError: If validation or saving fails.
        """
        # Validate configuration
        self._validate_config_schema(config)
        
        # Create backup before saving
        if create_backup and self.config_file.exists():
            self._create_backup()
        
        try:
            # Encrypt sensitive values
            encrypted_config = self.secure_config.encrypt_dict_values(config, self._sensitive_keys)
            
            # Write to temporary file first, then move to prevent corruption
            temp_file = self.config_file.with_suffix('.tmp')
            try:
                with open(temp_file, 'w') as f:
                    json.dump(encrypted_config, f, indent=2)
                
                # Set restrictive permissions
                os.chmod(temp_file, 0o600)
                
                # Atomic move
                temp_file.replace(self.config_file)
            except Exception:
                # Clean up temp file if something goes wrong
                if temp_file.exists():
                    temp_file.unlink()
                raise
                
        except Exception as e:
            raise ConfigError(f"Failed to save configuration: {e}")

    def get(self: Self, key: str, default: Any = None) -> Any:
        """Get configuration value.
        
        Args:
            key: Configuration key to retrieve.
            default: Default value if key not found.
            
        Returns:
            Configuration value or default.
        """
        try:
            config = self.load(validate=False)
            return config.get(key, default)
        except ConfigError:
            return default

    def set(self: Self, key: str, value: Any, validate: bool = True) -> None:
        """Set configuration value with validation.
        
        Args:
            key: Configuration key to set.
            value: Value to set for the key.
            validate: Whether to validate the configuration after setting.
            
        Raises:
            ConfigError: If validation fails.
        """
        try:
            config = self.load(validate=False)
            config[key] = value
            self.save(config, create_backup=True)
        except Exception as e:
            raise ConfigError(f"Failed to set configuration value: {e}")

    def get_url(self: Self) -> Optional[str]:
        """Get WebOps panel URL.
        
        Returns:
            WebOps panel URL or None if not configured.
        """
        return self.get('url')

    def get_token(self: Self) -> Optional[str]:
        """Get API token.
        
        Returns:
            API authentication token or None if not configured.
        """
        return self.get('token')

    def is_configured(self: Self) -> bool:
        """Check if CLI is configured.
        
        Returns:
            True if both URL and token are configured, False otherwise.
        """
        return bool(self.get_url() and self.get_token())

    def list_backups(self: Self) -> List[str]:
        """List available configuration backups.
        
        Returns:
            List of backup timestamps.
        """
        try:
            backup_files = self.backup_dir.glob("config_*.json")
            timestamps = []
            for backup_file in backup_files:
                # Extract timestamp from filename
                name = backup_file.name
                if name.startswith("config_") and name.endswith(".json"):
                    timestamp = name[7:-5]  # Remove "config_" and ".json"
                    timestamps.append(timestamp)
            return sorted(timestamps, reverse=True)
        except Exception:
            return []

    def validate_configuration(self: Self) -> Dict[str, Any]:
        """Validate current configuration and return validation results.
        
        Returns:
            Dictionary with validation results and suggestions.
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'suggestions': []
        }
        
        try:
            config = self.load()
            
            # Check if basic configuration exists
            if not self.is_configured():
                results['valid'] = False
                results['errors'].append("Missing required configuration (URL and token)")
                results['suggestions'].append("Run: webops config --url <URL> --token <TOKEN>")
                return results
            
            # Validate specific configuration values
            url = self.get_url()
            if url and not self.validate_url(url):
                results['valid'] = False
                results['errors'].append(f"Invalid URL format: {url}")
                results['suggestions'].append("URL must start with http:// or https://")
            
            token = self.get_token()
            if token and not self.validate_token(token):
                results['warnings'].append("API token may be invalid (too short)")
                results['suggestions'].append("Generate a new API token from the control panel")
            
            # Check optional settings
            timeout = self.get('timeout', 30)
            if timeout < 5 or timeout > 300:
                results['warnings'].append(f"Timeout value {timeout} may be inappropriate")
                results['suggestions'].append("Consider setting timeout between 5-300 seconds")
            
            retries = self.get('retries', 3)
            if retries > 10:
                results['warnings'].append(f"High retry count ({retries}) may cause delays")
                results['suggestions'].append("Consider reducing retry count to 3-5")
                
        except ConfigError as e:
            results['valid'] = False
            results['errors'].append(str(e))
            results['suggestions'].append("Try restoring from backup or reconfigure")
        
        return results

    def reset(self: Self) -> None:
        """Reset configuration to default state.
        
        Creates a backup before resetting.
        """
        if self.config_file.exists():
            self._create_backup()
        
        # Remove config file
        if self.config_file.exists():
            self.config_file.unlink()
        
        # Create empty valid configuration with defaults
        config = {}
        for key, schema in self.CONFIG_SCHEMA.items():
            if 'default' in schema:
                config[key] = schema['default']
        
        self.save(config, create_backup=False)
