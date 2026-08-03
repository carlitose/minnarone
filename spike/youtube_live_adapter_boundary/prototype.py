"""Offline comparison of two YouTube adapter/media boundaries.

This module is deliberately outside ``src/minnarone``.  It opens no network,
browser, credential store, or process.  Every media resource is synthetic.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from urllib.parse import parse_qs, urlsplit

from minnarone.audio import AudioChunk
from minnarone.merge import MergingSourceAdapter
from minnarone.source import RawEvent, SourceAdapter
from minnarone.video import VideoFrame

_YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_SAFE_DESCRIPTOR_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_SAFE_QUALITY_RE = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")
_YOUTUBE_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com"})


@dataclass(frozen=True, slots=True)
class YouTubeVideoId:
    """Validated session target used by both prototype branches."""

    value: str

    def __post_init__(self) -> None:
        if not _YOUTUBE_VIDEO_ID_RE.fullmatch(self.value):
            raise ValueError("YouTube video ID must be exactly 11 safe characters")

    @classmethod
    def parse(cls, target: str) -> YouTubeVideoId:
        """Accept an ID or one explicitly supported HTTPS YouTube URL shape."""

        if _YOUTUBE_VIDEO_ID_RE.fullmatch(target):
            return cls(target)

        parsed = urlsplit(target)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise ValueError("target must be a video ID or supported HTTPS YouTube URL")
        if parsed.fragment:
            raise ValueError("YouTube target fragments are not accepted")
        try:
            if parsed.port is not None:
                raise ValueError("YouTube target ports are not accepted")
        except ValueError as exc:
            raise ValueError("invalid YouTube target port") from exc

        host = (parsed.hostname or "").lower()
        if host == "youtu.be":
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) != 1:
                raise ValueError("unsupported youtu.be target shape")
            return cls(parts[0])

        if host not in _YOUTUBE_HOSTS:
            raise ValueError("unsupported YouTube target host")
        if parsed.path == "/watch":
            values = parse_qs(parsed.query).get("v", [])
            if len(values) != 1:
                raise ValueError("watch URL must contain exactly one video ID")
            return cls(values[0])
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) == 2 and parts[0] == "live":
            return cls(parts[1])
        raise ValueError("unsupported YouTube target path")


class MediaKind(str, Enum):
    AUDIO = "audio"
    VIDEO = "video"


@dataclass(frozen=True, slots=True)
class ResolvedMediaSource:
    """Typed media descriptor; it cannot carry a URL or shell command."""

    provider: str
    resource_id: str
    kind: MediaKind
    quality: str

    def __post_init__(self) -> None:
        if not _SAFE_DESCRIPTOR_RE.fullmatch(self.provider):
            raise ValueError("media provider must be a safe descriptor")
        if not _SAFE_DESCRIPTOR_RE.fullmatch(self.resource_id):
            raise ValueError("media resource ID must be a safe descriptor, not a URL")
        if not isinstance(self.kind, MediaKind):
            raise TypeError("media kind must be a MediaKind")
        if not _SAFE_QUALITY_RE.fullmatch(self.quality):
            raise ValueError("media quality must be a safe token")


class FakeYouTubeMediaResolver:
    """Synthetic resolver standing in for a future policy-approved edge."""

    def resolve(
        self,
        *,
        target: YouTubeVideoId,
        kind: MediaKind,
        quality: str = "best",
    ) -> ResolvedMediaSource:
        if not isinstance(target, YouTubeVideoId):
            raise TypeError("resolver requires a validated YouTubeVideoId")
        return ResolvedMediaSource(
            provider="youtube-fake",
            resource_id=target.value,
            kind=kind,
            quality=quality,
        )


@dataclass(slots=True)
class SyntheticMediaStream:
    """In-memory readable/closable stream used by the neutral readers."""

    payloads: tuple[object, ...]
    closed: bool = False
    close_calls: int = 0

    def read_all(self) -> tuple[object, ...]:
        if self.closed:
            raise RuntimeError("synthetic media stream is closed")
        return self.payloads

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.close_calls += 1


class ValidatedSyntheticMediaOpener:
    """Fake opener accepting only validated typed descriptors."""

    def __init__(
        self,
        fixtures: Mapping[tuple[str, MediaKind], Sequence[object]],
        *,
        fail_kinds: frozenset[MediaKind] = frozenset(),
        fail_once_kinds: frozenset[MediaKind] = frozenset(),
    ) -> None:
        self._fixtures = {key: tuple(payloads) for key, payloads in fixtures.items()}
        self._fail_kinds = fail_kinds
        self._fail_once_kinds = fail_once_kinds
        self._failed_once: set[MediaKind] = set()
        self.opened: list[SyntheticMediaStream] = []
        self.calls: list[ResolvedMediaSource] = []

    def open(self, source: ResolvedMediaSource) -> SyntheticMediaStream:
        if not isinstance(source, ResolvedMediaSource):
            raise TypeError("opener requires a ResolvedMediaSource")
        if source.provider != "youtube-fake":
            raise ValueError("synthetic opener rejects an unrecognized provider")
        self.calls.append(source)
        if source.kind in self._fail_kinds:
            raise RuntimeError(f"{source.kind.value} source open failed")
        if (
            source.kind in self._fail_once_kinds
            and source.kind not in self._failed_once
        ):
            self._failed_once.add(source.kind)
            raise RuntimeError(f"{source.kind.value} source open failed once")
        key = (source.resource_id, source.kind)
        if key not in self._fixtures:
            raise LookupError("no synthetic fixture for resolved media source")
        stream = SyntheticMediaStream(self._fixtures[key])
        self.opened.append(stream)
        return stream


class NeutralSyntheticMediaReader(SourceAdapter):
    """Media-neutral lifecycle over a resolved source and injected opener."""

    def __init__(
        self,
        *,
        source: ResolvedMediaSource,
        opener: ValidatedSyntheticMediaOpener,
    ) -> None:
        self._source = source
        self._opener = opener
        self._stream: SyntheticMediaStream | None = None
        self._start_attempted = False
        self._running = False
        self.starts = 0
        self.stops = 0

    def channels(self) -> set[str]:
        return {self._source.kind.value}

    async def start(self) -> None:
        if self._start_attempted:
            return
        self._start_attempted = True
        self.starts += 1
        try:
            self._stream = self._opener.open(self._source)
        except Exception:
            self._start_attempted = False
            self._stream = None
            raise
        self._running = True

    async def stop(self) -> None:
        if not self._start_attempted:
            return
        self._start_attempted = False
        self.stops += 1
        self._running = False
        if self._stream is not None:
            self._stream.close()
            self._stream = None

    async def events(self) -> AsyncIterator[RawEvent]:
        if not self._start_attempted:
            await self.start()
        stream = self._stream
        if stream is None:
            return
        expected = AudioChunk if self._source.kind is MediaKind.AUDIO else VideoFrame
        for payload in stream.read_all():
            if not self._running:
                return
            if not isinstance(payload, expected):
                raise TypeError(
                    f"{self._source.kind.value} source returned {type(payload)!r}"
                )
            yield RawEvent(
                channel=self._source.kind.value,
                payload=payload,
                ts=payload.ts,
            )


# Branch A deliberately repeats the platform reader lifecycle.  This makes the
# duplication cost visible instead of hiding it behind a prematurely generic base.
class YouTubeSpecificChatReader(SourceAdapter):
    def __init__(
        self,
        *,
        target: YouTubeVideoId,
        messages: Sequence[dict[str, object]],
        fail_on_events: bool = False,
    ) -> None:
        self.target = target
        self._messages = tuple(messages)
        self._fail_on_events = fail_on_events
        self._start_attempted = self._running = False
        self.starts = self.stops = 0

    def channels(self) -> set[str]:
        return {"chat"}

    async def start(self) -> None:
        if self._start_attempted:
            return
        self._start_attempted = self._running = True
        self.starts += 1

    async def stop(self) -> None:
        if not self._start_attempted:
            return
        self._start_attempted = False
        self._running = False
        self.stops += 1

    async def events(self) -> AsyncIterator[RawEvent]:
        if not self._start_attempted:
            await self.start()
        if self._fail_on_events:
            raise RuntimeError("chat reader failed")
        for message in self._messages:
            if not self._running:
                return
            yield RawEvent(channel="chat", payload=message, ts=float(message["ts"]))


class YouTubeSpecificAudioReader(SourceAdapter):
    def __init__(
        self,
        *,
        target: YouTubeVideoId,
        chunks: Sequence[AudioChunk],
        fail_on_events: bool = False,
    ) -> None:
        self.target = target
        self._chunks = tuple(chunks)
        self._fail_on_events = fail_on_events
        self._start_attempted = self._running = False
        self.starts = self.stops = 0

    def channels(self) -> set[str]:
        return {"audio"}

    async def start(self) -> None:
        if self._start_attempted:
            return
        self._start_attempted = self._running = True
        self.starts += 1

    async def stop(self) -> None:
        if not self._start_attempted:
            return
        self._start_attempted = False
        self._running = False
        self.stops += 1

    async def events(self) -> AsyncIterator[RawEvent]:
        if not self._start_attempted:
            await self.start()
        if self._fail_on_events:
            raise RuntimeError("audio reader failed")
        for chunk in self._chunks:
            if not self._running:
                return
            yield RawEvent(channel="audio", payload=chunk, ts=chunk.ts)


class YouTubeSpecificVideoReader(SourceAdapter):
    def __init__(
        self,
        *,
        target: YouTubeVideoId,
        frames: Sequence[VideoFrame],
        fail_on_events: bool = False,
    ) -> None:
        self.target = target
        self._frames = tuple(frames)
        self._fail_on_events = fail_on_events
        self._start_attempted = self._running = False
        self.starts = self.stops = 0

    def channels(self) -> set[str]:
        return {"video"}

    async def start(self) -> None:
        if self._start_attempted:
            return
        self._start_attempted = self._running = True
        self.starts += 1

    async def stop(self) -> None:
        if not self._start_attempted:
            return
        self._start_attempted = False
        self._running = False
        self.stops += 1

    async def events(self) -> AsyncIterator[RawEvent]:
        if not self._start_attempted:
            await self.start()
        if self._fail_on_events:
            raise RuntimeError("video reader failed")
        for frame in self._frames:
            if not self._running:
                return
            yield RawEvent(channel="video", payload=frame, ts=frame.ts)


@dataclass(slots=True)
class PrototypeBranch:
    name: str
    target: YouTubeVideoId
    readers: dict[str, SourceAdapter]
    adapter: MergingSourceAdapter
    opener: ValidatedSyntheticMediaOpener | None = None


def _fixtures(target: YouTubeVideoId) -> dict[str, object]:
    return {
        "chat": {
            "text": "synthetic hello",
            "speaker": "Synthetic Viewer",
            "message_id": "synthetic-message-1",
            "author_channel_id": "synthetic-author-1",
            "live_chat_id": f"chat-{target.value}",
            "ts": 1.0,
        },
        "audio": AudioChunk(
            samples=b"\x00\x00" * 8,
            sample_rate=16_000,
            source_label="youtube",
            ts=2.0,
        ),
        "video": VideoFrame(
            pixels=b"synthetic-frame",
            source_label="youtube",
            ts=3.0,
        ),
    }


def build_specific_branch(
    target: YouTubeVideoId,
    *,
    queue_size: int = 8,
    failing_channel: str | None = None,
    empty_channel: str | None = None,
) -> PrototypeBranch:
    """Alternative A: three YouTube-specific readers composed by the merger."""

    fixture = _fixtures(target)
    readers: dict[str, SourceAdapter] = {
        "audio": YouTubeSpecificAudioReader(
            target=target,
            chunks=[] if empty_channel == "audio" else [fixture["audio"]],
            fail_on_events=failing_channel == "audio",
        ),
        "video": YouTubeSpecificVideoReader(
            target=target,
            frames=[] if empty_channel == "video" else [fixture["video"]],
            fail_on_events=failing_channel == "video",
        ),
        "chat": YouTubeSpecificChatReader(
            target=target,
            messages=[] if empty_channel == "chat" else [fixture["chat"]],
            fail_on_events=failing_channel == "chat",
        ),
    }
    adapter = MergingSourceAdapter(
        readers=readers,
        priority_channels=("chat",),
        queue_size=queue_size,
        cleanup_timeout=0.2,
    )
    return PrototypeBranch("specific-readers", target, readers, adapter)


def build_typed_media_branch(
    target: YouTubeVideoId,
    *,
    queue_size: int = 8,
    failing_channel: str | None = None,
    empty_channel: str | None = None,
    fail_once_channel: str | None = None,
) -> PrototypeBranch:
    """Alternative B: YouTube chat plus typed media sources and neutral readers."""

    fixture = _fixtures(target)
    resolver = FakeYouTubeMediaResolver()
    audio_source = resolver.resolve(target=target, kind=MediaKind.AUDIO)
    video_source = resolver.resolve(target=target, kind=MediaKind.VIDEO)
    failed_kinds = {
        kind
        for kind in MediaKind
        if failing_channel is not None and kind.value == failing_channel
    }
    opener = ValidatedSyntheticMediaOpener(
        {
            (target.value, MediaKind.AUDIO): (
                [] if empty_channel == "audio" else [fixture["audio"]]
            ),
            (target.value, MediaKind.VIDEO): (
                [] if empty_channel == "video" else [fixture["video"]]
            ),
        },
        fail_kinds=frozenset(failed_kinds),
        fail_once_kinds=frozenset(
            kind for kind in MediaKind if kind.value == fail_once_channel
        ),
    )
    readers: dict[str, SourceAdapter] = {
        "audio": NeutralSyntheticMediaReader(source=audio_source, opener=opener),
        "video": NeutralSyntheticMediaReader(source=video_source, opener=opener),
        "chat": YouTubeSpecificChatReader(
            target=target,
            messages=[] if empty_channel == "chat" else [fixture["chat"]],
            fail_on_events=failing_channel == "chat",
        ),
    }
    adapter = MergingSourceAdapter(
        readers=readers,
        priority_channels=("chat",),
        queue_size=queue_size,
        cleanup_timeout=0.2,
    )
    return PrototypeBranch("typed-media-source", target, readers, adapter, opener)
