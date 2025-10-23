"""
Security models for audit logging and monitoring.

Provides comprehensive security event tracking for compliance and forensics.
"""

from django.db import models
from django.contrib.auth.models import User

from apps.core.common.models import BaseModel


class SecurityAuditLog(BaseModel):
    """Security audit log for all security-relevant events."""

    class EventType(models.TextChoices):
        LOGIN_SUCCESS = 'login_success', 'Login Success'
        LOGIN_FAILED = 'login_failed', 'Login Failed'
        LOGOUT = 'logout', 'Logout'
        PASSWORD_CHANGE = 'password_change', 'Password Changed'
        TFA_ENABLED = '2fa_enabled', '2FA Enabled'
        TFA_DISABLED = '2fa_disabled', '2FA Disabled'
        TFA_SUCCESS = '2fa_success', '2FA Success'
        TFA_FAILED = '2fa_failed', '2FA Failed'
        TOKEN_CREATED = 'token_created', 'API Token Created'
        TOKEN_REVOKED = 'token_revoked', 'API Token Revoked'
        DEPLOYMENT_CREATED = 'deployment_created', 'Deployment Created'
        DEPLOYMENT_DELETED = 'deployment_deleted', 'Deployment Deleted'
        DATABASE_ACCESSED = 'database_accessed', 'Database Credentials Accessed'
        SUSPICIOUS_ACTIVITY = 'suspicious_activity', 'Suspicious Activity'
        UNAUTHORIZED_ACCESS = 'unauthorized_access', 'Unauthorized Access Attempt'

    class Severity(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'
        CRITICAL = 'critical', 'Critical'

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_logs'
    )
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.INFO)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'core_security_audit_log'
        verbose_name = 'Security Audit Log'
        verbose_name_plural = 'Security Audit Logs'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['event_type']),
            models.Index(fields=['severity']),
        ]

    def __str__(self) -> str:
        user_str = self.user.username if self.user else "Anonymous"
        return f"[{self.severity.upper()}] {user_str} - {self.event_type}"
