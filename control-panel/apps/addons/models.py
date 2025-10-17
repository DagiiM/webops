from django.db import models
from apps.core.models import BaseModel

class Addon(BaseModel):
    """Represents a discovered addon from addon.yaml manifest.

    Metrics fields help monitor hook execution health and performance.
    """

    name = models.CharField(max_length=200, unique=True)
    version = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    author = models.CharField(max_length=200, blank=True)
    license = models.CharField(max_length=100, blank=True)

    enabled = models.BooleanField(default=True)
    django_app = models.CharField(max_length=255, blank=True)
    cli_entrypoint = models.CharField(max_length=255, blank=True)
    manifest_path = models.CharField(max_length=500)

    # simple JSON blob for capabilities and settings schema
    capabilities = models.JSONField(default=list, blank=True)
    settings_schema = models.JSONField(default=dict, blank=True)

    # Metrics/state fields
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_duration_ms = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.version})"