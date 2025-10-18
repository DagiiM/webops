"""
Deployment models for WebOps.

Reference: CLAUDE.md "Database Models" section
Architecture: PROPOSAL.md section 5.1 "Deployment Workflow"

This module follows WebOps coding standards:
- Type hints required
- Inherit from BaseModel
- Follow model naming conventions
"""

from django.db import models
from django.contrib.auth.models import User
from apps.core.models import BaseModel


class Deployment(BaseModel):
    """Represents a deployed application."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        BUILDING = 'building', 'Building'
        RUNNING = 'running', 'Running'
        STOPPED = 'stopped', 'Stopped'
        FAILED = 'failed', 'Failed'

    class ProjectType(models.TextChoices):
        DJANGO = 'django', 'Django'
        STATIC = 'static', 'Static Site'
        LLM = 'llm', 'LLM Model (vLLM)'

    name = models.CharField(max_length=100, unique=True)
    repo_url = models.URLField(max_length=500)
    branch = models.CharField(max_length=100, default='main')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    project_type = models.CharField(
        max_length=20,
        choices=ProjectType.choices,
        default=ProjectType.DJANGO
    )
    port = models.IntegerField(unique=True, null=True, blank=True)
    domain = models.CharField(max_length=255, blank=True)
    env_vars = models.JSONField(default=dict, blank=True)
    deployed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='deployments'
    )

    # LLM-specific fields
    model_name = models.CharField(max_length=255, blank=True, help_text='HuggingFace model ID (e.g., meta-llama/Llama-2-7b-chat-hf)')
    tensor_parallel_size = models.IntegerField(default=1, help_text='Number of GPUs for tensor parallelism')
    gpu_memory_utilization = models.FloatField(default=0.9, help_text='GPU memory utilization (0.0-1.0)')
    max_model_len = models.IntegerField(null=True, blank=True, help_text='Maximum model context length')
    quantization = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('', 'None'),
            ('awq', 'AWQ'),
            ('gptq', 'GPTQ'),
            ('squeezellm', 'SqueezeLLM'),
        ],
        help_text='Model quantization method'
    )
    dtype = models.CharField(
        max_length=20,
        default='auto',
        choices=[
            ('auto', 'Auto'),
            ('float16', 'Float16'),
            ('bfloat16', 'BFloat16'),
            ('float32', 'Float32'),
        ],
        help_text='Model data type'
    )

    # Docker-specific fields
    use_docker = models.BooleanField(default=False, help_text='Deploy using Docker containerization')
    dockerfile_path = models.CharField(
        max_length=255,
        blank=True,
        default='Dockerfile',
        help_text='Path to Dockerfile relative to repository root'
    )
    docker_compose_path = models.CharField(
        max_length=255,
        blank=True,
        default='docker-compose.yml',
        help_text='Path to docker-compose.yml relative to repository root'
    )
    docker_image_name = models.CharField(
        max_length=255,
        blank=True,
        help_text='Custom Docker image name (auto-generated if empty)'
    )
    docker_build_args = models.JSONField(
        default=dict,
        blank=True,
        help_text='Docker build arguments as key-value pairs'
    )
    docker_env_vars = models.JSONField(
        default=dict,
        blank=True,
        help_text='Docker container environment variables'
    )
    docker_volumes = models.JSONField(
        default=list,
        blank=True,
        help_text='Docker volume mounts as list of {"host": "path", "container": "path"}'
    )
    docker_ports = models.JSONField(
        default=list,
        blank=True,
        help_text='Additional Docker port mappings as list of {"host": port, "container": port}'
    )
    docker_network_mode = models.CharField(
        max_length=50,
        blank=True,
        default='bridge',
        choices=[
            ('bridge', 'Bridge'),
            ('host', 'Host'),
            ('none', 'None'),
        ],
        help_text='Docker network mode'
    )
    auto_generate_dockerfile = models.BooleanField(
        default=False,
        help_text='Automatically generate Dockerfile if not present in repository'
    )

    def __str__(self) -> str:
        return f"{self.name} ({self.status})"

    class Meta:
        db_table = 'deployments'
        verbose_name = 'Deployment'
        verbose_name_plural = 'Deployments'
        ordering = ['-created_at']


class DeploymentLog(BaseModel):
    """Deployment operation logs."""

    class Level(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'
        SUCCESS = 'success', 'Success'

    deployment = models.ForeignKey(
        Deployment,
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


class HealthCheckRecord(BaseModel):
    """Health check results for deployments."""

    deployment = models.ForeignKey(
        Deployment,
        on_delete=models.CASCADE,
        related_name='health_check_records'
    )
    overall_healthy = models.BooleanField(default=True)
    process_healthy = models.BooleanField(default=True)
    http_healthy = models.BooleanField(default=True)
    resources_healthy = models.BooleanField(default=True)
    disk_healthy = models.BooleanField(default=True)

    # Detailed metrics
    cpu_percent = models.FloatField(null=True, blank=True)
    memory_mb = models.FloatField(null=True, blank=True)
    disk_free_gb = models.FloatField(null=True, blank=True)
    response_time_ms = models.FloatField(null=True, blank=True)
    http_status_code = models.IntegerField(null=True, blank=True)

    # Full results as JSON
    results = models.JSONField(default=dict)

    # Auto-restart tracking
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