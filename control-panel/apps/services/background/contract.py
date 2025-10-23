"""
Abstract contract for all background-processor adapters.

Any new backend (RabbitMQ, RQ, SQS, etc.) must subclass `BackgroundProcessor`
and implement every method below.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional


class BackgroundProcessor(ABC):
    """Low-level interface for enqueueing and managing background tasks."""

    @abstractmethod
    def enqueue(
        self,
        task_path: str,
        args: tuple = (),
        kwargs: Optional[dict[str, Any]] = None,
        countdown: int = 0,
        queue: str = "default",
    ) -> str:
        """
        Schedule a task for asynchronous execution.

        Args:
            task_path: Dotted import path to the task function (e.g. "myapp.tasks.send_email").
            args: Positional arguments for the task.
            kwargs: Keyword arguments for the task.
            countdown: Seconds to wait before the task is executed.
            queue: Logical queue name (adapter decides how to map it).

        Returns:
            A unique job identifier that can be used to query status or revoke.
        """
        raise NotImplementedError

    @abstractmethod
    def revoke(self, job_id: str, terminate: bool = False) -> bool:
        """
        Cancel a scheduled or running task.

        Args:
            job_id: Identifier returned by `enqueue`.
            terminate: If True, attempt to kill a running worker process.

        Returns:
            True if the task was found and cancelled, False otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def status(self, job_id: str) -> str:
        """
        Return the current state of a job.

        Returns:
            One of:  PENDING, STARTED, SUCCESS, FAILURE, REVOKED
        """
        raise NotImplementedError

    @abstractmethod
    def result(self, job_id: str, timeout: Optional[float] = None) -> Any:
        """
        Block until the job finishes and return its result (or raise its exception).

        Args:
            job_id: Identifier returned by `enqueue`.
            timeout: Maximum seconds to wait; None means forever.

        Raises:
            TimeoutError if timeout is reached.
            Exception raised by the task itself on failure.
        """
        raise NotImplementedError

    @abstractmethod
    def healthcheck(self) -> bool:
        """
        Lightweight liveness probe for the underlying broker/workers.

        Returns:
            True if the adapter believes it can accept work right now.
        """
        raise NotImplementedError

    @abstractmethod
    def metrics(self) -> dict[str, Any]:
        """
        Optional runtime metrics exposed to the monitoring page.

        Returns:
            Dict of adapter-specific metrics (queue depth, worker count, etc.).
        """
        raise NotImplementedError