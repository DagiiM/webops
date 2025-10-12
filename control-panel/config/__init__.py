"""
WebOps Django Configuration Package.

This module initializes Celery for the Django project.
"""

# This will make sure the app is always imported when Django starts
from .celery_app import app as celery_app

__all__ = ('celery_app',)