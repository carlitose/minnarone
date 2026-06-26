"""Raw Twitch video capture.

This module is the Twitch-specific media edge for video only. It emits sampled
JPEG frames as `RawEvent(channel="video")` without VLM captioning.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from collections.abc import AsyncIterator, Callable

from .source import RawEvent, SourceAdapter
from .twitch_media import (
    AsyncioProcessRunner,
    ProcessRunner,
    StreamlinkFfmpegPipeline,
)
from .video import VideoFrame

_JPEG_START = b"\xff\xd8"
_JPEG_END = b"\xff\xd9"
_READ_BYTES = 64 * 1024
_PROCESS_STOP_TIMEOUT_SECONDS = 5.0
_MAX_VIDEO_FPS = 10.0


def validate_video_fps(fps: float) -> float:
    """Return a valid low-rate FPS value for smoke video sampling."""
    if not math.isfinite(fps) or fps <= 0 or fps > _MAX_VIDEO_FPS:
        raise ValueError("video_fps must be > 0 and <= 10")
    return fps


class JpegFrameSplitter:
    """Incrementally split concatenated JPEG bytes from FFmpeg stdout."""

    def __init__(self, *, max_buffer_bytes: int = 10 * 1024 * 1024) -> None:
        self._buffer = bytearray()
        self._max_buffer_bytes = max_buffer_bytes

    def feed(self, data: bytes) -> list[bytes]:
        """Add bytes and return all complete JPEG frames currently available."""
        self._buffer.extend(data)
        if len(self._buffer) > self._max_buffer_bytes:
            raise ValueError("JPEG frame buffer exceeded limit")

        frames: list[bytes] = []
        while True:
            start = self._buffer.find(_JPEG_START)
            if start < 0:
                keep = self._buffer[-1:] if self._buffer.endswith(b"\xff") else b""
                self._buffer.clear()
                self._buffer.extend(keep)
                return frames
            if start:
                del self._buffer[:start]

            end = self._buffer.find(_JPEG_END, len(_JPEG_START))
            if end < 0:
                return frames

            frame_end = end + len(_JPEG_END)
            frames.append(bytes(self._buffer[:frame_end]))
            del self._buffer[:frame_end]


class TwitchVideoReader(SourceAdapter):
    """Read Twitch stream video as low-rate JPEG `VideoFrame` events."""

    def __init__(
        self,
        *,
        channel: str,
        quality: str = "best",
        fps: float = 1.0,
        process_runner: ProcessRunner | None = None,
        clock: Callable[[], float] = time.time,
        process_stop_timeout: float = _PROCESS_STOP_TIMEOUT_SECONDS,
    ) -> None:
        self._fps = validate_video_fps(fps)
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
                "-an",
                "-vf",
                f"fps={self._fps:g}",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "pipe:1",
            ],
            label="video",
            process_runner=process_runner or AsyncioProcessRunner(),
            process_stop_timeout=process_stop_timeout,
        )
        self._running = False
        self._splitter = JpegFrameSplitter()
        self._pending_frames: deque[bytes] = deque()

    def channels(self) -> set[str]:
        return {"video"}

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
            frame = await self._read_video_frame()
            if not frame:
                return
            ts = self._clock()
            yield RawEvent(
                channel="video",
                payload=VideoFrame(pixels=frame, source_label="stream", ts=ts),
                ts=ts,
            )

    async def _read_video_frame(self) -> bytes:
        if self._pending_frames:
            return self._pending_frames.popleft()
        while not self._pending_frames:
            part = await self._pipeline.read_ffmpeg_stdout(_READ_BYTES)
            if not part:
                self._pipeline.raise_pump_failure_if_done()
                returncode = await self._pipeline.wait_ffmpeg()
                if returncode != 0:
                    raise OSError(f"ffmpeg exited with status {returncode}")
                await asyncio.sleep(0)
                self._pipeline.raise_pump_failure_if_done()
                return b""
            self._pending_frames.extend(self._splitter.feed(part))
        return self._pending_frames.popleft()
