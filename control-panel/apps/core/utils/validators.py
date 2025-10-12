"""
Validation utilities for WebOps.

Reference: CLAUDE.md "Input Validation" section
"""

import re
from typing import Optional
from urllib.parse import urlparse


def validate_repo_url(url: str) -> bool:
    """
    Validate GitHub repository URL.

    Args:
        url: Repository URL to validate

    Returns:
        True if valid, False otherwise
    """
    if not url:
        return False

    # Support both HTTPS and SSH GitHub URLs
    patterns = [
        r'^https://github\.com/[\w-]+/[\w.-]+(?:\.git)?$',
        r'^git@github\.com:[\w-]+/[\w.-]+(?:\.git)?$',
    ]

    return any(re.match(pattern, url) for pattern in patterns)


def validate_domain(domain: str) -> bool:
    """
    Validate domain name format.

    Args:
        domain: Domain name to validate

    Returns:
        True if valid, False otherwise
    """
    if not domain:
        return False

    # Basic domain validation pattern
    pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    return bool(re.match(pattern, domain))


def validate_app_name(name: str) -> bool:
    """
    Validate application name (alphanumeric, hyphens, underscores).

    Args:
        name: Application name to validate

    Returns:
        True if valid, False otherwise
    """
    if not name or len(name) > 100:
        return False

    pattern = r'^[a-z0-9][a-z0-9-_]*[a-z0-9]$'
    return bool(re.match(pattern, name))


def sanitize_deployment_name(name: str) -> str:
    """
    Sanitize deployment name by converting to lowercase and replacing invalid characters.

    Args:
        name: Raw deployment name to sanitize

    Returns:
        Sanitized deployment name

    Raises:
        ValueError: If the name cannot be sanitized to a valid format
    """
    if not name or not name.strip():
        raise ValueError("Deployment name cannot be empty")
    
    # Convert to lowercase and strip whitespace
    sanitized = name.strip().lower()
    
    # Replace spaces and special characters with hyphens
    sanitized = re.sub(r'[^a-z0-9-_]', '-', sanitized)
    
    # Remove consecutive hyphens
    sanitized = re.sub(r'-+', '-', sanitized)
    
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip('-')
    
    # Ensure it starts and ends with alphanumeric
    if not sanitized:
        raise ValueError("Deployment name must contain at least one alphanumeric character")
    
    if not re.match(r'^[a-z0-9]', sanitized):
        sanitized = 'app-' + sanitized
    
    if not re.match(r'[a-z0-9]$', sanitized):
        sanitized = sanitized + '-app'
    
    # Validate final result
    if not validate_app_name(sanitized):
        raise ValueError(f"Invalid deployment name format: '{name}'")
    
    return sanitized