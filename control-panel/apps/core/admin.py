"""
Admin configuration for core app.

"Django Admin" section
"""

from django.contrib import admin
from .models import (
    TwoFactorAuth,
    GitHubConnection,
    HuggingFaceConnection,
    SecurityAuditLog,
    SystemHealthCheck,
    SSLCertificate,
    BrandingSettings,
    Webhook,
    WebhookDelivery,
    NotificationChannel,
    NotificationLog,
    GoogleConnection,
)


@admin.register(BrandingSettings)
class BrandingSettingsAdmin(admin.ModelAdmin):
    """Admin interface for branding settings."""

    list_display = ['site_name', 'primary_color', 'secondary_color', 'updated_at']
    fields = [
        'site_name',
        'logo',
        'favicon',
        'primary_color',
        'secondary_color',
        'accent_color',
        'header_bg_color',
    ]

    def has_add_permission(self, request):
        """Only allow one instance (singleton pattern)."""
        return not BrandingSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of branding settings."""
        return False


@admin.register(TwoFactorAuth)
class TwoFactorAuthAdmin(admin.ModelAdmin):
    """Admin interface for 2FA settings."""

    list_display = ['user', 'is_enabled', 'created_at', 'last_used']
    list_filter = ['is_enabled']
    search_fields = ['user__username']
    readonly_fields = ['secret', 'created_at', 'last_used']


@admin.register(GitHubConnection)
class GitHubConnectionAdmin(admin.ModelAdmin):
    """Admin interface for GitHub connections."""

    list_display = ['user', 'username', 'created_at', 'last_synced']
    search_fields = ['user__username', 'username']
    readonly_fields = ['access_token', 'refresh_token', 'created_at']


@admin.register(SecurityAuditLog)
class SecurityAuditLogAdmin(admin.ModelAdmin):
    """Admin interface for security audit logs."""

    list_display = ['event_type', 'user', 'severity', 'ip_address', 'created_at']
    list_filter = ['event_type', 'severity', 'created_at']
    search_fields = ['user__username', 'ip_address', 'description']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(SystemHealthCheck)
class SystemHealthCheckAdmin(admin.ModelAdmin):
    """Admin interface for system health checks."""

    list_display = ['is_healthy', 'cpu_percent', 'memory_percent', 'disk_percent', 'created_at']
    list_filter = ['is_healthy', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(SSLCertificate)
class SSLCertificateAdmin(admin.ModelAdmin):
    """Admin interface for SSL certificates."""

    list_display = ['domain', 'status', 'issued_at', 'expires_at', 'auto_renew']
    list_filter = ['status', 'auto_renew']
    search_fields = ['domain']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(HuggingFaceConnection)
class HuggingFaceConnectionAdmin(admin.ModelAdmin):
    """Admin interface for Hugging Face connections."""

    list_display = ['user', 'username', 'token_type', 'is_valid', 'created_at']
    list_filter = ['is_valid', 'token_type']
    search_fields = ['user__username', 'username']
    readonly_fields = ['access_token', 'created_at', 'last_synced']


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    """Admin interface for webhooks."""

    list_display = ['name', 'deployment', 'user', 'trigger_event', 'is_active', 'status', 'trigger_count', 'created_at']
    list_filter = ['is_active', 'status', 'trigger_event']
    search_fields = ['name', 'deployment__name', 'user__username']
    readonly_fields = ['secret', 'created_at', 'updated_at', 'last_triggered', 'trigger_count']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'user', 'deployment')
        }),
        ('Configuration', {
            'fields': ('trigger_event', 'branch_filter', 'is_active', 'status')
        }),
        ('Security', {
            'fields': ('secret',)
        }),
        ('Statistics', {
            'fields': ('trigger_count', 'last_triggered', 'last_error')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    """Admin interface for webhook deliveries."""

    list_display = ['webhook', 'status', 'triggered_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['webhook__name', 'triggered_by']
    readonly_fields = ['created_at', 'updated_at', 'payload', 'response']
    date_hierarchy = 'created_at'


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    """Admin interface for notification channels."""

    list_display = ['name', 'user', 'channel_type', 'is_active', 'status', 'notification_count', 'created_at']
    list_filter = ['is_active', 'status', 'channel_type']
    search_fields = ['name', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'last_notification', 'notification_count']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'user', 'channel_type', 'is_active', 'status')
        }),
        ('Configuration', {
            'fields': ('config',),
            'description': 'Channel-specific configuration (JSON)'
        }),
        ('Event Filters', {
            'fields': (
                'notify_on_deploy_success',
                'notify_on_deploy_failure',
                'notify_on_deploy_start',
                'notify_on_health_check_fail',
                'notify_on_resource_warning',
            )
        }),
        ('Statistics', {
            'fields': ('notification_count', 'last_notification', 'last_error')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """Admin interface for notification logs."""

    list_display = ['channel', 'event_type', 'subject', 'status', 'created_at']
    list_filter = ['status', 'event_type', 'created_at']
    search_fields = ['channel__name', 'subject', 'message']
    readonly_fields = ['created_at', 'updated_at', 'metadata']
    date_hierarchy = 'created_at'


@admin.register(GoogleConnection)
class GoogleConnectionAdmin(admin.ModelAdmin):
    """Admin interface for Google connections."""

    list_display = ['user', 'email', 'is_valid', 'created_at', 'last_synced']
    list_filter = ['is_valid']
    search_fields = ['user__username', 'email']
    readonly_fields = ['access_token', 'refresh_token', 'id_token', 'created_at', 'last_synced']
