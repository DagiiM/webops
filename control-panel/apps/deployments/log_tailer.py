"""
Robust, fault-tolerant log tailer with chunking, backpressure, and rate limiting.

Design goals:
- Zero external dependencies (stdlib + Django/Channels already in project)
- Chunked message handling for large streams
- Backpressure via bounded queues
- Rate limiting with token-bucket
- Comprehensive error handling (file rotation, permission, transient errors)
- Efficient memory usage for sustained operation
- Modular components for future extensions

Primary use: stream vLLM service logs to WebSocket groups for real-time visibility.

"""

from __future__ import annotations

import os
import io
import time
import asyncio
from dataclasses import dataclass
from typing import List, Optional, Callable
from collections import deque

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone


# -----------------------
# Rate Limiter (Token Bucket)
# -----------------------

class RateLimiter:
    """Simple token-bucket rate limiter for async workflows.

    Controls the number of "units" allowed per second with a configurable burst.
    Units can represent chunks or total bytes, depending on usage.
    """

    def __init__(self, rate_per_sec: float, burst: int):
        self.rate = float(rate_per_sec)
        self.burst = int(burst)
        self.tokens = float(burst)
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        if elapsed <= 0:
            return
        self.last_refill = now
        # Add tokens based on elapsed time and rate
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)

    async def acquire(self, units: float = 1.0) -> None:
        """Acquire tokens, waiting if necessary until enough are available."""
        while True:
            self._refill()
            if self.tokens >= units:
                self.tokens -= units
                return
            # Sleep proportionally to deficit to avoid busy-wait
            deficit = units - self.tokens
            await asyncio.sleep(max(0.01, deficit / max(self.rate, 1e-6)))


# -----------------------
# Chunk Aggregator
# -----------------------

@dataclass
class Chunk:
    lines: List[str]
    byte_size: int
    created_at: float


class ChunkAggregator:
    """Aggregates log lines into bounded chunks for efficient streaming.

    Flushes a chunk when one of the thresholds is hit:
    - max_lines
    - max_bytes
    - flush_interval seconds since chunk creation
    """

    def __init__(
        self,
        max_lines: int = 200,
        max_bytes: int = 64 * 1024,
        flush_interval: float = 0.5,
        max_line_bytes: int = 16 * 1024,
    ) -> None:
        self.max_lines = max_lines
        self.max_bytes = max_bytes
        self.flush_interval = flush_interval
        self.max_line_bytes = max_line_bytes
        self._lines: List[str] = []
        self._bytes: int = 0
        self._created_at: Optional[float] = None

    def _truncate(self, s: str) -> str:
        # Ensure individual lines are bounded
        if len(s) > self.max_line_bytes:
            return s[: self.max_line_bytes]
        return s

    def add_line(self, line: str) -> Optional[Chunk]:
        line = self._truncate(line)
        if self._created_at is None:
            self._created_at = time.monotonic()
        self._lines.append(line)
        self._bytes += len(line.encode('utf-8', errors='ignore'))

        if len(self._lines) >= self.max_lines or self._bytes >= self.max_bytes:
            return self.flush()
        return None

    def maybe_flush_by_time(self) -> Optional[Chunk]:
        if self._created_at is None:
            return None
        if (time.monotonic() - self._created_at) >= self.flush_interval and self._lines:
            return self.flush()
        return None

    def flush(self) -> Optional[Chunk]:
        if not self._lines:
            return None
        chunk = Chunk(lines=self._lines, byte_size=self._bytes, created_at=self._created_at or time.monotonic())
        self._lines = []
        self._bytes = 0
        self._created_at = None
        return chunk


# -----------------------
# File Tailer (blocking reader run in thread)
# -----------------------

