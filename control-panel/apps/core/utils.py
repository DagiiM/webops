"""
Core utility functions for WebOps.

Reference: CLAUDE.md "Security Best Practices" section
"""

import secrets
import string
import re
from typing import Set, Optional
from urllib.parse import urlparse
from cryptography.fernet import Fernet
from django.conf import settings


def generate_password(length: int = 32) -> str:
    """
    Generate cryptographically secure password.
    
    Args:
        length: Password length (minimum 12)
        
    Returns:
        Secure random password
    """
    if length < 12:
        length = 12
        
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_secret_key() -> str:
    """
    Generate Django SECRET_KEY.
    
    Returns:
        Cryptographically secure secret key
    """
    chars = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
    return ''.join(secrets.choice(chars) for _ in range(50))


def encrypt_password(password: str) -> str:
    """
    Encrypt password for storage.
    
    Args:
        password: Plain text password
        
    Returns:
        Encrypted password
    """
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not configured in settings")
        
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    """
    Decrypt password from storage.
    
    Args:
        encrypted: Encrypted password
        
    Returns:
        Plain text password
    """
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not configured in settings")
        
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return fernet.decrypt(encrypted.encode()).decode()


def generate_port(used_ports: Set[int], min_port: int = 8001, max_port: int = 9000) -> int:
    """
    Generate available port number.
    
    Args:
        used_ports: Set of already used ports
        min_port: Minimum port number
        max_port: Maximum port number
        
    Returns:
        Available port number
        
    Raises:
        ValueError: If no ports are available
    """
    available_ports = set(range(min_port, max_port + 1)) - used_ports
    
    if not available_ports:
        raise ValueError(f"No available ports in range {min_port}-{max_port}")
        
    return secrets.choice(list(available_ports))


def validate_repo_url(url: str) -> bool:
    """
    Validate repository URL.
    
    Args:
        url: Repository URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
        
    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    
    # Check for SSH format (git@github.com:user/repo.git)
    ssh_pattern = r'^git@github\.com:[^/]+/[^/]+\.git$'
    if re.match(ssh_pattern, url):
        return True
    
    # Check HTTPS format
    if parsed.scheme not in ['https']:
        return False
        
    if parsed.netloc not in ['github.com', 'www.github.com']:
        return False
        
    # Path should be /user/repo or /user/repo.git
    path_parts = parsed.path.strip('/').split('/')
    if len(path_parts) != 2:
        return False
        
    user, repo = path_parts
    if not user or not repo:
        return False
        
    # Remove .git suffix if present for validation
    if repo.endswith('.git'):
        repo = repo[:-4]
        
    # Basic username/repo validation (GitHub rules)
    username_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9]|-(?!-))*[a-zA-Z0-9]$|^[a-zA-Z0-9]$'
    repo_pattern = r'^[a-zA-Z0-9._-]+$'
    
    if not re.match(username_pattern, user) or not re.match(repo_pattern, repo):
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


def get_client_ip(request) -> str:
    """
    Get client IP address from request.
    
    Args:
        request: Django request object
        
    Returns:
        Client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes into human readable format.
    
    Args:
        bytes_value: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.2 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def format_uptime(seconds: int) -> str:
    """
    Format uptime in seconds to human readable format.
    
    Args:
        seconds: Uptime in seconds
        
    Returns:
        Formatted string (e.g., "2 days, 3 hours")
    """
    if seconds < 60:
        return f"{seconds} seconds"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minutes"
    
    hours = minutes // 60
    minutes = minutes % 60
    if hours < 24:
        return f"{hours}h {minutes}m"
    
    days = hours // 24
    hours = hours % 24
    return f"{days}d {hours}h"