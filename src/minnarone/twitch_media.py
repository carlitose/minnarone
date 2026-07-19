"""Shared Twitch media subprocess pipeline."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from typing import Protocol

_TWITCH_CHANNEL_RE = re.compile(r"^[a-z0-9_]{1,25}$")
STREAMLINK_READ_BYTES = 64 * 1024
PROCESS_STOP_TIMEOUT_SECONDS = 5.0


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


class StreamlinkFfmpegPipeline:
    """Owns a Streamlink stdout -> FFmpeg stdin process pair."""

    def __init__(
        self,
        *,
        channel: str,
        quality: str,
        ffmpeg_args: Sequence[str],
        label: str,
        process_runner: ProcessRunner | None = None,
        process_stop_timeout: float = PROCESS_STOP_TIMEOUT_SECONDS,
    ) -> None:
        self._channel = normalize_twitch_channel(channel)
        self._quality = quality
        self._ffmpeg_args = list(ffmpeg_args)
        self._label = label
        self._process_runner = process_runner or AsyncioProcessRunner()
        self._process_stop_timeout = process_stop_timeout
        self._streamlink: MediaProcess | None = None
        self._ffmpeg: MediaProcess | None = None
        self._pump_task: asyncio.Task[None] | None = None
        self._reported_pump_failure = False

    async def start(self) -> None:
        if self._ffmpeg is not None:
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
            ffmpeg = await self._process_runner.start(self._ffmpeg_args)
        except BaseException:
            await self._stop_process(ffmpeg)
            await self._stop_process(streamlink)
            raise
        self._streamlink = streamlink
        self._ffmpeg = ffmpeg
        self._reported_pump_failure = False
        self._pump_task = asyncio.create_task(self._pump_streamlink_to_ffmpeg())

    async def stop(self) -> None:
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
                    pump_error = TimeoutError(
                        f"{self._label} pump did not stop in time"
                    )
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
            raise OSError(
                f"{self._label} pipeline failed: {pump_error}"
            ) from pump_error

    async def read_ffmpeg_stdout(self, size: int) -> bytes:
        if self._ffmpeg is None:
            return b""
        return await self._ffmpeg.read_stdout(size)

    async def wait_ffmpeg(self) -> int:
        if self._ffmpeg is None:
            return 0
        return await self._ffmpeg.wait()

    def raise_pump_failure_if_done(self) -> None:
        task = self._pump_task
        if task is None or not task.done() or task.cancelled():
            return
        exc = task.exception()
        if exc is None:
            return
        self._reported_pump_failure = True
        raise OSError(f"{self._label} pipeline failed: {exc}") from exc

    async def _pump_streamlink_to_ffmpeg(self) -> None:
        streamlink = self._streamlink
        ffmpeg = self._ffmpeg
        if streamlink is None or ffmpeg is None:
            return
        try:
            while True:
                data = await streamlink.read_stdout(STREAMLINK_READ_BYTES)
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


def normalize_twitch_channel(channel: str) -> str:
    normalized = channel.strip().lstrip("#").lower()
    if not _TWITCH_CHANNEL_RE.fullmatch(normalized):
        raise ValueError("invalid Twitch channel")
    return normalized
