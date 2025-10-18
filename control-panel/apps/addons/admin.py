"""
Django admin interface for Addon management.

Provides a simple interface to enable/disable addons and view their metrics.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Addon


@admin.register(Addon)
class AddonAdmin(admin.ModelAdmin):
    """Admin interface for Addon model."""

    list_display = [
        'name',
        'version',
        'enabled_status',
        'capabilities_display',
        'success_rate',
        'last_run_display',
        'created_at',
    ]

    list_filter = ['enabled', 'created_at']
    search_fields = ['name', 'description', 'author']
    readonly_fields = [
        'name',
        'version',
        'description',
        'author',
        'license',
        'manifest_path',
        'capabilities',
        'settings_schema',
        'success_count',
        'failure_count',
        'last_run_at',
        'last_success_at',
        'last_duration_ms',
        'last_error',
        'created_at',
        'updated_at',
    ]

    fields = [
        'name',
        'version',
        'enabled',
        'description',
        'author',
        'license',
        'manifest_path',
        'capabilities',
        'settings_schema',
        ('success_count', 'failure_count'),
        ('last_run_at', 'last_success_at'),
        'last_duration_ms',
        'last_error',
        ('created_at', 'updated_at'),
    ]

    def enabled_status(self, obj):
        """Display enabled status with color."""
        if obj.enabled:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Enabled</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Disabled</span>'
            )
    enabled_status.short_description = 'Status'

    def capabilities_display(self, obj):
        """Display capabilities as comma-separated list."""
        if obj.capabilities:
            return ', '.join(obj.capabilities)
        return '-'
    capabilities_display.short_description = 'Capabilities'

    def success_rate(self, obj):
        """Calculate and display success rate."""
        total = obj.success_count + obj.failure_count
        if total == 0:
            return '-'

        rate = (obj.success_count / total) * 100
        color = 'green' if rate >= 90 else 'orange' if rate >= 70 else 'red'

        return format_html(
            '<span style="color: {};">{:.1f}% ({}/{})</span>',
            color,
            rate,
            obj.success_count,
            total
        )
    success_rate.short_description = 'Success Rate'

    def last_run_display(self, obj):
        """Display last run time."""
        if obj.last_run_at:
            return obj.last_run_at.strftime('%Y-%m-%d %H:%M:%S')
        return 'Never'
    last_run_display.short_description = 'Last Run'

    def has_add_permission(self, request):
        """Prevent manual addon creation (addons are discovered)."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent addon deletion from admin (managed by discovery)."""
        return False

    def get_actions(self, request):
        """Add custom actions for enabling/disabling addons."""
        actions = super().get_actions(request)

        def enable_addons(modeladmin, request, queryset):
            count = queryset.update(enabled=True)
            modeladmin.message_user(
                request,
                f'{count} addon(s) enabled. Restart WebOps for changes to take effect.'
            )
        enable_addons.short_description = 'Enable selected addons'

        def disable_addons(modeladmin, request, queryset):
            count = queryset.update(enabled=False)
            modeladmin.message_user(
                request,
                f'{count} addon(s) disabled. Restart WebOps for changes to take effect.'
            )
        disable_addons.short_description = 'Disable selected addons'

        actions['enable_addons'] = (enable_addons, 'enable_addons', enable_addons.short_description)
        actions['disable_addons'] = (disable_addons, 'disable_addons', disable_addons.short_description)

        return actions