"""Smoke artifact writer for Twitch capture slices."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .audio import AudioChunk
from .chat import ChatPerceiver
from .source import RawEvent, SourceAdapter
from .store import PerceptionStore

_SMOKE_STOP_TIMEOUT_SECONDS = 5.0


@dataclass(slots=True)
class SmokeStats:
    """Counters and failures written at the end of a manual smoke run."""

    chat_events: int = 0
    audio_events: int = 0
    audio_samples_saved: int = 0
    failures: list[str] = field(default_factory=list)

    def as_json(self) -> dict[str, object]:
        return {
            "chat_events": self.chat_events,
            "audio_events": self.audio_events,
            "audio_samples_saved": self.audio_samples_saved,
            "failures": list(self.failures),
        }


class TwitchSmokeArtifacts:
    """Writes bounded capture artifacts under one output directory."""

    def __init__(
        self,
        output_dir: str | Path,
        *,
        max_audio_samples: int = 3,
        perceptions_path: str | Path | None = None,
    ) -> None:
        if max_audio_samples < 0:
            raise ValueError("max_audio_samples deve essere >= 0")
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._audio_dir = self._dir / "raw" / "audio"
        self._audio_dir.mkdir(parents=True, exist_ok=True)
        self._perceptions_path = (
            Path(perceptions_path)
            if perceptions_path is not None
            else self._dir / "perceptions.jsonl"
        )
        self._perceptions_path.parent.mkdir(parents=True, exist_ok=True)
        self._perceptions_path.write_text("", encoding="utf-8")
        for stale_sample in self._audio_dir.glob("*.pcm"):
            stale_sample.unlink()
        self._store = PerceptionStore(self.perceptions_path)
        self._chat = ChatPerceiver(self._store)
        self._max_audio_samples = max_audio_samples
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
            if self.stats.audio_samples_saved < self._max_audio_samples:
                index = self.stats.audio_samples_saved + 1
                sample_path = self._audio_dir / f"audio-{index:04d}.pcm"
                samples = event.payload.samples
                if not isinstance(samples, (bytes, bytearray, memoryview)):
                    raise TypeError("AudioChunk.samples deve essere bytes-like")
                sample_path.write_bytes(bytes(samples))
                self.stats.audio_samples_saved += 1
            return True
        return False

    def add_failure(self, message: str) -> None:
        self.stats.failures.append(message)

    def write_stats(self) -> None:
        self.stats_path.write_text(
            json.dumps(self.stats.as_json(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


async def capture_twitch_smoke(
    adapters: Sequence[SourceAdapter],
    *,
    output_dir: str | Path,
    duration: float,
    max_audio_samples: int = 3,
    stop_timeout: float = _SMOKE_STOP_TIMEOUT_SECONDS,
) -> SmokeStats:
    """Run enabled adapters for a bounded duration and write smoke artifacts."""
    if not adapters:
        raise ValueError("almeno un canale smoke deve essere abilitato")
    artifacts = TwitchSmokeArtifacts(
        output_dir,
        max_audio_samples=max_audio_samples,
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
        artifacts.write_stats()
    return artifacts.stats