class FileTailer:
    """Async file tailer that follows a log file robustly.

    Handles rotation, truncation, and transient errors by reopening with backoff.
    Emits lines into an asyncio.Queue for downstream processing without threads.
    """

    def __init__(
        self,
        path: str,
        queue: asyncio.Queue[str],
        start_at_end: bool = True,
        poll_interval: float = 0.2,
        backoff_initial: float = 0.5,
        backoff_max: float = 10.0,
        encoding: str = 'utf-8',
    ) -> None:
        self.path = path
        self.queue = queue
        self.start_at_end = start_at_end
        self.poll_interval = poll_interval
        self.backoff_initial = backoff_initial
        self.backoff_max = backoff_max
        self.encoding = encoding
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    def _open(self) -> io.TextIOWrapper:
        return open(self.path, 'r', encoding=self.encoding, errors='replace')

    def _stat(self) -> Optional[os.stat_result]:
        try:
            return os.stat(self.path)
        except FileNotFoundError:
            return None

    async def run(self) -> None:
        """Run the tailer in the event loop (non-blocking read pattern)."""
        backoff = self.backoff_initial
        fp: Optional[io.TextIOWrapper] = None
        last_inode: Optional[int] = None
        last_size: Optional[int] = None

        while not self._stop.is_set():
            try:
                st = self._stat()
                if st is None:
                    await asyncio.sleep(backoff)
                    backoff = min(self.backoff_max, backoff * 1.5)
                    continue

                if fp is None:
                    fp = self._open()
                    # Seek to end or beginning
                    if self.start_at_end:
                        fp.seek(0, os.SEEK_END)
                    last_inode = st.st_ino
                    last_size = st.st_size
                    backoff = self.backoff_initial

                # Detect rotation/truncation
                if st.st_ino != last_inode or (last_size is not None and st.st_size < last_size):
                    try:
                        fp.close()
                    except Exception:
                        pass
                    fp = self._open()
                    last_inode = st.st_ino
                    last_size = st.st_size

                # Read available lines
                # At EOF, readline() returns "" quickly, so we can poll without blocking
                while not self._stop.is_set():
                    pos = fp.tell()
                    line = fp.readline()
                    if not line:
                        # No new data; sleep briefly
                        await asyncio.sleep(self.poll_interval)
                        break
                    # Update last_size to current position
                    last_size = pos + len(line)
                    # Enqueue with backpressure (awaits when full)
                    await self.queue.put(line.rstrip('\n'))

            except Exception:
                # On any error, close and backoff
                try:
                    if fp:
                        fp.close()
                except Exception:
                    pass
                fp = None
                await asyncio.sleep(backoff)
                backoff = min(self.backoff_max, backoff * 1.5)

        try:
            if fp:
                fp.close()
        except Exception:
            pass


# -----------------------
# Channels Dispatcher
# -----------------------

class ChannelsDispatcher:
    """Dispatch log chunks to Channels groups for per-deployment streaming."""

    def __init__(self, deployment_id: int, deployment_name: str) -> None:
        self.deployment_id = deployment_id
        self.deployment_name = deployment_name
        self.group = f"deployment_{deployment_name}"
        self.layer = get_channel_layer()

    async def send_chunk(self, chunk: Chunk) -> None:
        # Prepare event payload matching consumer expectations
        event = {
            'type': 'deployment_logs',  # Channels consumer method name
            'deployment_id': self.deployment_id,
            'logs': chunk.lines,
            'timestamp': timezone.now().isoformat(),
        }
        # group_send is async; if layer is not available, fallback to async_to_sync
        try:
            await self.layer.group_send(self.group, event)
        except RuntimeError:
            # In case we are in a non-async context (shouldn't happen here), try sync fallback
            async_to_sync(self.layer.group_send)(self.group, event)


# -----------------------
# Tailer Orchestrator
# -----------------------

