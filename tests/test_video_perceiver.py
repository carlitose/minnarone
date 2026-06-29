"""Test di contratto del VideoPerceiver: sampling -> hashing/dedup -> caption.

Tutto offline con fake deterministici: nessun modello VLM, nessun device schermo.
La parte model-free (campionamento + hashing per saltare frame ~identici) è
quella esercitata davvero e in modo deterministico. Le parti async usano
`asyncio.run` per non dipendere da plugin pytest.
"""

import asyncio

import pytest

from minnarone.capture import (
    ScreenCaptureAdapter,
    make_device_screen_capture_source,
)
from minnarone.fakes import FakeCaptioner
from minnarone.perception import Source
from minnarone.source import RawEvent
from minnarone.store import PerceptionStore
from minnarone.video import (
    ByteFrameDeduper,
    Captioner,
    VideoFrame,
    VideoPerceiver,
    VideoPerceptionConfig,
)


def _perceiver(tmp_path, captioner, **kwargs):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    return VideoPerceiver(store, captioner, **kwargs), store


def test_fake_captioner_satisfies_protocol():
    assert isinstance(FakeCaptioner(), Captioner)


def test_new_frame_produces_caption_perception(tmp_path):
    # Un frame genuinamente nuovo -> captioner invocato -> Perception(video, caption).
    captioner = FakeCaptioner(text="una tazza rossa")
    perceiver, store = _perceiver(tmp_path, captioner)

    created = perceiver.perceive_frame(
        VideoFrame(pixels="frame-a", ts=5.0)
    )

    assert len(created) == 1
    assert captioner.calls == 1
    p = store.read_since(0.0)[0]
    assert p.source is Source.VIDEO
    assert p.type == "caption"
    assert p.text == "una tazza rossa"
    assert p.ts == 5.0


def test_near_identical_consecutive_frames_are_skipped_via_hashing(tmp_path):
    # Frame consecutivi identici: hashing -> il captioner è chiamato UNA volta sola
    # e non si producono percezioni duplicate.
    captioner = FakeCaptioner(text="schermo")
    perceiver, store = _perceiver(tmp_path, captioner)

    perceiver.perceive_frame(VideoFrame(pixels="same", ts=1.0))
    perceiver.perceive_frame(VideoFrame(pixels="same", ts=2.0))
    perceiver.perceive_frame(VideoFrame(pixels="same", ts=3.0))

    assert captioner.calls == 1
    assert len(store.read_since(0.0)) == 1


def test_changed_frame_after_identical_run_produces_new_caption(tmp_path):
    # Dopo una serie di frame identici, un frame cambiato riattiva il captioner.
    captioner = FakeCaptioner()  # caption = str(pixels)
    perceiver, store = _perceiver(tmp_path, captioner)

    perceiver.perceive_frame(VideoFrame(pixels="a", ts=1.0))
    perceiver.perceive_frame(VideoFrame(pixels="a", ts=2.0))  # saltato
    perceiver.perceive_frame(VideoFrame(pixels="b", ts=3.0))  # nuovo

    assert captioner.calls == 2
    texts = [p.text for p in store.read_since(-1.0)]
    assert texts == ["a", "b"]


def test_sampling_reduces_captioner_calls(tmp_path):
    # Il captioning è campionato, non per-frame: con sample_every=3 solo 1 frame
    # su 3 viene considerato per il captioning (vincolo costo/latenza).
    captioner = FakeCaptioner()  # caption = str(pixels)
    perceiver, store = _perceiver(tmp_path, captioner, sample_every=3)

    # 6 frame tutti diversi: senza sampling sarebbero 6 caption.
    for i in range(6):
        perceiver.perceive_frame(VideoFrame(pixels=f"f{i}", ts=float(i)))

    # Campionati gli indici 0 e 3 -> 2 caption.
    assert captioner.calls == 2
    texts = [p.text for p in store.read_since(-1.0)]
    assert texts == ["f0", "f3"]


def test_configured_sample_every_reduces_captioner_calls(tmp_path):
    captioner = FakeCaptioner()
    perceiver, store = _perceiver(
        tmp_path,
        captioner,
        config=VideoPerceptionConfig(sample_every=2),
    )

    for i in range(5):
        perceiver.perceive_frame(VideoFrame(pixels=f"f{i}", ts=float(i)))

    assert captioner.calls == 3
    assert [p.text for p in store.read_since(-1.0)] == ["f0", "f2", "f4"]


