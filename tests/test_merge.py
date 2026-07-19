"""Comportamento del `MergingSourceAdapter` neutro (merge/backpressure).

Le parti async sono eseguite con `asyncio.run` per non dipendere da plugin
pytest, come nel resto della suite.
"""

import asyncio

import pytest

from minnarone.merge import MergeRuntimeError, MergingSourceAdapter
from minnarone.source import RawEvent, SourceAdapter


class _FakeReader(SourceAdapter):
    """Reader in-memory a canale singolo, con knob di guasto per i test.

    Struttura volutamente compatta (config raccolta in un dict) per non
    duplicare altri fake della suite.
    """

    def __init__(self, channel: str, events: list[RawEvent], **knobs: object) -> None:
        self._channel = channel
        self._events = list(events)
        self._cfg = {
            "fail_after": knobs.get("fail_after"),
            "block_events": bool(knobs.get("block_events", False)),
            "hang_on_stop": bool(knobs.get("hang_on_stop", False)),
        }
        self.starts = self.stops = 0

    def channels(self) -> set[str]:
        return {self._channel}

    async def start(self) -> None:
        self.starts += 1

    async def stop(self) -> None:
        self.stops += 1
        if self._cfg["hang_on_stop"]:
            await _forever()

    async def events(self):
        if self._cfg["block_events"]:
            await _forever()
        limit = self._cfg["fail_after"]
        for index, event in enumerate(self._events):
            if limit is not None and index >= limit:
                raise RuntimeError(f"{self._channel} failed")
            yield event


async def _forever() -> None:
    await asyncio.Event().wait()


def _event(channel: str, text: str) -> RawEvent:
    return RawEvent(channel=channel, payload={"text": text}, ts=float(len(text)))


def test_channels_reflect_injected_reader_set():
    adapter = MergingSourceAdapter(
        readers={
            "audio": _FakeReader("audio", []),
            "chat": _FakeReader("chat", []),
        }
    )

    assert adapter.channels() == {"chat", "audio"}


def test_events_merge_all_reader_output_into_one_stream():
    adapter = MergingSourceAdapter(
        readers={
            "chat": _FakeReader("chat", [_event("chat", "c")]),
            "audio": _FakeReader("audio", [_event("audio", "a")]),
        }
    )

    async def run():
        await adapter.start()
        return [event async for event in adapter.events()]

    events = asyncio.run(run())

    assert {event.channel for event in events} == {"chat", "audio"}
    stats = adapter.stats()
    assert stats.running is False
    assert stats.produced["chat"] == 1
    assert stats.produced["audio"] == 1


def test_ordered_channels_follow_deterministic_mapping_order():
    adapter = MergingSourceAdapter(
        readers={
            "video": _FakeReader("video", []),
            "chat": _FakeReader("chat", []),
            "audio": _FakeReader("audio", []),
        }
    )

    assert adapter.ordered_channels() == ["video", "chat", "audio"]


def test_full_queue_drops_non_priority_to_keep_priority_channel():
    adapter = MergingSourceAdapter(
        queue_size=1,
        priority_channels=("chat",),
        readers={
            "audio": _FakeReader("audio", [_event("audio", "a")]),
            "chat": _FakeReader("chat", [_event("chat", "c")]),
        },
    )

    async def run():
        await adapter.start()
        await asyncio.sleep(0)
        await adapter.stop()
        return adapter.stats()

    stats = asyncio.run(run())

    assert stats.produced["chat"] == 1
    assert stats.dropped["audio"] == 1


def test_priority_event_evicts_buffered_non_priority_on_full_queue():
    # Pilotiamo l'enqueue direttamente per rendere l'ordine deterministico e
    # colpire davvero il ramo di eviction a metà buffer (`_evict_one_low`),
    # cosa che il test full-queue order-invariant non garantisce.
    adapter = MergingSourceAdapter(
        queue_size=1,
        priority_channels=("chat",),
        readers={
            "audio": _FakeReader("audio", []),
            "chat": _FakeReader("chat", []),
        },
    )
    low = _event("audio", "a")
    high = _event("chat", "c")

    async def run():
        await adapter._enqueue(low)
        buffered_before = list(adapter._buffer)
        await adapter._enqueue(high)
        return buffered_before, list(adapter._buffer)

    buffered_before, buffered_after = asyncio.run(run())

    # Il non-prioritario è stato bufferizzato...
    assert buffered_before == [low]
    # ...poi sfrattato dal prioritario, che ora è l'unico presente.
    assert buffered_after == [high]
    stats = adapter.stats()
    assert stats.produced["chat"] == 1
    assert stats.dropped["audio"] == 1


def test_reader_failure_is_isolated_and_recorded_in_stats():
    adapter = MergingSourceAdapter(
        readers={
            "chat": _FakeReader("chat", [_event("chat", "c")]),
            "video": _FakeReader("video", [_event("video", "v")], fail_after=0),
        }
    )

    async def run():
        await adapter.start()
        return [event async for event in adapter.events()]

    events = asyncio.run(run())

    assert [event.channel for event in events] == ["chat"]
    stats = adapter.stats()
    assert "video failed" in stats.failures["video"]
    assert stats.produced["chat"] == 1


def test_start_is_idempotent_and_stop_closes_every_reader():
    chat = _FakeReader("chat", [_event("chat", "c")])
    adapter = MergingSourceAdapter(readers={"chat": chat})

    async def run():
        await adapter.start()
        await adapter.start()
        await asyncio.sleep(0)
        await adapter.stop()

    asyncio.run(run())

    assert chat.starts == 1
    assert chat.stops == 1
    assert adapter.stats().running is False


def test_events_drain_completed_run_without_restarting_readers():
    chat = _FakeReader("chat", [_event("chat", "c")])
    adapter = MergingSourceAdapter(readers={"chat": chat})

    async def wait_until_done() -> None:
        while adapter.stats().running:
            await asyncio.sleep(0)

    async def run():
        await adapter.start()
        await asyncio.wait_for(wait_until_done(), timeout=0.5)
        return [event async for event in adapter.events()]

    events = asyncio.run(run())

    assert [event.channel for event in events] == ["chat"]
    assert chat.starts == 1
    assert adapter.stats().produced["chat"] == 1


def test_injected_reader_must_expose_only_its_mapping_channel():
    with pytest.raises(ValueError, match="channel 'chat'"):
        MergingSourceAdapter(readers={"chat": _FakeReader("audio", [])})


def test_all_readers_failing_without_output_raises_after_stream_finishes():
    adapter = MergingSourceAdapter(
        readers={"chat": _FakeReader("chat", [_event("chat", "c")], fail_after=0)}
    )

    async def run():
        await adapter.start()
        with pytest.raises(MergeRuntimeError, match="chat failed"):
            async for _ in adapter.events():
                pass

    asyncio.run(run())


def test_stop_times_out_a_hung_reader_cleanup_and_records_failure():
    chat = _FakeReader("chat", [], block_events=True, hang_on_stop=True)
    adapter = MergingSourceAdapter(readers={"chat": chat}, cleanup_timeout=0.01)

    async def run():
        await adapter.start()
        await asyncio.sleep(0)
        await asyncio.wait_for(adapter.stop(), timeout=0.5)

    asyncio.run(run())

    stats = adapter.stats()
    assert chat.stops == 1
    assert stats.running is False
    assert "cleanup timed out" in stats.failures["chat"]
