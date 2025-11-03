"""Application deployment model."""

from django.db import models
from django.core.validators import URLValidator
from .base import BaseDeployment


class ApplicationDeployment(BaseDeployment):
    """Regular web application deployment with auto-detection support."""

    class ProjectType(models.TextChoices):
        # Python
        DJANGO = 'django', 'Django'
        PYTHON = 'python', 'Python (FastAPI/Flask)'

        # JavaScript/TypeScript
        NODEJS = 'nodejs', 'Node.js'
        NEXTJS = 'nextjs', 'Next.js'
        REACT = 'react', 'React'
        VUE = 'vue', 'Vue.js'

        # PHP
        LARAVEL = 'laravel', 'Laravel'
        WORDPRESS = 'wordpress', 'WordPress'
        PHP = 'php', 'PHP'

        # JVM Languages
        JAVA = 'java', 'Java'
        SPRING_BOOT = 'spring-boot', 'Spring Boot'

        # .NET
        DOTNET = 'dotnet', '.NET/C#'
        ASPNET = 'aspnet-core', 'ASP.NET Core'

        # Functional/Modern
        ELIXIR = 'elixir', 'Elixir'
        PHOENIX = 'phoenix', 'Phoenix'

        # System Languages
        GO = 'go', 'Go'
        RUST = 'rust', 'Rust'
        RUBY = 'ruby', 'Ruby/Rails'

        # Static & Docker
        STATIC = 'static', 'Static Site'
        DOCKER = 'docker', 'Docker'

    project_type = models.CharField(
        max_length=30,
        choices=ProjectType.choices,
        default=ProjectType.DJANGO
    )

    repo_url = models.URLField(
        max_length=500,
        validators=[URLValidator()]
    )

    branch = models.CharField(max_length=100, default='main')
    env_vars = models.JSONField(default=dict, blank=True)

    # Auto-detection fields (Railway-style)
    auto_detected = models.BooleanField(default=False, help_text='Project type auto-detected')
    detected_framework = models.CharField(max_length=100, blank=True, help_text='Detected framework (e.g., nextjs, fastapi)')
    detected_version = models.CharField(max_length=50, blank=True, help_text='Detected language/framework version')
    build_command = models.TextField(blank=True, help_text='Auto-generated build command')
    start_command = models.TextField(blank=True, help_text='Auto-generated start command')
    install_command = models.TextField(blank=True, help_text='Auto-generated install command')
    package_manager = models.CharField(max_length=50, blank=True, help_text='Detected package manager (npm, pip, etc.)')
    detection_confidence = models.FloatField(default=0.0, help_text='Detection confidence score (0-1)')

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
