"""
Core forms for WebOps.

This module provides backward compatibility by importing forms from their
new domain-specific locations. For new code, please import directly from
the domain modules instead of this compatibility layer.
"""

# Import forms from their new domain locations
from .branding.forms import BrandingSettingsForm
from .webhooks.forms import WebhookForm
from .notifications.forms import NotificationChannelForm
from .auth.forms import (
    WebOpsLoginForm,
    WebOpsRegistrationForm,
    WebOpsPasswordResetForm,
    WebOpsSetPasswordForm,
    TwoFactorSetupForm,
    TwoFactorVerifyForm
)

# Re-export for backward compatibility
__all__ = [
    'BrandingSettingsForm',
    'WebhookForm',
    'NotificationChannelForm',
    'WebOpsLoginForm',
    'WebOpsRegistrationForm',
    'WebOpsPasswordResetForm',
    'WebOpsSetPasswordForm',
    'TwoFactorSetupForm',
    'TwoFactorVerifyForm',
]
