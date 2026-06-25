"""Boundary test del `StreamCaptureAdapter` generico (chiude T1).

Verifica il ciclo di vita `start/stop/events`, l'impacchettamento di un payload
`Timestamped` in `RawEvent(channel, payload, ts)`, la semantica real-time dello
`stop()` (nessun item estratto/emesso dopo lo stop) e la normalizzazione di una
sorgente sia sincrona sia asincrona — una volta sola, non per ogni canale.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from minnarone.capture import (
    StreamCaptureAdapter,
    os_audio_capture,
    os_screen_capture,
)


@dataclass(frozen=True)
class _Payload:
    """Payload minimale che espone `.ts` (soddisfa il Protocol `Timestamped`)."""

    name: str
    ts: float


def test_channels_reflects_configured_channel():
    assert StreamCaptureAdapter("audio", []).channels() == {"audio"}
    assert StreamCaptureAdapter("video", []).channels() == {"video"}


def test_events_wrap_sync_payloads_into_raw_events():
    payloads = [_Payload("a", 1.0), _Payload("b", 2.0)]
    adapter = StreamCaptureAdapter("audio", payloads)

    async def run():
        assert adapter.channels() == {"audio"}
        await adapter.start()
        collected = [e async for e in adapter.events()]
        await adapter.stop()
        return collected

    events = asyncio.run(run())
    assert [e.channel for e in events] == ["audio", "audio"]
    assert [e.payload for e in events] == payloads
    assert [e.ts for e in events] == [1.0, 2.0]


def test_events_normalize_async_source():
    async def async_source():
        for i in range(3):
            yield _Payload(f"f{i}", float(i))

    adapter = StreamCaptureAdapter("video", async_source())

    async def run():
        await adapter.start()
        collected = [e async for e in adapter.events()]
        await adapter.stop()
        return collected

    events = asyncio.run(run())
    assert [e.channel for e in events] == ["video", "video", "video"]
    assert [e.ts for e in events] == [0.0, 1.0, 2.0]


def test_stop_before_iteration_emits_nothing():
    adapter = StreamCaptureAdapter("audio", [_Payload("a", 1.0)])

    async def run():
        await adapter.start()
        await adapter.stop()
        return [e async for e in adapter.events()]

    assert asyncio.run(run()) == []


def test_stop_does_not_pull_extra_item():
    # Semantica real-time: dopo stop() non si estrae né si emette un item extra.
    pulled = {"n": 0}

    async def counting_source():
        for i in range(5):
            pulled["n"] += 1
            yield _Payload(f"p{i}", float(i))

    adapter = StreamCaptureAdapter("audio", counting_source())

    async def drive():
        await adapter.start()
        emitted = []
        async for ev in adapter.events():
            emitted.append(ev)
            await adapter.stop()  # ferma subito dopo il primo evento
        return emitted

    emitted = asyncio.run(drive())
    assert len(emitted) == 1
    assert pulled["n"] == 1


def test_os_audio_capture_constructor():
    adapter = os_audio_capture([_Payload("a", 1.0)])
    assert isinstance(adapter, StreamCaptureAdapter)
    assert adapter.channels() == {"audio"}


def test_os_screen_capture_constructor():
    adapter = os_screen_capture([_Payload("a", 1.0)])
    assert isinstance(adapter, StreamCaptureAdapter)
    assert adapter.channels() == {"video"}
