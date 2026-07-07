"""Local output stream for dashboard-visible Minnarone comments."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from .console import ConsoleOutputRouter
from .output import OutputMode, OutputRouter

_DEFAULT_RECENT_MINNARONE_MESSAGES = 20


@dataclass(frozen=True, slots=True)
class MinnaroneOutputMessage:
    """One local Minnarone output event captured for observability."""

    ts: float
    text: str
    mode: OutputMode


class MinnaroneOutputStream:
    """Bounded in-memory stream of recent Minnarone output events."""

    def __init__(
        self,
        *,
        max_messages: int = _DEFAULT_RECENT_MINNARONE_MESSAGES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_messages <= 0:
            raise ValueError("max_messages deve essere > 0")
        self._messages: deque[MinnaroneOutputMessage] = deque(maxlen=max_messages)
        self._clock = clock

    def append(self, text: str, mode: OutputMode) -> None:
        self._messages.append(
            MinnaroneOutputMessage(ts=self._clock(), text=text, mode=mode)
        )

    def recent_messages(self, n: int | None = None) -> list[MinnaroneOutputMessage]:
        messages = list(self._messages)
        if n is None:
            return messages
        if n <= 0:
            return []
        return messages[-n:]


class TuiPrivateOutputRouter(OutputRouter):
    """Route private comments to the dashboard stream instead of stdout."""

    def __init__(
        self,
        stream: MinnaroneOutputStream,
        *,
        public_router: OutputRouter | None = None,
    ) -> None:
        self.stream = stream
        self._public_router = (
            public_router if public_router is not None else ConsoleOutputRouter()
        )

    async def route(self, message: str, mode: OutputMode) -> None:
        if mode is OutputMode.PRIVATE:
            self.stream.append(message, mode)
            return
        await self._public_router.route(message, mode)
        # Capture PUBLIC messages with send markers for dashboard MINNARONE panel.
        last = getattr(self._public_router, "last_decision", None)
        if last is not None:
            if last.action == "send":
                self.stream.append(f"[SENT] {message}", mode)
            elif last.action != "drop":
                self.stream.append(f"[SHADOW] {message}", mode)
