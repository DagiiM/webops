"""
Configuration service for managing dynamic settings in WebOps.

This service provides a centralized way to manage configuration settings
that can be updated at runtime without requiring application restarts.
"""

from typing import Dict, Any, Optional
from django.conf import settings
from django.core.cache import cache
from .models import Configuration


class ConfigurationService:
    """Service for managing dynamic configuration settings."""
    
    # Cache timeout for configuration values (5 minutes)
    CACHE_TIMEOUT = 300
    CACHE_PREFIX = 'webops_config'
    
    # OAuth configuration keys
    GOOGLE_OAUTH_CLIENT_ID = 'google_oauth_client_id'
    GOOGLE_OAUTH_CLIENT_SECRET = 'google_oauth_client_secret'
    GOOGLE_OAUTH_REDIRECT_URI = 'google_oauth_redirect_uri'
    
    GITHUB_OAUTH_CLIENT_ID = 'github_oauth_client_id'
    GITHUB_OAUTH_CLIENT_SECRET = 'github_oauth_client_secret'
    GITHUB_OAUTH_REDIRECT_URI = 'github_oauth_redirect_uri'
    
    def __init__(self):
        """Initialize the configuration service."""
        pass
    
    def get_config(self, key: str, default: Any = None, use_cache: bool = True) -> Any:
        """
        Get a configuration value by key.
        
        Args:
            key: Configuration key
            default: Default value if not found
            use_cache: Whether to use caching
            
        Returns:
            Configuration value or default
        """
        cache_key = f"{self.CACHE_PREFIX}:{key}"
        
        if use_cache:
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
        
        # Try to get from database first
        db_value = Configuration.get_config(key)
        if db_value:
            if use_cache:
                cache.set(cache_key, db_value, self.CACHE_TIMEOUT)
            return db_value
        
        # Fall back to Django settings
        fallback_value = getattr(settings, key.upper(), default)
        if use_cache and fallback_value is not None:
            cache.set(cache_key, fallback_value, self.CACHE_TIMEOUT)
        
        return fallback_value
    
    def set_config(self, key: str, value: Any, config_type: str = Configuration.ConfigType.SYSTEM,
                   is_sensitive: bool = False, description: str = '') -> Configuration:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
            config_type: Type of configuration
            is_sensitive: Whether the value is sensitive
            description: Description of the configuration
            
        Returns:
            Configuration instance
        """
        config = Configuration.set_config(
            key=key,
            value=str(value),
            config_type=config_type,
            is_sensitive=is_sensitive,
            description=description
        )
        
        # Clear cache for this key
        cache_key = f"{self.CACHE_PREFIX}:{key}"
        cache.delete(cache_key)
        
        return config
    
    def delete_config(self, key: str) -> bool:
        """
        Delete a configuration value.
        
        Args:
            key: Configuration key
            
        Returns:
            True if deleted, False if not found
        """
        try:
            config = Configuration.objects.get(key=key)
            config.delete()
            
            # Clear cache
            cache_key = f"{self.CACHE_PREFIX}:{key}"
            cache.delete(cache_key)
            
            return True
        except Configuration.DoesNotExist:
            return False
    
    def clear_cache(self, key: Optional[str] = None) -> None:
        """
        Clear configuration cache.
        
        Args:
            key: Specific key to clear, or None to clear all
        """
        if key:
            cache_key = f"{self.CACHE_PREFIX}:{key}"
            cache.delete(cache_key)
        else:
            # Clear all configuration cache keys
            # This is a simple implementation - in production you might want
            # to use cache versioning or pattern-based deletion
            cache.clear()
    
    def get_oauth_config(self, provider: str) -> Dict[str, str]:
        """
        Get OAuth configuration for a specific provider.
        
        Args:
            provider: OAuth provider ('google', 'github')
            
        Returns:
            Dictionary with OAuth configuration
        """
        if provider.lower() == 'google':
            return {
                'client_id': self.get_config(self.GOOGLE_OAUTH_CLIENT_ID, ''),
                'client_secret': self.get_config(self.GOOGLE_OAUTH_CLIENT_SECRET, ''),
                'redirect_uri': self.get_config(self.GOOGLE_OAUTH_REDIRECT_URI, ''),
            }
        elif provider.lower() == 'github':
            return {
                'client_id': self.get_config(self.GITHUB_OAUTH_CLIENT_ID, ''),
                'client_secret': self.get_config(self.GITHUB_OAUTH_CLIENT_SECRET, ''),
                'redirect_uri': self.get_config(self.GITHUB_OAUTH_REDIRECT_URI, ''),
            }
        else:
            raise ValueError(f"Unsupported OAuth provider: {provider}")
    
    def set_oauth_config(self, provider: str, client_id: str, client_secret: str, 
                        redirect_uri: str = '') -> Dict[str, Configuration]:
        """
        Set OAuth configuration for a specific provider.
        
        Args:
            provider: OAuth provider ('google', 'github')
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: OAuth redirect URI
            
        Returns:
            Dictionary with created Configuration instances
        """
        provider = provider.lower()
        configs = {}
        
        if provider == 'google':
            configs['client_id'] = self.set_config(
                self.GOOGLE_OAUTH_CLIENT_ID,
                client_id,
                Configuration.ConfigType.OAUTH,
                is_sensitive=False,
                description='Google OAuth Client ID'
            )
            configs['client_secret'] = self.set_config(
                self.GOOGLE_OAUTH_CLIENT_SECRET,
                client_secret,
                Configuration.ConfigType.OAUTH,
                is_sensitive=True,
                description='Google OAuth Client Secret'
            )
            if redirect_uri:
                configs['redirect_uri'] = self.set_config(
                    self.GOOGLE_OAUTH_REDIRECT_URI,
                    redirect_uri,
                    Configuration.ConfigType.OAUTH,
                    is_sensitive=False,
                    description='Google OAuth Redirect URI'
                )
        elif provider == 'github':
            configs['client_id'] = self.set_config(
                self.GITHUB_OAUTH_CLIENT_ID,
                client_id,
                Configuration.ConfigType.OAUTH,
                is_sensitive=False,
                description='GitHub OAuth Client ID'
            )
            configs['client_secret'] = self.set_config(
                self.GITHUB_OAUTH_CLIENT_SECRET,
                client_secret,
                Configuration.ConfigType.OAUTH,
                is_sensitive=True,
                description='GitHub OAuth Client Secret'
            )
            if redirect_uri:
                configs['redirect_uri'] = self.set_config(
                    self.GITHUB_OAUTH_REDIRECT_URI,
                    redirect_uri,
                    Configuration.ConfigType.OAUTH,
                    is_sensitive=False,
                    description='GitHub OAuth Redirect URI'
                )
        else:
            raise ValueError(f"Unsupported OAuth provider: {provider}")
        
        return configs
    
    def is_oauth_configured(self, provider: str) -> bool:
        """
        Check if OAuth is configured for a specific provider.
        
        Args:
            provider: OAuth provider ('google', 'github')
            
        Returns:
            True if OAuth is configured, False otherwise
        """
        config = self.get_oauth_config(provider)
        return bool(config.get('client_id') and config.get('client_secret'))
    
    def get_all_configs(self, config_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all configuration values.
        
        Args:
            config_type: Filter by configuration type
            
        Returns:
            Dictionary of all configuration values
        """
        queryset = Configuration.objects.filter(is_active=True)
        if config_type:
            queryset = queryset.filter(config_type=config_type)
        
        configs = {}
        for config in queryset:
            configs[config.key] = config.get_value()
        
        return configs
    
    def validate_oauth_config(self, provider: str, client_id: str, client_secret: str) -> tuple[bool, str]:
        """
        Validate OAuth configuration by testing the credentials.
        
        Args:
            provider: OAuth provider ('google', 'github')
            client_id: OAuth client ID
            client_secret: OAuth client secret
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not client_id or not client_secret:
            return False, "Both client ID and client secret are required"
        
        # Basic validation - in a real implementation, you might want to
        # make a test API call to validate the credentials
        if provider.lower() == 'google':
            # Google client IDs typically end with .googleusercontent.com
            if not client_id.endswith('.googleusercontent.com'):
                return False, "Invalid Google OAuth client ID format"
        elif provider.lower() == 'github':
            # GitHub client IDs are typically alphanumeric
            if not client_id.replace('_', '').replace('-', '').isalnum():
                return False, "Invalid GitHub OAuth client ID format"
        
        return True, "OAuth configuration is valid"


# Global instance for easy access
config_service = ConfigurationService()