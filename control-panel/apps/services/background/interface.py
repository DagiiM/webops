from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Protocol


class TaskStatus(str, Enum):
    """Canonical task status values across processors."""
    PENDING = "pending"
    STARTED = "started"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TaskHandle:
    """Opaque handle for a submitted background task."""
    id: str
    processor: str  # e.g., "celery", "rq", "memory"
    task_name: Optional[str] = None


class BackgroundProcessor(Protocol):
    """Standardized interface for background processing operations.

    Implementors must be thread-safe for submission and status retrieval.
    """

    name: str

    def submit(self, task_name: str, *args: Any, **kwargs: Any) -> TaskHandle:
        """Submit a task by name with arguments.

        Returns a TaskHandle that can be used to query status/result.
        """
        ...

    def status(self, handle: TaskHandle) -> TaskStatus:
        """Return canonical status for the given task handle."""
        ...

    def result(self, handle: TaskHandle, timeout: Optional[float] = None) -> Any:
        """Return task result or raise if task failed or not available."""
        ...

    def revoke(self, handle: TaskHandle, terminate: bool = False) -> bool:
        """Cancel/revoke a task if supported. Returns True on success."""
        ...

    def backend_info(self) -> Dict[str, Any]:
        """Return diagnostic information for the processor backend."""
        ...

    def get_status(self) -> Dict[str, Any]:
        """Return comprehensive status information for the processor."""
        ...