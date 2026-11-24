"""
Encryption utilities for WebOps.

"Security Best Practices" section
Handles password generation, secret key generation, and encryption/decryption.
"""

import secrets
import string
from cryptography.fernet import Fernet
from django.conf import settings


def _balanced_random_secret(length: int, symbols: str) -> str:
    """Generate a CSPRNG secret with each required character class."""
    if length < 4:
        raise ValueError("A balanced secret requires four characters")
    groups = (string.ascii_uppercase, string.ascii_lowercase,
              string.digits, symbols)
    chars = [secrets.choice(group) for group in groups]
    alphabet = ''.join(groups)
    chars.extend(secrets.choice(alphabet) for _ in range(length - len(chars)))
    secrets.SystemRandom().shuffle(chars)
    return ''.join(chars)


def generate_password(length: int = 32) -> str:
    """Generate a strong password (minimum twelve characters)."""
    return _balanced_random_secret(max(length, 12), "!@#$%^&*")


def generate_secret_key() -> str:
    """Generate a fifty-character Django secret with balanced character classes."""
    return _balanced_random_secret(50, "!@#$%^&*(-_=+)")


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
    if not encrypted:
        return ""          # nothing stored (e.g. SQLite): not an error
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not configured in settings")
        
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return fernet.decrypt(encrypted.encode()).decode()


# Backward compatibility aliases
encrypt_password = encrypt_value
decrypt_password = decrypt_value