"""
Django admin configuration for automation app.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Workflow,
    WorkflowNode,
    WorkflowConnection,
    WorkflowExecution,
    WorkflowTemplate,
    DataSourceCredential
)


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'status_badge', 'trigger_type', 'total_executions', 'success_rate', 'last_executed_at', 'created_at']
    list_filter = ['status', 'trigger_type', 'created_at']
    search_fields = ['name', 'description', 'owner__username']
    readonly_fields = ['total_executions', 'successful_executions', 'failed_executions', 'last_executed_at', 'average_duration_ms', 'created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'owner', 'status', 'trigger_type')
        }),
        ('Schedule', {
            'fields': ('schedule_cron',),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('timeout_seconds', 'retry_on_failure', 'max_retries')
        }),
        ('Statistics', {
            'fields': ('total_executions', 'successful_executions', 'failed_executions', 'last_executed_at', 'average_duration_ms'),
            'classes': ('collapse',)
        }),
        ('Canvas Data', {
            'fields': ('canvas_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        colors = {
            'draft': '#6c757d',
            'active': '#28a745',
            'paused': '#ffc107',
            'disabled': '#dc3545'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def success_rate(self, obj):
        if obj.total_executions == 0:
            return '—'
        rate = (obj.successful_executions / obj.total_executions) * 100
        color = '#28a745' if rate >= 80 else '#ffc107' if rate >= 50 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color,
            rate
        )
    success_rate.short_description = 'Success Rate'


@admin.register(WorkflowNode)
class WorkflowNodeAdmin(admin.ModelAdmin):
    list_display = ['label', 'workflow', 'node_type', 'node_id', 'enabled', 'created_at']
    list_filter = ['node_type', 'enabled', 'workflow']
    search_fields = ['label', 'node_id', 'workflow__name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('workflow', 'node_id', 'node_type', 'label', 'enabled')
        }),
        ('Position', {
            'fields': ('position_x', 'position_y')
        }),
        ('Configuration', {
            'fields': ('config', 'addon')
        }),
        ('Execution Settings', {
            'fields': ('timeout_seconds', 'retry_on_failure', 'max_retries'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(WorkflowConnection)
class WorkflowConnectionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'workflow', 'source_handle', 'target_handle', 'created_at']
    list_filter = ['workflow']
    search_fields = ['workflow__name', 'source_node__label', 'target_node__label']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WorkflowExecution)
class WorkflowExecutionAdmin(admin.ModelAdmin):
    list_display = ['workflow', 'status_badge', 'trigger_type', 'triggered_by', 'started_at', 'duration_display']
    list_filter = ['status', 'trigger_type', 'started_at']
    search_fields = ['workflow__name', 'triggered_by__username', 'error_message']
    readonly_fields = ['started_at', 'completed_at', 'duration_ms']
    date_hierarchy = 'started_at'

    fieldsets = (
        ('Execution Info', {
            'fields': ('workflow', 'status', 'started_at', 'completed_at', 'duration_ms')
        }),
        ('Trigger', {
            'fields': ('trigger_type', 'triggered_by', 'trigger_data')
        }),
        ('Data', {
            'fields': ('input_data', 'output_data'),
            'classes': ('collapse',)
        }),
        ('Errors', {
            'fields': ('error_message', 'error_traceback'),
            'classes': ('collapse',)
        }),
        ('Node Logs', {
            'fields': ('node_logs',),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        colors = {
            'pending': '#6c757d',
            'running': '#17a2b8',
            'success': '#28a745',
            'failed': '#dc3545',
            'cancelled': '#6c757d',
            'timeout': '#ffc107'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def duration_display(self, obj):
        if not obj.duration_ms:
            return '—'
        seconds = obj.duration_ms / 1000
        if seconds < 60:
            return f'{seconds:.1f}s'
        minutes = seconds / 60
        return f'{minutes:.1f}m'
    duration_display.short_description = 'Duration'


@admin.register(WorkflowTemplate)
class WorkflowTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'author', 'is_official', 'is_public', 'usage_count', 'created_at']
    list_filter = ['category', 'is_official', 'is_public', 'created_at']
    search_fields = ['name', 'description', 'author__username']
    readonly_fields = ['usage_count', 'created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category', 'thumbnail_url')
        }),
        ('Settings', {
            'fields': ('author', 'is_official', 'is_public')
        }),
        ('Template Data', {
            'fields': ('workflow_data',)
        }),
        ('Statistics', {
            'fields': ('usage_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DataSourceCredential)
class DataSourceCredentialAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'provider', 'is_valid', 'last_validated_at', 'expires_at']
    list_filter = ['provider', 'is_valid', 'created_at']
    search_fields = ['name', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'last_validated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'provider', 'name')
        }),
        ('Credentials', {
            'fields': ('credentials',),
            'description': 'Credentials are encrypted in the database'
        }),
        ('Status', {
            'fields': ('is_valid', 'last_validated_at', 'expires_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
