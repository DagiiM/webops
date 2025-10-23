"""Application deployment model."""

from django.db import models
from django.core.validators import URLValidator
from .base import BaseDeployment


class ApplicationDeployment(BaseDeployment):
    """Regular web application deployment (Django, Laravel, WordPress, Static)."""

    class ProjectType(models.TextChoices):
        DJANGO = 'django', 'Django'
        LARAVEL = 'laravel', 'Laravel'
        WORDPRESS = 'wordpress', 'WordPress'
        STATIC = 'static', 'Static Site'
        NODEJS = 'nodejs', 'Node.js'
        PYTHON = 'python', 'Python'

    project_type = models.CharField(
        max_length=20,
        choices=ProjectType.choices,
        default=ProjectType.DJANGO
    )

    repo_url = models.URLField(
        max_length=500,
        validators=[URLValidator()]
    )
    
    branch = models.CharField(max_length=100, default='main')
    env_vars = models.JSONField(default=dict, blank=True)

    # Docker configuration
    use_docker = models.BooleanField(default=False)
    dockerfile_path = models.CharField(max_length=255, blank=True, default='Dockerfile')
    docker_compose_path = models.CharField(max_length=255, blank=True, default='docker-compose.yml')
    docker_image_name = models.CharField(max_length=255, blank=True)
    docker_build_args = models.JSONField(default=dict, blank=True)
    docker_env_vars = models.JSONField(default=dict, blank=True)
    docker_volumes = models.JSONField(default=list, blank=True)
    docker_ports = models.JSONField(default=list, blank=True)
    docker_network_mode = models.CharField(
        max_length=50,
        blank=True,
        default='bridge',
        choices=[('bridge', 'Bridge'), ('host', 'Host'), ('none', 'None')]
    )
    auto_generate_dockerfile = models.BooleanField(default=False)

    class Meta:
        db_table = 'application_deployments'
        verbose_name = 'Application Deployment'
        verbose_name_plural = 'Application Deployments'
        ordering = ['-created_at']

    def get_service_manager(self):
        """Return the application deployment service."""
        from apps.deployments.services.application import ApplicationDeploymentService
        return ApplicationDeploymentService()

    def get_repo_identifier(self) -> str:
        """Extract owner/repo from GitHub URL."""
        import re
        match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', self.repo_url)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
        return self.repo_url
