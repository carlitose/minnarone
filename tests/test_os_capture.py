"""Boundary test dell'`OsCaptureAdapter` (slice 05).

Verifica che, data una `OsCaptureConfig` e le sorgenti device iniettate (liste
in-memory di `AudioChunk`/`VideoFrame`), l'adapter componga i `StreamCaptureAdapter`
di canale in un unico stream `RawEvent` via `MergingSourceAdapter`: emette gli
eventi sui canali attesi con il payload corretto, rispetta il ciclo di vita
`start()/stop()`, si ferma quando le sorgenti si esauriscono, espone `stats()`
coerenti, solleva se una sorgente di canale abilitato manca e NON itera le
sorgenti prima di `start()`.
"""

from __future__ import annotations

import asyncio

import pytest

from minnarone.audio import AudioChunk
from minnarone.config import OsCaptureConfig
from minnarone.merge import MergeStats
from minnarone.os_capture import OsCaptureAdapter
from minnarone.source import RawEvent
from minnarone.video import VideoFrame


def _audio(n: int) -> list[AudioChunk]:
    return [AudioChunk(samples=f"a{i}", ts=float(i)) for i in range(n)]


def _video(n: int) -> list[VideoFrame]:
    return [VideoFrame(pixels=f"v{i}", ts=float(i)) for i in range(n)]


async def _drain(adapter: OsCaptureAdapter) -> list[RawEvent]:
    await adapter.start()
    collected = [event async for event in adapter.events()]
    await adapter.stop()
    return collected


def test_channels_reflects_enabled_audio_and_video() -> None:
    config = OsCaptureConfig(audio=True, video=True)
    adapter = OsCaptureAdapter(config, audio_source=_audio(1), video_source=_video(1))
    assert adapter.channels() == {"audio", "video"}


def test_channels_audio_only() -> None:
    config = OsCaptureConfig(audio=True, video=False)
    adapter = OsCaptureAdapter(config, audio_source=_audio(1))
    assert adapter.channels() == {"audio"}


def test_channels_video_only() -> None:
    config = OsCaptureConfig(audio=False, video=True)
    adapter = OsCaptureAdapter(config, video_source=_video(1))
    assert adapter.channels() == {"video"}


def test_audio_only_emits_audio_raw_events_with_payloads() -> None:
    chunks = _audio(3)
    config = OsCaptureConfig(audio=True, video=False)
    adapter = OsCaptureAdapter(config, audio_source=chunks)

    events = asyncio.run(_drain(adapter))

    assert {event.channel for event in events} == {"audio"}
    assert [event.payload for event in events] == chunks
    assert [event.ts for event in events] == [0.0, 1.0, 2.0]


def test_video_only_emits_video_raw_events_with_payloads() -> None:
    frames = _video(2)
    config = OsCaptureConfig(audio=False, video=True)
    adapter = OsCaptureAdapter(config, video_source=frames)

    events = asyncio.run(_drain(adapter))

    assert {event.channel for event in events} == {"video"}
    assert [event.payload for event in events] == frames


def test_both_channels_emit_expected_payload_types() -> None:
    chunks = _audio(2)
    frames = _video(2)
    config = OsCaptureConfig(audio=True, video=True)
    adapter = OsCaptureAdapter(config, audio_source=chunks, video_source=frames)

    events = asyncio.run(_drain(adapter))

    by_channel: dict[str, list[object]] = {"audio": [], "video": []}
    for event in events:
        by_channel[event.channel].append(event.payload)
    assert by_channel["audio"] == chunks
    assert by_channel["video"] == frames


def test_stops_when_sources_exhaust() -> None:
    config = OsCaptureConfig(audio=True, video=False)
    adapter = OsCaptureAdapter(config, audio_source=_audio(2))

    async def run() -> bool:
        await adapter.start()
        async for _event in adapter.events():
            pass
        # Le sorgenti si sono esaurite: il merge non è più running.
        running = adapter.stats().running
        await adapter.stop()
        return running

    assert asyncio.run(run()) is False


