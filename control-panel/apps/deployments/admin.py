"""Django admin configuration for Deployments app."""

from django.contrib import admin
from .models import Deployment, DeploymentLog, HealthCheckRecord


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'project_type', 'domain', 'deployed_by', 'created_at']
    list_filter = ['status', 'project_type', 'created_at']
    search_fields = ['name', 'repo_url', 'domain']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DeploymentLog)
class DeploymentLogAdmin(admin.ModelAdmin):
    list_display = ['deployment', 'level', 'message', 'created_at']
    list_filter = ['level', 'created_at']
    search_fields = ['message', 'deployment__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(HealthCheckRecord)
class HealthCheckRecordAdmin(admin.ModelAdmin):
    list_display = [
        'deployment',
        'overall_healthy',
        'process_healthy',
        'http_healthy',
        'resources_healthy',
        'cpu_percent',
        'memory_mb',
        'response_time_ms',
        'created_at'
    ]
    list_filter = [
        'overall_healthy',
        'process_healthy',
        'http_healthy',
        'resources_healthy',
        'disk_healthy',
        'auto_restart_attempted',
        'created_at'
    ]
    search_fields = ['deployment__name']
    readonly_fields = ['created_at', 'updated_at', 'results']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Deployment', {
            'fields': ('deployment',)
        }),
        ('Health Status', {
            'fields': (
                'overall_healthy',
                'process_healthy',
                'http_healthy',
                'resources_healthy',
                'disk_healthy'
            )
        }),
        ('Metrics', {
            'fields': (
                'cpu_percent',
                'memory_mb',
                'disk_free_gb',
                'response_time_ms',
                'http_status_code'
            )
        }),
        ('Auto-Restart', {
            'fields': ('auto_restart_attempted', 'auto_restart_successful')
        }),
        ('Detailed Results', {
            'fields': ('results',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )