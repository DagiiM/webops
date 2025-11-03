from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.common.models import BaseModel
from typing import Dict

User = get_user_model()


class Addon(BaseModel):
    """Represents a discovered addon from addon.yaml manifest.

    Metrics fields help monitor hook execution health and performance.
    """

    name = models.CharField(max_length=200, unique=True)
    version = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    author = models.CharField(max_length=200, blank=True)
    license = models.CharField(max_length=100, blank=True)

    enabled = models.BooleanField(default=True)
    django_app = models.CharField(max_length=255, blank=True)
    cli_entrypoint = models.CharField(max_length=255, blank=True)
    manifest_path = models.CharField(max_length=500)

    # simple JSON blob for capabilities and settings schema
    capabilities = models.JSONField(default=list, blank=True)
    settings_schema = models.JSONField(default=dict, blank=True)

    # Metrics/state fields
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_duration_ms = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.version})"


class SystemAddon(BaseModel):
    """
    Represents a system-level (bash) addon.

    Tracks installation status, configuration, and health of infrastructure
    addons like PostgreSQL, Kubernetes, etcd, etc.
    """

    STATUS_CHOICES = [
        ('not_installed', 'Not Installed'),
        ('installing', 'Installing'),
        ('installed', 'Installed'),
        ('configuring', 'Configuring'),
        ('failed', 'Failed'),
        ('uninstalling', 'Uninstalling'),
        ('degraded', 'Degraded'),
    ]

    HEALTH_CHOICES = [
        ('healthy', 'Healthy'),
        ('unhealthy', 'Unhealthy'),
        ('degraded', 'Degraded'),
        ('unknown', 'Unknown'),
    ]

    # Addon identification
    name = models.CharField(max_length=100, unique=True, db_index=True)
    display_name = models.CharField(max_length=200)
    script_path = models.CharField(max_length=500)
    version = models.CharField(max_length=50, blank=True)

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='not_installed',
        db_index=True
    )
    health = models.CharField(
        max_length=20,
        choices=HEALTH_CHOICES,
        default='unknown'
    )

    # Configuration
    config = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True, db_index=True)

    # Metadata
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, default='general')
    depends_on = models.JSONField(default=list, blank=True)
    provides = models.JSONField(default=list, blank=True)
    conflicts_with = models.JSONField(default=list, blank=True)

    # Installation tracking
    installed_at = models.DateTimeField(null=True, blank=True)
    installed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='installed_system_addons'
    )

    # Execution tracking
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    last_duration_ms = models.IntegerField(null=True, blank=True)

    # Statistics
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'system_addons'
        ordering = ['display_name']
        verbose_name = 'System Addon'
        verbose_name_plural = 'System Addons'

    def __str__(self) -> str:
        return f"{self.display_name} ({self.status})"

    def mark_installing(self, user: User = None) -> None:
        """Mark addon as installing."""
        self.status = 'installing'
        if user:
            self.installed_by = user
        self.save()

    def mark_installed(self, version: str = None) -> None:
        """Mark addon as successfully installed."""
        self.status = 'installed'
        self.health = 'healthy'
        if version:
            self.version = version
        self.installed_at = timezone.now()
        self.last_success_at = timezone.now()
        self.success_count += 1
        self.save()

    def mark_failed(self, error: str) -> None:
        """Mark addon installation as failed."""
        self.status = 'failed'
        self.health = 'unhealthy'
        self.last_error = error
        self.failure_count += 1
        self.save()

    def mark_uninstalling(self) -> None:
        """Mark addon as uninstalling."""
        self.status = 'uninstalling'
        self.save()

    def mark_uninstalled(self) -> None:
        """Mark addon as uninstalled."""
        self.status = 'not_installed'
        self.health = 'unknown'
        self.installed_at = None
        self.version = ''
        self.save()

    def update_health(self, health: str) -> None:
        """Update addon health status."""
        self.health = health
        if health == 'healthy':
            self.status = 'installed'
        elif health in ['unhealthy', 'degraded']:
            self.status = 'degraded'
        self.save()


class AddonExecution(BaseModel):
    """
    Tracks individual addon operation executions.

    Provides audit trail and debugging information for addon operations.
    """

    OPERATION_CHOICES = [
        ('install', 'Install'),
        ('uninstall', 'Uninstall'),
        ('configure', 'Configure'),
        ('health_check', 'Health Check'),
        ('validate', 'Validate'),
        ('status', 'Status Check'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
    ]

    system_addon = models.ForeignKey(
        SystemAddon,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    operation = models.CharField(max_length=20, choices=OPERATION_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )

    # Execution details
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)

    # Request context
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='addon_executions'
    )
    input_data = models.JSONField(default=dict, blank=True)

    # Results
    output_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    stdout = models.TextField(blank=True)
    stderr = models.TextField(blank=True)

    # Async task tracking
    celery_task_id = models.CharField(max_length=255, blank=True, db_index=True)

    class Meta:
        db_table = 'addon_executions'
        ordering = ['-started_at']
        verbose_name = 'Addon Execution'
        verbose_name_plural = 'Addon Executions'
        indexes = [
            models.Index(fields=['system_addon', '-started_at']),
            models.Index(fields=['status', '-started_at']),
        ]

    def __str__(self) -> str:
        return f"{self.system_addon.name} - {self.operation} ({self.status})"

    def mark_running(self, celery_task_id: str = None) -> None:
        """Mark execution as running."""
        self.status = 'running'
        if celery_task_id:
            self.celery_task_id = celery_task_id
        self.save()

    def mark_success(self, output: Dict = None) -> None:
        """Mark execution as successful."""
        self.status = 'success'
        self.completed_at = timezone.now()
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)
        if output:
            self.output_data = output
        self.save()

        # Update addon statistics
        self.system_addon.last_success_at = timezone.now()
        self.system_addon.last_duration_ms = self.duration_ms
        self.system_addon.success_count += 1
        self.system_addon.save()

    def mark_failed(self, error: str, stderr: str = None) -> None:
        """Mark execution as failed."""
        self.status = 'failed'
        self.completed_at = timezone.now()
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)
        self.error_message = error
        if stderr:
            self.stderr = stderr
        self.save()

        # Update addon statistics
        self.system_addon.last_error = error
        self.system_addon.last_duration_ms = self.duration_ms
        self.system_addon.failure_count += 1
        self.system_addon.save()