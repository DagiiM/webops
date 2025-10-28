"""
Services monitoring models for WebOps.

"Database Models" section
Architecture: System health monitoring, service status tracking, resource usage
"""

from django.db import models
from django.utils import timezone
from apps.core.common.models import BaseModel
from apps.deployments.models import BaseDeployment


class ServiceStatus(BaseModel):
    """Track status of a deployed service."""

    class Status(models.TextChoices):
        RUNNING = 'running', 'Running'
        STOPPED = 'stopped', 'Stopped'
        FAILED = 'failed', 'Failed'
        STARTING = 'starting', 'Starting'
        STOPPING = 'stopping', 'Stopping'

    deployment = models.OneToOneField(
        BaseDeployment,
        on_delete=models.CASCADE,
        related_name='service_status'
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
        BaseDeployment,
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
        BaseDeployment,
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


class SSLConfiguration(BaseModel):
    """SSL certificate and configuration management for deployments."""

    class SSLStatus(models.TextChoices):
        DISABLED = 'disabled', 'Disabled'
        ENABLED = 'enabled', 'Enabled'
        EXPIRING = 'expiring', 'Expiring Soon'
        EXPIRED = 'expired', 'Expired'
        INVALID = 'invalid', 'Invalid Certificate'

    class CertificateType(models.TextChoices):
        SELF_SIGNED = 'self_signed', 'Self-Signed'
        LETS_ENCRYPT = 'lets_encrypt', "Let's Encrypt"
        CUSTOM = 'custom', 'Custom Certificate'
        WILDCARD = 'wildcard', 'Wildcard Certificate'

    deployment = models.OneToOneField(
        BaseDeployment,
        on_delete=models.CASCADE,
        related_name='ssl_config'
    )
    ssl_enabled = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=SSLStatus.choices,
        default=SSLStatus.DISABLED
    )
    certificate_type = models.CharField(
        max_length=20,
        choices=CertificateType.choices,
        default=CertificateType.SELF_SIGNED
    )
    domain = models.CharField(max_length=255, blank=True)
    certificate_file = models.FileField(
        upload_to='ssl/certificates/',
        blank=True,
        null=True
    )
    private_key_file = models.FileField(
        upload_to='ssl/private_keys/',
        blank=True,
        null=True
    )
    certificate_chain_file = models.FileField(
        upload_to='ssl/chains/',
        blank=True,
        null=True
    )
    certificate_expires_at = models.DateTimeField(null=True, blank=True)
    certificate_issuer = models.CharField(max_length=255, blank=True)
    certificate_subject = models.CharField(max_length=255, blank=True)
    encryption_protocol = models.CharField(
        max_length=20,
        default='TLSv1.3',
        choices=[
            ('TLSv1.3', 'TLS 1.3'),
            ('TLSv1.2', 'TLS 1.2'),
            ('TLSv1.1', 'TLS 1.1'),
            ('TLSv1.0', 'TLS 1.0'),
        ]
    )
    cipher_suite = models.CharField(
        max_length=50,
        default='ECDHE-RSA-AES256-GCM-SHA384',
        help_text="SSL cipher suite configuration"
    )
    hsts_enabled = models.BooleanField(
        default=True,
        help_text="HTTP Strict Transport Security"
    )
    hsts_max_age = models.IntegerField(
        default=31536000,  # 1 year in seconds
        help_text="HSTS max-age in seconds"
    )
    auto_redirect_http = models.BooleanField(
        default=True,
        help_text="Automatically redirect HTTP to HTTPS"
    )
    validation_error = models.TextField(blank=True)
    last_validation_at = models.DateTimeField(null=True, blank=True)
    lets_encrypt_email = models.EmailField(blank=True)
    auto_renew = models.BooleanField(default=True)
    renewal_days_before = models.IntegerField(default=30)

    class Meta:
        db_table = 'ssl_configurations'
        verbose_name = 'SSL Configuration'
        verbose_name_plural = 'SSL Configurations'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"SSL Config for {self.deployment.name} - {self.get_status_display()}"

    def is_certificate_valid(self) -> bool:
        """Check if the current certificate is valid and not expired."""
        if not self.certificate_expires_at:
            return False
        
        from django.utils import timezone
        now = timezone.now()
        
        # Check if certificate is expired
        if self.certificate_expires_at <= now:
            return False
            
        # Check if certificate is expiring soon (within 30 days)
        days_until_expiry = (self.certificate_expires_at - now).days
        if days_until_expiry <= self.renewal_days_before:
            self.status = self.SSLStatus.EXPIRING
            self.save(update_fields=['status'])
            
        return True

    def get_days_until_expiry(self) -> int:
        """Get number of days until certificate expires."""
        if not self.certificate_expires_at:
            return -1
            
        from django.utils import timezone
        now = timezone.now()
        days = (self.certificate_expires_at - now).days
        return max(0, days)

    def needs_renewal(self) -> bool:
        """Check if certificate needs renewal."""
        if not self.auto_renew or not self.certificate_expires_at:
            return False
            
        days_until_expiry = self.get_days_until_expiry()
        return days_until_expiry <= self.renewal_days_before