class LogTailer:
    """High-level orchestrator: read file -> aggregate -> rate limit -> dispatch.

    Backpressure is enforced via a bounded asyncio.Queue. The reader blocks when the
    queue is full; the aggregator consumes and dispatches chunks subject to a rate
    limiter to avoid overwhelming the system.
    """

    def __init__(
        self,
        deployment_id: int,
        deployment_name: str,
        file_path: str,
        *,
        queue_maxsize: int = 1000,
        chunk_max_lines: int = 200,
        chunk_max_bytes: int = 64 * 1024,
        flush_interval: float = 0.5,
        max_line_bytes: int = 16 * 1024,
        rate_chunks_per_sec: float = 10.0,
        rate_burst: int = 20,
    ) -> None:
        self.deployment_id = deployment_id
        self.deployment_name = deployment_name
        self.file_path = file_path
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=queue_maxsize)
        self.aggregator = ChunkAggregator(
            max_lines=chunk_max_lines,
            max_bytes=chunk_max_bytes,
            flush_interval=flush_interval,
            max_line_bytes=max_line_bytes,
        )
        self.rate_limiter = RateLimiter(rate_per_sec=rate_chunks_per_sec, burst=rate_burst)
        self.dispatcher = ChannelsDispatcher(deployment_id, deployment_name)
        self._stop = asyncio.Event()
        self._reader = FileTailer(path=file_path, queue=self.queue)

    async def start(self) -> None:
        """Start reader and processing tasks."""
        reader_task = asyncio.create_task(self._reader.run())
        processor_task = asyncio.create_task(self._process_loop())
        try:
            await asyncio.wait([reader_task, processor_task], return_when=asyncio.FIRST_COMPLETED)
        finally:
            self._reader.stop()
            self._stop.set()

    async def _process_loop(self) -> None:
        """Consume lines, aggregate chunks, and dispatch respecting rate limits."""
        while not self._stop.is_set():
            try:
                # Wait for at least one line or timeout to consider time-based flush
                try:
                    line = await asyncio.wait_for(self.queue.get(), timeout=0.2)
                    chunk = self.aggregator.add_line(line)
                    if chunk:
                        await self.rate_limiter.acquire(1.0)
                        await self.dispatcher.send_chunk(chunk)
                except asyncio.TimeoutError:
                    pass

                # Time-based flush to avoid latency
                timed_chunk = self.aggregator.maybe_flush_by_time()
                if timed_chunk:
                    await self.rate_limiter.acquire(1.0)
                    await self.dispatcher.send_chunk(timed_chunk)

            except Exception:
                # In case of any processing error, continue after a brief pause
                await asyncio.sleep(0.1)


# -----------------------
# Utilities to build tailers for LLM deployments
# -----------------------

def get_llm_log_paths(base_path: str) -> List[str]:
    """Return list of relevant LLM log files to tail."""
    # vLLM service template writes to vllm.log and vllm-error.log
    return [
        os.path.join(base_path, 'logs', 'vllm.log'),
        os.path.join(base_path, 'logs', 'vllm-error.log'),
    ]


async def run_tailers_for_deployment(
    deployment_id: int,
    deployment_name: str,
    deployment_path: str,
    *,
    queue_maxsize: int = 1000,
    chunk_max_lines: int = 200,
    chunk_max_bytes: int = 64 * 1024,
    flush_interval: float = 0.5,
    max_line_bytes: int = 16 * 1024,
    rate_chunks_per_sec: float = 10.0,
    rate_burst: int = 20,
) -> None:
    """Build and run tailers for all LLM log files for a deployment."""
    paths = get_llm_log_paths(deployment_path)
    tailers = [
        LogTailer(
            deployment_id,
            deployment_name,
            file_path=p,
            queue_maxsize=queue_maxsize,
            chunk_max_lines=chunk_max_lines,
            chunk_max_bytes=chunk_max_bytes,
            flush_interval=flush_interval,
            max_line_bytes=max_line_bytes,
            rate_chunks_per_sec=rate_chunks_per_sec,
            rate_burst=rate_burst,
        )
        for p in paths
    ]

    # Run all tailers concurrently; each tailer owns its reader and processor
    await asyncio.gather(*(t.start() for t in tailers))