"""
Encryption utilities for WebOps.

Reference: CLAUDE.md "Security Best Practices" section
"""

import secrets
import string
from typing import Optional
from django.conf import settings
from cryptography.fernet import Fernet


def generate_password(length: int = 32) -> str:
    """
    Generate cryptographically secure password.

    Args:
        length: Password length (default: 32)

    Returns:
        Secure random password
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    # Remove confusing characters
    alphabet = alphabet.replace('"', '').replace("'", '').replace('\\', '')
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def encrypt_password(password: str) -> str:
    """
    Encrypt password for storage.

    Args:
        password: Plain text password

    Returns:
        Encrypted password string
    """
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not configured in settings")

    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    """
    Decrypt password from storage.

    Args:
        encrypted: Encrypted password string

    Returns:
        Plain text password
    """
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not configured in settings")

    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return fernet.decrypt(encrypted.encode()).decode()