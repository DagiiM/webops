"""
Automation app configuration.
"""

from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.automation'
    verbose_name = 'Automation Workflows'

    def ready(self):
        """Import signals and register handlers."""
        # Import signals when app is ready
        try:
            from . import signals  # noqa
        except ImportError:
            pass
