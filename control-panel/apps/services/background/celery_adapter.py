from __future__ import annotations

from typing import Any, Dict, Optional
from dataclasses import dataclass
from threading import RLock

from .interface import BackgroundProcessor, TaskHandle, TaskStatus


@dataclass
class _CeleryAppRef:
    app: Any


class CeleryBackgroundProcessor(BackgroundProcessor):
    """Celery adapter implementing the BackgroundProcessor interface.

    This adapter discovers tasks via Celery's app and submits by task name.
    Thread-safe submission and status retrieval are ensured via RLock.
    """

    name = "celery"

    def __init__(self, app: Any):
        self._app_ref = _CeleryAppRef(app=app)
        self._lock = RLock()

    def submit(self, task_name: str, *args: Any, **kwargs: Any) -> TaskHandle:
        with self._lock:
            task = self._app_ref.app.tasks.get(task_name)
            # Fallback: allow dotted path lookup
            if task is None:
                task = self._app_ref.app.tasks.get(f"{task_name}")
            if task is None:
                # Allow Django autodiscovered tasks accessed by attribute
                # Example: services.start_service_task
                task = self._app_ref.app.tasks.get(task_name)
            if task is None:
                raise ValueError(f"Unknown Celery task: {task_name}")
            async_result = task.apply_async(args=args, kwargs=kwargs)
            return TaskHandle(id=async_result.id, processor=self.name, task_name=task_name)

    def status(self, handle: TaskHandle) -> TaskStatus:
        with self._lock:
            res = self._get_async_result(handle)
            if res is None:
                return TaskStatus.UNKNOWN
            if res.failed():
                return TaskStatus.FAILED
            if res.status in ("PENDING", "REVOKED"):
                return TaskStatus.PENDING if res.status == "PENDING" else TaskStatus.REVOKED
            if res.status in ("STARTED", "RETRY"):
                return TaskStatus.STARTED
            if res.status == "SUCCESS":
                return TaskStatus.SUCCESS
            # Celery can have custom states; map generically
            return TaskStatus.UNKNOWN

    def result(self, handle: TaskHandle, timeout: Optional[float] = None) -> Any:
        with self._lock:
            res = self._get_async_result(handle)
            if res is None:
                raise ValueError("Unknown task handle for Celery backend")
            return res.get(timeout=timeout)

    def revoke(self, handle: TaskHandle, terminate: bool = False) -> bool:
        with self._lock:
            res = self._get_async_result(handle)
            if res is None:
                return False
            res.revoke(terminate=terminate)
            return True

    def backend_info(self) -> Dict[str, Any]:
        return {
            "broker_url": getattr(self._app_ref.app.conf, "broker_url", None),
            "result_backend": getattr(self._app_ref.app.conf, "result_backend", None),
            "timezone": getattr(self._app_ref.app.conf, "timezone", None),
        }

    def get_status(self) -> Dict[str, Any]:
        """Return comprehensive status information for the Celery processor."""
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            
            # Get worker statistics
            stats = inspect.stats() or {}
            active_workers = len(stats.keys()) if stats else 0
            
            # Get task counts
            active_tasks = inspect.active() or {}
            scheduled_tasks = inspect.scheduled() or {}
            reserved_tasks = inspect.reserved() or {}
            
            total_active = sum(len(tasks) for tasks in active_tasks.values())
            total_scheduled = sum(len(tasks) for tasks in scheduled_tasks.values())
            total_reserved = sum(len(tasks) for tasks in reserved_tasks.values())
            
            # Get queue information
            from kombu import Connection
            broker_url = getattr(self._app_ref.app.conf, "broker_url", None)
            queue_info = {}
            if broker_url:
                try:
                    with Connection(broker_url) as conn:
                        # Get queue sizes (this is approximate)
                        queue_info["broker_connected"] = True
                        queue_info["broker_url"] = broker_url
                except Exception as e:
                    queue_info["broker_connected"] = False
                    queue_info["broker_error"] = str(e)
            
            return {
                "processor": "celery",
                "status": "healthy" if active_workers > 0 else "no_workers",
                "active_workers": active_workers,
                "total_active": total_active,
                "total_scheduled": total_scheduled,
                "total_reserved": total_reserved,
                "broker_info": queue_info,
                "backend_info": self.backend_info()
            }
        except Exception as e:
            return {
                "processor": "celery",
                "status": "error",
                "error": str(e),
                "backend_info": self.backend_info()
            }

    def _get_async_result(self, handle: TaskHandle):
        # Lazily import Celery AsyncResult via app
        try:
            return self._app_ref.app.AsyncResult(handle.id)
        except Exception:
            return None