"""
Generator utilities for WebOps.

Reference: CLAUDE.md "Core Utilities" section
"""

import secrets
import string
from typing import Set
from django.conf import settings


def generate_secret_key(length: int = 50) -> str:
    """
    Generate Django SECRET_KEY.

    Args:
        length: Key length (default: 50)

    Returns:
        Random secret key
    """
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_port(used_ports: Set[int] = None) -> int:
    """
    Generate available port number for deployment.

    Args:
        used_ports: Set of already used ports

    Returns:
        Available port number

    Raises:
        ValueError: If no ports available in range
    """
    if used_ports is None:
        used_ports = set()

    min_port = settings.MIN_PORT
    max_port = settings.MAX_PORT

    available_ports = set(range(min_port, max_port + 1)) - used_ports

    if not available_ports:
        raise ValueError(f"No available ports in range {min_port}-{max_port}")

    return secrets.choice(list(available_ports))


def generate_encryption_key() -> str:
    """
    Generate Fernet encryption key.

    Returns:
        Base64-encoded 32-byte key
    """
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()