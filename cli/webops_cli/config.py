"""Configuration management for WebOps CLI."""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, Self

from .encryption import SecureConfig, EncryptionError


class Config:
    """Manages CLI configuration with encryption for sensitive data."""

    def __init__(self: Self) -> None:
        """Initialize configuration manager."""
        self.config_dir = Path.home() / ".webops"
        self.config_file = self.config_dir / "config.json"
        self._ensure_config_dir()
        self.secure_config = SecureConfig()
        self._sensitive_keys = ['token', 'password', 'secret', 'key']

    def _ensure_config_dir(self: Self) -> None:
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions
        os.chmod(self.config_dir, 0o700)

    def load(self: Self) -> Dict[str, Any]:
        """Load configuration from file.
        
        Returns:
            Dictionary containing configuration data.
        """
        if not self.config_file.exists():
            return {}

        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            # Decrypt sensitive values
            return self.secure_config.decrypt_dict_values(config, self._sensitive_keys)
        except (json.JSONDecodeError, IOError, EncryptionError):
            return {}

    def save(self: Self, config: Dict[str, Any]) -> None:
        """Save configuration to file with encryption for sensitive data.
        
        Args:
            config: Configuration dictionary to save.
        """
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

    def get(self: Self, key: str, default: Any = None) -> Any:
        """Get configuration value.
        
        Args:
            key: Configuration key to retrieve.
            default: Default value if key not found.
            
        Returns:
            Configuration value or default.
        """
        config = self.load()
        return config.get(key, default)

    def set(self: Self, key: str, value: Any) -> None:
        """Set configuration value.
        
        Args:
            key: Configuration key to set.
            value: Value to set for the key.
        """
        config = self.load()
        config[key] = value
        self.save(config)

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
