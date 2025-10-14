"""Configuration management for WebOps CLI."""

import json
from pathlib import Path
from typing import Optional, Dict, Any, Self


class Config:
    """Manages CLI configuration."""

    def __init__(self: Self) -> None:
        """Initialize configuration manager."""
        self.config_dir = Path.home() / ".webops"
        self.config_file = self.config_dir / "config.json"
        self._ensure_config_dir()

    def _ensure_config_dir(self: Self) -> None:
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load(self: Self) -> Dict[str, Any]:
        """Load configuration from file.
        
        Returns:
            Dictionary containing configuration data.
        """
        if not self.config_file.exists():
            return {}

        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save(self: Self, config: Dict[str, Any]) -> None:
        """Save configuration to file.
        
        Args:
            config: Configuration dictionary to save.
        """
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)

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
