"""
Django admin configuration for services app.

"Django Admin" section
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import ServiceStatus, ResourceUsage, Alert, HealthCheck
from .restart_policy import RestartPolicy, RestartAttempt


@admin.register(ServiceStatus)
class ServiceStatusAdmin(admin.ModelAdmin):
    """Admin for service status records."""

    list_display = ['deployment', 'status_badge', 'pid', 'memory_mb', 'cpu_percent', 'uptime_display', 'last_checked']
    list_filter = ['status', 'last_checked']
    search_fields = ['deployment__name']
    readonly_fields = ['created_at', 'updated_at', 'last_checked']
    ordering = ['-last_checked']

    def status_badge(self, obj):
        """Display status with color badge."""
        colors = {
            'running': 'green',
            'stopped': 'gray',
            'failed': 'red',
            'starting': 'orange',
            'stopping': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def uptime_display(self, obj):
        """Display uptime in human-readable format."""
        if obj.uptime_seconds:
            hours = obj.uptime_seconds // 3600
            minutes = (obj.uptime_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        return "-"
    uptime_display.short_description = 'Uptime'


@admin.register(ResourceUsage)
class ResourceUsageAdmin(admin.ModelAdmin):
    """Admin for resource usage records."""

    list_display = ['created_at', 'cpu_percent', 'memory_percent', 'disk_percent', 'load_average_1m']
    list_filter = ['created_at']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        """Disable manual addition."""
        return False


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    """Admin for alerts."""

    list_display = ['severity_badge', 'title', 'alert_type', 'deployment', 'acknowledged_badge', 'created_at']
    list_filter = ['severity', 'alert_type', 'is_acknowledged', 'created_at']
    search_fields = ['title', 'message']
    readonly_fields = ['created_at', 'updated_at', 'acknowledged_at']
    ordering = ['-created_at']
    actions = ['acknowledge_alerts']

    def severity_badge(self, obj):
        """Display severity with color badge."""
        colors = {
            'info': 'blue',
            'warning': 'orange',
            'error': 'red',
            'critical': 'darkred',
        }
        color = colors.get(obj.severity, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_severity_display()
        )
    severity_badge.short_description = 'Severity'

    def acknowledged_badge(self, obj):
        """Display acknowledgement status."""
        if obj.is_acknowledged:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    acknowledged_badge.short_description = 'Ack'

    def acknowledge_alerts(self, request, queryset):
        """Bulk acknowledge alerts."""
        count = 0
        for alert in queryset:
            if not alert.is_acknowledged:
                alert.acknowledge()
                count += 1
        self.message_user(request, f"{count} alerts acknowledged")
    acknowledge_alerts.short_description = "Acknowledge selected alerts"


@admin.register(HealthCheck)
class HealthCheckAdmin(admin.ModelAdmin):
    """Admin for health checks."""

    list_display = ['deployment', 'healthy_badge', 'status_code', 'response_time_ms', 'created_at']
    list_filter = ['is_healthy', 'created_at']
    search_fields = ['deployment__name', 'url']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def healthy_badge(self, obj):
        """Display health status."""
        if obj.is_healthy:
            return format_html('<span style="color: green; font-weight: bold;">✓ Healthy</span>')
        return format_html('<span style="color: red; font-weight: bold;">✗ Unhealthy</span>')
    healthy_badge.short_description = 'Health'

    def has_add_permission(self, request):
        """Disable manual addition."""
        return False


@admin.register(RestartPolicy)
class RestartPolicyAdmin(admin.ModelAdmin):
    """Admin for restart policies."""

    list_display = ['deployment', 'policy_type', 'enabled_badge', 'max_restarts', 'time_window_minutes', 'updated_at']
    list_filter = ['policy_type', 'enabled', 'updated_at']
    search_fields = ['deployment__name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Settings', {
            'fields': ('deployment', 'policy_type', 'enabled')
        }),
        ('Restart Limits', {
            'fields': ('max_restarts', 'time_window_minutes', 'cooldown_minutes')
        }),
        ('Backoff Configuration', {
            'fields': ('initial_delay_seconds', 'max_delay_seconds', 'backoff_multiplier'),
            'classes': ('collapse',)
        }),
        ('Health Check Integration', {
            'fields': ('require_health_check', 'health_check_retries'),
            'classes': ('collapse',)
        }),
        ('Notifications', {
            'fields': ('notify_on_restart', 'notify_on_max_restarts'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def enabled_badge(self, obj):
        """Display enabled status."""
        if obj.enabled:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    enabled_badge.short_description = 'Enabled'


@admin.register(RestartAttempt)
class RestartAttemptAdmin(admin.ModelAdmin):
    """Admin for restart attempts."""

    list_display = ['deployment', 'attempt_number', 'success_badge', 'delay_seconds', 'reason', 'started_at']
    list_filter = ['success', 'started_at']
    search_fields = ['deployment__name', 'reason', 'error_message']
    readonly_fields = ['created_at', 'updated_at', 'started_at', 'completed_at']
    ordering = ['-started_at']

    def success_badge(self, obj):
        """Display success status."""
        if obj.success:
            return format_html('<span style="color: green; font-weight: bold;">✓ Success</span>')
        return format_html('<span style="color: red; font-weight: bold;">✗ Failed</span>')
    success_badge.short_description = 'Result'

    def has_add_permission(self, request):
        """Disable manual addition."""
        return False
