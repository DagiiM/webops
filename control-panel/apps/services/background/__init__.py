"""
Background processing adapter system for WebOps services.

Provides a standardized interface and factory to select the active background
processor (Celery by default), enabling extensible support for additional
processors via adapters without changing service logic.
"""
from .factory import get_background_processor
from .interface import BackgroundProcessor, TaskHandle, TaskStatus

__all__ = [
    "get_background_processor",
    "BackgroundProcessor",
    "TaskHandle",
    "TaskStatus",
]