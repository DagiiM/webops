"""
Security services for WebOps.

Provides encryption and security audit logging functionality.
"""

import hmac
import hashlib
import base64
from typing import Optional
from django.conf import settings
from django.utils import timezone
from django.http import HttpRequest
from cryptography.fernet import Fernet

from .models import SecurityAuditLog


class EncryptionService:
    """
    Encryption service for sensitive configuration data.
    Uses Fernet (symmetric encryption) for secure storage.
    """

    @staticmethod
    def _get_encryption_key() -> bytes:
        """Get or generate encryption key from Django secret key."""
        # Use Django's SECRET_KEY to derive a consistent encryption key
        key_material = settings.SECRET_KEY.encode('utf-8')
        # Use HKDF to derive a proper 32-byte key for Fernet
        derived_key = hashlib.pbkdf2_hmac('sha256', key_material, b'webops-config', 100000)
        return base64.urlsafe_b64encode(derived_key)

    @staticmethod
    def encrypt(plaintext: str) -> str:
        """Encrypt a plaintext string."""
        if not plaintext:
            return plaintext

        key = EncryptionService._get_encryption_key()
        fernet = Fernet(key)
        encrypted_bytes = fernet.encrypt(plaintext.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')

    @staticmethod
    def decrypt(encrypted_text: str) -> str:
        """Decrypt an encrypted string."""
        if not encrypted_text:
            return encrypted_text

        try:
            key = EncryptionService._get_encryption_key()
            fernet = Fernet(key)
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode('utf-8'))
            decrypted_bytes = fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception:
            # If decryption fails, return the original text (might be unencrypted)
            return encrypted_text


class SecurityAuditService:
    """Service for security audit logging."""

    @staticmethod
    def log_event(
        event_type: str,
        request: HttpRequest,
        description: str,
        severity: str = 'info',
        **metadata
    ) -> SecurityAuditLog:
        """
        Log a security event.

        Args:
            event_type: Type of event
            request: Django request object
            description: Event description
            severity: Severity level
            **metadata: Additional metadata

        Returns:
            SecurityAuditLog instance
        """
        # Get IP address
        ip_address = SecurityAuditService._get_client_ip(request)

        # Get user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Get user
        user = request.user if request.user.is_authenticated else None

        return SecurityAuditLog.objects.create(
            event_type=event_type,
            ip_address=ip_address,
            user_agent=user_agent,
            description=description,
            user=user,
            severity=severity,
            metadata=metadata
        )

    @staticmethod
    def _get_client_ip(request: HttpRequest) -> str:
        """Get client IP address from request."""
        # Check for proxy headers
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip

    @staticmethod
    def get_failed_login_attempts(ip_address: str, since_minutes: int = 15) -> int:
        """Get count of failed login attempts from IP."""
        since = timezone.now() - timezone.timedelta(minutes=since_minutes)

        return SecurityAuditLog.objects.filter(
            event_type='login_failed',
            ip_address=ip_address,
            created_at__gte=since
        ).count()

    @staticmethod
    def is_ip_blocked(ip_address: str, max_attempts: int = 5) -> bool:
        """Check if IP should be blocked due to failed attempts."""
        attempts = SecurityAuditService.get_failed_login_attempts(ip_address)
        return attempts >= max_attempts
