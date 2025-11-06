"""Encryption utilities for securing sensitive data in WebOps CLI.

This module provides encryption and decryption capabilities for sensitive
configuration data like API tokens, passwords, and other secrets.
"""

import os
import base64
import hashlib
import secrets
from typing import Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionError(Exception):
    """Raised when encryption/decryption operations fail."""
    pass


class SecureConfig:
    """Manages encrypted configuration storage for sensitive data."""
    
    def __init__(self, encryption_key: Optional[bytes] = None) -> None:
        """Initialize secure configuration manager.
        
        Args:
            encryption_key: Optional encryption key. If not provided,
                          will attempt to get from environment or generate.
        
        Raises:
            EncryptionError: If key generation fails.
        """
        self.key = encryption_key or self._get_or_create_key()
        self.cipher = Fernet(self.key)
    
    def _get_or_create_key(self) -> bytes:
        """Get encryption key from environment or create a new one.
        
        Returns:
            Encryption key as bytes.
            
        Raises:
            EncryptionError: If key generation fails.
        """
        # Try to get key from environment
        env_key = os.environ.get('WEBOPS_ENCRYPTION_KEY')
        if env_key:
            try:
                return base64.urlsafe_b64decode(env_key.encode())
            except Exception as e:
                raise EncryptionError(f"Invalid encryption key in environment: {e}")
        
        # Try to get key from key file
        key_file = os.path.expanduser("~/provisioning/.encryption_key")
        if os.path.exists(key_file):
            try:
                with open(key_file, 'rb') as f:
                    return f.read()
            except Exception as e:
                raise EncryptionError(f"Failed to read encryption key file: {e}")
        
        # Generate new key
        try:
            key = Fernet.generate_key()
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            
            # Save key with restrictive permissions
            with open(key_file, 'wb') as f:
                f.write(key)
            
            # Set file permissions to read/write by owner only
            os.chmod(key_file, 0o600)
            
            return key
        except Exception as e:
            raise EncryptionError(f"Failed to generate encryption key: {e}")
    
    def encrypt_value(self, value: str) -> str:
        """Encrypt a string value.
        
        Args:
            value: String value to encrypt
            
        Returns:
            Base64-encoded encrypted string
            
        Raises:
            EncryptionError: If encryption fails.
        """
        if not isinstance(value, str):
            raise EncryptionError("Value must be a string")
        
        try:
            encrypted_bytes = self.cipher.encrypt(value.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt value: {e}")
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt an encrypted string value.
        
        Args:
            encrypted_value: Base64-encoded encrypted string
            
        Returns:
            Decrypted string value
            
        Raises:
            EncryptionError: If decryption fails.
        """
        if not isinstance(encrypted_value, str):
            raise EncryptionError("Encrypted value must be a string")
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode('utf-8'))
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt value: {e}")
    
    def is_encrypted(self, value: str) -> bool:
        """Check if a value appears to be encrypted.
        
        Args:
            value: String value to check
            
        Returns:
            True if value appears to be encrypted, False otherwise
        """
        if not isinstance(value, str):
            return False
        
        try:
            # Try to decode as base64 and decrypt
            encrypted_bytes = base64.urlsafe_b64decode(value.encode('utf-8'))
            self.cipher.decrypt(encrypted_bytes)
            return True
        except Exception:
            return False
    
    def encrypt_dict_values(self, data: dict, sensitive_keys: list) -> dict:
        """Encrypt sensitive values in a dictionary.
        
        Args:
            data: Dictionary containing configuration data
            sensitive_keys: List of keys whose values should be encrypted
            
        Returns:
            Dictionary with sensitive values encrypted
            
        Raises:
            EncryptionError: If encryption fails.
        """
        if not isinstance(data, dict):
            raise EncryptionError("Data must be a dictionary")
        
        result = data.copy()
        
        for key in sensitive_keys:
            if key in result and result[key] is not None:
                # Check if already encrypted
                if not self.is_encrypted(str(result[key])):
                    result[key] = self.encrypt_value(str(result[key]))
        
        return result
    
    def decrypt_dict_values(self, data: dict, sensitive_keys: list) -> dict:
        """Decrypt sensitive values in a dictionary.
        
        Args:
            data: Dictionary containing encrypted configuration data
            sensitive_keys: List of keys whose values should be decrypted
            
        Returns:
            Dictionary with sensitive values decrypted
            
        Raises:
            EncryptionError: If decryption fails.
        """
        if not isinstance(data, dict):
            raise EncryptionError("Data must be a dictionary")
        
        result = data.copy()
        
        for key in sensitive_keys:
            if key in result and result[key] is not None:
                # Try to decrypt if it appears to be encrypted
                if self.is_encrypted(str(result[key])):
                    try:
                        result[key] = self.decrypt_value(str(result[key]))
                    except EncryptionError:
                        # If decryption fails, leave as-is
                        pass
        
        return result


class PasswordManager:
    """Manages secure password generation and validation."""
    
    @staticmethod
    def generate_secure_password(length: int = 32) -> str:
        """Generate a cryptographically secure password.
        
        Args:
            length: Length of the password to generate
            
        Returns:
            Secure random password
        """
        if length < 12:
            raise ValueError("Password length must be at least 12 characters")
        
        # Generate secure random bytes and encode as base64
        random_bytes = secrets.token_bytes((length * 3 + 3) // 4)  # Ensure enough bytes
        password = base64.urlsafe_b64encode(random_bytes).decode('utf-8')[:length]
        
        # Ensure password contains at least one of each required character type
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        
        # If missing required character types, regenerate
        if not (has_upper and has_lower and has_digit and has_special):
            return PasswordManager.generate_secure_password(length)
        
        return password
    
    @staticmethod
    def validate_password_strength(password: str) -> dict:
        """Validate password strength.
        
        Args:
            password: Password to validate
            
        Returns:
            Dictionary containing validation results
        """
        result = {
            'valid': True,
            'score': 0,
            'issues': [],
            'suggestions': []
        }
        
        if len(password) < 12:
            result['valid'] = False
            result['issues'].append("Password must be at least 12 characters long")
            result['suggestions'].append("Use a longer password")
        else:
            result['score'] += 1
        
        if not any(c.isupper() for c in password):
            result['valid'] = False
            result['issues'].append("Password must contain uppercase letters")
            result['suggestions'].append("Add uppercase letters")
        else:
            result['score'] += 1
        
        if not any(c.islower() for c in password):
            result['valid'] = False
            result['issues'].append("Password must contain lowercase letters")
            result['suggestions'].append("Add lowercase letters")
        else:
            result['score'] += 1
        
        if not any(c.isdigit() for c in password):
            result['valid'] = False
            result['issues'].append("Password must contain numbers")
            result['suggestions'].append("Add numbers")
        else:
            result['score'] += 1
        
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
            result['valid'] = False
            result['issues'].append("Password must contain special characters")
            result['suggestions'].append("Add special characters")
        else:
            result['score'] += 1
        
        # Check for common patterns
        if password.lower() in ['password', '123456', 'qwerty', 'admin', 'letmein']:
            result['valid'] = False
            result['issues'].append("Password is too common")
            result['suggestions'].append("Use a more unique password")
            result['score'] = 0
        
        return result


def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
    """Derive encryption key from password using PBKDF2.
    
    Args:
        password: Password to derive key from
        salt: Optional salt. If not provided, generates random salt
        
    Returns:
        Tuple of (derived_key, salt)
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt


def hash_sensitive_data(data: str, salt: Optional[bytes] = None) -> tuple[str, bytes]:
    """Hash sensitive data for verification purposes.
    
    Args:
        data: Data to hash
        salt: Optional salt. If not provided, generates random salt
        
    Returns:
        Tuple of (hashed_data, salt)
    """
    if salt is None:
        salt = os.urandom(16)
    
    # Use SHA-256 for hashing
    hasher = hashlib.sha256()
    hasher.update(salt + data.encode('utf-8'))
    hashed_data = hasher.hexdigest()
    
    return hashed_data, salt


def verify_sensitive_data(data: str, hashed_data: str, salt: bytes) -> bool:
    """Verify sensitive data against a hash.
    
    Args:
        data: Data to verify
        hashed_data: Hash to verify against
        salt: Salt used for hashing
        
    Returns:
        True if data matches hash, False otherwise
    """
    expected_hash, _ = hash_sensitive_data(data, salt)
    return secrets.compare_digest(expected_hash, hashed_data)