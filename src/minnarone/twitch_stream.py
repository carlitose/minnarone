"""Unified Twitch `SourceAdapter`.

`TwitchStreamAdapter` composes the independent chat/audio/video readers behind
one lifecycle and one bounded `RawEvent` stream. It remains a Twitch edge
adapter: the core source port still only sees `RawEvent` values.

Il merge/backpressure NON è reimplementato qui: è delegato interamente a
`MergingSourceAdapter` (motore neutro e già testato in isolamento). Questo
modulo conserva solo la parte Twitch-specifica: `_build_readers` (costruzione
dei reader chat/audio/video con i relativi controlli di credenziali) e i
default Twitch. `stats()` riavvolge `MergeStats` in `TwitchStreamStats` per non
alterare la superficie che la TUI/osservabilità già legge.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field

from .merge import MergeRuntimeError, MergingSourceAdapter
from .source import RawEvent, SourceAdapter
from .twitch_audio import ProcessRunner, TwitchAudioReader
from .twitch_chat import ConnectIRC, TwitchChatReader
from .twitch_video import (
    TwitchPyAvVideoReader,
    TwitchVideoStreamOpener,
    VideoFrameDecoder,
)

_CHANNEL_ORDER = ("chat", "audio", "video")


@dataclass(frozen=True, slots=True)
class TwitchStreamStats:
    """Immutable stats snapshot for the unified Twitch adapter."""

    running: bool
    produced: dict[str, int] = field(default_factory=dict)
    dropped: dict[str, int] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)


class TwitchStreamRuntimeError(RuntimeError):
    """Errore runtime dell'adapter Twitch unificato."""


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
        chat_connect: ConnectIRC | None = None,
        readers: Mapping[str, SourceAdapter] | None = None,
        audio_process_runner: ProcessRunner | None = None,
        video_process_runner: ProcessRunner | None = None,
        video_stream_opener: TwitchVideoStreamOpener | None = None,
        video_frame_decoder: VideoFrameDecoder | None = None,
    ) -> None:
        built = (
            dict(readers)
            if readers is not None
            else self._build_readers(
                channel=channel,
                username=username,
                oauth_token=oauth_token,
                quality=quality,
                chat=chat,
                audio=audio,
                video=video,
                audio_chunk_seconds=audio_chunk_seconds,
                video_fps=video_fps,
                chat_connect=chat_connect,
                audio_process_runner=audio_process_runner,
                video_process_runner=video_process_runner,
                video_stream_opener=video_stream_opener,
                video_frame_decoder=video_frame_decoder,
            )
        )
        if not built:
            raise ValueError("enable at least one Twitch channel")
        # Validazione dei canali con il messaggio Twitch-specifico PRIMA di
        # delegare: il motore neutro validerebbe con un altro testo.
        self._validate_reader_channels(built)
        # Tutto il merge/backpressure vive nel motore neutro: chat è il canale
        # prioritario (invariata la policy di drop media-prima-di-chat).
        self._merger = MergingSourceAdapter(
            readers=built,
            priority_channels=("chat",),
            queue_size=queue_size,
            cleanup_timeout=cleanup_timeout,
        )

    def channels(self) -> set[str]:
        return self._merger.channels()

    async def start(self) -> None:
        await self._merger.start()

    async def stop(self) -> None:
        await self._merger.stop()

    async def events(self) -> AsyncIterator[RawEvent]:
        # Traduce il guasto fatale del motore neutro nell'errore Twitch-specifico
        # atteso dai chiamanti, senza cambiare la semantica di produzione.
        try:
            async for event in self._merger.events():
                yield event
        except MergeRuntimeError as exc:
            # Riscrive il prefisso del motore neutro nel wording Twitch storico
            # atteso dall'operatore (il riepilogo per-canale resta invariato).
            message = str(exc).replace(
                "merge failed before producing events:",
                "Twitch stream failed before producing events:",
                1,
            )
            raise TwitchStreamRuntimeError(message) from exc

    def stats(self) -> TwitchStreamStats:
        # Riavvolge `MergeStats` nella forma `TwitchStreamStats` che la
        # TUI/osservabilità e i test già leggono (running/produced/dropped/failures).
        snapshot = self._merger.stats()
        return TwitchStreamStats(
            running=snapshot.running,
            produced=snapshot.produced,
            dropped=snapshot.dropped,
            failures=snapshot.failures,
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
        chat_connect: ConnectIRC | None,
        audio_process_runner: ProcessRunner | None,
        video_process_runner: ProcessRunner | None,
        video_stream_opener: TwitchVideoStreamOpener | None,
        video_frame_decoder: VideoFrameDecoder | None,
    ) -> dict[str, SourceAdapter]:
        readers: dict[str, SourceAdapter] = {}
        if chat:
            if username is None or oauth_token is None:
                raise ValueError("missing Twitch chat credentials")
            readers["chat"] = TwitchChatReader(
                channel=channel,
                username=username,
                oauth_token=oauth_token,
                connect=chat_connect,
            )
        if audio:
            readers["audio"] = TwitchAudioReader(
                channel=channel,
                quality=quality,
                chunk_seconds=audio_chunk_seconds,
                process_runner=audio_process_runner,
            )
        if video:
            readers["video"] = TwitchPyAvVideoReader(
                channel=channel,
                quality=quality,
                fps=video_fps,
                stream_opener=video_stream_opener,
                frame_decoder=video_frame_decoder,
            )
        return readers

    @staticmethod
    def _validate_reader_channels(readers: Mapping[str, SourceAdapter]) -> None:
        for channel, reader in readers.items():
            if reader.channels() != {channel}:
                raise ValueError(
                    f"reader {channel!r} must expose only channel {channel!r}"
                )


def ordered_twitch_channels(channels: set[str]) -> list[str]:
    """Deterministic channel ordering for tests and diagnostics."""
    return [channel for channel in _CHANNEL_ORDER if channel in channels]
