from __future__ import annotations

import os
from typing import Optional
from threading import RLock

from django.conf import settings

from .interface import BackgroundProcessor
from .celery_adapter import CeleryBackgroundProcessor
from .memory_adapter import InMemoryBackgroundProcessor

# Thread-safe singleton for the background processor
_processor_instance: Optional[BackgroundProcessor] = None
_lock = RLock()


def get_background_processor() -> BackgroundProcessor:
    """Return the configured background processor instance.

    Selection order:
    1) Environment variable `WEBOPS_BG_PROCESSOR` if set (e.g., "celery", "memory").
    2) Default to Celery when available.
    3) Fallback to in-memory adapter.
    """
    global _processor_instance
    if _processor_instance is not None:
        return _processor_instance

    with _lock:
        if _processor_instance is not None:
            return _processor_instance

        # Prefer database configuration via config manager, fallback to environment
        try:
            from apps.services.config_manager import config_manager
            choice = str(config_manager.get('background.processor', 'celery')).lower()
        except Exception:
            choice = os.getenv("WEBOPS_BG_PROCESSOR", "celery").lower()

        if choice == "celery":
            try:
                from config.celery_app import app as celery_app
                # Import all task modules to ensure they're registered with Celery
                import apps.deployments.tasks
                import apps.services.tasks
                # Force task discovery after imports
                celery_app.autodiscover_tasks()
            except Exception:
                celery_app = None
            if celery_app is not None:
                _processor_instance = CeleryBackgroundProcessor(app=celery_app)
                return _processor_instance
            # If Celery import fails, fallback

        if choice == "memory":
            _processor_instance = InMemoryBackgroundProcessor()
            return _processor_instance

        # Default fallback
        try:
            from config.celery_app import app as celery_app
            # Import all task modules to ensure they're registered with Celery
            import apps.deployments.tasks
            import apps.services.tasks
            # Force task discovery after imports
            celery_app.autodiscover_tasks()
            _processor_instance = CeleryBackgroundProcessor(app=celery_app)
        except Exception:
            _processor_instance = InMemoryBackgroundProcessor()
        return _processor_instance