"""
Authentication services for WebOps.

Provides Two-Factor Authentication (2FA) using TOTP (Time-based One-Time Password).
Pure Python implementation - compatible with Google Authenticator, Authy, etc.
"""

import hmac
import hashlib
import secrets
import time
import base64
import struct
import string
from typing import Tuple, List
from urllib.parse import quote

from django.contrib.auth.models import User
from django.utils import timezone

from .models import TwoFactorAuth


class TOTPService:
    """
    Time-based One-Time Password service.

    Pure Python implementation - zero external dependencies.
    Compatible with Google Authenticator, Authy, etc.
    """

    @staticmethod
    def generate_secret() -> str:
        """Generate base32-encoded secret (16 bytes = 128 bits)."""
        secret_bytes = secrets.token_bytes(20)
        return base64.b32encode(secret_bytes).decode('utf-8').rstrip('=')

    @staticmethod
    def get_totp_token(secret: str, time_step: int = 30) -> str:
        """
        Generate 6-digit TOTP token.

        Args:
            secret: Base32-encoded secret
            time_step: Time step in seconds (default 30)

        Returns:
            6-digit OTP
        """
        # Decode secret
        secret_bytes = base64.b32decode(secret + '=' * ((8 - len(secret) % 8) % 8))

        # Get time counter
        counter = int(time.time()) // time_step

        # Convert counter to bytes
        counter_bytes = struct.pack('>Q', counter)

        # HMAC-SHA1
        hmac_result = hmac.new(secret_bytes, counter_bytes, hashlib.sha1).digest()

        # Dynamic truncation
        offset = hmac_result[-1] & 0x0F
        truncated = struct.unpack('>I', hmac_result[offset:offset+4])[0]
        truncated &= 0x7FFFFFFF

        # Generate 6-digit code
        token = truncated % 1000000

        return f"{token:06d}"

    @staticmethod
    def verify_token(secret: str, token: str, window: int = 1) -> bool:
        """
        Verify TOTP token.

        Args:
            secret: Base32-encoded secret
            token: 6-digit token to verify
            window: Number of time steps to check before/after current

        Returns:
            True if token is valid
        """
        current_time = int(time.time())
        time_step = 30

        for offset in range(-window, window + 1):
            check_time = current_time + (offset * time_step)
            counter = check_time // time_step

            # Generate token for this time step
            expected_token = TOTPService._generate_token_for_counter(secret, counter)

            if hmac.compare_digest(token, expected_token):
                return True

        return False

    @staticmethod
    def _generate_token_for_counter(secret: str, counter: int) -> str:
        """Generate TOTP token for specific counter value."""
        secret_bytes = base64.b32decode(secret + '=' * ((8 - len(secret) % 8) % 8))
        counter_bytes = struct.pack('>Q', counter)
        hmac_result = hmac.new(secret_bytes, counter_bytes, hashlib.sha1).digest()
        offset = hmac_result[-1] & 0x0F
        truncated = struct.unpack('>I', hmac_result[offset:offset+4])[0]
        truncated &= 0x7FFFFFFF
        token = truncated % 1000000
        return f"{token:06d}"

    @staticmethod
    def get_provisioning_uri(secret: str, username: str, issuer: str = "WebOps") -> str:
        """
        Get provisioning URI for QR code generation.

        Args:
            secret: Base32-encoded secret
            username: Username to display in authenticator app
            issuer: Issuer name (appears in app)

        Returns:
            otpauth:// URI
        """
        return (
            f"otpauth://totp/{quote(issuer)}:{quote(username)}"
            f"?secret={secret}&issuer={quote(issuer)}"
        )


class TwoFactorService:
    """Service for managing 2FA."""

    @staticmethod
    def setup_2fa(user: User) -> Tuple[TwoFactorAuth, str, List[str]]:
        """
        Set up 2FA for user.

        Args:
            user: User instance

        Returns:
            Tuple of (TwoFactorAuth instance, provisioning URI, backup codes)
        """
        # Generate secret
        secret = TOTPService.generate_secret()

        # Generate backup codes
        backup_codes = TwoFactorService._generate_backup_codes()

        # Create or update 2FA settings
        two_factor, created = TwoFactorAuth.objects.get_or_create(user=user)
        two_factor.secret = secret
        two_factor.backup_codes = backup_codes
        two_factor.is_enabled = False  # User must verify first
        two_factor.save()

        # Get provisioning URI for QR code
        uri = TOTPService.get_provisioning_uri(
            secret,
            user.email or user.username,
            "WebOps"
        )

        return two_factor, uri, backup_codes

    @staticmethod
    def enable_2fa(user: User, token: str) -> bool:
        """
        Enable 2FA after user verifies with token.

        Args:
            user: User instance
            token: 6-digit TOTP token

        Returns:
            True if enabled successfully
        """
        try:
            two_factor = user.two_factor
        except TwoFactorAuth.DoesNotExist:
            return False

        # Verify token
        if TOTPService.verify_token(two_factor.secret, token):
            two_factor.is_enabled = True
            two_factor.last_used = timezone.now()
            two_factor.save()
            return True

        return False

    @staticmethod
    def verify_2fa(user: User, token: str) -> bool:
        """
        Verify 2FA token during login.

        Args:
            user: User instance
            token: 6-digit token or backup code

        Returns:
            True if valid
        """
        try:
            two_factor = user.two_factor
        except TwoFactorAuth.DoesNotExist:
            return False

        if not two_factor.is_enabled:
            return False

        # Try TOTP first
        if TOTPService.verify_token(two_factor.secret, token):
            two_factor.last_used = timezone.now()
            two_factor.save()
            return True

        # Try backup code
        if token in two_factor.backup_codes:
            two_factor.backup_codes.remove(token)
            two_factor.save()
            return True

        return False

    @staticmethod
    def disable_2fa(user: User) -> bool:
        """Disable 2FA for user."""
        try:
            two_factor = user.two_factor
            two_factor.is_enabled = False
            two_factor.save()
            return True
        except TwoFactorAuth.DoesNotExist:
            return False

    @staticmethod
    def _generate_backup_codes(count: int = 10) -> List[str]:
        """Generate backup codes for 2FA recovery."""
        codes = []
        for _ in range(count):
            code = ''.join(
                secrets.choice(string.ascii_uppercase + string.digits)
                for _ in range(8)
            )
            # Format as XXXX-XXXX
            formatted = f"{code[:4]}-{code[4:]}"
            codes.append(formatted)
        return codes
