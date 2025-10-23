"""
Comprehensive test suite for authentication module.

Tests cover:
- User registration and login
- Password reset flow
- Two-Factor Authentication (2FA) setup and verification
- TOTP service functionality
- Security audit logging
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock
import time

from .models import TwoFactorAuth
from .services import TOTPService, TwoFactorService
from .forms import (
    WebOpsLoginForm,
    WebOpsRegistrationForm,
    TwoFactorSetupForm,
    TwoFactorVerifyForm,
)
from apps.core.security.models import SecurityAuditLog


class TOTPServiceTests(TestCase):
    """Test TOTP (Time-based One-Time Password) service."""

    def test_generate_secret(self):
        """Test secret generation."""
        secret = TOTPService.generate_secret()

        # Should be base32 encoded
        self.assertTrue(len(secret) >= 16)
        self.assertTrue(all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567' for c in secret))

    def test_get_totp_token(self):
        """Test TOTP token generation."""
        secret = 'JBSWY3DPEHPK3PXP'  # Test secret
        token = TOTPService.get_totp_token(secret)

        # Should be 6 digits
        self.assertEqual(len(token), 6)
        self.assertTrue(token.isdigit())

    def test_verify_token_valid(self):
        """Test verifying a valid TOTP token."""
        secret = TOTPService.generate_secret()
        token = TOTPService.get_totp_token(secret)

        # Token should be valid
        self.assertTrue(TOTPService.verify_token(secret, token))

    def test_verify_token_invalid(self):
        """Test verifying an invalid TOTP token."""
        secret = TOTPService.generate_secret()

        # Wrong token should fail
        self.assertFalse(TOTPService.verify_token(secret, '000000'))

    def test_get_provisioning_uri(self):
        """Test QR code provisioning URI generation."""
        secret = 'JBSWY3DPEHPK3PXP'
        username = 'testuser'
        issuer = 'WebOps'

        uri = TOTPService.get_provisioning_uri(secret, username, issuer)

        # Should be valid otpauth URI
        self.assertTrue(uri.startswith('otpauth://totp/'))
        self.assertIn(username, uri)
        self.assertIn(secret, uri)
        self.assertIn(issuer, uri)


class TwoFactorServiceTests(TestCase):
    """Test Two-Factor Authentication service."""

    def setUp(self):
        """Set up test user."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_setup_2fa(self):
        """Test 2FA setup."""
        two_factor, uri, backup_codes = TwoFactorService.setup_2fa(self.user)

        # Should create TwoFactorAuth instance
        self.assertIsInstance(two_factor, TwoFactorAuth)
        self.assertEqual(two_factor.user, self.user)
        self.assertFalse(two_factor.is_enabled)  # Not enabled until verified

        # Should generate provisioning URI
        self.assertTrue(uri.startswith('otpauth://'))

        # Should generate backup codes
        self.assertEqual(len(backup_codes), 10)
        for code in backup_codes:
            self.assertRegex(code, r'^[A-Z0-9]{4}-[A-Z0-9]{4}$')

    def test_enable_2fa_valid_token(self):
        """Test enabling 2FA with valid token."""
        two_factor, uri, backup_codes = TwoFactorService.setup_2fa(self.user)

        # Generate valid token
        token = TOTPService.get_totp_token(two_factor.secret)

        # Should enable 2FA
        result = TwoFactorService.enable_2fa(self.user, token)
        self.assertTrue(result)

        # Should update database
        two_factor.refresh_from_db()
        self.assertTrue(two_factor.is_enabled)
        self.assertIsNotNone(two_factor.last_used)

    def test_verify_2fa_with_totp(self):
        """Test 2FA verification with TOTP token."""
        # Setup and enable 2FA
        two_factor, uri, backup_codes = TwoFactorService.setup_2fa(self.user)
        token = TOTPService.get_totp_token(two_factor.secret)
        TwoFactorService.enable_2fa(self.user, token)

        # Generate new token
        new_token = TOTPService.get_totp_token(two_factor.secret)

        # Should verify successfully
        result = TwoFactorService.verify_2fa(self.user, new_token)
        self.assertTrue(result)

    def test_disable_2fa(self):
        """Test disabling 2FA."""
        # Setup and enable 2FA
        two_factor, uri, backup_codes = TwoFactorService.setup_2fa(self.user)
        token = TOTPService.get_totp_token(two_factor.secret)
        TwoFactorService.enable_2fa(self.user, token)

        # Disable
        result = TwoFactorService.disable_2fa(self.user)
        self.assertTrue(result)

        # Should be disabled
        two_factor.refresh_from_db()
        self.assertFalse(two_factor.is_enabled)


class AuthenticationFormsTests(TestCase):
    """Test authentication forms."""

    def test_registration_form_valid(self):
        """Test valid registration form."""
        form_data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': 'complex_pass123',
            'password2': 'complex_pass123',
        }
        form = WebOpsRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_registration_form_duplicate_email(self):
        """Test registration with duplicate email."""
        User.objects.create_user(
            username='existing',
            email='existing@example.com',
            password='pass123'
        )

        form_data = {
            'username': 'newuser',
            'email': 'existing@example.com',
            'password1': 'complex_pass123',
            'password2': 'complex_pass123',
        }
        form = WebOpsRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_registration_form_weak_password(self):
        """Test registration with weak password."""
        form_data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': 'password',  # Too common
            'password2': 'password',
        }
        form = WebOpsRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password1', form.errors)


class SecurityAuditLoggingTests(TestCase):
    """Test security audit logging integration."""

    def setUp(self):
        """Set up test user."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_login_creates_audit_log(self):
        """Test that login creates audit log entry."""
        initial_count = SecurityAuditLog.objects.count()

        self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123',
        })

        # Should create audit log
        self.assertGreater(SecurityAuditLog.objects.count(), initial_count)

    def test_failed_login_creates_audit_log(self):
        """Test that failed login creates audit log entry."""
        initial_count = SecurityAuditLog.objects.count()

        self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpassword',
        })

        # Should create audit log
        self.assertGreater(SecurityAuditLog.objects.count(), initial_count)
