"""Validated, explicit YouTube video targets.

Ticket 01 selected an explicit ``video_id`` as the session identity.  Supported
URL forms are input conveniences only: a running session never follows a
channel page or silently retargets another broadcast.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_YOUTUBE_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com"})


@dataclass(frozen=True, slots=True)
class YouTubeVideoId:
    """One normalized YouTube video ID selected by the operator."""

    value: str

    def __post_init__(self) -> None:
        if not _VIDEO_ID_RE.fullmatch(self.value):
            raise ValueError("YouTube video ID must be exactly 11 safe characters")

    @classmethod
    def parse(cls, target: str) -> YouTubeVideoId:
        """Accept an ID or one explicit, supported HTTPS YouTube URL shape."""

        if not isinstance(target, str):
            raise ValueError("YouTube target must be a video ID or supported URL")
        value = target.strip()
        if _VIDEO_ID_RE.fullmatch(value):
            return cls(value)

        parsed = urlsplit(value)
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


@dataclass(frozen=True, slots=True)
class YouTubeChannelId:
    """One stable YouTube channel identity, never a mutable display name."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _CHANNEL_ID_RE.fullmatch(self.value):
            raise ValueError("YouTube channel ID must be UC plus 22 safe characters")

    @classmethod
    def parse(cls, value: object) -> YouTubeChannelId:
        if not isinstance(value, str):
            raise ValueError("YouTube channel ID must be a string")
        return cls(value.strip())
