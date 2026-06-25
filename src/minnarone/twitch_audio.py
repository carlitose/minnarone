"""Raw Twitch audio capture.

This module is the Twitch-specific media edge for audio only. It emits raw PCM
bytes as `RawEvent(channel="audio")` without VAD, ASR, or speaker tagging.
"""

from __future__ import annotations

import asyncio
import math
import re
import time
from collections.abc import AsyncIterator, Callable, Sequence
from typing import Protocol

from .audio import AudioChunk
from .source import RawEvent, SourceAdapter

_TWITCH_CHANNEL_RE = re.compile(r"^[a-z0-9_]{1,25}$")
PCM_SAMPLE_RATE = 16_000
PCM_SAMPLE_WIDTH_BYTES = 2
PCM_CHANNELS = 1
_STREAMLINK_READ_BYTES = 64 * 1024
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


class MediaProcess(Protocol):
    """Small subprocess boundary used by Twitch media readers."""

    async def read_stdout(self, size: int) -> bytes: ...

    async def write_stdin(self, data: bytes) -> None: ...

    async def close_stdin(self) -> None: ...

    async def wait(self) -> int: ...

    async def terminate(self) -> None: ...

    async def kill(self) -> None: ...


class ProcessRunner(Protocol):
    """Launch external commands from argv lists, never shell strings."""

    async def start(self, argv: Sequence[str]) -> MediaProcess: ...


class AsyncioProcessRunner:
    """`asyncio` implementation of the fakeable process runner boundary."""

    async def start(self, argv: Sequence[str]) -> MediaProcess:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return _AsyncioMediaProcess(process)


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
        self._channel = _normalize_channel(channel)
        self._quality = quality
        self._chunk_size = pcm_chunk_size_bytes(chunk_seconds)
        self._process_runner = process_runner or AsyncioProcessRunner()
        self._clock = clock
        self._process_stop_timeout = process_stop_timeout
        self._streamlink: MediaProcess | None = None
        self._ffmpeg: MediaProcess | None = None
        self._pump_task: asyncio.Task[None] | None = None
        self._reported_pump_failure = False
        self._running = False

    def channels(self) -> set[str]:
        return {"audio"}

    async def start(self) -> None:
        if self._running:
            return
        streamlink: MediaProcess | None = None
        ffmpeg: MediaProcess | None = None
        try:
            streamlink = await self._process_runner.start(
                [
                    "streamlink",
                    "--stdout",
                    f"https://www.twitch.tv/{self._channel}",
                    self._quality,
                ]
            )
            ffmpeg = await self._process_runner.start(
                [
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
                ]
            )
        except BaseException:
            await self._stop_process(ffmpeg)
            await self._stop_process(streamlink)
            raise
        self._streamlink = streamlink
        self._ffmpeg = ffmpeg
        self._reported_pump_failure = False
        self._running = True
        self._pump_task = asyncio.create_task(self._pump_streamlink_to_ffmpeg())

    async def stop(self) -> None:
        self._running = False
        pump_error: BaseException | None = None
        try:
            if self._pump_task is not None:
                if not self._pump_task.done():
                    self._pump_task.cancel()
                try:
                    await asyncio.wait_for(
                        self._pump_task,
                        timeout=self._process_stop_timeout,
                    )
                except asyncio.CancelledError:
                    pass
                except TimeoutError:
                    pump_error = TimeoutError("audio pump did not stop in time")
                except BaseException as exc:
                    pump_error = exc
        finally:
            self._pump_task = None
            try:
                await self._stop_process(self._ffmpeg)
            finally:
                await self._stop_process(self._streamlink)
                self._ffmpeg = None
                self._streamlink = None
        if pump_error is not None and not self._reported_pump_failure:
            self._reported_pump_failure = True
            raise OSError(f"audio pipeline failed: {pump_error}") from pump_error

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
        ffmpeg = self._ffmpeg
        if ffmpeg is None:
            return b""
        data = bytearray()
        while len(data) < self._chunk_size:
            part = await ffmpeg.read_stdout(self._chunk_size - len(data))
            if not part:
                self._raise_pump_failure_if_done()
                returncode = await ffmpeg.wait()
                if returncode != 0:
                    raise OSError(f"ffmpeg exited with status {returncode}")
                await asyncio.sleep(0)
                self._raise_pump_failure_if_done()
                return b""
            data.extend(part)
        return bytes(data)

    async def _pump_streamlink_to_ffmpeg(self) -> None:
        streamlink = self._streamlink
        ffmpeg = self._ffmpeg
        if streamlink is None or ffmpeg is None:
            return
        try:
            while self._running:
                data = await streamlink.read_stdout(_STREAMLINK_READ_BYTES)
                if not data:
                    returncode = await asyncio.wait_for(
                        streamlink.wait(),
                        timeout=self._process_stop_timeout,
                    )
                    if returncode != 0:
                        raise OSError(f"streamlink exited with status {returncode}")
                    break
                await ffmpeg.write_stdin(data)
        finally:
            try:
                await asyncio.wait_for(
                    ffmpeg.close_stdin(),
                    timeout=self._process_stop_timeout,
                )
            except TimeoutError:
                pass

    def _raise_pump_failure_if_done(self) -> None:
        task = self._pump_task
        if task is None or not task.done() or task.cancelled():
            return
        exc = task.exception()
        if exc is None:
            return
        self._reported_pump_failure = True
        raise OSError(f"audio pipeline failed: {exc}") from exc

    async def _stop_process(self, process: MediaProcess | None) -> None:
        if process is None:
            return
        await process.terminate()
        try:
            await asyncio.wait_for(
                process.wait(),
                timeout=self._process_stop_timeout,
            )
        except TimeoutError:
            await process.kill()
            await asyncio.wait_for(
                process.wait(),
                timeout=self._process_stop_timeout,
            )


class _AsyncioMediaProcess:
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process

    async def read_stdout(self, size: int) -> bytes:
        if self._process.stdout is None:
            return b""
        return await self._process.stdout.read(size)

    async def write_stdin(self, data: bytes) -> None:
        if self._process.stdin is None:
            return
        self._process.stdin.write(data)
        await self._process.stdin.drain()

    async def close_stdin(self) -> None:
        if self._process.stdin is not None and not self._process.stdin.is_closing():
            self._process.stdin.close()
            await self._process.stdin.wait_closed()

    async def wait(self) -> int:
        return await self._process.wait()

    async def terminate(self) -> None:
        if self._process.returncode is None:
            self._process.terminate()

    async def kill(self) -> None:
        if self._process.returncode is None:
            self._process.kill()


def _normalize_channel(channel: str) -> str:
    normalized = channel.strip().lstrip("#").lower()
    if not _TWITCH_CHANNEL_RE.fullmatch(normalized):
        raise ValueError("channel Twitch non valido")
    return normalized
