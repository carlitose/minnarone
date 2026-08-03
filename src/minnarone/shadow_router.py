"""Twitch edge adapter for the neutral public output router."""

from __future__ import annotations

from typing import TextIO

from .public_router import PublicOutputRouter
from .public_send import PublicTarget
from .twitch_media import normalize_twitch_channel


class TwitchPublicOutputRouter(PublicOutputRouter):
    """Compatibility adapter that normalizes a Twitch channel at the edge."""

    def __init__(
        self,
        *,
        policy: object,
        channel: str,
        stream: TextIO | None = None,
        event_recorder: object | None = None,
        sender: object | None = None,
        echo: bool = True,
    ) -> None:
        super().__init__(
            policy=policy,
            target=PublicTarget("twitch", normalize_twitch_channel(channel)),
            stream=stream,
            event_recorder=event_recorder,
            sender=sender,
            echo=echo,
        )
