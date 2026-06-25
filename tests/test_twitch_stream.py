"""Unified TwitchStreamAdapter behavior."""

import asyncio

import pytest

from minnarone.source import RawEvent, SourceAdapter
from minnarone.twitch_stream import TwitchStreamAdapter, ordered_twitch_channels


class _FakeReader(SourceAdapter):
    def __init__(
        self,
        channel: str,
        events: list[RawEvent],
        *,
        fail_after: int | None = None,
        block_events: bool = False,
        hang_on_stop: bool = False,
    ) -> None:
        self._channel = channel
        self._events = list(events)
        self._fail_after = fail_after
        self._block_events = block_events
        self._hang_on_stop = hang_on_stop
        self.starts = 0
        self.stops = 0

    def channels(self) -> set[str]:
        return {self._channel}

    async def start(self) -> None:
        self.starts += 1

    async def stop(self) -> None:
        self.stops += 1
        if self._hang_on_stop:
            await asyncio.Event().wait()

    async def events(self):
        if self._block_events:
            await asyncio.Event().wait()
        for index, event in enumerate(self._events):
            if self._fail_after is not None and index >= self._fail_after:
                raise RuntimeError(f"{self._channel} failed")
            yield event


def _event(channel: str, text: str) -> RawEvent:
    return RawEvent(channel=channel, payload={"text": text}, ts=float(len(text)))


def test_channels_reflect_enabled_reader_set():
    adapter = TwitchStreamAdapter(
        channel="minnarone",
        readers={
            "audio": _FakeReader("audio", []),
            "chat": _FakeReader("chat", []),
        },
    )

    assert adapter.channels() == {"chat", "audio"}
    assert ordered_twitch_channels(adapter.channels()) == ["chat", "audio"]


def test_events_expose_all_reader_output_through_one_stream():
    adapter = TwitchStreamAdapter(
        channel="minnarone",
        readers={
            "chat": _FakeReader("chat", [_event("chat", "c")]),
            "audio": _FakeReader("audio", [_event("audio", "a")]),
        },
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


def test_events_drain_completed_run_without_restarting_readers():
    chat = _FakeReader("chat", [_event("chat", "c")])
    adapter = TwitchStreamAdapter(channel="minnarone", readers={"chat": chat})

    async def wait_for_completion() -> None:
        while adapter.stats().running:
            await asyncio.sleep(0)

    async def run():
        await adapter.start()
        await asyncio.wait_for(wait_for_completion(), timeout=0.5)
        return [event async for event in adapter.events()]

    events = asyncio.run(run())

    assert [event.channel for event in events] == ["chat"]
    assert chat.starts == 1
    assert adapter.stats().produced["chat"] == 1


def test_start_is_idempotent_and_stop_closes_readers():
    chat = _FakeReader("chat", [_event("chat", "c")])
    adapter = TwitchStreamAdapter(channel="minnarone", readers={"chat": chat})

    async def run():
        await adapter.start()
        await adapter.start()
        await asyncio.sleep(0)
        await adapter.stop()

    asyncio.run(run())

    assert chat.starts == 1
    assert chat.stops == 1
    assert adapter.stats().running is False


def test_stop_times_out_hung_reader_cleanup_and_records_failure():
    chat = _FakeReader("chat", [], block_events=True, hang_on_stop=True)
    adapter = TwitchStreamAdapter(
        channel="minnarone",
        readers={"chat": chat},
        cleanup_timeout=0.01,
    )

    async def run():
        await adapter.start()
        await asyncio.sleep(0)
        await asyncio.wait_for(adapter.stop(), timeout=0.5)

    asyncio.run(run())

    stats = adapter.stats()
    assert chat.stops == 1
    assert stats.running is False
    assert "cleanup timed out" in stats.failures["chat"]


def test_bounded_queue_drops_media_before_chat_when_full():
    adapter = TwitchStreamAdapter(
        channel="minnarone",
        queue_size=1,
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


def test_reader_failure_is_recorded_while_other_reader_continues():
    adapter = TwitchStreamAdapter(
        channel="minnarone",
        readers={
            "chat": _FakeReader("chat", [_event("chat", "c")]),
            "video": _FakeReader(
                "video",
                [_event("video", "v")],
                fail_after=0,
            ),
        },
    )

    async def run():
        await adapter.start()
        return [event async for event in adapter.events()]

    events = asyncio.run(run())

    assert [event.channel for event in events] == ["chat"]
    stats = adapter.stats()
    assert "video failed" in stats.failures["video"]
    assert stats.produced["chat"] == 1


def test_constructor_requires_credentials_only_when_chat_reader_is_built():
    TwitchStreamAdapter(channel="minnarone", chat=False, audio=True)
    with pytest.raises(ValueError, match="credenziali"):
        TwitchStreamAdapter(channel="minnarone", chat=True, audio=False)


def test_injected_reader_must_match_mapping_channel():
    with pytest.raises(ValueError, match="reader 'chat'"):
        TwitchStreamAdapter(
            channel="minnarone",
            readers={"chat": _FakeReader("audio", [])},
        )
