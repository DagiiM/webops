"""Configuration management for WebOps CLI."""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any


class Config:
    """Manages CLI configuration."""

    def __init__(self):
        self.config_dir = Path.home() / ".webops"
        self.config_file = self.config_dir / "config.json"
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if not self.config_file.exists():
            return {}

        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save(self, config: Dict[str, Any]) -> None:
        """Save configuration to file."""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        config = self.load()
        return config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        config = self.load()
        config[key] = value
        self.save(config)

    def get_url(self) -> Optional[str]:
        """Get WebOps panel URL."""
        return self.get('url')

    def get_token(self) -> Optional[str]:
        """Get API token."""
        return self.get('token')

    def is_configured(self) -> bool:
        """Check if CLI is configured."""
        return bool(self.get_url() and self.get_token())
