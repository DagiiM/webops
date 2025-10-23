"""
Encryption utilities for WebOps.

"Security Best Practices" section
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
        raise ValueError("ENCRYPTION_KEY not configured in settings. Set a valid Fernet key in .env")

    try:
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    except Exception as e:
        raise ValueError(
            "Invalid ENCRYPTION_KEY: must be 32 url-safe base64-encoded bytes.\n"
            "Generate one with: from cryptography.fernet import Fernet; Fernet.generate_key().decode()"
        ) from e
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
        raise ValueError("ENCRYPTION_KEY not configured in settings. Set a valid Fernet key in .env")

    try:
        fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    except Exception as e:
        raise ValueError(
            "Invalid ENCRYPTION_KEY: must be 32 url-safe base64-encoded bytes.\n"
            "Generate one with: from cryptography.fernet import Fernet; Fernet.generate_key().decode()"
        ) from e
    return fernet.decrypt(encrypted.encode()).decode()