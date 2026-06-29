"""Deterministic tests for the utterance-level VAD audio path."""

import pytest

from minnarone.audio import AudioChunk
from minnarone.vad import (
    PcmFrameSplitter,
    StreamingVad,
    VadConfig,
    VadInputError,
    WebRtcVadDetector,
)


class _BytePrefixDetector:
    def is_speech(self, frame: bytes, sample_rate: int) -> bool:
        return frame.startswith(b"S")


def _frame(label: bytes, cfg: VadConfig) -> bytes:
    return label * cfg.frame_bytes


def test_vad_config_defaults_match_prd_and_validate_input_contract():
    cfg = VadConfig()

    assert cfg.mode == 2
    assert cfg.frame_ms == 30
    assert cfg.padding_ms == 300
    assert cfg.sample_rate == 16_000

    with pytest.raises(VadInputError, match="frame_ms"):
        VadConfig(frame_ms=25)
    with pytest.raises(VadInputError, match="mode"):
        VadConfig(mode=4)
    with pytest.raises(VadInputError, match="padding_ms"):
        VadConfig(padding_ms=0)
    with pytest.raises(VadInputError, match="sample_rate"):
        VadConfig(sample_rate=8_000)
    with pytest.raises(VadInputError, match="max_utterance_seconds"):
        VadConfig(padding_ms=300, max_utterance_seconds=0.1)


def test_pcm_frame_splitter_emits_exact_frames_and_carries_partial_tail():
    cfg = VadConfig(frame_ms=30)
    frame_a = b"a" * cfg.frame_bytes
    frame_b = b"b" * cfg.frame_bytes
    frame_c = b"c" * cfg.frame_bytes
    splitter = PcmFrameSplitter(cfg)

    frames = splitter.push(frame_a + frame_b[:100])

    assert frames == [frame_a]
    assert splitter.pending_bytes == 100

    frames = splitter.push(frame_b[100:] + frame_c)

    assert frames == [frame_b, frame_c]
    assert splitter.pending_bytes == 0


def test_streaming_vad_silence_only_emits_no_segments():
    cfg = VadConfig()
    vad = StreamingVad(config=cfg, detector=_BytePrefixDetector())
    silence = _frame(b"_", cfg) * 25

    assert vad.segments(AudioChunk(samples=silence, sample_rate=16_000, ts=10.0)) == []


def test_streaming_vad_partial_frame_keeps_starting_chunk_metadata():
    cfg = VadConfig(padding_ms=30)
    vad = StreamingVad(config=cfg, detector=_BytePrefixDetector())
    frame = _frame(b"S", cfg)

    assert (
        vad.segments(
            AudioChunk(
                samples=frame[:100],
                sample_rate=16_000,
                source_label="first",
                ts=42.0,
            )
        )
        == []
    )

    assert (
        vad.segments(
            AudioChunk(
                samples=frame[100:],
                sample_rate=16_000,
                source_label="second",
                ts=99.0,
            )
        )
        == []
    )

    segments = vad.flush()

    assert len(segments) == 1
    assert segments[0].ts == 42.0
    assert segments[0].source_label == "first"


def test_streaming_vad_partial_frame_followed_by_silence_preserves_metadata():
    cfg = VadConfig(padding_ms=30)
    vad = StreamingVad(config=cfg, detector=_BytePrefixDetector())
    frame = _frame(b"S", cfg)

    assert (
        vad.segments(
            AudioChunk(
                samples=frame[:100],
                sample_rate=16_000,
                source_label="first",
                ts=42.0,
            )
        )
        == []
    )

    segments = vad.segments(
        AudioChunk(
            samples=frame[100:] + _frame(b"_", cfg),
            sample_rate=16_000,
            source_label="second",
            ts=99.0,
        )
    )

    assert len(segments) == 1
    assert segments[0].ts == 42.0
    assert segments[0].source_label == "first"


def test_streaming_vad_multi_chunk_partial_frame_keeps_original_source():
    cfg = VadConfig(padding_ms=30)
    vad = StreamingVad(config=cfg, detector=_BytePrefixDetector())
    frame = _frame(b"S", cfg)

    assert (
        vad.segments(
            AudioChunk(
                samples=frame[:100],
                sample_rate=16_000,
                source_label="first",
                ts=42.0,
            )
        )
        == []
    )
    assert (
        vad.segments(
            AudioChunk(
                samples=frame[100:200],
                sample_rate=16_000,
                source_label="second",
                ts=99.0,
            )
        )
        == []
    )

    segments = vad.segments(
        AudioChunk(
            samples=frame[200:] + _frame(b"_", cfg),
            sample_rate=16_000,
            source_label="third",
            ts=100.0,
        )
    )

    assert len(segments) == 1
    assert segments[0].ts == 42.0
    assert segments[0].source_label == "first"


def test_streaming_vad_rejects_pcm_chunks_that_break_input_contract():
    cfg = VadConfig()
    vad = StreamingVad(config=cfg, detector=_BytePrefixDetector())

    with pytest.raises(VadInputError, match="sample_rate"):
        vad.segments(AudioChunk(samples=b"\0\0", sample_rate=48_000, ts=0.0))
    with pytest.raises(VadInputError, match="16-bit"):
        vad.segments(AudioChunk(samples=b"\0", sample_rate=16_000, ts=0.0))
    with pytest.raises(VadInputError, match="bytes-like"):
        vad.segments(AudioChunk(samples="not-pcm", sample_rate=16_000, ts=0.0))


def test_webrtcvad_detector_uses_runtime_dependency_on_legal_silence_frame():
    cfg = VadConfig()
    detector = WebRtcVadDetector(cfg)

    assert detector.is_speech(b"\0" * cfg.frame_bytes, cfg.sample_rate) is False


def test_streaming_vad_emits_one_padded_utterance_for_speech_burst():
    cfg = VadConfig()
    vad = StreamingVad(config=cfg, detector=_BytePrefixDetector())
    samples = _frame(b"_", cfg) * 10 + _frame(b"S", cfg) * 14 + _frame(b"_", cfg) * 9

    segments = vad.segments(
        AudioChunk(samples=samples, sample_rate=16_000, source_label="stream", ts=10.0)
    )

    assert len(segments) == 1
    assert segments[0].sample_rate == 16_000
    assert segments[0].source_label == "stream"
    assert segments[0].samples == (
        _frame(b"_", cfg) + _frame(b"S", cfg) * 14 + _frame(b"_", cfg) * 9
    )


def test_streaming_vad_force_flushes_long_continuous_speech():
    cfg = VadConfig(padding_ms=30, max_utterance_seconds=0.09)
    vad = StreamingVad(config=cfg, detector=_BytePrefixDetector())

    segments = vad.segments(
        AudioChunk(samples=_frame(b"S", cfg) * 8, sample_rate=16_000, ts=0.0)
    )

    assert [len(segment.samples) // cfg.frame_bytes for segment in segments] == [3, 3]


def test_streaming_vad_flush_emits_trailing_triggered_utterance_once():
    cfg = VadConfig(padding_ms=30)
    vad = StreamingVad(config=cfg, detector=_BytePrefixDetector())

    assert (
        vad.segments(
            AudioChunk(samples=_frame(b"S", cfg) * 2, sample_rate=16_000, ts=0.0)
        )
        == []
    )

    flushed = vad.flush()

    assert [len(segment.samples) // cfg.frame_bytes for segment in flushed] == [2]
    assert vad.flush() == []
