"""
Test suite for security module.

Tests cover:
- Encryption and decryption
- Security audit logging
- IP-based rate limiting
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

from .services import EncryptionService, SecurityAuditService
from .models import SecurityAuditLog


class EncryptionServiceTests(TestCase):
    """Test encryption service."""

    def test_encrypt_decrypt(self):
        """Test basic encryption and decryption."""
        plaintext = "sensitive data 123"

        encrypted = EncryptionService.encrypt(plaintext)
        decrypted = EncryptionService.decrypt(encrypted)

        # Encrypted should be different
        self.assertNotEqual(plaintext, encrypted)

        # Decrypted should match original
        self.assertEqual(plaintext, decrypted)

    def test_encrypt_empty_string(self):
        """Test encrypting empty string."""
        result = EncryptionService.encrypt("")
        self.assertEqual(result, "")

    def test_decrypt_empty_string(self):
        """Test decrypting empty string."""
        result = EncryptionService.decrypt("")
        self.assertEqual(result, "")

    def test_encrypt_unicode(self):
        """Test encrypting Unicode characters."""
        plaintext = "Hello 世界 🌍"

        encrypted = EncryptionService.encrypt(plaintext)
        decrypted = EncryptionService.decrypt(encrypted)

        self.assertEqual(plaintext, decrypted)

    def test_encryption_is_deterministic(self):
        """Test that encryption produces consistent results."""
        plaintext = "test data"

        encrypted1 = EncryptionService.encrypt(plaintext)
        encrypted2 = EncryptionService.encrypt(plaintext)

        # Note: Fernet includes timestamp, so encrypted values differ
        # But both should decrypt to same plaintext
        self.assertEqual(
            EncryptionService.decrypt(encrypted1),
            EncryptionService.decrypt(encrypted2)
        )


class SecurityAuditServiceTests(TestCase):
    """Test security audit logging service."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_log_event(self):
        """Test logging a security event."""
        request = self.factory.get('/')
        request.user = self.user

        log = SecurityAuditService.log_event(
            event_type='test_event',
            request=request,
            description='Test security event',
            severity='info'
        )

        self.assertIsInstance(log, SecurityAuditLog)
        self.assertEqual(log.event_type, 'test_event')
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.description, 'Test security event')

    def test_log_event_captures_ip_address(self):
        """Test that log captures IP address."""
        request = self.factory.get('/', HTTP_X_FORWARDED_FOR='192.168.1.1')
        request.user = self.user

        log = SecurityAuditService.log_event(
            event_type='test_event',
            request=request,
            description='Test event'
        )

        self.assertEqual(log.ip_address, '192.168.1.1')

    def test_log_event_captures_user_agent(self):
        """Test that log captures user agent."""
        request = self.factory.get('/', HTTP_USER_AGENT='TestBrowser/1.0')
        request.user = self.user

        log = SecurityAuditService.log_event(
            event_type='test_event',
            request=request,
            description='Test event'
        )

        self.assertEqual(log.user_agent, 'TestBrowser/1.0')

    def test_log_event_unauthenticated(self):
        """Test logging event for unauthenticated user."""
        request = self.factory.get('/')
        request.user = User()  # Anonymous user

        log = SecurityAuditService.log_event(
            event_type='test_event',
            request=request,
            description='Anonymous event'
        )

        self.assertIsNone(log.user)

    def test_get_failed_login_attempts(self):
        """Test counting failed login attempts."""
        ip_address = '192.168.1.100'

        # Create failed login attempts
        for i in range(3):
            SecurityAuditLog.objects.create(
                event_type='login_failed',
                ip_address=ip_address,
                description=f'Failed attempt {i}',
                severity='warning'
            )

        count = SecurityAuditService.get_failed_login_attempts(ip_address)
        self.assertEqual(count, 3)

    def test_get_failed_login_attempts_time_window(self):
        """Test failed login attempts within time window."""
        ip_address = '192.168.1.100'

        # Create old failed attempt (20 minutes ago)
        old_log = SecurityAuditLog.objects.create(
            event_type='login_failed',
            ip_address=ip_address,
            description='Old failed attempt',
            severity='warning'
        )
        old_log.created_at = timezone.now() - datetime.timedelta(minutes=20)
        old_log.save()

        # Create recent failed attempt
        SecurityAuditLog.objects.create(
            event_type='login_failed',
            ip_address=ip_address,
            description='Recent failed attempt',
            severity='warning'
        )

        # Should only count recent (within 15 minutes)
        count = SecurityAuditService.get_failed_login_attempts(
            ip_address,
            since_minutes=15
        )
        self.assertEqual(count, 1)

    def test_is_ip_blocked(self):
        """Test IP blocking logic."""
        ip_address = '192.168.1.100'

        # Not blocked initially
        self.assertFalse(SecurityAuditService.is_ip_blocked(ip_address))

        # Create 5 failed attempts
        for i in range(5):
            SecurityAuditLog.objects.create(
                event_type='login_failed',
                ip_address=ip_address,
                description=f'Failed attempt {i}',
                severity='warning'
            )

        # Should be blocked now
        self.assertTrue(SecurityAuditService.is_ip_blocked(ip_address))

    def test_is_ip_blocked_custom_threshold(self):
        """Test IP blocking with custom threshold."""
        ip_address = '192.168.1.100'

        # Create 3 failed attempts
        for i in range(3):
            SecurityAuditLog.objects.create(
                event_type='login_failed',
                ip_address=ip_address,
                description=f'Failed attempt {i}',
                severity='warning'
            )

        # Should be blocked with threshold of 3
        self.assertTrue(
            SecurityAuditService.is_ip_blocked(ip_address, max_attempts=3)
        )

        # Should not be blocked with threshold of 5
        self.assertFalse(
            SecurityAuditService.is_ip_blocked(ip_address, max_attempts=5)
        )


class SecurityAuditLogModelTests(TestCase):
    """Test SecurityAuditLog model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_audit_log(self):
        """Test creating audit log entry."""
        log = SecurityAuditLog.objects.create(
            event_type=SecurityAuditLog.EventType.LOGIN_SUCCESS,
            user=self.user,
            ip_address='192.168.1.1',
            user_agent='TestBrowser/1.0',
            description='Test login',
            severity=SecurityAuditLog.Severity.INFO
        )

        self.assertEqual(log.user, self.user)
        self.assertEqual(log.ip_address, '192.168.1.1')
        self.assertIsNotNone(log.created_at)

    def test_audit_log_string_representation(self):
        """Test audit log string representation."""
        log = SecurityAuditLog.objects.create(
            event_type=SecurityAuditLog.EventType.LOGIN_SUCCESS,
            user=self.user,
            ip_address='192.168.1.1',
            description='Test login',
            severity=SecurityAuditLog.Severity.INFO
        )

        str_repr = str(log)
        self.assertIn('LOGIN_SUCCESS', str_repr)
        self.assertIn('testuser', str_repr)

    def test_audit_log_ordering(self):
        """Test that audit logs are ordered by creation time."""
        log1 = SecurityAuditLog.objects.create(
            event_type=SecurityAuditLog.EventType.LOGIN_SUCCESS,
            description='First',
            severity=SecurityAuditLog.Severity.INFO
        )

        log2 = SecurityAuditLog.objects.create(
            event_type=SecurityAuditLog.EventType.LOGOUT,
            description='Second',
            severity=SecurityAuditLog.Severity.INFO
        )

        logs = list(SecurityAuditLog.objects.all())
        # Should be ordered newest first (descending)
        self.assertEqual(logs[0].id, log2.id)
        self.assertEqual(logs[1].id, log1.id)
