"""Raw Twitch video capture.

This module owns two Twitch video edges:

- `TwitchPyAvVideoReader` is the main runtime path. Streamlink opens the Twitch
  stream, PyAV decodes frames, and sampled `VideoFrame` events are emitted
  without captioning.
- `TwitchVideoReader` is the FFmpeg JPEG smoke diagnostic path. It remains
  separate so operators can save raw `.jpg` frames for capture troubleshooting.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from collections.abc import AsyncIterator, Callable, Iterator
from concurrent.futures import CancelledError as FutureCancelledError
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import suppress
from dataclasses import dataclass
from threading import Event as ThreadingEvent
from threading import Thread
from typing import Protocol

from .source import RawEvent, SourceAdapter
from .twitch_media import (
    AsyncioProcessRunner,
    ProcessRunner,
    StreamlinkFfmpegPipeline,
    normalize_twitch_channel,
)
from .video import VideoFrame

_JPEG_START = b"\xff\xd8"
_JPEG_END = b"\xff\xd9"
_READ_BYTES = 64 * 1024
_PROCESS_STOP_TIMEOUT_SECONDS = 5.0
_MAX_VIDEO_FPS = 10.0


@dataclass(frozen=True, slots=True)
class DecodedVideoFrame:
    """Frame decoded by the PyAV boundary before runtime event wrapping."""

    pixels: object
    time_seconds: float | None


class TwitchVideoStreamOpener(Protocol):
    """Fakeable Streamlink boundary for opening a Twitch video byte stream."""

    def open(self, *, channel: str, quality: str) -> object: ...


class VideoFrameDecoder(Protocol):
    """Fakeable PyAV boundary for decoding video frames from a stream."""

    def decode(self, stream: object) -> Iterator[DecodedVideoFrame]: ...


@dataclass(frozen=True, slots=True)
class _DecoderFailure:
    exc: BaseException


@dataclass(frozen=True, slots=True)
class _DecoderFinished:
    pass


_DECODER_FINISHED = _DecoderFinished()
_DecoderQueueItem = RawEvent | _DecoderFailure | _DecoderFinished


class StreamlinkVideoStreamOpener:
    """Open a Twitch stream as a file-like object via Streamlink."""

    def open(self, *, channel: str, quality: str) -> object:
        try:
            import streamlink
        except ModuleNotFoundError as exc:  # pragma: no cover - env dependent.
            raise RuntimeError(
                "PyAV Twitch video runtime requires Streamlink's Python package; "
                "install the video extra"
            ) from exc

        session = streamlink.Streamlink()
        streams = session.streams(f"https://www.twitch.tv/{channel}")
        stream = streams.get(quality) or streams.get("best")
        if stream is None:
            raise OSError(f"Twitch stream quality {quality!r} is not available")
        return stream.open()


class PyAvVideoFrameDecoder:
    """Decode video frames from a Streamlink file-like stream via PyAV."""

    def decode(self, stream: object) -> Iterator[DecodedVideoFrame]:
        try:
            import av
        except ModuleNotFoundError as exc:  # pragma: no cover - env dependent.
            raise RuntimeError(
                "PyAV Twitch video runtime requires the 'av' package; "
                "install the video extra"
            ) from exc
        try:
            import numpy as numpy_module
        except ModuleNotFoundError as exc:  # pragma: no cover - env dependent.
            raise RuntimeError(
                "PyAV Twitch video runtime requires NumPy for frame.to_ndarray(); "
                "install the video extra"
            ) from exc
        del numpy_module

        container = av.open(_pyav_readable_stream(stream))
        try:
            for frame in container.decode(video=0):
                yield DecodedVideoFrame(
                    pixels=frame.to_ndarray(format="rgb24"),
                    time_seconds=frame.time,
                )
        finally:
            close = getattr(container, "close", None)
            if close is not None:
                close()


class _ReadableStreamWrapper:
    """File-like adapter for stream objects that can read but report unreadable."""

    def __init__(self, stream: object) -> None:
        self._stream = stream

    def read(self, size: int = -1) -> object:
        return self._stream.read(size)  # type: ignore[attr-defined]

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def close(self) -> None:
        close = getattr(self._stream, "close", None)
        if close is not None:
            close()


def _pyav_readable_stream(stream: object) -> object:
    """Return a PyAV-compatible readable stream object."""
    if not hasattr(stream, "read"):
        return stream
    readable = getattr(stream, "readable", None)
    if readable is None:
        return stream
    try:
        if readable():
            return stream
    except Exception:  # noqa: BLE001 - PyAV will validate the final object.
        return stream
    return _ReadableStreamWrapper(stream)


def validate_video_fps(fps: float) -> float:
    """Return a valid low-rate FPS value for Twitch video sampling."""
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


class TwitchPyAvVideoReader(SourceAdapter):
    """Read Twitch stream video as sampled PyAV `VideoFrame` events."""

    def __init__(
        self,
        *,
        channel: str,
        quality: str = "best",
        fps: float = 1.0,
        stream_opener: TwitchVideoStreamOpener | None = None,
        frame_decoder: VideoFrameDecoder | None = None,
        clock: Callable[[], float] = time.time,
        sample_clock: Callable[[], float] = time.monotonic,
        event_queue_size: int = 2,
        cleanup_timeout: float = _PROCESS_STOP_TIMEOUT_SECONDS,
    ) -> None:
        if event_queue_size <= 0:
            raise ValueError("event_queue_size must be > 0")
        if cleanup_timeout <= 0:
            raise ValueError("cleanup_timeout must be > 0")
        self._channel = normalize_twitch_channel(channel)
        self._quality = quality
        self._fps = validate_video_fps(fps)
        self._sample_interval_seconds = 1.0 / self._fps
        self._stream_opener = stream_opener or StreamlinkVideoStreamOpener()
        self._frame_decoder = frame_decoder or PyAvVideoFrameDecoder()
        self._clock = clock
        self._sample_clock = sample_clock
        self._event_queue_size = event_queue_size
        self._cleanup_timeout = cleanup_timeout
        self._running = False
        self._started_once = False
        self._active_stream: object | None = None
        self._stop_requested = ThreadingEvent()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[_DecoderQueueItem] | None = None
        self._decode_thread: Thread | None = None

    def channels(self) -> set[str]:
        return {"video"}

    async def start(self) -> None:
        thread = self._decode_thread
        if self._running or (thread is not None and thread.is_alive()):
            return
        self._running = True
        self._started_once = True
        self._stop_requested.clear()
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue(maxsize=self._event_queue_size)
        self._decode_thread = Thread(
            target=self._decode_worker,
            name=f"twitch-pyav-video-{self._channel}",
            daemon=True,
        )
        self._decode_thread.start()

    async def stop(self) -> None:
        thread = self._decode_thread
        if not self._running and thread is None:
            return
        self._running = False
        self._stop_requested.set()
        self._close_resource(self._active_stream)
        if thread is None:
            self._active_stream = None
            return
        await asyncio.to_thread(thread.join, self._cleanup_timeout)
        if thread.is_alive():
            raise TimeoutError("PyAV video decode cleanup timed out")
        self._decode_thread = None
        self._active_stream = None

    async def events(self) -> AsyncIterator[RawEvent]:
        if self._queue is None and not self._started_once:
            await self.start()
        queue = self._queue
        if queue is None:
            return
        while True:
            item = await queue.get()
            if isinstance(item, RawEvent):
                yield item
            elif isinstance(item, _DecoderFailure):
                raise OSError(f"PyAV Twitch video runtime failed: {item.exc}") from (
                    item.exc
                )
            else:
                return

    def _decode_worker(self) -> None:
        try:
            stream = self._stream_opener.open(
                channel=self._channel,
                quality=self._quality,
            )
            self._active_stream = stream
            self._decode_stream(stream)
        except BaseException as exc:  # noqa: BLE001 - surfaced through events().
            if not self._stop_requested.is_set():
                self._submit_from_worker(_DecoderFailure(exc))
        finally:
            self._close_resource(self._active_stream)
            self._active_stream = None
            self._finish_from_worker()
            self._running = False

    def _decode_stream(self, stream: object) -> None:
        next_sample_time: float | None = None
        for decoded in self._frame_decoder.decode(stream):
            if self._stop_requested.is_set():
                return
            frame_time = self._frame_sample_time(decoded)
            if next_sample_time is not None and frame_time < next_sample_time:
                continue
            next_sample_time = frame_time + self._sample_interval_seconds
            ts = self._clock()
            if not self._submit_from_worker(
                RawEvent(
                    channel="video",
                    payload=VideoFrame(
                        pixels=decoded.pixels,
                        source_label="stream",
                        ts=ts,
                    ),
                    ts=ts,
                )
            ):
                return

    def _submit_from_worker(self, item: _DecoderQueueItem) -> bool:
        loop = self._loop
        queue = self._queue
        if loop is None or queue is None or loop.is_closed():
            return False
        future = asyncio.run_coroutine_threadsafe(queue.put(item), loop)
        while True:
            try:
                future.result(timeout=0.05)
                return True
            except FutureCancelledError:
                return False
            except FutureTimeoutError:
                if self._stop_requested.is_set():
                    future.cancel()
                    return False

    def _finish_from_worker(self) -> None:
        loop = self._loop
        queue = self._queue
        if loop is None or queue is None or loop.is_closed():
            return
        future = asyncio.run_coroutine_threadsafe(
            self._force_completion_item(queue), loop
        )
        with suppress(FutureCancelledError, FutureTimeoutError):
            future.result(timeout=0.5)

    @staticmethod
    async def _force_completion_item(
        queue: asyncio.Queue[_DecoderQueueItem],
    ) -> None:
        while queue.full():
            try:
                queued = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if isinstance(queued, (_DecoderFailure, _DecoderFinished)):
                await queue.put(queued)
                return
            queue.task_done()
        await queue.put(_DECODER_FINISHED)

    @staticmethod
    def _close_resource(resource: object | None) -> None:
        close = getattr(resource, "close", None)
        if close is not None:
            with suppress(Exception):
                close()

    def _frame_sample_time(self, decoded: DecodedVideoFrame) -> float:
        if decoded.time_seconds is not None:
            return decoded.time_seconds
        return self._sample_clock()


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
