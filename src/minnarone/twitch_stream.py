"""Unified Twitch `SourceAdapter`.

`TwitchStreamAdapter` composes the independent chat/audio/video readers behind
one lifecycle and one bounded `RawEvent` stream. It remains a Twitch edge
adapter: the core source port still only sees `RawEvent` values.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Mapping
from contextlib import suppress
from dataclasses import dataclass, field

from .source import RawEvent, SourceAdapter
from .twitch_audio import ProcessRunner, TwitchAudioReader
from .twitch_chat import TwitchChatReader
from .twitch_video import TwitchVideoReader

_CHANNEL_ORDER = ("chat", "audio", "video")


@dataclass(frozen=True, slots=True)
class TwitchStreamStats:
    """Immutable stats snapshot for the unified Twitch adapter."""

    running: bool
    produced: dict[str, int] = field(default_factory=dict)
    dropped: dict[str, int] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)


class TwitchStreamAdapter(SourceAdapter):
    """Compose Twitch chat/audio/video readers as one source adapter."""

    def __init__(
        self,
        *,
        channel: str,
        username: str | None = None,
        oauth_token: str | None = None,
        quality: str = "best",
        chat: bool = True,
        audio: bool = False,
        video: bool = False,
        audio_chunk_seconds: float = 1.0,
        video_fps: float = 1.0,
        queue_size: int = 100,
        cleanup_timeout: float = 5.0,
        readers: Mapping[str, SourceAdapter] | None = None,
        audio_process_runner: ProcessRunner | None = None,
        video_process_runner: ProcessRunner | None = None,
    ) -> None:
        if queue_size <= 0:
            raise ValueError("queue_size deve essere > 0")
        if cleanup_timeout <= 0:
            raise ValueError("cleanup_timeout deve essere > 0")
        self._readers = dict(readers) if readers is not None else self._build_readers(
            channel=channel,
            username=username,
            oauth_token=oauth_token,
            quality=quality,
            chat=chat,
            audio=audio,
            video=video,
            audio_chunk_seconds=audio_chunk_seconds,
            video_fps=video_fps,
            audio_process_runner=audio_process_runner,
            video_process_runner=video_process_runner,
        )
        if not self._readers:
            raise ValueError("abilita almeno un canale Twitch")
        self._validate_reader_channels(self._readers)
        self._queue_size = queue_size
        self._cleanup_timeout = cleanup_timeout
        self._queue: deque[RawEvent] = deque()
        self._event_available = asyncio.Condition()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._active_channels: set[str] = set()
        self._running = False
        self._started_once = False
        self._produced = {name: 0 for name in self._readers}
        self._dropped = {name: 0 for name in self._readers}
        self._failures: dict[str, str] = {}

    def channels(self) -> set[str]:
        return set(self._readers)

    async def start(self) -> None:
        if self._running:
            return
        self._queue.clear()
        self._failures.clear()
        self._produced = self._empty_counts()
        self._dropped = self._empty_counts()
        self._active_channels = set(self._readers)
        self._running = True
        self._started_once = True
        self._tasks = {
            channel: asyncio.create_task(self._run_reader(channel, reader))
            for channel, reader in self._readers.items()
        }

    async def stop(self) -> None:
        self._running = False
        tasks = dict(self._tasks)
        for task in tasks.values():
            if not task.done():
                task.cancel()
        if tasks:
            done, pending = await asyncio.wait(
                tasks.values(),
                timeout=self._cleanup_timeout * 2,
            )
            for channel, task in tasks.items():
                if task in pending:
                    self._record_failure(channel, "cleanup timed out")
                    task.cancel()
                elif task in done:
                    with suppress(asyncio.CancelledError):
                        exception = task.exception()
                        if exception is not None:
                            self._record_failure(channel, str(exception))
        self._tasks = {}
        self._active_channels.clear()
        async with self._event_available:
            self._event_available.notify_all()

    async def events(self) -> AsyncIterator[RawEvent]:
        if not self._running and not self._started_once:
            await self.start()
        while True:
            async with self._event_available:
                await self._event_available.wait_for(
                    lambda: bool(self._queue)
                    or not self._running
                    or not self._active_channels
                )
                if self._queue:
                    event = self._queue.popleft()
                    self._event_available.notify_all()
                elif not self._running or not self._active_channels:
                    return
                else:  # pragma: no cover - wait_for predicate prevents this.
                    continue
            yield event

    def stats(self) -> TwitchStreamStats:
        return TwitchStreamStats(
            running=self._running,
            produced=dict(self._produced),
            dropped=dict(self._dropped),
            failures=dict(self._failures),
        )

    @staticmethod
    def _build_readers(
        *,
        channel: str,
        username: str | None,
        oauth_token: str | None,
        quality: str,
        chat: bool,
        audio: bool,
        video: bool,
        audio_chunk_seconds: float,
        video_fps: float,
        audio_process_runner: ProcessRunner | None,
        video_process_runner: ProcessRunner | None,
    ) -> dict[str, SourceAdapter]:
        readers: dict[str, SourceAdapter] = {}
        if chat:
            if username is None or oauth_token is None:
                raise ValueError("credenziali Twitch chat mancanti")
            readers["chat"] = TwitchChatReader(
                channel=channel,
                username=username,
                oauth_token=oauth_token,
            )
        if audio:
            readers["audio"] = TwitchAudioReader(
                channel=channel,
                quality=quality,
                chunk_seconds=audio_chunk_seconds,
                process_runner=audio_process_runner,
            )
        if video:
            readers["video"] = TwitchVideoReader(
                channel=channel,
                quality=quality,
                fps=video_fps,
                process_runner=video_process_runner,
            )
        return readers

    @staticmethod
    def _validate_reader_channels(readers: Mapping[str, SourceAdapter]) -> None:
        for channel, reader in readers.items():
            if reader.channels() != {channel}:
                raise ValueError(
                    f"reader {channel!r} deve esporre solo il canale {channel!r}"
                )

    async def _run_reader(self, channel: str, reader: SourceAdapter) -> None:
        try:
            await reader.start()
            async for event in reader.events():
                await self._publish(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - per-channel isolation.
            self._record_failure(channel, str(exc))
        finally:
            await self._stop_reader(channel, reader)
            self._active_channels.discard(channel)
            if not self._active_channels:
                self._running = False
            async with self._event_available:
                self._event_available.notify_all()

    async def _stop_reader(self, channel: str, reader: SourceAdapter) -> None:
        try:
            await asyncio.wait_for(reader.stop(), timeout=self._cleanup_timeout)
        except TimeoutError:
            self._record_failure(channel, "cleanup timed out")
        except Exception as exc:  # noqa: BLE001 - exposed in stats.
            self._record_failure(channel, str(exc))

    async def _publish(self, event: RawEvent) -> None:
        async with self._event_available:
            if len(self._queue) < self._queue_size:
                self._queue.append(event)
                self._produced[event.channel] = self._produced.get(event.channel, 0) + 1
                self._event_available.notify_all()
                return

            if event.channel == "chat" and self._drop_one_media_event():
                self._queue.append(event)
                self._produced[event.channel] = self._produced.get(event.channel, 0) + 1
                self._event_available.notify_all()
                return

            self._dropped[event.channel] = self._dropped.get(event.channel, 0) + 1
            self._event_available.notify_all()

    def _drop_one_media_event(self) -> bool:
        for index, queued in enumerate(self._queue):
            if queued.channel != "chat":
                del self._queue[index]
                self._dropped[queued.channel] = self._dropped.get(queued.channel, 0) + 1
                return True
        return False

    def _empty_counts(self) -> dict[str, int]:
        return {name: 0 for name in self._readers}

    def _record_failure(self, channel: str, message: str) -> None:
        previous = self._failures.get(channel)
        if previous is None:
            self._failures[channel] = message
        elif message not in previous:
            self._failures[channel] = f"{previous}; {message}"


def ordered_twitch_channels(channels: set[str]) -> list[str]:
    """Deterministic channel ordering for tests and diagnostics."""
    return [channel for channel in _CHANNEL_ORDER if channel in channels]
