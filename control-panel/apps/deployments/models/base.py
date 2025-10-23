"""
Base deployment models for WebOps.

This module contains the base models shared by all deployment types.
"""

from django.db import models
from django.contrib.auth.models import User
from apps.core.common.models import BaseModel


class BaseDeployment(BaseModel):
    """
    Base deployment model with common attributes for all deployment types.

    This is NOT an abstract model - it creates a real table that stores
    common fields. ApplicationDeployment and LLMDeployment inherit from this.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        BUILDING = 'building', 'Building'
        RUNNING = 'running', 'Running'
        STOPPED = 'stopped', 'Stopped'
        FAILED = 'failed', 'Failed'

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Unique deployment name (used for systemd service, nginx config)'
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    port = models.IntegerField(
        unique=True,
        null=True,
        blank=True,
        help_text='Allocated port for this deployment'
    )
    
    domain = models.CharField(
        max_length=255,
        blank=True,
        help_text='Custom domain for this deployment'
    )

    deployed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='deployments'
    )

    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"

    class Meta:
        db_table = 'base_deployments'
        verbose_name = 'Base Deployment'
        verbose_name_plural = 'Base Deployments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['status']),
            models.Index(fields=['deployed_by', '-created_at']),
        ]

    def get_service_manager(self):
        """Factory method to get the appropriate service for this deployment."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_service_manager()"
        )

    def get_deployment_type(self) -> str:
        """Return the deployment type ('application' or 'llm')."""
        if hasattr(self, 'applicationdeployment'):
            return 'application'
        elif hasattr(self, 'llmdeployment'):
            return 'llm'
        return 'unknown'


class DeploymentLog(BaseModel):
    """Deployment operation logs."""

    class Level(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'
        SUCCESS = 'success', 'Success'

    deployment = models.ForeignKey(
        BaseDeployment,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    level = models.CharField(
        max_length=10,
        choices=Level.choices,
        default=Level.INFO
    )
    message = models.TextField()

    def __str__(self) -> str:
        return f"[{self.level}] {self.deployment.name}: {self.message[:50]}"

    class Meta:
        db_table = 'deployment_logs'
        verbose_name = 'Deployment Log'
        verbose_name_plural = 'Deployment Logs'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['deployment', '-created_at']),
            models.Index(fields=['level', '-created_at']),
        ]


class HealthCheckRecord(BaseModel):
    """Health check results for deployments."""

    deployment = models.ForeignKey(
        BaseDeployment,
        on_delete=models.CASCADE,
        related_name='health_check_records'
    )
    overall_healthy = models.BooleanField(default=True)
    process_healthy = models.BooleanField(default=True)
    http_healthy = models.BooleanField(default=True)
    resources_healthy = models.BooleanField(default=True)
    disk_healthy = models.BooleanField(default=True)

    cpu_percent = models.FloatField(null=True, blank=True)
    memory_mb = models.FloatField(null=True, blank=True)
    disk_free_gb = models.FloatField(null=True, blank=True)
    response_time_ms = models.FloatField(null=True, blank=True)
    http_status_code = models.IntegerField(null=True, blank=True)

    results = models.JSONField(default=dict)

    auto_restart_attempted = models.BooleanField(default=False)
    auto_restart_successful = models.BooleanField(null=True, blank=True)

    def __str__(self) -> str:
        status = "✓ Healthy" if self.overall_healthy else "✗ Unhealthy"
        return f"{self.deployment.name} - {status} at {self.created_at}"

    class Meta:
        db_table = 'health_check_records'
        verbose_name = 'Health Check Record'
        verbose_name_plural = 'Health Check Records'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['deployment', '-created_at']),
            models.Index(fields=['overall_healthy', '-created_at']),
        ]
