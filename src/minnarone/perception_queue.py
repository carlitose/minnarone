"""Bounded work queue for model-backed local perception.

Audio and video perception may call local models that are slower than live
capture. This queue keeps that work behind a small public surface: submit raw
media events, let per-channel workers process them, and expose counters for
operators/tests. Chat is intentionally not handled here; it stays on the direct
perception path.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from threading import Thread

from .perception_work import (
    PerceptionWorkToken,
    cancel_perception_work,
    clear_perception_work,
    new_perception_work_token,
    perception_work_scope,
)
from .source import RawEvent

PerceptionProcessor = Callable[[RawEvent], object | Awaitable[object]]


@dataclass(frozen=True, slots=True)
class PerceptionQueueChannelStats:
    """Diagnostic counters for one media channel."""

    queued: int = 0
    processed: int = 0
    dropped: int = 0
    failed: int = 0
    cancelled: int = 0
    cleanup_failures: int = 0
    abandoned: int = 0
    queue_depth: int = 0
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class PerceptionQueueStats:
    """Snapshot of local perception queue diagnostics."""

    channels: dict[str, PerceptionQueueChannelStats]


@dataclass(slots=True)
class _MutableChannelStats:
    queued: int = 0
    processed: int = 0
    dropped: int = 0
    failed: int = 0
    cancelled: int = 0
    cleanup_failures: int = 0
    abandoned: int = 0
    last_error: str | None = None


class BoundedLocalPerceptionQueue:
    """Run slow audio/video perception through bounded per-channel queues."""

    def __init__(
        self,
        processors: Mapping[str, PerceptionProcessor],
        *,
        capacity: int,
        shutdown_timeout: float,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if shutdown_timeout <= 0:
            raise ValueError("shutdown_timeout must be > 0")
        self._processors = dict(processors)
        self._shutdown_timeout = shutdown_timeout
        self._queues: dict[str, asyncio.Queue[RawEvent]] = {
            channel: asyncio.Queue(maxsize=capacity) for channel in self._processors
        }
        self._stats: dict[str, _MutableChannelStats] = {
            channel: _MutableChannelStats() for channel in self._processors
        }
        self._inflight: dict[str, int] = {channel: 0 for channel in self._processors}
        self._active_tokens: dict[str, PerceptionWorkToken | None] = {
            channel: None for channel in self._processors
        }
        self._active_threads: dict[str, Thread | None] = {
            channel: None for channel in self._processors
        }
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._running = False

    def handles(self, channel: str) -> bool:
        """Return whether this queue owns model-backed work for `channel`."""
        return channel in self._processors

    async def start(self) -> None:
        """Start one isolated worker per configured channel."""
        if self._running:
            return
        self._running = True
        for channel in self._processors:
            self._tasks[channel] = asyncio.create_task(self._worker(channel))

    def submit(self, event: RawEvent) -> bool:
        """Try to enqueue `event`; return False and count it if the queue is full."""
        if not self._running:
            raise RuntimeError("perception queue is not running")
        queue = self._queues[event.channel]
        stats = self._stats[event.channel]
        if event.channel == "video":
            stats.dropped += self._drain_queue(queue)
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            stats.dropped += 1
            return False
        stats.queued += 1
        return True

    async def stop(self) -> None:
        """Drain accepted work within the bounded timeout, then stop workers."""
        if not self._running:
            return
        try:
            await asyncio.wait_for(
                asyncio.gather(*(queue.join() for queue in self._queues.values())),
                timeout=self._shutdown_timeout,
            )
        except TimeoutError:
            for channel, queue in self._queues.items():
                pending = queue.qsize() + self._inflight[channel]
                if not pending:
                    continue
                token = self._active_tokens[channel]
                if token is not None:
                    cancel_perception_work(token)
                stats = self._stats[channel]
                stats.cancelled += self._drain_queue(queue)
                stats.cleanup_failures += 1
                stats.last_error = "shutdown timed out with unfinished work"
        finally:
            self._running = False
            for task in self._tasks.values():
                task.cancel()
            if self._tasks:
                done, pending = await asyncio.wait(
                    self._tasks.values(),
                    timeout=self._shutdown_timeout,
                )
                for task in done:
                    task.exception() if not task.cancelled() else None
                for channel, task in self._tasks.items():
                    if task in pending:
                        stats = self._stats[channel]
                        stats.cleanup_failures += 1
                        stats.last_error = "worker cleanup timed out"
                    thread = self._active_threads[channel]
                    if thread is not None and thread.is_alive():
                        self._record_abandoned_thread(channel)
            self._tasks.clear()

    def stats(self) -> PerceptionQueueStats:
        """Return an immutable snapshot of counters and current queue depths."""
        return PerceptionQueueStats(
            channels={
                channel: PerceptionQueueChannelStats(
                    queued=stats.queued,
                    processed=stats.processed,
                    dropped=stats.dropped,
                    failed=stats.failed,
                    cancelled=stats.cancelled,
                    cleanup_failures=stats.cleanup_failures,
                    abandoned=stats.abandoned,
                    queue_depth=self._queues[channel].qsize(),
                    last_error=stats.last_error,
                )
                for channel, stats in self._stats.items()
            }
        )

    async def _worker(self, channel: str) -> None:
        queue = self._queues[channel]
        processor = self._processors[channel]
        stats = self._stats[channel]
        while True:
            event = await queue.get()
            self._inflight[channel] += 1
            token = new_perception_work_token()
            self._active_tokens[channel] = token
            cancelled = False
            try:
                await self._run_processor(processor, event, token)
            except asyncio.CancelledError:
                cancel_perception_work(token)
                cancelled = True
                stats.cancelled += 1
                raise
            except Exception as exc:
                stats.failed += 1
                stats.last_error = str(exc)
            else:
                stats.processed += 1
            finally:
                if not cancelled:
                    clear_perception_work(token)
                self._active_tokens[channel] = None
                if not cancelled:
                    self._active_threads[channel] = None
                self._inflight[channel] -= 1
                queue.task_done()

    async def _run_processor(
        self,
        processor: PerceptionProcessor,
        event: RawEvent,
        token: PerceptionWorkToken,
    ) -> None:
        result, thread = _run_processor_in_daemon(processor, event, token)
        self._active_threads[event.channel] = thread
        await result

    @staticmethod
    def _drain_queue(queue: asyncio.Queue[RawEvent]) -> int:
        drained = 0
        while True:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                return drained
            queue.task_done()
            drained += 1

    def _record_abandoned_thread(self, channel: str) -> None:
        stats = self._stats[channel]
        stats.abandoned += 1
        stats.cleanup_failures += 1
        stats.last_error = "processor abandoned after shutdown timeout"


def _run_processor_in_daemon(
    processor: PerceptionProcessor,
    event: RawEvent,
    token: PerceptionWorkToken,
) -> tuple[asyncio.Future[None], Thread]:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[None] = loop.create_future()

    def complete_with_result() -> None:
        if not future.done():
            future.set_result(None)

    def complete_with_exception(exc: BaseException) -> None:
        if not future.done():
            future.set_exception(exc)

    def run() -> None:
        try:
            with perception_work_scope(token):
                result = processor(event)
                if inspect.isawaitable(result):
                    asyncio.run(result)
        except BaseException as exc:  # noqa: BLE001 - forwarded to worker stats.
            try:
                loop.call_soon_threadsafe(complete_with_exception, exc)
            except RuntimeError:
                return
            return
        try:
            loop.call_soon_threadsafe(complete_with_result)
        except RuntimeError:
            pass

    thread = Thread(target=run, daemon=True)
    thread.start()
    return future, thread
