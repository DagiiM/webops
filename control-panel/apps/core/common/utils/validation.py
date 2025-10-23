"""
Validation utilities for WebOps.

"Security Best Practices" section
Handles domain name validation and deployment name sanitization.
"""

import re


def validate_domain_name(domain: str) -> bool:
    """
    Validate domain name format.
    
    Args:
        domain: Domain name to validate
        
    Returns:
        True if valid domain format
    """
    if not domain:
        return False
        
    # Basic domain name pattern
    pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
    
    if not re.match(pattern, domain):
        return False
        
    # Check length constraints
    if len(domain) > 253:
        return False
        
    # Check label lengths
    labels = domain.split('.')
    for label in labels:
        if len(label) > 63:
            return False
            
    return True


def sanitize_deployment_name(name: str) -> str:
    """
    Sanitize deployment name for filesystem and service names.
    
    Args:
        name: Raw deployment name
        
    Returns:
        Sanitized name safe for filesystem and systemd
    """
    if not name:
        raise ValueError("Deployment name cannot be empty")
        
    # Convert to lowercase and replace invalid chars with hyphens
    sanitized = re.sub(r'[^a-z0-9-]', '-', name.lower())
    
    # Remove consecutive hyphens
    sanitized = re.sub(r'-+', '-', sanitized)
    
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip('-')
    
    # Ensure minimum length
    if len(sanitized) < 2:
        raise ValueError("Deployment name too short after sanitization")
        
    # Ensure maximum length
    if len(sanitized) > 50:
        sanitized = sanitized[:50].rstrip('-')
        
    return sanitized