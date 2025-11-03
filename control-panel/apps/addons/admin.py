"""
Django admin interface for Addon management.

Provides a simple interface to enable/disable addons and view their metrics.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Addon, SystemAddon, AddonExecution


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


@admin.register(SystemAddon)
class SystemAddonAdmin(admin.ModelAdmin):
    """Admin interface for System Addon management."""

    list_display = [
        'display_name',
        'name',
        'version',
        'status_display',
        'health_display',
        'enabled_status',
        'category',
        'success_rate',
        'installed_at',
    ]

    list_filter = ['status', 'health', 'enabled', 'category', 'installed_at']
    search_fields = ['name', 'display_name', 'description']
    readonly_fields = [
        'name',
        'script_path',
        'version',
        'description',
        'category',
        'depends_on',
        'provides',
        'conflicts_with',
        'installed_at',
        'installed_by',
        'last_run_at',
        'last_success_at',
        'last_error',
        'last_duration_ms',
        'success_count',
        'failure_count',
        'created_at',
        'updated_at',
        'executions_link',
    ]

    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'display_name', 'version', 'script_path', 'description']
        }),
        ('Status', {
            'fields': ['status', 'health', 'enabled']
        }),
        ('Dependencies', {
            'fields': ['category', 'depends_on', 'provides', 'conflicts_with'],
            'classes': ['collapse']
        }),
        ('Configuration', {
            'fields': ['config'],
            'classes': ['collapse']
        }),
        ('Installation', {
            'fields': ['installed_at', 'installed_by']
        }),
        ('Execution Statistics', {
            'fields': [
                ('success_count', 'failure_count'),
                ('last_run_at', 'last_success_at'),
                'last_duration_ms',
                'last_error',
                'executions_link'
            ]
        }),
        ('Timestamps', {
            'fields': [('created_at', 'updated_at')],
            'classes': ['collapse']
        }),
    ]

    def status_display(self, obj):
        """Display status with color coding."""
        colors = {
            'not_installed': 'gray',
            'installing': 'blue',
            'installed': 'green',
            'configuring': 'orange',
            'failed': 'red',
            'uninstalling': 'orange',
            'degraded': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'

    def health_display(self, obj):
        """Display health with color coding."""
        colors = {
            'healthy': 'green',
            'unhealthy': 'red',
            'degraded': 'orange',
            'unknown': 'gray',
        }
        icons = {
            'healthy': '✓',
            'unhealthy': '✗',
            'degraded': '⚠',
            'unknown': '?',
        }
        color = colors.get(obj.health, 'gray')
        icon = icons.get(obj.health, '?')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            obj.get_health_display()
        )
    health_display.short_description = 'Health'

    def enabled_status(self, obj):
        """Display enabled status."""
        if obj.enabled:
            return format_html('<span style="color: green;">✓ Enabled</span>')
        return format_html('<span style="color: red;">✗ Disabled</span>')
    enabled_status.short_description = 'Enabled'

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

    def executions_link(self, obj):
        """Link to execution history."""
        if obj.pk:
            url = reverse('admin:addons_addonexecution_changelist') + f'?system_addon__id__exact={obj.pk}'
            count = obj.executions.count()
            return mark_safe(f'<a href="{url}">View {count} execution(s)</a>')
        return '-'
    executions_link.short_description = 'Execution History'

    def has_add_permission(self, request):
        """System addons are discovered, not manually created."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion from admin."""
        return False

    def get_actions(self, request):
        """Custom actions for system addons."""
        actions = super().get_actions(request)

        def sync_status(modeladmin, request, queryset):
            """Sync status from bash scripts."""
            from .tasks import sync_system_addon_status
            count = 0
            for addon in queryset:
                sync_system_addon_status.delay(addon.id)
                count += 1
            modeladmin.message_user(
                request,
                f'Status sync started for {count} addon(s)'
            )
        sync_status.short_description = 'Sync status from system'

        def run_health_check(modeladmin, request, queryset):
            """Run health checks."""
            from .tasks import health_check_system_addons
            health_check_system_addons.delay()
            modeladmin.message_user(
                request,
                'Health check task started for all addons'
            )
        run_health_check.short_description = 'Run health checks'

        actions['sync_status'] = (sync_status, 'sync_status', sync_status.short_description)
        actions['run_health_check'] = (run_health_check, 'run_health_check', run_health_check.short_description)

        return actions


@admin.register(AddonExecution)
class AddonExecutionAdmin(admin.ModelAdmin):
    """Admin interface for Addon Execution history."""

    list_display = [
        'system_addon',
        'operation',
        'status_display',
        'requested_by',
        'started_at',
        'duration_display',
    ]

    list_filter = ['operation', 'status', 'started_at']
    search_fields = ['system_addon__name', 'system_addon__display_name', 'error_message']
    readonly_fields = [
        'system_addon',
        'operation',
        'status',
        'started_at',
        'completed_at',
        'duration_ms',
        'requested_by',
        'input_data',
        'output_data',
        'error_message',
        'stdout',
        'stderr',
        'celery_task_id',
    ]

    fieldsets = [
        ('Execution Info', {
            'fields': ['system_addon', 'operation', 'status', 'requested_by']
        }),
        ('Timing', {
            'fields': ['started_at', 'completed_at', 'duration_ms', 'celery_task_id']
        }),
        ('Input/Output', {
            'fields': ['input_data', 'output_data'],
            'classes': ['collapse']
        }),
        ('Error Details', {
            'fields': ['error_message', 'stderr', 'stdout'],
            'classes': ['collapse']
        }),
    ]

    def status_display(self, obj):
        """Display status with color coding."""
        colors = {
            'pending': 'gray',
            'running': 'blue',
            'success': 'green',
            'failed': 'red',
            'timeout': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'

    def duration_display(self, obj):
        """Display duration in human-readable format."""
        if obj.duration_ms is None:
            return '-'

        if obj.duration_ms < 1000:
            return f'{obj.duration_ms}ms'
        elif obj.duration_ms < 60000:
            return f'{obj.duration_ms / 1000:.1f}s'
        else:
            minutes = obj.duration_ms / 60000
            return f'{minutes:.1f}m'
    duration_display.short_description = 'Duration'

    def has_add_permission(self, request):
        """Executions are created by the system."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion of old execution records."""
        return True