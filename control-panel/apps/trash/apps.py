from django.apps import AppConfig


class TrashConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.trash"
    verbose_name = "Trash / Recycle Bin"

    def ready(self):
        # Import signals to register them
        try:
            from . import signals
        except ImportError:
            pass
