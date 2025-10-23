"""
Security services for WebOps.

Implements 2FA, GitHub OAuth, security auditing, and system monitoring.
Minimal dependencies approach - uses stdlib where possible.
"""

import hmac
import hashlib
import secrets
import time
import base64
import struct
from typing import Dict, Any, Optional, Tuple
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from cryptography.fernet import Fernet
from apps.core.integrations.models import HuggingFaceConnection,GitHubConnection
from apps.core.auth.models import TwoFactorAuth
from apps.core.security.models import SecurityAuditLog
from apps.core.common.models import SystemHealthCheck

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
        from urllib.parse import quote

        return (
            f"otpauth://totp/{quote(issuer)}:{quote(username)}"
            f"?secret={secret}&issuer={quote(issuer)}"
        )


class TwoFactorService:
    """Service for managing 2FA."""

    @staticmethod
    def setup_2fa(user: User) -> Tuple[TwoFactorAuth, str, list]:
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
    def _generate_backup_codes(count: int = 10) -> list:
        """Generate backup codes for 2FA recovery."""
        import string

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


class SecurityAuditService:
    """Service for security audit logging."""

    @staticmethod
    def log_event(
        event_type: str,
        request,
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
    def _get_client_ip(request) -> str:
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


class SystemHealthService:
    """Service for system health monitoring."""

    @staticmethod
    def run_health_check() -> SystemHealthCheck:
        """
        Run comprehensive system health check.

        Returns:
            SystemHealthCheck instance
        """
        import psutil
        from apps.deployments.models import BaseDeployment

        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)

        # Memory
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_mb = memory.used // (1024 ** 2)
        memory_total_mb = memory.total // (1024 ** 2)

        # Disk
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used_gb = disk.used / (1024 ** 3)
        disk_total_gb = disk.total / (1024 ** 3)

        # Deployments
        active_deployments = ApplicationDeployment.objects.filter(
            status=ApplicationDeployment.Status.RUNNING
        ).count()

        failed_deployments = ApplicationDeployment.objects.filter(
            status=ApplicationDeployment.Status.FAILED
        ).count()

        # Determine health status
        issues = []
        is_healthy = True

        if cpu_percent > 90:
            issues.append(f"High CPU usage: {cpu_percent}%")
            is_healthy = False

        if memory_percent > 90:
            issues.append(f"High memory usage: {memory_percent}%")
            is_healthy = False

        if disk_percent > 90:
            issues.append(f"Low disk space: {disk_percent}% used")
            is_healthy = False

        # Create health check record
        return SystemHealthCheck.objects.create(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_used_mb,
            memory_total_mb=memory_total_mb,
            disk_percent=disk_percent,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            active_deployments=active_deployments,
            failed_deployments=failed_deployments,
            is_healthy=is_healthy,
            issues=issues
        )

    @staticmethod
    def get_latest_health() -> Optional[SystemHealthCheck]:
        """Get latest health check result."""
        return SystemHealthCheck.objects.order_by('-created_at').first()

    @staticmethod
    def get_health_trend(hours: int = 24) -> Dict[str, Any]:
        """
        Get health trend over time.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with trend data
        """
        since = timezone.now() - timezone.timedelta(hours=hours)

        checks = SystemHealthCheck.objects.filter(
            created_at__gte=since
        ).order_by('created_at')

        if not checks.exists():
            return {
                'has_data': False,
                'message': 'No health check data available'
            }

        return {
            'has_data': True,
            'checks_count': checks.count(),
            'avg_cpu': sum(c.cpu_percent for c in checks) / checks.count(),
            'avg_memory': sum(c.memory_percent for c in checks) / checks.count(),
            'avg_disk': sum(c.disk_percent for c in checks) / checks.count(),
            'unhealthy_count': checks.filter(is_healthy=False).count(),
            'checks': list(checks.values(
                'created_at', 'cpu_percent', 'memory_percent',
                'disk_percent', 'is_healthy'
            ))
        }


class GoogleOAuthService:
    """Helpers for Google OAuth: auth URL, token exchange, and user info."""

    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

    def __init__(self):
        self.client_id = settings.GOOGLE_OAUTH_CLIENT_ID
        self.client_secret = settings.GOOGLE_OAUTH_CLIENT_SECRET

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        from urllib.parse import urlencode
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_token(self, code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
        try:
            data = {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
            resp = requests.post(self.TOKEN_URL, data=data, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"Google token exchange failed HTTP {resp.status_code}: {resp.text}")
        except Exception:
            logger.exception("Google token exchange exception")
        return None

    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        try:
            data = {
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
            }
            resp = requests.post(self.TOKEN_URL, data=data, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"Google token refresh failed HTTP {resp.status_code}: {resp.text}")
        except Exception:
            logger.exception("Google token refresh exception")
        return None

    def get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            resp = requests.get(self.USERINFO_URL, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"Google userinfo failed HTTP {resp.status_code}: {resp.text}")
        except Exception:
            logger.exception("Google userinfo exception")
        return None