def test_stop_halts_a_still_live_stream() -> None:
    # Osservabile che conta davvero: `stop()` porta il merge a NON running anche
    # quando la sorgente non si è esaurita. La sorgente emette un chunk e poi si
    # blocca per sempre, quindi il worker resta VIVO: l'unica cosa che può
    # fermarlo è `stop()`. (Il vecchio `len(emitted) == 1` non provava l'halt: il
    # merger drena avidamente in un buffer da 100 e lo stream si fermava da solo
    # per esaurimento, non per effetto di stop().)
    async def blocking_source():
        yield AudioChunk(samples="a0", ts=0.0)
        await asyncio.Event().wait()  # non si esaurisce mai

    config = OsCaptureConfig(audio=True, video=False)
    adapter = OsCaptureAdapter(config, audio_source=blocking_source())

    async def run() -> bool:
        await adapter.start()
        async for _event in adapter.events():
            # Mentre il worker è ancora vivo (sorgente non esaurita), fermiamo.
            assert adapter.stats().running is True
            await adapter.stop()
            break
        return adapter.stats().running

    assert asyncio.run(run()) is False


def test_backpressure_drops_both_channels_no_channel_is_protected() -> None:
    # PIN della decisione OS-specifica `priority_channels=()` (os_capture.py):
    # la cattura del SO non ha una chat da proteggere, quindi audio e video
    # sono paritari sotto pressione e ENTRAMBI possono essere droppati. Se
    # qualcuno cambiasse la riga in `("audio",)`, `("video",)` o `("chat",)`,
    # questo test deve fallire.
    #
    # Tecnica deterministica (come test_merge.py): pilotiamo `_enqueue`
    # direttamente con `queue_size=1`, così l'ordine è preciso e colpiamo il
    # ramo di overflow senza dipendere dallo scheduler.
    config = OsCaptureConfig(audio=True, video=True)
    adapter = OsCaptureAdapter(
        config,
        audio_source=_audio(1),
        video_source=_video(1),
        queue_size=1,
    )
    merger = adapter._merger  # noqa: SLF001 - pin della composizione OS.

    audio_evt = RawEvent(channel="audio", payload="a", ts=0.0)
    video_evt = RawEvent(channel="video", payload="v", ts=0.0)

    async def overflow_channel(filler: RawEvent, overflow: RawEvent) -> None:
        # Riempie il buffer (size 1) col filler, poi tenta l'overflow: senza
        # canali prioritari NON c'è eviction, quindi l'overflow è droppato e il
        # buffer resta col filler originale.
        await merger._enqueue(filler)  # noqa: SLF001
        await merger._enqueue(overflow)  # noqa: SLF001

    async def run() -> tuple[frozenset[str], dict[str, int], list[str]]:
        # Overflow su video (audio filler): video viene droppato.
        await overflow_channel(audio_evt, video_evt)
        # Overflow su audio (video filler): audio viene droppato.
        await overflow_channel(video_evt, audio_evt)
        return (
            merger._priority,  # noqa: SLF001
            dict(merger.stats().dropped),
            [event.channel for event in merger._buffer],  # noqa: SLF001
        )

    priority, dropped, buffered = asyncio.run(run())

    # Nessun canale è protetto: la priorità del merge è vuota...
    assert priority == frozenset()
    # ...e sotto pressione ENTRAMBI i canali vengono droppati (nessuna
    # eviction ha promosso l'overflow al posto del filler bufferizzato).
    assert dropped["audio"] >= 1
    assert dropped["video"] >= 1
    assert buffered == ["audio"]


def test_stats_returns_coherent_merge_stats() -> None:
    config = OsCaptureConfig(audio=True, video=True)
    adapter = OsCaptureAdapter(config, audio_source=_audio(2), video_source=_video(3))

    async def run() -> MergeStats:
        await adapter.start()
        async for _event in adapter.events():
            pass
        stats = adapter.stats()
        await adapter.stop()
        return stats

    stats = asyncio.run(run())
    assert isinstance(stats, MergeStats)
    assert stats.produced == {"audio": 2, "video": 3}
    assert stats.dropped == {"audio": 0, "video": 0}
    assert stats.failures == {}


def test_missing_audio_source_for_enabled_channel_raises() -> None:
    config = OsCaptureConfig(audio=True, video=False)
    with pytest.raises(ValueError, match="audio"):
        OsCaptureAdapter(config, audio_source=None)


def test_missing_video_source_for_enabled_channel_raises() -> None:
    config = OsCaptureConfig(audio=False, video=True)
    with pytest.raises(ValueError, match="video"):
        OsCaptureAdapter(config, video_source=None)


def test_sources_not_iterated_before_start() -> None:
    pulled = {"n": 0}

    def counting_source():
        for i in range(3):
            pulled["n"] += 1
            yield AudioChunk(samples=f"a{i}", ts=float(i))

    config = OsCaptureConfig(audio=True, video=False)
    OsCaptureAdapter(config, audio_source=counting_source())

    # La costruzione dell'adapter non deve estrarre nulla dalla sorgente.
    assert pulled["n"] == 0
