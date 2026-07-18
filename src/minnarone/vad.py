"""Streaming WebRTC VAD utterance segmentation.

The public contract is intentionally narrow: callers provide raw mono 16 kHz
signed 16-bit PCM `AudioChunk` values and receive completed `SpeechSegment`
utterances. ASR and speaker tagging live downstream.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from .audio import AudioChunk, SpeechSegment


class VadInputError(ValueError):
    """Invalid PCM/VAD configuration or input."""


@dataclass(frozen=True, slots=True)
class VadConfig:
    """Configuration for legal WebRTC VAD frames and utterance collection."""

    mode: int = 2
    frame_ms: int = 30
    padding_ms: int = 300
    max_utterance_seconds: float = 30.0
    sample_rate: int = 16_000

    def __post_init__(self) -> None:
        if (
            isinstance(self.mode, bool)
            or not isinstance(self.mode, int)
            or self.mode not in range(4)
        ):
            raise VadInputError("mode deve essere un intero tra 0 e 3")
        if (
            isinstance(self.frame_ms, bool)
            or not isinstance(self.frame_ms, int)
            or self.frame_ms not in {10, 20, 30}
        ):
            raise VadInputError("frame_ms deve essere 10, 20 o 30")
        if (
            isinstance(self.padding_ms, bool)
            or not isinstance(self.padding_ms, int)
            or self.padding_ms <= 0
        ):
            raise VadInputError("padding_ms deve essere > 0")
        if self.padding_ms < self.frame_ms:
            raise VadInputError("padding_ms deve essere >= frame_ms")
        if not math.isfinite(self.max_utterance_seconds):
            raise VadInputError("max_utterance_seconds deve essere finito")
        if self.max_utterance_seconds <= 0:
            raise VadInputError("max_utterance_seconds deve essere > 0")
        if self.max_utterance_seconds < self.padding_ms / 1000:
            raise VadInputError(
                "max_utterance_seconds deve essere >= padding_ms / 1000"
            )
        if self.sample_rate != 16_000:
            raise VadInputError("sample_rate deve essere 16000 Hz")

    @property
    def frame_bytes(self) -> int:
        """Bytes in one mono signed 16-bit PCM frame."""
        return int(self.sample_rate * self.frame_ms / 1000) * 2

    @property
    def frame_seconds(self) -> float:
        """Duration of one VAD frame in seconds."""
        return self.frame_ms / 1000

    @property
    def padding_frames(self) -> int:
        """Number of VAD frames retained for pre-roll/hangover padding."""
        return math.ceil(self.padding_ms / self.frame_ms)

    @property
    def threshold_frames(self) -> int:
        """90% speech/silence threshold expressed as a frame count."""
        return max(1, math.ceil(self.padding_frames * 0.9))

    @property
    def max_utterance_frames(self) -> int:
        """Maximum utterance duration expressed as whole VAD frames."""
        return max(
            1,
            math.floor((self.max_utterance_seconds * 1000) / self.frame_ms),
        )


class PcmFrameSplitter:
    """Split arbitrary PCM chunks into exact WebRTC VAD frames."""

    def __init__(self, config: VadConfig) -> None:
        self._config = config
        self._pending = bytearray()

    @property
    def pending_bytes(self) -> int:
        """Bytes waiting for a future chunk to complete a frame."""
        return len(self._pending)

    def push(self, pcm: bytes | bytearray | memoryview) -> list[bytes]:
        """Return complete frames, carrying any incomplete trailing bytes."""
        if not isinstance(pcm, (bytes, bytearray, memoryview)):
            raise VadInputError("samples deve essere PCM bytes-like")
        raw = bytes(pcm)
        if len(raw) % 2:
            raise VadInputError("samples deve essere PCM mono 16-bit sample-aligned")
        data = self._pending + raw
        frame_bytes = self._config.frame_bytes
        complete_bytes = (len(data) // frame_bytes) * frame_bytes
        frames = [
            bytes(data[index : index + frame_bytes])
            for index in range(0, complete_bytes, frame_bytes)
        ]
        self._pending = bytearray(data[complete_bytes:])
        return frames


@dataclass(frozen=True, slots=True)
class _TimedFrame:
    pcm: bytes
    ts: float
    source_label: str


class StreamingVad:
    """Stateful VAD adapter from raw PCM chunks to speech utterances."""

    def __init__(self, *, config: VadConfig | None = None, detector: object) -> None:
        self._config = config or VadConfig()
        self._detector = detector
        self._splitter = PcmFrameSplitter(self._config)
        self._pending_start_ts: float | None = None
        self._pending_source_label: str | None = None
        self._ring: deque[tuple[bytes, bool, float, str]] = deque(
            maxlen=self._config.padding_frames
        )
        self._voiced: list[tuple[bytes, float, str]] = []
        self._triggered = False
        self._next_frame_ts: float | None = None

    def segments(self, chunk: AudioChunk) -> list[SpeechSegment]:
        """Return completed speech utterances from this PCM chunk."""
        if chunk.sample_rate != self._config.sample_rate:
            raise VadInputError("AudioChunk.sample_rate deve essere 16000 Hz")
        if self._next_frame_ts is None:
            self._next_frame_ts = chunk.ts

        emitted: list[SpeechSegment] = []
        frames = self._timed_frames(chunk)
        for timed_frame in frames:
            frame = timed_frame.pcm
            is_speech = bool(
                self._detector.is_speech(frame, self._config.sample_rate)  # type: ignore[attr-defined]
            )
            emitted.extend(
                self._accept_frame(
                    frame,
                    is_speech=is_speech,
                    ts=timed_frame.ts,
                    source_label=timed_frame.source_label,
                )
            )
        return emitted

    def _timed_frames(self, chunk: AudioChunk) -> list[_TimedFrame]:
        assert self._next_frame_ts is not None
        frame_start_ts = self._pending_start_ts
        frame_source_label = self._pending_source_label
        if self._splitter.pending_bytes == 0:
            frame_start_ts = self._next_frame_ts
            frame_source_label = chunk.source_label
        frames = self._splitter.push(chunk.samples)  # type: ignore[arg-type]
        timed: list[_TimedFrame] = []
        for frame in frames:
            assert frame_start_ts is not None
            assert frame_source_label is not None
            timed.append(
                _TimedFrame(
                    pcm=frame,
                    ts=frame_start_ts,
                    source_label=frame_source_label,
                )
            )
            frame_start_ts += self._config.frame_seconds
            frame_source_label = chunk.source_label
        self._next_frame_ts = frame_start_ts
        if self._splitter.pending_bytes:
            self._pending_start_ts = frame_start_ts
            self._pending_source_label = frame_source_label
        else:
            self._pending_start_ts = None
            self._pending_source_label = None
        return timed

    def flush(self) -> list[SpeechSegment]:
        """Emit the active triggered utterance, if one is in progress."""
        if not self._triggered or not self._voiced:
            return []
        self._triggered = False
        self._ring.clear()
        return [self._flush_voiced()]

    def _accept_frame(
        self,
        frame: bytes,
        *,
        is_speech: bool,
        ts: float,
        source_label: str,
    ) -> list[SpeechSegment]:
        if not self._triggered:
            self._ring.append((frame, is_speech, ts, source_label))
            if self._ring_is_ready(speech=True):
                self._triggered = True
                self._voiced.extend(
                    (queued_frame, queued_ts, queued_source)
                    for queued_frame, _speech, queued_ts, queued_source in self._ring
                )
                self._ring.clear()
                if self._max_duration_reached():
                    self._triggered = False
                    return [self._flush_voiced()]
            return []

        self._voiced.append((frame, ts, source_label))
        self._ring.append((frame, is_speech, ts, source_label))
        if self._max_duration_reached():
            self._triggered = False
            self._ring.clear()
            return [self._flush_voiced()]
        if not self._ring_is_ready(speech=False):
            return []

        self._triggered = False
        self._ring.clear()
        return [self._flush_voiced()]

    def _ring_is_ready(self, *, speech: bool) -> bool:
        if len(self._ring) < self._config.padding_frames:
            return False
        matching = sum(
            1 for _frame, is_speech, _ts, _source in self._ring if is_speech is speech
        )
        return matching >= self._config.threshold_frames

    def _max_duration_reached(self) -> bool:
        return len(self._voiced) >= self._config.max_utterance_frames

    def _flush_voiced(self) -> SpeechSegment:
        segment = _speech_segment(self._voiced, sample_rate=self._config.sample_rate)
        self._voiced = []
        return segment


class WebRtcVadDetector:
    """Thin adapter over the `webrtcvad` Python package."""

    def __init__(self, config: VadConfig | None = None) -> None:
        self._config = config or VadConfig()
        try:
            import webrtcvad
        except ImportError as exc:  # pragma: no cover - exercised by packaging.
            raise RuntimeError(
                "dipendenza runtime mancante: installa webrtcvad-wheels"
            ) from exc
        self._vad = webrtcvad.Vad()
        self._vad.set_mode(self._config.mode)

    def is_speech(self, frame: bytes, sample_rate: int) -> bool:
        """Return whether this legal PCM frame contains speech."""
        return bool(self._vad.is_speech(frame, sample_rate))


def _speech_segment(
    frames: Iterable[tuple[bytes, float, str]],
    *,
    sample_rate: int,
) -> SpeechSegment:
    materialized = list(frames)
    first = materialized[0]
    return SpeechSegment(
        samples=b"".join(frame for frame, _ts, _source in materialized),
        sample_rate=sample_rate,
        source_label=first[2],
        ts=first[1],
    )
