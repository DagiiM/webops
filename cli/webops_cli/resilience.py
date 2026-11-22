"""Bounded, thread-safe resilience primitives for WebOps deployment orchestration.

These are deterministic under an injected clock; neither retries nor agent
output can grant deployment authority. Safe for threaded API callers.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import math
import threading
import time
from typing import Callable, TypeVar

T = TypeVar("T")


class ResilienceError(RuntimeError):
    pass


class RateLimited(ResilienceError):
    pass


class CircuitOpen(ResilienceError):
    pass


class RetryableError(ResilienceError):
    pass


class InvalidTransition(ResilienceError):
    pass


class TokenBucket:
    """Non-blocking rate limiter, with a monotonic injectable clock."""

    def __init__(self, capacity: int, refill_per_sec: float,
                 clock: Callable[[], float] = time.monotonic):
        if capacity <= 0 or not math.isfinite(refill_per_sec) or refill_per_sec < 0:
            raise ValueError("Invalid token-bucket limits")
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self.clock = clock
        self._last = clock()
        self._tokens = float(capacity)
        self._lock = threading.Lock()

    def consume(self, amount: float = 1.0) -> bool:
        if not math.isfinite(amount) or amount <= 0 or amount > self.capacity:
            raise ValueError("Invalid token amount")
        with self._lock:
            now = self.clock()
            if now < self._last:
                raise ValueError("Monotonic clock moved backwards")
            self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.refill_per_sec)
            self._last = now
            if self._tokens + 1e-10 < amount:
                return False
            self._tokens -= amount
            return True

    @property
    def available(self) -> float:
        with self._lock:
            return self._tokens


class CircuitBreaker:
    """Fail closed while open; permit only one half-open recovery probe."""

    def __init__(self, threshold: int = 3, reset_after: float = 10.0,
                 clock: Callable[[], float] = time.monotonic):
        if threshold < 1 or reset_after <= 0 or not math.isfinite(reset_after):
            raise ValueError("Invalid circuit breaker limits")
        self.threshold = threshold
        self.reset_after = reset_after
        self.clock = clock
        self.failures = 0
        self._opened_at: float | None = None
        self._probing = False
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._opened_at is None:
                return "closed"
            if self.clock() - self._opened_at < self.reset_after:
                return "open"
            return "half_open"

    def call(self, operation: Callable[[], T]) -> T:
        with self._lock:
            if self._opened_at is not None:
                if self.clock() - self._opened_at < self.reset_after or self._probing:
                    raise CircuitOpen("Remote service circuit is open")
                self._probing = True
        try:
            result = operation()
        except Exception:
            with self._lock:
                self.failures += 1
                if self._probing or self.failures >= self.threshold:
                    self._opened_at = self.clock()
                self._probing = False
            raise
        with self._lock:
            self.failures = 0
            self._opened_at = None
            self._probing = False
        return result


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 3
    base_delay: float = 0.1
    max_delay: float = 1.0

    def __post_init__(self) -> None:
        if self.attempts < 1 or self.attempts > 16:
            raise ValueError("Retry attempts must be between 1 and 16")
        if not all(math.isfinite(x) and x >= 0 for x in (self.base_delay, self.max_delay)):
            raise ValueError("Invalid retry interval")
        if self.max_delay < self.base_delay:
            raise ValueError("Max delay smaller than base delay")

    def delay(self, retry_index: int) -> float:
        if retry_index < 0:
            raise ValueError("Negative retry index")
        return min(self.max_delay, self.base_delay * 2 ** min(30, retry_index))


def retry_read(operation: Callable[[], T], policy: RetryPolicy = RetryPolicy(),
               sleep: Callable[[float], None] = time.sleep) -> T:
    """Retry only explicitly safe reads; never retry a deployment POST."""
    for attempt in range(policy.attempts):
        try:
            return operation()
        except RetryableError:
            if attempt + 1 == policy.attempts:
                raise
            sleep(policy.delay(attempt))
    raise AssertionError("Unreachable")


class ConcurrencyLimiter:
    """Nonblocking admission and guaranteed release on exception."""

    def __init__(self, limit: int):
        if limit < 1:
            raise ValueError("Concurrency limit must be positive")
        self.limit = limit
        self._current = 0
        self._lock = threading.Lock()

    @property
    def active(self) -> int:
        with self._lock:
            return self._current

    @contextmanager
    def admit(self):
        with self._lock:
            if self._current >= self.limit:
                raise RateLimited("Too many simultaneous deployments")
            self._current += 1
        try:
            yield
        finally:
            with self._lock:
                self._current -= 1


TRANSITIONS = {
    "planned": frozenset(("validated", "failed")),
    "validated": frozenset(("queued", "failed")),
    "queued": frozenset(("building", "failed")),
    "building": frozenset(("starting", "failed")),
    "starting": frozenset(("verifying", "failed")),
    "verifying": frozenset(("ready", "failed")),
    "ready": frozenset(("failed",)),
    "failed": frozenset(("rolled_back",)),
    "rolled_back": frozenset(),
}


class DeploymentState:
    """Idempotent event state machine, with an auditable transition history."""

    def __init__(self):
        self.state = "planned"
        self._seen: set[str] = set()
        self.history: list[tuple[str, str, str]] = []
        self._lock = threading.Lock()

    def advance(self, to: str, event_id: str) -> bool:
        if not event_id or len(event_id) > 128:
            raise ValueError("Invalid event id")
        with self._lock:
            if event_id in self._seen:
                return False
            if to not in TRANSITIONS[self.state]:
                raise InvalidTransition(f"{self.state} cannot transition to {to}")
            old = self.state
            self.state = to
            self._seen.add(event_id)
            self.history.append((old, to, event_id))
            return True


class HealthWindow:
    """Bounded memory SLO evaluator: error rate and p95 over recent requests."""

    def __init__(self, capacity: int = 100, min_samples: int = 20,
                 max_error_rate: float = 0.05, max_p95_ms: float = 2000.0):
        if capacity < 1 or min_samples < 1 or min_samples > capacity:
            raise ValueError("Invalid health window size")
        if not 0 <= max_error_rate <= 1 or max_p95_ms <= 0:
            raise ValueError("Invalid SLO")
        self.samples: deque[tuple[bool, float]] = deque(maxlen=capacity)
        self.min_samples = min_samples
        self.max_error_rate = max_error_rate
        self.max_p95_ms = max_p95_ms
        self._lock = threading.Lock()

    def record(self, success: bool, latency_ms: float) -> None:
        if not math.isfinite(latency_ms) or latency_ms < 0:
            raise ValueError("Invalid latency")
        with self._lock:
            self.samples.append((bool(success), latency_ms))

    def snapshot(self) -> dict:
        with self._lock:
            values = list(self.samples)
        if not values:
            return {"samples": 0, "error_rate": None, "p95_ms": None, "healthy": False}
        sorted_latencies = sorted(v for _, v in values)
        p95 = sorted_latencies[math.ceil(0.95 * len(values)) - 1]
        error_rate = sum(not success for success, _ in values) / len(values)
        return {"samples": len(values), "error_rate": error_rate, "p95_ms": p95,
                "healthy": (len(values) >= self.min_samples and
                            error_rate <= self.max_error_rate and p95 <= self.max_p95_ms)}


class SingleFlight:
    """Coalesce concurrent duplicate deployment submissions within a process."""

    class _Pending:
        def __init__(self):
            self.ready = threading.Event()
            self.value = None
            self.error: BaseException | None = None

    def __init__(self, max_cached: int = 1024):
        if max_cached < 1:
            raise ValueError("SingleFlight cache bound must be positive")
        self._lock = threading.Lock()
        self._pending: dict[str, SingleFlight._Pending] = {}
        self._succeeded: OrderedDict[str, object] = OrderedDict()
        self.max_cached = max_cached

    def run(self, key: str, submit: Callable[[], T]) -> T:
        if not key:
            raise ValueError("Empty idempotency key")
        with self._lock:
            if key in self._succeeded:
                self._succeeded.move_to_end(key)
                return self._succeeded[key]  # type: ignore[return-value]
            pending = self._pending.get(key)
            owner = pending is None
            if owner:
                pending = self._Pending()
                self._pending[key] = pending
        if owner:
            try:
                pending.value = submit()
                with self._lock:
                    self._succeeded[key] = pending.value
                    self._succeeded.move_to_end(key)
                    if len(self._succeeded) > self.max_cached:
                        self._succeeded.popitem(last=False)
            except BaseException as exc:
                pending.error = exc
            finally:
                pending.ready.set()
                with self._lock:
                    del self._pending[key]
        else:
            pending.ready.wait()
        if pending.error is not None:
            raise pending.error
        return pending.value  # type: ignore[return-value]


def deployment_key(repository: str, branch: str, name: str) -> str:
    if not repository or not branch or not name:
        raise ValueError("Required deployment coordinates missing")
    return sha256(("\0".join((repository.lower(), branch, name))).encode()).hexdigest()