def test_video_perceiver_stats_track_sampling_dedup_and_failures(tmp_path):
    class SometimesFailingCaptioner:
        def caption(self, frame: VideoFrame) -> str:
            if frame.pixels == "fail":
                raise RuntimeError("vlm failed")
            return str(frame.pixels)

    perceiver, _store_obj = _perceiver(
        tmp_path,
        SometimesFailingCaptioner(),
        sample_every=2,
    )

    perceiver.perceive_frame(VideoFrame(pixels="a", ts=1.0))  # captioned
    perceiver.perceive_frame(VideoFrame(pixels="ignored", ts=2.0))  # sampled out
    perceiver.perceive_frame(VideoFrame(pixels="a", ts=3.0))  # dedup skip
    perceiver.perceive_frame(VideoFrame(pixels="skipped", ts=4.0))  # sampled out
    with pytest.raises(RuntimeError, match="vlm failed"):
        perceiver.perceive_frame(VideoFrame(pixels="fail", ts=5.0))

    stats = perceiver.stats()
    assert stats.frames_seen == 5
    assert stats.sampled == 3
    assert stats.dedup_skipped == 1
    assert stats.captioned == 1
    assert stats.failed == 1


def test_dedup_threshold_skips_micro_changes_before_captioning(tmp_path):
    captioner = FakeCaptioner()
    perceiver, store = _perceiver(
        tmp_path,
        captioner,
        dedup_change_threshold=0.2,
    )

    perceiver.perceive_frame(VideoFrame(pixels=b"\x00" * 10, ts=1.0))
    perceiver.perceive_frame(VideoFrame(pixels=b"\x01" + (b"\x00" * 9), ts=2.0))
    perceiver.perceive_frame(VideoFrame(pixels=b"\xff" * 10, ts=3.0))

    assert captioner.calls == 2
    assert [p.ts for p in store.read_since(0.0)] == [1.0, 3.0]


def test_byte_frame_deduper_is_testable_without_captioner_or_pyav():
    deduper = ByteFrameDeduper(change_threshold=0.5)
    first = VideoFrame(pixels=b"\x00" * 4, ts=1.0)
    tiny_change = VideoFrame(pixels=b"\x01" + (b"\x00" * 3), ts=2.0)
    big_change = VideoFrame(pixels=b"\xff" * 4, ts=3.0)

    assert deduper.should_caption(first) is True
    deduper.remember(first)
    assert deduper.should_caption(first) is False
    assert deduper.should_caption(tiny_change) is False
    assert deduper.should_caption(big_change) is True


def test_empty_caption_produces_no_perception(tmp_path):
    # VLM che ritorna stringa vuota/whitespace -> nessuna percezione (guardia .strip()).
    captioner = FakeCaptioner(text="   \n\t")
    perceiver, store = _perceiver(tmp_path, captioner)

    created = perceiver.perceive_frame(VideoFrame(pixels="x", ts=1.0))

    assert created == []
    assert store.read_since(0.0) == []


def test_empty_caption_still_updates_dedup_reference(tmp_path):
    captioner = FakeCaptioner(text="   \n\t")
    perceiver, store = _perceiver(tmp_path, captioner)

    perceiver.perceive_frame(VideoFrame(pixels="static", ts=1.0))
    perceiver.perceive_frame(VideoFrame(pixels="static", ts=2.0))

    assert captioner.calls == 1
    assert store.read_since(0.0) == []


def test_caption_failure_still_updates_dedup_reference(tmp_path):
    class FailingCaptioner:
        def __init__(self):
            self.calls = 0

        def caption(self, _frame: VideoFrame) -> str:
            self.calls += 1
            raise RuntimeError("vlm failed")

    captioner = FailingCaptioner()
    perceiver, store = _perceiver(tmp_path, captioner)

    with pytest.raises(RuntimeError, match="vlm failed"):
        perceiver.perceive_frame(VideoFrame(pixels="static", ts=1.0))

    assert perceiver.perceive_frame(VideoFrame(pixels="static", ts=2.0)) == []
    assert captioner.calls == 1
    assert store.read_since(0.0) == []


def test_zero_timestamp_is_preserved(tmp_path):
    captioner = FakeCaptioner(text="zero")
    perceiver, store = _perceiver(tmp_path, captioner)

    created = perceiver.perceive_frame(VideoFrame(pixels="frame", ts=0.0))

    assert len(created) == 1
    assert created[0].ts == 0.0
    assert store.read_since(-1.0)[0].ts == 0.0


def test_dedup_threshold_rejects_one_point_zero():
    with pytest.raises(ValueError, match="change_threshold"):
        ByteFrameDeduper(change_threshold=1.0)
    with pytest.raises(ValueError, match="dedup_change_threshold"):
        VideoPerceptionConfig(dedup_change_threshold=1.0)


def test_perceive_event_ignores_non_video_channels(tmp_path):
    perceiver, _ = _perceiver(tmp_path, FakeCaptioner(text="x"))
    event = RawEvent(channel="audio", payload={"x": 1}, ts=1.0)
    assert perceiver.perceive_event(event) == []


