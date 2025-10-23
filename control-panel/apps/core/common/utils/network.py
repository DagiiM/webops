"""
Network utilities for WebOps.

"Security Best Practices" section
Handles port generation, URL validation, and client IP extraction.
"""

import secrets
import re
from typing import Set
from urllib.parse import urlparse


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