from django.apps import AppConfig

class ComplianceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.compliance'
    verbose_name = 'Compliance & Security'
    
    def ready(self):
        """Initialize compliance app when Django starts."""
        from . import signals  # noqa