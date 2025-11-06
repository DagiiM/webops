"""
Core models for WebOps.

This module imports and re-exports all models from the domain modules
to maintain backward compatibility while organizing code by domain.

Architecture: Domain-driven design with separate modules for each business domain.
"""

# Import all models from domain modules
from .branding.models import BrandingSettings
from .security.models import SecurityAuditLog
from .auth.models import TwoFactorAuth, UserPreferences
from .integrations.models import GitHubConnection, HuggingFaceConnection, GoogleConnection
from .webhooks.models import Webhook, WebhookDelivery
from .notifications.models import NotificationChannel, NotificationLog
from .common.models import SystemHealthCheck, SSLCertificate

# Enterprise models
from .enterprise.models import (
    Organization, Team, Role, OrganizationMember, TeamMember,
    Permission, RolePermission, ResourcePermission
)
from .enterprise.audit import AuditLog
from .enterprise.sso import SSOProvider, SSOSession

# Export all models for backward compatibility
__all__ = [
    # Branding
    'BrandingSettings',

    # Security
    'SecurityAuditLog',

    # Authentication
    'TwoFactorAuth',
    'UserPreferences',

    # Integrations
    'GitHubConnection',
    'HuggingFaceConnection',
    'GoogleConnection',

    # Webhooks
    'Webhook',
    'WebhookDelivery',

    # Notifications
    'NotificationChannel',
    'NotificationLog',

    # Common models
    'SystemHealthCheck',
    'SSLCertificate',

    # Enterprise
    'Organization',
    'Team',
    'Role',
    'OrganizationMember',
    'TeamMember',
    'Permission',
    'RolePermission',
    'ResourcePermission',
    'AuditLog',
    'SSOProvider',
    'SSOSession',
]
