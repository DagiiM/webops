"""Input validation and sanitization for WebOps CLI.

This module provides comprehensive validation functions for all CLI inputs
to prevent injection attacks and ensure data integrity.
"""

import re
import ipaddress
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class InputValidator:
    """Validates and sanitizes user inputs for security."""
    
    # Security patterns for validation
    PATTERNS = {
        'deployment_name': re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,62}[a-zA-Z0-9])?$'),
        'env_var_key': re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$'),
        'env_var_value': re.compile(r'^[^\x00-\x08\x0B\x0C\x0E-\x1F\x7F]*$'),
        'git_branch': re.compile(r'^[a-zA-Z0-9_\-\/\.]+$'),
        'domain_name': re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'),
        'safe_string': re.compile(r'^[a-zA-Z0-9\s\-_\.@]+$'),
        'api_token': re.compile(r'^[a-zA-Z0-9\-_\.]+$'),
    }
    
    # Maximum lengths for various inputs
    MAX_LENGTHS = {
        'deployment_name': 64,
        'env_var_key': 255,
        'env_var_value': 8192,
        'git_branch': 255,
        'domain_name': 253,
        'url': 2048,
        'api_token': 1024,
    }
    
    @classmethod
    def validate_deployment_name(cls, name: str) -> str:
        """Validate deployment name.
        
        Args:
            name: Deployment name to validate
            
        Returns:
            Sanitized deployment name
            
        Raises:
            ValidationError: If name is invalid
        """
        if not name:
            raise ValidationError("Deployment name cannot be empty")
        
        if len(name) > cls.MAX_LENGTHS['deployment_name']:
            raise ValidationError(f"Deployment name cannot exceed {cls.MAX_LENGTHS['deployment_name']} characters")
        
        if not cls.PATTERNS['deployment_name'].match(name):
            raise ValidationError(
                "Deployment name must contain only alphanumeric characters and hyphens, "
                "cannot start or end with a hyphen, and must be 3-64 characters long"
            )
        
        # Additional security checks
        if name.lower() in ['www', 'mail', 'ftp', 'admin', 'root', 'api']:
            raise ValidationError(f"Deployment name '{name}' is reserved and cannot be used")
        
        return name
    
    @classmethod
    def validate_git_url(cls, url: str) -> str:
        """Validate Git repository URL.
        
        Args:
            url: Git repository URL to validate
            
        Returns:
            Sanitized URL
            
        Raises:
            ValidationError: If URL is invalid
        """
        if not url:
            raise ValidationError("Repository URL cannot be empty")
        
        if len(url) > cls.MAX_LENGTHS['url']:
            raise ValidationError(f"URL cannot exceed {cls.MAX_LENGTHS['url']} characters")
        
        # Parse URL to validate structure
        try:
            parsed = urlparse(url)
            
            # Check for allowed schemes
            if parsed.scheme not in ['http', 'https', 'git', 'ssh']:
                raise ValidationError("URL must use http, https, git, or ssh protocol")
            
            # Check for dangerous patterns
            dangerous_patterns = [
                r'\.\./',  # Directory traversal
                r'file://',  # Local file access
                r'ftp://',  # FTP protocol
                r'ldap://',  # LDAP protocol
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    raise ValidationError(f"URL contains potentially dangerous pattern: {pattern}")
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Invalid URL format: {e}")
        
        return url.strip()
    
    @classmethod
    def validate_git_branch(cls, branch: str) -> str:
        """Validate Git branch name.
        
        Args:
            branch: Git branch name to validate
            
        Returns:
            Sanitized branch name
            
        Raises:
            ValidationError: If branch name is invalid
        """
        if not branch:
            return 'main'  # Default branch
        
        if len(branch) > cls.MAX_LENGTHS['git_branch']:
            raise ValidationError(f"Branch name cannot exceed {cls.MAX_LENGTHS['git_branch']} characters")
        
        if not cls.PATTERNS['git_branch'].match(branch):
            raise ValidationError(
                "Branch name must contain only alphanumeric characters, "
                "underscores, hyphens, forward slashes, and dots"
            )
        
        # Prevent branch name injection
        if branch.startswith('-') or branch.endswith('/'):
            raise ValidationError("Branch name cannot start with hyphen or end with slash")
        
        return branch
    
    @classmethod
    def validate_domain_name(cls, domain: str) -> str:
        """Validate domain name.
        
        Args:
            domain: Domain name to validate
            
        Returns:
            Sanitized domain name
            
        Raises:
            ValidationError: If domain name is invalid
        """
        if not domain:
            return ''  # Domain is optional
        
        domain = domain.lower().strip()
        
        if len(domain) > cls.MAX_LENGTHS['domain_name']:
            raise ValidationError(f"Domain name cannot exceed {cls.MAX_LENGTHS['domain_name']} characters")
        
        if not cls.PATTERNS['domain_name'].match(domain):
            raise ValidationError("Invalid domain name format")
        
        # Additional validation
        try:
            # Validate IP address format if it's an IP
            ipaddress.ip_address(domain)
            # If it's a valid IP, that's fine for internal networks
        except ValueError:
            # Not an IP, so it should be a domain name
            if domain.startswith('.') or domain.endswith('.'):
                raise ValidationError("Domain name cannot start or end with a dot")
            
            if '..' in domain:
                raise ValidationError("Domain name cannot contain consecutive dots")
        
        return domain
    
    @classmethod
    def validate_env_var_key(cls, key: str) -> str:
        """Validate environment variable key.
        
        Args:
            key: Environment variable key to validate
            
        Returns:
            Sanitized key
            
        Raises:
            ValidationError: If key is invalid
        """
        if not key:
            raise ValidationError("Environment variable key cannot be empty")
        
        if len(key) > cls.MAX_LENGTHS['env_var_key']:
            raise ValidationError(f"Environment variable key cannot exceed {cls.MAX_LENGTHS['env_var_key']} characters")
        
        if not cls.PATTERNS['env_var_key'].match(key):
            raise ValidationError(
                "Environment variable key must start with a letter or underscore, "
                "and contain only alphanumeric characters and underscores"
            )
        
        return key
    
    @classmethod
    def validate_env_var_value(cls, value: str) -> str:
        """Validate environment variable value.
        
        Args:
            value: Environment variable value to validate
            
        Returns:
            Sanitized value
            
        Raises:
            ValidationError: If value is invalid
        """
        if value is None:
            return ''
        
        if len(value) > cls.MAX_LENGTHS['env_var_value']:
            raise ValidationError(f"Environment variable value cannot exceed {cls.MAX_LENGTHS['env_var_value']} characters")
        
        # Check for control characters (except common ones)
        if not cls.PATTERNS['env_var_value'].match(value):
            raise ValidationError("Environment variable value contains invalid characters")
        
        return value
    
    @classmethod
    def validate_api_token(cls, token: str) -> str:
        """Validate API token.
        
        Args:
            token: API token to validate
            
        Returns:
            Sanitized token
            
        Raises:
            ValidationError: If token is invalid
        """
        if not token:
            raise ValidationError("API token cannot be empty")
        
        if len(token) < 10:
            raise ValidationError("API token appears to be too short")
        
        if len(token) > cls.MAX_LENGTHS['api_token']:
            raise ValidationError(f"API token cannot exceed {cls.MAX_LENGTHS['api_token']} characters")
        
        if not cls.PATTERNS['api_token'].match(token):
            raise ValidationError("API token contains invalid characters")
        
        return token.strip()
    
    @classmethod
    def validate_url(cls, url: str) -> str:
        """Validate WebOps panel URL.
        
        Args:
            url: URL to validate
            
        Returns:
            Sanitized URL
            
        Raises:
            ValidationError: If URL is invalid
        """
        if not url:
            raise ValidationError("URL cannot be empty")
        
        if len(url) > cls.MAX_LENGTHS['url']:
            raise ValidationError(f"URL cannot exceed {cls.MAX_LENGTHS['url']} characters")
        
        url = url.strip()
        
        # Parse URL to validate structure
        try:
            parsed = urlparse(url)
            
            # Check for allowed schemes
            if parsed.scheme not in ['http', 'https']:
                raise ValidationError("URL must use http or https protocol")
            
            # Check for hostname
            if not parsed.hostname:
                raise ValidationError("URL must include a valid hostname")
            
            # Validate hostname
            if parsed.hostname.startswith('.') or parsed.hostname.endswith('.'):
                raise ValidationError("Invalid hostname in URL")
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Invalid URL format: {e}")
        
        # Remove trailing slash for consistency
        return url.rstrip('/')
    
    @classmethod
    def validate_page_number(cls, page: int) -> int:
        """Validate page number for pagination.
        
        Args:
            page: Page number to validate
            
        Returns:
            Validated page number
            
        Raises:
            ValidationError: If page number is invalid
        """
        if page < 1:
            raise ValidationError("Page number must be greater than 0")
        
        if page > 1000:
            raise ValidationError("Page number cannot exceed 1000")
        
        return page
    
    @classmethod
    def validate_per_page(cls, per_page: int) -> int:
        """Validate per-page count for pagination.
        
        Args:
            per_page: Per-page count to validate
            
        Returns:
            Validated per-page count
            
        Raises:
            ValidationError: If per-page count is invalid
        """
        if per_page < 1:
            raise ValidationError("Per-page count must be greater than 0")
        
        if per_page > 100:
            raise ValidationError("Per-page count cannot exceed 100")
        
        return per_page
    
    @classmethod
    def validate_tail_count(cls, tail: Optional[int]) -> Optional[int]:
        """Validate tail count for log viewing.
        
        Args:
            tail: Tail count to validate
            
        Returns:
            Validated tail count
            
        Raises:
            ValidationError: If tail count is invalid
        """
        if tail is None:
            return None
        
        if tail < 1:
            raise ValidationError("Tail count must be greater than 0")
        
        if tail > 10000:
            raise ValidationError("Tail count cannot exceed 10000")
        
        return tail
    
    @classmethod
    def sanitize_custom_env_vars(cls, env_vars: List[str]) -> Dict[str, str]:
        """Validate and sanitize custom environment variables.
        
        Args:
            env_vars: List of environment variable strings in KEY=VALUE format
            
        Returns:
            Dictionary of validated environment variables
            
        Raises:
            ValidationError: If any environment variable is invalid
        """
        result = {}
        
        for env_var in env_vars:
            if '=' not in env_var:
                raise ValidationError(f"Invalid environment variable format: {env_var}")
            
            key, value = env_var.split('=', 1)
            key = cls.validate_env_var_key(key.strip())
            value = cls.validate_env_var_value(value.strip())
            
            result[key] = value
        
        return result


def validate_input(value: str, pattern: str, max_length: int = 255) -> bool:
    """Generic input validation function.
    
    Args:
        value: Value to validate
        pattern: Regex pattern to match against
        max_length: Maximum allowed length
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    if not value:
        raise ValidationError("Value cannot be empty")
    
    if len(value) > max_length:
        raise ValidationError(f"Value cannot exceed {max_length} characters")
    
    if not re.match(pattern, value):
        raise ValidationError("Value format is invalid")
    
    return True