def test_perceive_event_rejects_wrong_payload(tmp_path):
    perceiver, _ = _perceiver(tmp_path, FakeCaptioner(text="x"))
    event = RawEvent(channel="video", payload="not-a-frame", ts=1.0)
    with pytest.raises(TypeError):
        perceiver.perceive_event(event)


# --- ScreenCaptureAdapter ---------------------------------------------------


def test_screen_capture_adapter_yields_video_raw_events(tmp_path):
    frames = [
        VideoFrame(pixels="a", ts=1.0),
        VideoFrame(pixels="b", ts=2.0),
    ]
    adapter = ScreenCaptureAdapter(frames)

    async def run():
        assert adapter.channels() == {"video"}
        await adapter.start()
        collected = [e async for e in adapter.events()]
        await adapter.stop()
        return collected

    events = asyncio.run(run())
    assert [e.channel for e in events] == ["video", "video"]
    assert [e.payload for e in events] == frames
    assert [e.ts for e in events] == [1.0, 2.0]


def test_screen_capture_adapter_stop_halts_stream(tmp_path):
    adapter = ScreenCaptureAdapter([VideoFrame(pixels="a", ts=1.0)])

    async def run():
        await adapter.start()
        await adapter.stop()
        return [e async for e in adapter.events()]

    assert asyncio.run(run()) == []


def test_screen_capture_stop_does_not_pull_extra_frame(tmp_path):
    pulled = {"n": 0}

    async def counting_source():
        for i in range(5):
            pulled["n"] += 1
            yield VideoFrame(pixels=f"f{i}", ts=float(i))

    adapter = ScreenCaptureAdapter(counting_source())

    async def drive():
        await adapter.start()
        emitted = []
        async for ev in adapter.events():
            emitted.append(ev)
            await adapter.stop()  # ferma subito dopo il primo evento
        return emitted

    emitted = asyncio.run(drive())
    assert len(emitted) == 1
    assert pulled["n"] == 1  # nessun frame extra estratto dopo lo stop


def test_device_screen_capture_source_is_optional_and_not_loaded_afk():
    # Il backend di cattura schermo reale è opzionale: non disponibile AFK, ma
    # il modulo si carica senza dipendenze pesanti (nessun VLM/PyAV importato).
    with pytest.raises(NotImplementedError):
        make_device_screen_capture_source()


def test_integration_adapter_frames_through_perceiver_land_in_store(tmp_path):
    # End-to-end: RawEvent dell'adapter -> VideoPerceiver -> store. I frame
    # identici NON producono duplicati.
    frames = [
        VideoFrame(pixels="scene-1", ts=1.0),
        VideoFrame(pixels="scene-1", ts=2.0),  # identico: saltato
        VideoFrame(pixels="scene-2", ts=3.0),
    ]
    adapter = ScreenCaptureAdapter(frames)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    perceiver = VideoPerceiver(store, FakeCaptioner())  # caption = str(pixels)

    async def run():
        await adapter.start()
        events = [e async for e in adapter.events()]
        await adapter.stop()
        return events

    events = asyncio.run(run())
    created = perceiver.perceive_events(events)

    assert len(created) == 2  # il frame "scene-1" ripetuto è saltato
    texts = [p.text for p in store.read_since(0.0)]
    assert texts == ["scene-1", "scene-2"]
    for p in store.read_since(0.0):
        assert p.source is Source.VIDEO
        assert p.type == "caption"


class _FakeArray:
    """Stand-in di un ndarray: espone tobytes() come numpy, con repr troncato."""

    def __init__(self, content: bytes) -> None:
        self._content = content

    def tobytes(self) -> bytes:
        return self._content

    def __repr__(self) -> str:  # repr identico => smaschera l'hash basato su repr
        return "<array ...troncato...>"


def test_frame_hash_uses_content_bytes_not_truncated_repr(tmp_path):
    from minnarone.video import _frame_hash

    a = VideoFrame(pixels=_FakeArray(b"AAAA" * 1000 + b"X"), ts=1.0)
    b = VideoFrame(pixels=_FakeArray(b"AAAA" * 1000 + b"Y"), ts=2.0)
    # repr identico ma contenuto diverso: gli hash DEVONO differire.
    assert repr(a.pixels) == repr(b.pixels)
    assert _frame_hash(a) != _frame_hash(b)


def test_distinct_array_frames_are_not_deduped(tmp_path):
    store = PerceptionStore(tmp_path / "p.jsonl")
    cap = FakeCaptioner(text="caption")
    perceiver = VideoPerceiver(store, cap)
    perceiver.perceive_frame(VideoFrame(pixels=_FakeArray(b"AAAA" * 1000 + b"X"), ts=1.0))
    perceiver.perceive_frame(VideoFrame(pixels=_FakeArray(b"AAAA" * 1000 + b"Y"), ts=2.0))
    # due frame con contenuto diverso non collassano in uno solo
    assert len(store.read_since(0.0)) == 2
