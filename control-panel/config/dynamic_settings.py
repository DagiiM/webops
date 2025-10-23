"""
Dynamic settings module for WebOps.

This module provides dynamic access to configuration settings that can be
updated at runtime without requiring application restarts. It reads from
the database first, then falls back to environment variables.
"""

from typing import Any, Optional
from django.conf import settings as django_settings
from decouple import config


class DynamicSettings:
    """Dynamic settings provider that reads from database with fallback to environment."""
    
    def __init__(self):
        """Initialize the dynamic settings provider."""
        self._config_service = None
    
    @property
    def config_service(self):
        """Lazy load the configuration service to avoid circular imports."""
        if self._config_service is None:
            try:
                from apps.core.services.config_service import config_service
                self._config_service = config_service
            except ImportError:
                # Fallback if the service is not available (e.g., during migrations)
                self._config_service = None
        return self._config_service
    
    def get_setting(self, key: str, default: Any = None, env_key: Optional[str] = None) -> Any:
        """
        Get a setting value with database-first lookup.
        
        Args:
            key: Configuration key for database lookup
            default: Default value if not found
            env_key: Environment variable key (defaults to key.upper())
            
        Returns:
            Setting value from database, environment, or default
        """
        if env_key is None:
            env_key = key.upper()
        
        # Try database first if config service is available
        if self.config_service:
            try:
                db_value = self.config_service.get_config(key, use_cache=True)
                if db_value is not None and db_value != '':
                    return db_value
            except Exception:
                # If database is not available (e.g., during migrations), continue to fallback
                pass
        
        # Fall back to environment variable
        return config(env_key, default=default)
    
    @property
    def GOOGLE_OAUTH_CLIENT_ID(self) -> str:
        """Get Google OAuth Client ID from database or environment."""
        return self.get_setting('google_oauth_client_id', '', 'GOOGLE_OAUTH_CLIENT_ID')
    
    @property
    def GOOGLE_OAUTH_CLIENT_SECRET(self) -> str:
        """Get Google OAuth Client Secret from database or environment."""
        return self.get_setting('google_oauth_client_secret', '', 'GOOGLE_OAUTH_CLIENT_SECRET')
    
    @property
    def GOOGLE_OAUTH_REDIRECT_URI(self) -> str:
        """Get Google OAuth Redirect URI from database or environment."""
        return self.get_setting(
            'google_oauth_redirect_uri', 
            'http://localhost:8000/auth/login/google/callback/', 
            'GOOGLE_OAUTH_REDIRECT_URI'
        )
    
    @property
    def GITHUB_OAUTH_CLIENT_ID(self) -> str:
        """Get GitHub OAuth Client ID from database or environment."""
        return self.get_setting('github_oauth_client_id', '', 'GITHUB_OAUTH_CLIENT_ID')
    
    @property
    def GITHUB_OAUTH_CLIENT_SECRET(self) -> str:
        """Get GitHub OAuth Client Secret from database or environment."""
        return self.get_setting('github_oauth_client_secret', '', 'GITHUB_OAUTH_CLIENT_SECRET')
    
    @property
    def GITHUB_OAUTH_REDIRECT_URI(self) -> str:
        """Get GitHub OAuth Redirect URI from database or environment."""
        return self.get_setting(
            'github_oauth_redirect_uri', 
            'http://localhost:8000/integrations/github/callback', 
            'GITHUB_OAUTH_REDIRECT_URI'
        )


# Global instance for easy access
dynamic_settings = DynamicSettings()


def get_oauth_setting(provider: str, setting_type: str) -> str:
    """
    Convenience function to get OAuth settings.
    
    Args:
        provider: OAuth provider ('google', 'github')
        setting_type: Setting type ('client_id', 'client_secret', 'redirect_uri')
        
    Returns:
        OAuth setting value
    """
    provider = provider.lower()
    setting_type = setting_type.lower()
    
    if provider == 'google':
        if setting_type == 'client_id':
            return dynamic_settings.GOOGLE_OAUTH_CLIENT_ID
        elif setting_type == 'client_secret':
            return dynamic_settings.GOOGLE_OAUTH_CLIENT_SECRET
        elif setting_type == 'redirect_uri':
            return dynamic_settings.GOOGLE_OAUTH_REDIRECT_URI
    elif provider == 'github':
        if setting_type == 'client_id':
            return dynamic_settings.GITHUB_OAUTH_CLIENT_ID
        elif setting_type == 'client_secret':
            return dynamic_settings.GITHUB_OAUTH_CLIENT_SECRET
        elif setting_type == 'redirect_uri':
            return dynamic_settings.GITHUB_OAUTH_REDIRECT_URI
    
    return ''