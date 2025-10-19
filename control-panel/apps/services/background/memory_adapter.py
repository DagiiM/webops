from __future__ import annotations

import time
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass
from threading import RLock, Thread

from .interface import BackgroundProcessor, TaskHandle, TaskStatus


@dataclass
class _TaskEntry:
    fn: Callable[..., Any]
    args: tuple
    kwargs: dict
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[BaseException] = None


class InMemoryBackgroundProcessor(BackgroundProcessor):
    """Simple in-memory processor for tests and dev without Celery.

    Executes tasks in a separate thread and tracks status/result.
    """

    name = "memory"

    def __init__(self, registry: Optional[Dict[str, Callable[..., Any]]] = None):
        self._lock = RLock()
        self._tasks: Dict[str, _TaskEntry] = {}
        self._registry = registry or {}

    def submit(self, task_name: str, *args: Any, **kwargs: Any) -> TaskHandle:
        with self._lock:
            fn = self._registry.get(task_name)
            if fn is None:
                raise ValueError(f"Unknown task: {task_name}")
            task_id = str(time.time_ns())
            entry = _TaskEntry(fn=fn, args=args, kwargs=kwargs)
            self._tasks[task_id] = entry
            Thread(target=self._run_task, args=(task_id,), daemon=True).start()
            return TaskHandle(id=task_id, processor=self.name, task_name=task_name)

    def status(self, handle: TaskHandle) -> TaskStatus:
        with self._lock:
            entry = self._tasks.get(handle.id)
            return entry.status if entry else TaskStatus.UNKNOWN

    def result(self, handle: TaskHandle, timeout: Optional[float] = None) -> Any:
        start = time.time()
        while True:
            with self._lock:
                entry = self._tasks.get(handle.id)
                if not entry:
                    raise ValueError("Unknown task handle")
                if entry.status in (TaskStatus.SUCCESS, TaskStatus.FAILED):
                    if entry.error:
                        raise entry.error
                    return entry.result
            if timeout is not None and time.time() - start > timeout:
                raise TimeoutError("Task result timeout")
            time.sleep(0.01)

    def revoke(self, handle: TaskHandle, terminate: bool = False) -> bool:
        # Not supported for in-memory thread executor
        return False

    def backend_info(self) -> Dict[str, Any]:
        return {"type": "in-memory", "registry_size": len(self._registry)}

    def _run_task(self, task_id: str) -> None:
        with self._lock:
            entry = self._tasks.get(task_id)
            if not entry:
                return
            entry.status = TaskStatus.STARTED
        try:
            result = entry.fn(*entry.args, **entry.kwargs)
            with self._lock:
                entry.result = result
                entry.status = TaskStatus.SUCCESS
        except BaseException as exc:
            with self._lock:
                entry.error = exc
                entry.status = TaskStatus.FAILED