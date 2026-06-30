"""Deterministic tests for the local ASR backend."""

from __future__ import annotations

import struct
import sys
from types import SimpleNamespace

import pytest

from minnarone.asr import (
    AsrConfig,
    AsrInputError,
    AsrModelSetupError,
    FasterWhisperAsr,
)
from minnarone.audio import Asr, SpeechSegment


class _LazySegments:
    def __init__(self, texts: list[str]) -> None:
        self._texts = texts
        self.iterated = False

    def __iter__(self):
        self.iterated = True
        for text in self._texts:
            yield SimpleNamespace(text=text)


class _FakeWhisperModel:
    def __init__(self, texts: list[str]) -> None:
        self.calls: list[dict[str, object]] = []
        self.segments = _LazySegments(texts)

    def transcribe(self, audio, **kwargs):
        self.calls.append({"audio": audio, **kwargs})
        return self.segments, SimpleNamespace(language="it")


def test_faster_whisper_asr_transcribes_pcm_utterance_with_fake_model():
    model = _FakeWhisperModel([" ciao ", " mondo"])
    constructed: dict[str, object] = {}

    def model_factory(name: str, *, device: str, compute_type: str):
        constructed.update(
            {"name": name, "device": device, "compute_type": compute_type}
        )
        return model

    asr = FasterWhisperAsr(
        AsrConfig(device="cpu", compute_type="int8", language="it", beam_size=3),
        model_factory=model_factory,
    )

    text = asr.transcribe(
        SpeechSegment(
            samples=struct.pack("<hhh", -32768, 0, 32767),
            sample_rate=16_000,
            ts=12.0,
        )
    )

    assert isinstance(asr, Asr)
    assert constructed == {
        "name": "large-v3-turbo",
        "device": "cpu",
        "compute_type": "int8",
    }
    assert text == "ciao mondo"
    assert model.segments.iterated is True
    call = model.calls[0]
    assert call["language"] == "it"
    assert call["beam_size"] == 3
    assert call["condition_on_previous_text"] is False
    audio = call["audio"]
    assert getattr(audio, "typecode", None) == "f" or str(
        getattr(audio, "dtype", "")
    ) == "float32"
    assert list(audio) == pytest.approx([-1.0, 0.0, 32767 / 32768])


def test_faster_whisper_asr_uses_noop_progress_during_lazy_transcription(
    monkeypatch,
):
    class ExplodingTqdm:
        def __init__(self, *args, **kwargs) -> None:
            raise ValueError("bad value(s) in fds_to_keep")

    fake_transcribe_module = SimpleNamespace(tqdm=ExplodingTqdm)
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper.transcribe",
        fake_transcribe_module,
    )

    class TqdmUsingSegments:
        def __iter__(self):
            progress = fake_transcribe_module.tqdm(total=1, disable=True)
            progress.update(1)
            progress.close()
            yield SimpleNamespace(text=" audio ok ")

    class TqdmUsingModel:
        def transcribe(self, audio, **kwargs):
            return TqdmUsingSegments(), SimpleNamespace(language="it")

    asr = FasterWhisperAsr(
        AsrConfig(device="cpu", compute_type="int8"),
        model_factory=lambda *args, **kwargs: TqdmUsingModel(),
    )

    text = asr.transcribe(
        SpeechSegment(
            samples=struct.pack("<h", 0),
            sample_rate=16_000,
            ts=12.0,
        )
    )

    assert text == "audio ok"
    assert fake_transcribe_module.tqdm is ExplodingTqdm


def test_faster_whisper_model_setup_failure_is_actionable():
    def broken_factory(name: str, *, device: str, compute_type: str):
        raise RuntimeError("model path not found")

    with pytest.raises(AsrModelSetupError) as excinfo:
        FasterWhisperAsr(
            AsrConfig(device="cpu", compute_type="int8"),
            model_factory=broken_factory,
        )

    message = str(excinfo.value)
    assert "faster-whisper" in message
    assert "large-v3-turbo" in message
    assert "cpu" in message
    assert "int8" in message
    assert "model path not found" in message


def test_faster_whisper_asr_rejects_non_16khz_segments_before_model_call():
    model = _FakeWhisperModel(["ignored"])
    asr = FasterWhisperAsr(
        AsrConfig(device="cpu", compute_type="int8"),
        model_factory=lambda *args, **kwargs: model,
    )

    with pytest.raises(AsrInputError, match="16000"):
        asr.transcribe(
            SpeechSegment(
                samples=struct.pack("<h", 0),
                sample_rate=48_000,
                ts=12.0,
            )
        )

    assert model.calls == []
