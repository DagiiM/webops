"""Django admin configuration for Deployments app."""

from django.contrib import admin
from .models import (
    BaseDeployment,
    ApplicationDeployment,
    LLMDeployment,
    DeploymentLog,
    HealthCheckRecord,
)


@admin.register(BaseDeployment)
class BaseDeploymentAdmin(admin.ModelAdmin):
    """Admin for BaseDeployment model."""
    list_display = ['name', 'status', 'deployed_by', 'port', 'domain', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'domain']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ApplicationDeployment)
class ApplicationDeploymentAdmin(admin.ModelAdmin):
    """Admin for ApplicationDeployment model."""
    list_display = ['name', 'status', 'project_type', 'repo_url', 'branch', 'domain', 'deployed_by', 'created_at']
    list_filter = ['status', 'project_type', 'use_docker', 'created_at']
    search_fields = ['name', 'repo_url', 'domain', 'branch']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'deployed_by', 'status', 'port', 'domain')
        }),
        ('Repository', {
            'fields': ('project_type', 'repo_url', 'branch', 'env_vars')
        }),
        ('Docker Configuration', {
            'fields': (
                'use_docker',
                'auto_generate_dockerfile',
                'dockerfile_path',
                'docker_compose_path',
                'docker_image_name',
                'docker_build_args',
                'docker_env_vars',
                'docker_volumes',
                'docker_ports',
                'docker_network_mode'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )


@admin.register(LLMDeployment)
class LLMDeploymentAdmin(admin.ModelAdmin):
    """Admin for LLMDeployment model."""
    list_display = ['name', 'status', 'model_name', 'tensor_parallel_size', 'quantization', 'deployed_by', 'created_at']
    list_filter = ['status', 'quantization', 'dtype', 'download_completed', 'created_at']
    search_fields = ['name', 'model_name', 'domain']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'deployed_by', 'status', 'port', 'domain')
        }),
        ('Model Configuration', {
            'fields': (
                'model_name',
                'tensor_parallel_size',
                'gpu_memory_utilization',
                'max_model_len',
                'quantization',
                'dtype',
                'enable_trust_remote_code'
            )
        }),
        ('Advanced vLLM Settings', {
            'fields': ('vllm_args', 'model_size_gb', 'download_completed'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )


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