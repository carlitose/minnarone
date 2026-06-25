"""Test di contratto dell'AudioPerceiver: pipeline VAD -> ASR -> speaker tag.

Tutto offline con fake deterministici: nessun modello ML, nessun device.
Le parti async usano `asyncio.run` per non dipendere da plugin pytest.
"""

import asyncio

import pytest

from minnarone.audio import (
    STREAMER,
    Asr,
    AudioChunk,
    AudioPerceiver,
    SpeakerTagger,
    Vad,
)
from minnarone.capture import OSCaptureAdapter, make_device_capture_source
from minnarone.fakes import FakeAsr, FakeSpeakerTagger, FakeVad
from minnarone.perception import Source
from minnarone.source import RawEvent
from minnarone.store import PerceptionStore


def _perceiver(tmp_path, vad, asr, tagger):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    return AudioPerceiver(store, vad, asr, tagger), store


def test_fakes_satisfy_pipeline_protocols():
    assert isinstance(FakeVad(), Vad)
    assert isinstance(FakeAsr(), Asr)
    assert isinstance(FakeSpeakerTagger(), SpeakerTagger)


def test_silence_chunk_produces_no_perception_and_skips_asr(tmp_path):
    # VAD gating: un chunk di silenzio non genera percezioni e l'ASR non parte.
    vad = FakeVad()
    asr = FakeAsr()
    perceiver, store = _perceiver(tmp_path, vad, asr, FakeSpeakerTagger())

    created = perceiver.perceive_chunk(
        AudioChunk(samples="silence", source_label="mic", ts=1.0)
    )

    assert created == []
    assert store.read_since(0.0) == []
    assert vad.calls == 1
    assert asr.calls == 0  # ASR mai invocato sul silenzio


def test_speech_chunk_flows_through_pipeline_to_store(tmp_path):
    # Un segmento di parlato VAD->ASR->tagger finisce nello store come speech.
    perceiver, store = _perceiver(
        tmp_path,
        FakeVad(),
        FakeAsr(text="ciao a tutti"),
        FakeSpeakerTagger(streamer_label="mic"),
    )

    created = perceiver.perceive_chunk(
        AudioChunk(samples="audio-bytes", source_label="mic", ts=5.0)
    )

    assert len(created) == 1
    stored = store.read_since(0.0)
    assert len(stored) == 1
    p = stored[0]
    assert p.source is Source.AUDIO
    assert p.type == "speech"
    assert p.text == "ciao a tutti"
    assert p.speaker == STREAMER
    assert p.ts == 5.0


def test_operator_tagged_streamer_video_tagged_otherwise(tmp_path):
    # EC02: il parlato dell'operatore (mic) -> streamer; l'audio del video no.
    tagger = FakeSpeakerTagger(streamer_label="mic", other_label="video")
    perceiver, store = _perceiver(
        tmp_path, FakeVad(), FakeAsr(text="parola"), tagger
    )

    perceiver.perceive_chunk(AudioChunk(samples="x", source_label="mic", ts=1.0))
    perceiver.perceive_chunk(
        AudioChunk(samples="y", source_label="system", ts=2.0)
    )

    stored = store.read_since(0.0)
    by_speaker = {p.speaker for p in stored}
    assert STREAMER in by_speaker
    assert "video" in by_speaker
    # l'audio di sistema NON è taggato come streamer
    system_p = next(p for p in stored if p.ts == 2.0)
    assert system_p.speaker != STREAMER


def test_noisy_transcription_is_recorded_without_crashing(tmp_path):
    # EC01: una trascrizione rumorosa/garbled non rompe la pipeline.
    garbled = "ciaaa@@ tttutti ###"
    perceiver, store = _perceiver(
        tmp_path, FakeVad(), FakeAsr(text=garbled), FakeSpeakerTagger()
    )

    created = perceiver.perceive_chunk(
        AudioChunk(samples="noise", source_label="mic", ts=3.0)
    )

    assert len(created) == 1
    assert store.read_since(0.0)[0].text == garbled


def test_empty_asr_text_produces_no_perception(tmp_path):
    # ASR che non ricava nulla (testo vuoto) non scrive percezioni.
    perceiver, store = _perceiver(
        tmp_path, FakeVad(), FakeAsr(text=""), FakeSpeakerTagger()
    )

    created = perceiver.perceive_chunk(
        AudioChunk(samples="audio", source_label="mic", ts=1.0)
    )

    assert created == []
    assert store.read_since(0.0) == []


