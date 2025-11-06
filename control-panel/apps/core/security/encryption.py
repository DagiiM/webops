"""
Enhanced encryption utilities for WebOps security module.

This module provides encryption functions for sensitive data including:
- TOTP secrets (2FA)
- Webhook secrets
- API tokens
- Database passwords

Uses Fernet symmetric encryption (AES-128 in CBC mode).
All functions use Django settings.ENCRYPTION_KEY.
"""

from typing import Optional
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken
import logging

logger = logging.getLogger(__name__)


def get_fernet() -> Fernet:
    """
    Get Fernet cipher instance using the configured encryption key.

    Returns:
        Fernet: Configured Fernet cipher instance

    Raises:
        ValueError: If ENCRYPTION_KEY is not configured or invalid
    """
    if not settings.ENCRYPTION_KEY:
        raise ValueError(
            "ENCRYPTION_KEY not configured in settings. "
            "Generate one with: from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())"
        )

    try:
        return Fernet(settings.ENCRYPTION_KEY.encode())
    except Exception as e:
        raise ValueError(
            f"Invalid ENCRYPTION_KEY: must be 32 url-safe base64-encoded bytes. "
            f"Error: {e}"
        ) from e


def encrypt_field(value: str) -> str:
    """
    Encrypt a field value for database storage.

    Args:
        value: Plain text value to encrypt

    Returns:
        Encrypted value as base64-encoded string

    Raises:
        ValueError: If encryption key is not configured
        TypeError: If value is not a string
    """
    if not isinstance(value, str):
        raise TypeError(f"Value must be string, got {type(value).__name__}")

    if not value:
        return value

    fernet = get_fernet()
    encrypted_bytes = fernet.encrypt(value.encode())
    return encrypted_bytes.decode()


def decrypt_field(encrypted_value: str) -> str:
    """
    Decrypt a field value from database storage.

    Args:
        encrypted_value: Encrypted value as base64-encoded string

    Returns:
        Decrypted plain text value

    Raises:
        ValueError: If encryption key is not configured
        InvalidToken: If the encrypted value is invalid or was encrypted with a different key
    """
    if not encrypted_value:
        return encrypted_value

    fernet = get_fernet()

    try:
        decrypted_bytes = fernet.decrypt(encrypted_value.encode())
        return decrypted_bytes.decode()
    except InvalidToken:
        logger.error(
            "Failed to decrypt value - invalid token. "
            "This could mean the value was encrypted with a different key."
        )
        raise
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise


def rotate_encryption(old_encrypted: str, old_key: str, new_key: str) -> str:
    """
    Rotate encryption from old key to new key.

    This is useful when rotating encryption keys. It decrypts with the old key
    and re-encrypts with the new key.

    Args:
        old_encrypted: Value encrypted with old key
        old_key: Old encryption key
        new_key: New encryption key

    Returns:
        Value encrypted with new key

    Raises:
        ValueError: If keys are invalid
        InvalidToken: If decryption with old key fails
    """
    if not old_encrypted:
        return old_encrypted

    # Decrypt with old key
    old_fernet = Fernet(old_key.encode())
    decrypted = old_fernet.decrypt(old_encrypted.encode()).decode()

    # Encrypt with new key
    new_fernet = Fernet(new_key.encode())
    new_encrypted = new_fernet.encrypt(decrypted.encode()).decode()

    return new_encrypted


def is_encrypted(value: str) -> bool:
    """
    Check if a value appears to be encrypted.

    This is a heuristic check - it looks for Fernet token characteristics:
    - Starts with 'gAAAAA' (Fernet version byte + timestamp)
    - Contains base64 characters only
    - Reasonable length

    Args:
        value: Value to check

    Returns:
        True if value appears to be encrypted, False otherwise
    """
    if not value or len(value) < 40:
        return False

    # Fernet tokens start with version byte (0x80) which in base64 is 'gAAAAA'
    return value.startswith('gAAAAA')


def safe_decrypt(encrypted_value: str, default: Optional[str] = None) -> Optional[str]:
    """
    Safely decrypt a value, returning default if decryption fails.

    This is useful for migration scenarios where some values may not be
    encrypted yet, or when the encryption key has been rotated.

    Args:
        encrypted_value: Value to decrypt
        default: Default value to return if decryption fails

    Returns:
        Decrypted value, or default if decryption fails
    """
    if not encrypted_value:
        return default

    try:
        return decrypt_field(encrypted_value)
    except (ValueError, InvalidToken, Exception) as e:
        logger.warning(f"Safe decrypt failed: {e}. Returning default.")
        return default
