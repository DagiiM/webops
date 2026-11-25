"""ASGI entry point for the Runpod panel pod: the Django app plus static files (no separate web server)."""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.runpod_preview")

from config.asgi import application as base  # noqa: E402
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler  # noqa: E402

application = ASGIStaticFilesHandler(base)
