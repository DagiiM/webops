"""
Authentication module for WebOps.

Provides authentication, registration, password management, and Two-Factor Authentication (2FA).
"""

from .models import TwoFactorAuth
from .services import TOTPService, TwoFactorService
from .forms import (
    WebOpsLoginForm,
    WebOpsRegistrationForm,
    WebOpsPasswordResetForm,
    WebOpsSetPasswordForm,
    TwoFactorSetupForm,
    TwoFactorVerifyForm,
)

__all__ = [
    # Models
    "TwoFactorAuth",
    # Services
    "TOTPService",
    "TwoFactorService",
    # Forms
    "WebOpsLoginForm",
    "WebOpsRegistrationForm",
    "WebOpsPasswordResetForm",
    "WebOpsSetPasswordForm",
    "TwoFactorSetupForm",
    "TwoFactorVerifyForm",
]
