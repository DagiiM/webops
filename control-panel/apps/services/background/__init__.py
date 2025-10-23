"""
Background processing adapter system for WebOps services.

Provides a standardized interface and factory to select the active background
processor (Celery by default), enabling extensible support for additional
processors via adapters without changing service logic.
"""
from typing import Any, Callable, Optional

from .factory import get_background_processor
from .interface import BackgroundProcessor, TaskHandle, TaskStatus

__all__ = [
    "get_background_processor",
    "BackgroundProcessor",
    "TaskHandle",
    "TaskStatus",
    "submit_task",
    "get_status",
    "get_result",
    "revoke_task",
    "healthcheck",
    "register_task",
]

# Convenience aliases for the active processor

_processor: Optional[BackgroundProcessor] = None


def _get_proc() -> BackgroundProcessor:
    global _processor
    if _processor is None:
        _processor = get_background_processor()
    return _processor


def submit_task(task_name: str, *args: Any, **kwargs: Any) -> TaskHandle:
    """Submit a background task and return its handle."""
    return _get_proc().submit(task_name, *args, **kwargs)


def get_status(handle: TaskHandle) -> TaskStatus:
    """Return the current status of a task."""
    return _get_proc().status(handle)


def get_result(handle: TaskHandle, timeout: Optional[float] = None) -> Any:
    """Block until the task finishes and return its result."""
    return _get_proc().result(handle, timeout=timeout)


def revoke_task(handle: TaskHandle, terminate: bool = False) -> bool:
    """Attempt to cancel a task."""
    return _get_proc().revoke(handle, terminate=terminate)


def healthcheck() -> bool:
    """Quick liveness probe for the underlying backend."""
    return _get_proc().healthcheck()


def register_task(name: str, fn: Callable[..., Any]) -> None:
    """
    Register a task function so the in-memory adapter can resolve it by name.

    Celery tasks are auto-discovered via @shared_task, but the memory backend
    needs an explicit registry. Call this at import time or in AppConfig.ready().
    """
    from .memory_adapter import InMemoryBackgroundProcessor
    proc = _get_proc()
    if isinstance(proc, InMemoryBackgroundProcessor):
        proc._registry[name] = fn