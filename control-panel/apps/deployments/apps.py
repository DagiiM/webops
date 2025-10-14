from django.apps import AppConfig


class DeploymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.deployments"
    
    def ready(self) -> None:
        """Import signals when the app is ready."""
        import apps.deployments.signals  # noqa: F401
