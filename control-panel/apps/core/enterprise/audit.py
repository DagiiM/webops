"""
Audit logging system for compliance and security.

Features:
- Immutable audit trail
- Automatic context capture
- Query interface
- Compliance reporting
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField
import uuid

User = get_user_model()


class AuditLog(models.Model):
    """
    Immutable audit log for all system actions.

    Compliance features:
    - Complete audit trail
    - Actor tracking
    - IP address logging
    - Request context
    - Resource tracking
    """

    # Event types
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    VIEW = 'view'
    EXECUTE = 'execute'
    LOGIN = 'login'
    LOGOUT = 'logout'
    PERMISSION_CHANGE = 'permission_change'

    ACTION_CHOICES = [
        (CREATE, 'Create'),
        (UPDATE, 'Update'),
        (DELETE, 'Delete'),
        (VIEW, 'View'),
        (EXECUTE, 'Execute'),
        (LOGIN, 'Login'),
        (LOGOUT, 'Logout'),
        (PERMISSION_CHANGE, 'Permission Change'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs'
    )
    user_email = models.EmailField()  # Preserve even if user deleted

    # What
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    resource_type = models.CharField(max_length=100, db_index=True)
    resource_id = models.UUIDField(null=True, blank=True, db_index=True)
    resource_name = models.CharField(max_length=255, blank=True)

    # Context
    organization_id = models.UUIDField(null=True, blank=True, db_index=True)
    team_id = models.UUIDField(null=True, blank=True)

    # Request details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    request_method = models.CharField(max_length=10, blank=True)

    # Changes
    changes = models.JSONField(default=dict, blank=True)  # Before/after values
    metadata = models.JSONField(default=dict, blank=True)  # Additional context

    # Result
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    # Timestamp (immutable)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['organization_id', 'timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['timestamp']),  # For time-range queries
        ]
        # Make immutable
        permissions = [
            ('view_audit_log', 'Can view audit logs'),
            ('export_audit_log', 'Can export audit logs'),
        ]

    def __str__(self):
        return f"{self.user_email} {self.action} {self.resource_type}:{self.resource_id} at {self.timestamp}"

    def save(self, *args, **kwargs):
        # Only allow creation, no updates
        if not self._state.adding:
            raise ValueError("Audit logs are immutable")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Prevent deletion
        raise ValueError("Audit logs cannot be deleted")


class AuditLogQuery:
    """
    Query interface for audit logs.

    Usage:
        logs = AuditLogQuery.for_user(user)
        logs = AuditLogQuery.for_organization(org)
        logs = AuditLogQuery.for_resource('deployment', deployment_id)
    """

    @staticmethod
    def for_user(user, days=30):
        """Get audit logs for a user."""
        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days)
        return AuditLog.objects.filter(
            user=user,
            timestamp__gte=cutoff
        )

    @staticmethod
    def for_organization(org_id, days=30):
        """Get audit logs for an organization."""
        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days)
        return AuditLog.objects.filter(
            organization_id=org_id,
            timestamp__gte=cutoff
        )

    @staticmethod
    def for_resource(resource_type, resource_id, days=30):
        """Get audit logs for a specific resource."""
        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days)
        return AuditLog.objects.filter(
            resource_type=resource_type,
            resource_id=resource_id,
            timestamp__gte=cutoff
        )

    @staticmethod
    def security_events(days=7):
        """Get security-relevant events."""
        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days)
        return AuditLog.objects.filter(
            timestamp__gte=cutoff,
            action__in=[
                AuditLog.LOGIN,
                AuditLog.LOGOUT,
                AuditLog.PERMISSION_CHANGE
            ]
        )

    @staticmethod
    def failed_attempts(days=1):
        """Get failed action attempts."""
        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days)
        return AuditLog.objects.filter(
            timestamp__gte=cutoff,
            success=False
        )


def log_audit(
    user,
    action,
    resource_type,
    resource_id=None,
    resource_name='',
    organization_id=None,
    team_id=None,
    changes=None,
    metadata=None,
    request=None,
    success=True,
    error_message=''
):
    """
    Create an audit log entry.

    Usage:
        from apps.core.enterprise.audit import log_audit

        log_audit(
            user=request.user,
            action=AuditLog.CREATE,
            resource_type='deployment',
            resource_id=deployment.id,
            resource_name=deployment.name,
            organization_id=org.id,
            request=request
        )
    """

    # Extract request details
    ip_address = None
    user_agent = ''
    request_path = ''
    request_method = ''

    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        request_path = request.path[:500]
        request_method = request.method

    # Create log entry
    AuditLog.objects.create(
        user=user,
        user_email=user.email if user else '',
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        organization_id=organization_id,
        team_id=team_id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_path=request_path,
        request_method=request_method,
        changes=changes or {},
        metadata=metadata or {},
        success=success,
        error_message=error_message
    )


def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
