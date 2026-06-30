import asyncio
import time
from threading import Event

from minnarone.perception import Perception, Source
from minnarone.perception_queue import BoundedLocalPerceptionQueue
from minnarone.source import RawEvent
from minnarone.store import PerceptionStore


def _event(channel: str, label: str) -> RawEvent:
    return RawEvent(channel=channel, payload=label, ts=1.0)


class _GateProcessor:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.seen: list[str] = []

    async def __call__(self, event: RawEvent) -> None:
        self.seen.append(str(event.payload))
        self.started.set()
        while not self.release.is_set():
            await asyncio.sleep(0.001)


def test_media_queue_is_bounded_and_drains_accepted_work():
    async def run() -> None:
        processor = _GateProcessor()
        queue = BoundedLocalPerceptionQueue(
            {"audio": processor},
            capacity=2,
            shutdown_timeout=1.0,
        )

        await queue.start()
        assert queue.submit(_event("audio", "first")) is True
        assert await asyncio.to_thread(processor.started.wait, timeout=1.0)

        assert queue.submit(_event("audio", "second")) is True
        assert queue.submit(_event("audio", "third")) is True
        assert queue.submit(_event("audio", "dropped")) is False

        stats = queue.stats().channels["audio"]
        assert stats.queued == 3
        assert stats.dropped == 1
        assert stats.processed == 0

        processor.release.set()
        await queue.stop()

        stats = queue.stats().channels["audio"]
        assert processor.seen == ["first", "second", "third"]
        assert stats.processed == 3
        assert stats.dropped == 1

    asyncio.run(run())


def test_video_queue_replaces_stale_queued_frame_with_newest():
    async def run() -> None:
        processor = _GateProcessor()
        queue = BoundedLocalPerceptionQueue(
            {"video": processor},
            capacity=3,
            shutdown_timeout=1.0,
        )

        await queue.start()
        assert queue.submit(_event("video", "in-flight")) is True
        assert await asyncio.to_thread(processor.started.wait, timeout=1.0)

        assert queue.submit(_event("video", "stale-1")) is True
        assert queue.submit(_event("video", "stale-2")) is True
        assert queue.submit(_event("video", "newest")) is True

        stats = queue.stats().channels["video"]
        assert stats.queued == 4
        assert stats.dropped == 2
        assert stats.queue_depth == 1

        processor.release.set()
        await queue.stop()

        stats = queue.stats().channels["video"]
        assert processor.seen == ["in-flight", "newest"]
        assert stats.processed == 2
        assert stats.dropped == 2

    asyncio.run(run())


class _HangingProcessor:
    def __init__(self) -> None:
        self.started = Event()

    async def __call__(self, _event: RawEvent) -> None:
        self.started.set()
        await asyncio.Future()


def test_shutdown_timeout_records_inflight_cleanup_failure():
    async def run() -> None:
        processor = _HangingProcessor()
        queue = BoundedLocalPerceptionQueue(
            {"video": processor},
            capacity=1,
            shutdown_timeout=0.01,
        )

        await queue.start()
        assert queue.submit(_event("video", "frame")) is True
        assert await asyncio.to_thread(processor.started.wait, timeout=1.0)

        await asyncio.wait_for(queue.stop(), timeout=1.0)

        stats = queue.stats().channels["video"]
        assert stats.processed == 0
        assert stats.cancelled == 1
        assert stats.cleanup_failures >= 1
        assert stats.abandoned >= 1
        assert "timeout" in (stats.last_error or "")

    asyncio.run(run())


def test_shutdown_timeout_bounds_sync_processor_and_blocks_late_store_writes(tmp_path):
    async def run() -> None:
        started = Event()
        store = PerceptionStore(tmp_path / "perceptions.jsonl")

        def slow_processor(_event: RawEvent) -> None:
            started.set()
            time.sleep(0.15)
            store.append(
                Perception(ts=1.0, source=Source.AUDIO, type="speech", text="late")
            )

        queue = BoundedLocalPerceptionQueue(
            {"audio": slow_processor},
            capacity=1,
            shutdown_timeout=0.01,
        )

        await queue.start()
        assert queue.submit(_event("audio", "chunk")) is True
        assert await asyncio.to_thread(started.wait, timeout=1.0)

        before = time.monotonic()
        await asyncio.wait_for(queue.stop(), timeout=0.5)
        elapsed = time.monotonic() - before

        assert elapsed < 0.1
        stats = queue.stats().channels["audio"]
        assert stats.cancelled == 1
        assert stats.cleanup_failures >= 1
        assert stats.abandoned >= 1

        await asyncio.sleep(0.2)
        assert store.tail(10) == []

    asyncio.run(run())


class _FailingProcessor:
    async def __call__(self, _event: RawEvent) -> None:
        raise RuntimeError("model exploded")


class _RecordingProcessor:
    def __init__(self) -> None:
        self.seen: list[str] = []

    async def __call__(self, event: RawEvent) -> None:
        self.seen.append(str(event.payload))


class _SyncRecordingProcessor:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def __call__(self, event: RawEvent) -> None:
        self.seen.append(str(event.payload))


def test_queue_accepts_sync_processors_for_existing_perceivers():
    async def run() -> None:
        audio = _SyncRecordingProcessor()
        queue = BoundedLocalPerceptionQueue(
            {"audio": audio},
            capacity=1,
            shutdown_timeout=1.0,
        )

        await queue.start()
        assert queue.submit(_event("audio", "chunk")) is True
        await queue.stop()

        stats = queue.stats().channels["audio"]
        assert audio.seen == ["chunk"]
        assert stats.processed == 1

    asyncio.run(run())


def test_worker_failure_is_recorded_without_killing_other_channels():
    async def run() -> None:
        video = _RecordingProcessor()
        queue = BoundedLocalPerceptionQueue(
            {"audio": _FailingProcessor(), "video": video},
            capacity=2,
            shutdown_timeout=1.0,
        )

        await queue.start()
        assert queue.submit(_event("audio", "bad")) is True
        assert queue.submit(_event("video", "frame")) is True
        await queue.stop()

        stats = queue.stats().channels
        assert stats["audio"].failed == 1
        assert "model exploded" in (stats["audio"].last_error or "")
        assert stats["video"].processed == 1
        assert video.seen == ["frame"]

    asyncio.run(run())
