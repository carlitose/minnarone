"""TwitchPublicOutputRouter: tracer bullet shadow per l'invio pubblico (slice 03).

Compone la PublicSendPolicy con un display sink locale. In PUBLIC mode, chiede
alla policy se il messaggio va in shadow o in drop; shadow viene mostrato
localmente con il marcatore ``[SHADOW]``, drop viene registrato ma non mostrato.
Nessun invio reale in questa slice: il sender arriva nell'issue 07.
"""

from __future__ import annotations

import sys
from typing import TextIO

from .output import OutputMode, OutputRouter
from .public_send import ACTION_DROP, SendDecision


class TwitchPublicOutputRouter(OutputRouter):
    """Router pubblico Twitch: shadow/drop via policy, display locale."""

    def __init__(
        self,
        *,
        policy: object,
        channel: str,
        stream: TextIO | None = None,
        event_recorder: object | None = None,
    ) -> None:
        self._policy = policy
        self._channel = channel
        self._stream = stream if stream is not None else sys.stdout
        self._event_recorder = event_recorder
        self.last_decision: SendDecision | None = None

    async def route(self, message: str, mode: OutputMode) -> None:
        if mode is not OutputMode.PUBLIC:
            self.last_decision = None
            return

        decision = self._policy.decide(message, self._channel)
        self.last_decision = decision

        if decision.action != ACTION_DROP:
            print(f"[SHADOW] {message}", file=self._stream)

        if self._event_recorder is not None:
            self._event_recorder.record_send_decision(
                message=message,
                action=decision.action,
                reason=decision.reason,
                channel=self._channel,
            )
