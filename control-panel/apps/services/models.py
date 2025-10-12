"""
Services monitoring models for WebOps.

Reference: CLAUDE.md "Database Models" section
Architecture: System health monitoring, service status tracking, resource usage
"""

from django.db import models
from django.utils import timezone
from apps.core.models import BaseModel
from apps.deployments.models import Deployment


class ServiceStatus(BaseModel):
    """Track status of a deployed service."""

    class Status(models.TextChoices):
        RUNNING = 'running', 'Running'
        STOPPED = 'stopped', 'Stopped'
        FAILED = 'failed', 'Failed'
        STARTING = 'starting', 'Starting'
        STOPPING = 'stopping', 'Stopping'

    deployment = models.ForeignKey(
        Deployment,
        on_delete=models.CASCADE,
        related_name='service_statuses'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.STOPPED
    )
    pid = models.IntegerField(null=True, blank=True)
    memory_mb = models.FloatField(default=0.0)
    cpu_percent = models.FloatField(default=0.0)
    uptime_seconds = models.IntegerField(default=0)
    restart_count = models.IntegerField(default=0)
    last_checked = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'service_status'
        verbose_name = 'Service Status'
        verbose_name_plural = 'Service Statuses'
        ordering = ['-last_checked']

    def __str__(self) -> str:
        return f"{self.deployment.name} - {self.status}"


class ResourceUsage(BaseModel):
    """System-wide resource usage snapshots."""

    cpu_percent = models.FloatField()
    memory_percent = models.FloatField()
    memory_used_mb = models.IntegerField()
    memory_total_mb = models.IntegerField()
    disk_percent = models.FloatField()
    disk_used_gb = models.FloatField()
    disk_total_gb = models.FloatField()
    network_sent_mb = models.FloatField(default=0.0)
    network_recv_mb = models.FloatField(default=0.0)
    active_connections = models.IntegerField(default=0)
    load_average_1m = models.FloatField(default=0.0)
    load_average_5m = models.FloatField(default=0.0)
    load_average_15m = models.FloatField(default=0.0)

    class Meta:
        db_table = 'resource_usage'
        verbose_name = 'Resource Usage'
        verbose_name_plural = 'Resource Usage'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
        ]

    def __str__(self) -> str:
        return f"Resources @ {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"


class Alert(BaseModel):
    """System alerts for monitoring thresholds."""

    class Severity(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'
        CRITICAL = 'critical', 'Critical'

    class AlertType(models.TextChoices):
        CPU_HIGH = 'cpu_high', 'High CPU Usage'
        MEMORY_HIGH = 'memory_high', 'High Memory Usage'
        DISK_HIGH = 'disk_high', 'High Disk Usage'
        SERVICE_DOWN = 'service_down', 'Service Down'
        DEPLOYMENT_FAILED = 'deployment_failed', 'Deployment Failed'
        SSL_EXPIRING = 'ssl_expiring', 'SSL Certificate Expiring'
        DATABASE_ERROR = 'database_error', 'Database Error'

    alert_type = models.CharField(max_length=50, choices=AlertType.choices)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    deployment = models.ForeignKey(
        Deployment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='alerts'
    )

    class Meta:
        db_table = 'alerts'
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_acknowledged']),
            models.Index(fields=['severity']),
        ]

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.title}"

    def acknowledge(self) -> None:
        """Mark alert as acknowledged."""
        self.is_acknowledged = True
        self.acknowledged_at = timezone.now()
        self.save()


class HealthCheck(BaseModel):
    """Periodic health check results."""

    deployment = models.ForeignKey(
        Deployment,
        on_delete=models.CASCADE,
        related_name='health_checks'
    )
    url = models.URLField()
    status_code = models.IntegerField()
    response_time_ms = models.IntegerField()
    is_healthy = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = 'health_checks'
        verbose_name = 'Health Check'
        verbose_name_plural = 'Health Checks'
        ordering = ['-created_at']

    def __str__(self) -> str:
        status = "✓" if self.is_healthy else "✗"
        return f"{status} {self.deployment.name} - {self.status_code}"
