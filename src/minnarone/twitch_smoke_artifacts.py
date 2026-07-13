"""Smoke artifact writer for Twitch capture slices."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .audio import AudioChunk, SpeechSegment, Vad
from .chat import ChatPerceiver
from .source import RawEvent, SourceAdapter
from .store import PerceptionStore
from .video import VideoFrame

_SMOKE_STOP_TIMEOUT_SECONDS = 5.0


@dataclass(slots=True)
class SmokeStats:
    """Counters and failures written at the end of a manual smoke run."""

    chat_events: int = 0
    audio_events: int = 0
    audio_samples_saved: int = 0
    vad_utterances: int = 0
    vad_utterance_durations_ms: list[float] = field(default_factory=list)
    video_events: int = 0
    video_frames_saved: int = 0
    failures: list[str] = field(default_factory=list)

    def as_json(self) -> dict[str, object]:
        return {
            "chat_events": self.chat_events,
            "audio_events": self.audio_events,
            "audio_samples_saved": self.audio_samples_saved,
            "vad_utterances": self.vad_utterances,
            "vad_utterance_durations_ms": list(self.vad_utterance_durations_ms),
            "video_events": self.video_events,
            "video_frames_saved": self.video_frames_saved,
            "failures": list(self.failures),
        }


class TwitchSmokeArtifacts:
    """Writes bounded capture artifacts under one output directory."""

    def __init__(
        self,
        output_dir: str | Path,
        *,
        max_audio_samples: int = 3,
        max_video_frames: int = 3,
        perceptions_path: str | Path | None = None,
        vad: Vad | None = None,
    ) -> None:
        if max_audio_samples < 0:
            raise ValueError("max_audio_samples deve essere >= 0")
        if max_video_frames < 0:
            raise ValueError("max_video_frames deve essere >= 0")
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._audio_dir = self._dir / "raw" / "audio"
        self._audio_dir.mkdir(parents=True, exist_ok=True)
        self._video_dir = self._dir / "raw" / "video"
        self._video_dir.mkdir(parents=True, exist_ok=True)
        self._perceptions_path = (
            Path(perceptions_path)
            if perceptions_path is not None
            else self._dir / "perceptions.jsonl"
        )
        self._perceptions_path.parent.mkdir(parents=True, exist_ok=True)
        self._perceptions_path.write_text("", encoding="utf-8")
        for stale_sample in self._audio_dir.glob("*.pcm"):
            stale_sample.unlink()
        for stale_frame in self._video_dir.glob("*.jpg"):
            stale_frame.unlink()
        self._store = PerceptionStore(self.perceptions_path)
        self._chat = ChatPerceiver(self._store)
        self._vad = vad
        self._max_audio_samples = max_audio_samples
        self._max_video_frames = max_video_frames
        self.stats = SmokeStats()

    @property
    def perceptions_path(self) -> Path:
        return self._perceptions_path

    @property
    def stats_path(self) -> Path:
        return self._dir / "stats.json"

    def record(self, event: RawEvent) -> bool:
        """Persist a supported event and return whether it was recorded."""
        if self._chat.perceive_event(event) is not None:
            self.stats.chat_events += 1
            return True
        if event.channel == "audio" and isinstance(event.payload, AudioChunk):
            self.stats.audio_events += 1
            self._record_vad_segments(event.payload)
            if self.stats.audio_samples_saved < self._max_audio_samples:
                index = self.stats.audio_samples_saved + 1
                sample_path = self._audio_dir / f"audio-{index:04d}.pcm"
                samples = event.payload.samples
                if not isinstance(samples, (bytes, bytearray, memoryview)):
                    raise TypeError("AudioChunk.samples deve essere bytes-like")
                sample_path.write_bytes(bytes(samples))
                self.stats.audio_samples_saved += 1
            return True
        if event.channel == "video" and isinstance(event.payload, VideoFrame):
            self.stats.video_events += 1
            if self.stats.video_frames_saved < self._max_video_frames:
                index = self.stats.video_frames_saved + 1
                frame_path = self._video_dir / f"video-{index:04d}.jpg"
                pixels = event.payload.pixels
                if isinstance(pixels, (bytes, bytearray, memoryview)):
                    # Backend che emettono già JPEG (es. reader mjpeg Twitch).
                    frame_path.write_bytes(bytes(pixels))
                else:
                    # ndarray RGB (cattura schermo mss / frame PyAV rgb24) o
                    # immagine PIL: codifica in JPEG via Pillow (import lazy,
                    # come gli altri backend di cattura opzionali).
                    _save_frame_as_jpeg(pixels, frame_path)
                self.stats.video_frames_saved += 1
            return True
        return False

    def add_failure(self, message: str) -> None:
        self.stats.failures.append(message)

    def write_stats(self) -> None:
        self.stats_path.write_text(
            json.dumps(self.stats.as_json(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def flush_vad(self) -> None:
        if self._vad is None:
            return
        flush = getattr(self._vad, "flush", None)
        if not callable(flush):
            return
        for segment in flush():
            self._record_vad_segment(segment)

    def _record_vad_segments(self, chunk: AudioChunk) -> None:
        if self._vad is None:
            return
        for segment in self._vad.segments(chunk):
            self._record_vad_segment(segment)

    def _record_vad_segment(self, segment: SpeechSegment) -> None:
        self.stats.vad_utterances += 1
        self.stats.vad_utterance_durations_ms.append(_segment_duration_ms(segment))


def _save_frame_as_jpeg(pixels: object, path: Path) -> None:
    """Codifica un frame non-JPEG (ndarray RGB o immagine PIL) in un `.jpg`.

    I backend che emettono già bytes JPEG (es. il reader mjpeg Twitch) vengono
    scritti direttamente dal chiamante; qui si gestisce il caso ndarray/PIL (es.
    cattura schermo `mss`, frame PyAV `rgb24`). Pillow è importato lazy: il
    salvataggio degli artifact frame è un percorso diagnostico opzionale.
    """
    try:
        from PIL import Image  # noqa: PLC0415 - import lazy opzionale
    except ImportError as exc:  # pragma: no cover - richiede ambiente senza Pillow
        raise TypeError(
            "VideoFrame.pixels non è bytes-like e Pillow non è disponibile: "
            "impossibile salvare il frame come JPEG (installa l'extra os-capture)"
        ) from exc
    image = pixels if hasattr(pixels, "save") else Image.fromarray(pixels)
    image.convert("RGB").save(path, "JPEG")


def _segment_duration_ms(segment: SpeechSegment) -> float:
    samples = segment.samples
    if not isinstance(samples, (bytes, bytearray, memoryview)):
        raise TypeError("SpeechSegment.samples deve essere bytes-like")
    return round((len(samples) / (segment.sample_rate * 2)) * 1000, 3)


async def capture_twitch_smoke(
    adapters: Sequence[SourceAdapter],
    *,
    output_dir: str | Path,
    duration: float,
    max_audio_samples: int = 3,
    max_video_frames: int = 3,
    stop_timeout: float = _SMOKE_STOP_TIMEOUT_SECONDS,
    vad: Vad | None = None,
) -> SmokeStats:
    """Run enabled adapters for a bounded duration and write smoke artifacts."""
    if not adapters:
        raise ValueError("almeno un canale smoke deve essere abilitato")
    artifacts = TwitchSmokeArtifacts(
        output_dir,
        max_audio_samples=max_audio_samples,
        max_video_frames=max_video_frames,
        vad=vad,
    )

    async def pump(adapter: SourceAdapter) -> None:
        label = ",".join(sorted(adapter.channels()))
        try:
            await adapter.start()
            async for event in adapter.events():
                artifacts.record(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - smoke records channel failures.
            artifacts.add_failure(f"{label}: {exc}")

    tasks = [asyncio.create_task(pump(adapter)) for adapter in adapters]
    try:
        deadline = asyncio.timeout(duration)
        try:
            async with deadline:
                await asyncio.gather(*tasks)
        except TimeoutError:
            if not deadline.expired():
                raise
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=stop_timeout,
            )
        except TimeoutError:
            artifacts.add_failure("smoke cleanup timed out")
        for adapter in adapters:
            label = ",".join(sorted(adapter.channels()))
            try:
                await asyncio.wait_for(adapter.stop(), timeout=stop_timeout)
            except TimeoutError:
                artifacts.add_failure(f"{label}: cleanup timed out")
            except Exception as exc:  # noqa: BLE001 - smoke records cleanup failures.
                artifacts.add_failure(f"{label}: {exc}")
        try:
            artifacts.flush_vad()
        except Exception as exc:  # noqa: BLE001 - diagnostic failure is recorded.
            artifacts.add_failure(f"vad: {exc}")
        artifacts.write_stats()
    return artifacts.stats
