"""
Encryption utilities for WebOps.

"Security Best Practices" section
Handles password generation, secret key generation, and encryption/decryption.
"""

import secrets
import string
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


def encrypt_value(value: str) -> str:
    """
    Encrypt value for storage.
    
    Args:
        value: Plain text value
        
    Returns:
        Encrypted value
    """
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not configured in settings")
        
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """
    Decrypt value from storage.
    
    Args:
        encrypted: Encrypted value
        
    Returns:
        Plain text value
    """
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not configured in settings")
        
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return fernet.decrypt(encrypted.encode()).decode()


# Backward compatibility aliases
encrypt_password = encrypt_value
decrypt_password = decrypt_value