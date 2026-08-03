"""YouTube chat-only candidate output with no public-send capability."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TextIO

from .output import OutputMode, OutputRouter


@dataclass(frozen=True, slots=True)
class YouTubeShadowDecision:
    action: str = "shadow"
    reason: str = "read_only_adapter"


class YouTubeShadowOutputRouter(OutputRouter):
    """Expose public candidates locally while making network send impossible."""

    def __init__(
        self,
        *,
        video_id: str,
        stream: TextIO | None = None,
        event_recorder: object | None = None,
        echo: bool = True,
    ) -> None:
        self._video_id = video_id
        self._stream = stream if stream is not None else sys.stdout
        self._event_recorder = event_recorder
        self._echo = echo
        self.last_decision: YouTubeShadowDecision | None = None

    async def route(self, message: str, mode: OutputMode) -> None:
        if mode is not OutputMode.PUBLIC:
            self.last_decision = None
            return
        self.last_decision = YouTubeShadowDecision()
        if self._echo:
            print(f"[SHADOW] {message}", file=self._stream)
        recorder = self._event_recorder
        record = getattr(recorder, "record_send_decision", None)
        if callable(record):
            record(
                message=message,
                action="shadow",
                reason="read_only_adapter",
                channel=self._video_id,
            )
