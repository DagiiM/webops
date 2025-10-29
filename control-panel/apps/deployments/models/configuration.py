"""
Deployment configuration model.

Stores detected or user-provided project structure configuration
for each deployment, allowing for non-standard project layouts.
"""

from django.db import models
from apps.core.common.models import BaseModel
from .base import BaseDeployment


class DeploymentConfiguration(BaseModel):
    """
    Stores project structure configuration for a deployment.

    Inherits from BaseModel to get:
    - created_at, updated_at: Timestamp tracking
    - Soft-delete functionality (is_deleted, deleted_at, deleted_by)
    - Notification dispatch (send_notification, notify_*)

    This model handles non-standard project structures by storing
    detected or user-provided paths and settings.
    """

    deployment = models.OneToOneField(
        BaseDeployment,
        on_delete=models.CASCADE,
        related_name='configuration',
        help_text="Associated deployment"
    )

    # Project structure paths (relative to repo root)
    project_root = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        default='',
        help_text="Path to Django project root (where manage.py lives)"
    )

    manage_py_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        default='',
        help_text="Path to manage.py file"
    )

    # Settings configuration
    settings_module = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        default='',
        help_text="Django settings module (e.g., 'config.settings.production')"
    )

    settings_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        default='',
        help_text="Path to settings file or directory"
    )

    # WSGI/ASGI modules
    wsgi_module = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        default='',
        help_text="WSGI module path (e.g., 'config.wsgi:application')"
    )

    asgi_module = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        default='',
        help_text="ASGI module path (e.g., 'config.asgi:application')"
    )

    # Requirements
    requirements_file = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        default='',
        help_text="Path to requirements file to use"
    )

    # Project characteristics
    is_monorepo = models.BooleanField(
        default=False,
        help_text="Project is a monorepo (frontend + backend)"
    )

    has_backend_dir = models.BooleanField(
        default=False,
        help_text="Project has a backend directory"
    )

    has_split_settings = models.BooleanField(
        default=False,
        help_text="Settings are split into multiple files (base, production, etc.)"
    )

    # Detection status
    is_auto_detected = models.BooleanField(
        default=True,
        help_text="Configuration was auto-detected (vs user-provided)"
    )

    detection_complete = models.BooleanField(
        default=False,
        help_text="Structure detection has been completed"
    )

    # User overrides
    user_confirmed = models.BooleanField(
        default=False,
        help_text="User has confirmed the configuration"
    )

    # Metadata
    detection_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Full detection data from ProjectStructureDetector"
    )

    environment = models.CharField(
        max_length=50,
        default='production',
        choices=[
            ('development', 'Development'),
            ('staging', 'Staging'),
            ('production', 'Production'),
        ],
        help_text="Target deployment environment"
    )

    class Meta:
        db_table = 'deployment_configurations'
        verbose_name = 'Deployment Configuration'
        verbose_name_plural = 'Deployment Configurations'

    def __str__(self):
        return f"Config for {self.deployment.name}"

    def get_absolute_project_root(self):
        """Get absolute path to project root."""
        from pathlib import Path
        from django.conf import settings as django_settings

        base_path = Path(django_settings.WEBOPS_INSTALL_PATH) / "deployments"
        repo_path = base_path / self.deployment.name / "repo"

        if self.project_root:
            return repo_path / self.project_root
        return repo_path

    def get_absolute_requirements_file(self):
        """Get absolute path to requirements file."""
        if not self.requirements_file:
            return None

        from pathlib import Path
        from django.conf import settings as django_settings

        base_path = Path(django_settings.WEBOPS_INSTALL_PATH) / "deployments"
        repo_path = base_path / self.deployment.name / "repo"

        return repo_path / self.requirements_file

    def needs_user_input(self):
        """Check if configuration needs user input."""
        # If not auto-detected and not confirmed by user
        if not self.is_auto_detected and not self.user_confirmed:
            return True

        # If critical fields are missing
        if not self.settings_module or not self.project_root:
            return True

        return False

    def get_settings_for_environment(self, environment=None):
        """
        Get settings module for specific environment.

        Args:
            environment: Environment name (defaults to configured environment)

        Returns:
            Settings module string
        """
        env = environment or self.environment

        if not self.has_split_settings:
            return self.settings_module

        # If settings module already includes environment, use it
        if any(env_name in self.settings_module for env_name in ['production', 'development', 'staging']):
            return self.settings_module

        # Append environment to settings module
        base_module = self.settings_module.rsplit('.', 1)[0] if '.' in self.settings_module else self.settings_module
        return f"{base_module}.{env}"
