"""Raw Twitch audio capture.

This module is the Twitch-specific media edge for audio only. It emits raw PCM
bytes as `RawEvent(channel="audio")` without VAD, ASR, or speaker tagging.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import AsyncIterator, Callable

from .audio import AudioChunk
from .source import RawEvent, SourceAdapter
from .twitch_media import (
    AsyncioProcessRunner,
    ProcessRunner,
    StreamlinkFfmpegPipeline,
    normalize_twitch_channel,
)

PCM_SAMPLE_RATE = 16_000
PCM_SAMPLE_WIDTH_BYTES = 2
PCM_CHANNELS = 1
_PROCESS_STOP_TIMEOUT_SECONDS = 5.0
_MAX_CHUNK_SECONDS = 10.0


def pcm_chunk_size_bytes(chunk_seconds: float) -> int:
    """Return bytes for mono 16 kHz signed 16-bit PCM at `chunk_seconds`."""
    if (
        not math.isfinite(chunk_seconds)
        or chunk_seconds <= 0
        or chunk_seconds > _MAX_CHUNK_SECONDS
    ):
        raise ValueError("audio chunk duration must be > 0 and <= 10")
    frames = round(PCM_SAMPLE_RATE * chunk_seconds)
    if frames < 1:
        raise ValueError("audio chunk duration must produce at least one frame")
    return frames * PCM_SAMPLE_WIDTH_BYTES * PCM_CHANNELS


class TwitchAudioReader(SourceAdapter):
    """Read Twitch stream audio as fixed-duration raw PCM chunks."""

    def __init__(
        self,
        *,
        channel: str,
        quality: str = "audio_only",
        chunk_seconds: float = 1.0,
        process_runner: ProcessRunner | None = None,
        clock: Callable[[], float] = time.time,
        process_stop_timeout: float = _PROCESS_STOP_TIMEOUT_SECONDS,
    ) -> None:
        self._chunk_size = pcm_chunk_size_bytes(chunk_seconds)
        self._clock = clock
        self._pipeline = StreamlinkFfmpegPipeline(
            channel=channel,
            quality=quality,
            ffmpeg_args=[
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ac",
                "1",
                "-ar",
                str(PCM_SAMPLE_RATE),
                "-f",
                "s16le",
                "pipe:1",
            ],
            label="audio",
            process_runner=process_runner or AsyncioProcessRunner(),
            process_stop_timeout=process_stop_timeout,
        )
        self._running = False

    def channels(self) -> set[str]:
        return {"audio"}

    async def start(self) -> None:
        if self._running:
            return
        await self._pipeline.start()
        self._running = True

    async def stop(self) -> None:
        self._running = False
        await self._pipeline.stop()

    async def events(self) -> AsyncIterator[RawEvent]:
        if not self._running:
            await self.start()
        while self._running:
            chunk = await self._read_audio_chunk()
            if not chunk:
                return
            ts = self._clock()
            yield RawEvent(
                channel="audio",
                payload=AudioChunk(
                    samples=chunk,
                    sample_rate=PCM_SAMPLE_RATE,
                    source_label="stream",
                    ts=ts,
                ),
                ts=ts,
            )

    async def _read_audio_chunk(self) -> bytes:
        data = bytearray()
        while len(data) < self._chunk_size:
            part = await self._pipeline.read_ffmpeg_stdout(
                self._chunk_size - len(data)
            )
            if not part:
                self._pipeline.raise_pump_failure_if_done()
                returncode = await self._pipeline.wait_ffmpeg()
                if returncode != 0:
                    raise OSError(f"ffmpeg exited with status {returncode}")
                await asyncio.sleep(0)
                self._pipeline.raise_pump_failure_if_done()
                return b""
            data.extend(part)
        return bytes(data)


def _normalize_channel(channel: str) -> str:
    return normalize_twitch_channel(channel)