def test_perceive_event_ignores_non_audio_channels(tmp_path):
    perceiver, _ = _perceiver(
        tmp_path, FakeVad(), FakeAsr(text="x"), FakeSpeakerTagger()
    )
    event = RawEvent(channel="chat", payload={"text": "ciao"}, ts=1.0)
    assert perceiver.perceive_event(event) == []


# --- OSCaptureAdapter -------------------------------------------------------


def test_os_capture_adapter_yields_audio_raw_events(tmp_path):
    # Fake capture source in-memory: ogni AudioChunk -> RawEvent(channel=audio).
    chunks = [
        AudioChunk(samples="a", source_label="mic", ts=1.0),
        AudioChunk(samples="b", source_label="system", ts=2.0),
    ]
    adapter = OSCaptureAdapter(chunks)

    async def run():
        assert adapter.channels() == {"audio"}
        await adapter.start()
        collected = [e async for e in adapter.events()]
        await adapter.stop()
        return collected

    events = asyncio.run(run())
    assert [e.channel for e in events] == ["audio", "audio"]
    assert [e.payload for e in events] == chunks
    assert [e.ts for e in events] == [1.0, 2.0]


def test_os_capture_adapter_stop_halts_stream(tmp_path):
    # stop() chiamato prima di iterare: nessun evento emesso.
    adapter = OSCaptureAdapter([AudioChunk(samples="a", ts=1.0)])

    async def run():
        await adapter.start()
        await adapter.stop()
        return [e async for e in adapter.events()]

    assert asyncio.run(run()) == []


def test_device_capture_source_is_optional_and_not_loaded_afk():
    # Il backend di device reale è un percorso opzionale: non disponibile AFK,
    # ma il modulo si carica senza dipendenze pesanti. Slot per la cattura reale.
    with pytest.raises(NotImplementedError):
        make_device_capture_source()


def test_integration_adapter_events_through_perceiver_land_in_store(tmp_path):
    # End-to-end: RawEvent dell'adapter -> AudioPerceiver -> store.
    chunks = [
        AudioChunk(samples="hello", source_label="mic", ts=1.0),
        AudioChunk(samples="silence", source_label="mic", ts=2.0),  # saltato
        AudioChunk(samples="video-line", source_label="system", ts=3.0),
    ]
    adapter = OSCaptureAdapter(chunks)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    perceiver = AudioPerceiver(
        store,
        FakeVad(),
        FakeAsr(),  # trascrive str(samples)
        FakeSpeakerTagger(streamer_label="mic"),
    )

    async def run():
        await adapter.start()
        events = [e async for e in adapter.events()]
        await adapter.stop()
        return events

    events = asyncio.run(run())
    created = perceiver.perceive_events(events)

    assert len(created) == 2  # il chunk "silence" è saltato dal VAD
    stored = store.read_since(0.0)
    texts = {p.text: p.speaker for p in stored}
    assert texts["hello"] == STREAMER
    assert texts["video-line"] != STREAMER


def test_whitespace_only_asr_text_produces_no_perception(tmp_path):
    perceiver, store = _perceiver(
        tmp_path, FakeVad(always_speech=True), FakeAsr(text="   \n\t"), FakeSpeakerTagger()
    )
    created = perceiver.perceive_chunk(AudioChunk(samples="parlato", sample_rate=16000,
                                                  source_label="mic", ts=1.0))
    assert created == []                       # niente percezione
    assert store.read_since(0.0) == []         # nulla scritto nello store


def test_stop_does_not_pull_extra_chunk(tmp_path):
    pulled = {"n": 0}

    async def counting_source():
        for i in range(5):
            pulled["n"] += 1
            yield AudioChunk(samples=f"c{i}", sample_rate=16000, source_label="mic", ts=float(i))

    adapter = OSCaptureAdapter(counting_source())

    async def drive():
        await adapter.start()
        emitted = []
        async for ev in adapter.events():
            emitted.append(ev)
            await adapter.stop()   # ferma subito dopo il primo evento
        return emitted

    emitted = asyncio.run(drive())
    assert len(emitted) == 1          # un solo evento emesso
    assert pulled["n"] == 1           # nessun chunk extra estratto dopo lo stop
