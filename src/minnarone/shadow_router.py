"""TwitchPublicOutputRouter: shadow + live send per l'invio pubblico (slice 03 + 07).

Compone la PublicSendPolicy con un display sink locale e un sender opzionale.
In PUBLIC mode, chiede alla policy se il messaggio va in send, shadow o drop:

- ``send`` con sender: invoca ``sender.send()``, mostra ``[SENT]`` in locale,
  registra l'evento e chiama ``record_success()`` sulla policy. Se il sender
  fallisce con ``TwitchSendError``, mostra ``[FAILED]``, chiama
  ``record_failure()`` e registra l'evento come ``failed``. Al raggiungimento
  della soglia di fallimenti la policy ingaggia automaticamente il kill-switch.
- ``send`` senza sender: fallback a ``[SHADOW]`` (configurazione shadow-only).
- ``shadow``: mostrato localmente con il marcatore ``[SHADOW]``.
- ``drop``: registrato ma non mostrato.
"""

from __future__ import annotations

import sys
from typing import TextIO

from .output import OutputMode, OutputRouter
from .public_send import ACTION_DROP, ACTION_SEND, SendDecision
from .twitch_chat_sender import TwitchSendError


class TwitchPublicOutputRouter(OutputRouter):
    """Router pubblico Twitch: send/shadow/drop via policy, display locale."""

    def __init__(
        self,
        *,
        policy: object,
        channel: str,
        stream: TextIO | None = None,
        event_recorder: object | None = None,
        sender: object | None = None,
    ) -> None:
        self._policy = policy
        self._channel = channel
        self._stream = stream if stream is not None else sys.stdout
        self._event_recorder = event_recorder
        self._sender = sender
        self.last_decision: SendDecision | None = None

    async def route(self, message: str, mode: OutputMode) -> None:
        if mode is not OutputMode.PUBLIC:
            self.last_decision = None
            return

        decision = self._policy.decide(message, self._channel)
        self.last_decision = decision

        if decision.action == ACTION_SEND and self._sender is not None:
            try:
                await self._sender.send(message)
            except TwitchSendError as exc:
                # Failed send: display marker, feed policy, record event.
                # The turn is skipped (no retry, no queue).
                print(f"[FAILED] {message}", file=self._stream)
                self._policy.record_failure()
                if self._event_recorder is not None:
                    self._event_recorder.record_send_decision(
                        message=message,
                        action="failed",
                        reason=str(exc),
                        channel=self._channel,
                    )
                    self._record_auto_degrade_if_engaged()
                return

            # Successful send: display marker, feed policy, record event.
            print(f"[SENT] {message}", file=self._stream)
            self._policy.record_success()
        elif decision.action != ACTION_DROP:
            # Shadow display (also handles send-without-sender as fallback).
            print(f"[SHADOW] {message}", file=self._stream)

        if self._event_recorder is not None:
            self._event_recorder.record_send_decision(
                message=message,
                action=decision.action,
                reason=decision.reason,
                channel=self._channel,
            )

    def _record_auto_degrade_if_engaged(self) -> None:
        """Record an auto-degrade event if the kill switch was just engaged.

        After a failed send, if the kill switch is now active it was just
        triggered by ``record_failure()`` (it was off before, because the
        decision was ``send``). Record the transition as its own event.
        """
        try:
            snap = self._policy.snapshot()
        except AttributeError:
            return
        if snap.kill_switch and self._event_recorder is not None:
            self._event_recorder.record_send_decision(
                message="",
                action="auto_degrade",
                reason="kill_switch",
                channel=self._channel,
            )
