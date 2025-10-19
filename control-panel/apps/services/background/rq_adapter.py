from __future__ import annotations

from typing import Any, Dict, Optional
from dataclasses import dataclass
from threading import RLock
import importlib

from .interface import BackgroundProcessor, TaskHandle, TaskStatus


@dataclass
class _RQContext:
    queue: Any


class RQBackgroundProcessor(BackgroundProcessor):
    """Redis Queue (RQ) adapter implementing BackgroundProcessor.

    This adapter enqueues tasks by dotted path name, resolving to callables.
    It is loaded only if `rq` is installed; otherwise factory should avoid using it.
    """

    name = "rq"

    def __init__(self, queue: Any):
        self._ctx = _RQContext(queue=queue)
        self._lock = RLock()

    def submit(self, task_name: str, *args: Any, **kwargs: Any) -> TaskHandle:
        fn = self._resolve(task_name)
        if fn is None:
            raise ValueError(f"Unknown RQ task: {task_name}")
        with self._lock:
            job = self._ctx.queue.enqueue(fn, *args, **kwargs)
            return TaskHandle(id=job.id, processor=self.name, task_name=task_name)

    def status(self, handle: TaskHandle) -> TaskStatus:
        with self._lock:
            job = self._ctx.queue.fetch_job(handle.id)
            if job is None:
                return TaskStatus.UNKNOWN
            if job.is_finished:
                return TaskStatus.SUCCESS
            if job.is_failed:
                return TaskStatus.FAILED
            if job.is_started:
                return TaskStatus.STARTED
            return TaskStatus.PENDING

    def result(self, handle: TaskHandle, timeout: Optional[float] = None) -> Any:
        with self._lock:
            job = self._ctx.queue.fetch_job(handle.id)
            if job is None:
                raise ValueError("Unknown job id")
            if timeout is not None:
                job = job.wait(timeout=timeout)
            return job.result

    def revoke(self, handle: TaskHandle, terminate: bool = False) -> bool:
        with self._lock:
            job = self._ctx.queue.fetch_job(handle.id)
            if job is None:
                return False
            job.cancel()
            return True

    def backend_info(self) -> Dict[str, Any]:
        return {
            "connection": str(getattr(self._ctx.queue, "connection", None)),
            "name": getattr(self._ctx.queue, "name", None),
        }

    def _resolve(self, dotted: str):
        try:
            module_path, fn_name = dotted.rsplit('.', 1)
            module = importlib.import_module(module_path)
            return getattr(module, fn_name, None)
        except Exception:
            return None