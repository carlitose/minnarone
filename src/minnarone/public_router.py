"""Platform-neutral public output routing behind the safety policy."""

from __future__ import annotations

import sys
from typing import TextIO

from .output import OutputMode, OutputRouter
from .public_send import ACTION_DROP, ACTION_SEND, PublicTarget, SendDecision


class PublicSendFailure(RuntimeError):
    """Expected, typed failure raised by a platform send transport."""


class PublicOutputRouter(OutputRouter):
    """Route one public target through send/shadow/drop without retries."""

    def __init__(
        self,
        *,
        policy: object,
        target: PublicTarget,
        stream: TextIO | None = None,
        event_recorder: object | None = None,
        sender: object | None = None,
        echo: bool = True,
    ) -> None:
        if not isinstance(target, PublicTarget):
            raise TypeError("target must be a PublicTarget")
        self._policy = policy
        self._target = target
        self._stream = stream if stream is not None else sys.stdout
        self._event_recorder = event_recorder
        self._sender = sender
        self._echo = echo
        self.last_decision: SendDecision | None = None

    def _display(self, marker: str, message: str) -> None:
        if self._echo:
            print(f"{marker} {message}", file=self._stream)

    async def route(self, message: str, mode: OutputMode) -> None:
        if mode is not OutputMode.PUBLIC:
            self.last_decision = None
            return

        decision = self._policy.decide(message, self._target)
        self.last_decision = decision

        if decision.action == ACTION_SEND and self._sender is not None:
            try:
                await self._sender.send(message)
            except PublicSendFailure as exc:
                # A failed turn is skipped once.  There is no retry or stale
                # message queue. Unexpected exceptions propagate unchanged.
                self._display("[FAILED]", message)
                disarms_live = bool(getattr(exc, "disarms_live", False))
                if disarms_live:
                    disable_live = getattr(self._policy, "disable_live", None)
                    if callable(disable_live):
                        disable_live()
                self._policy.record_failure()
                self._record_decision(message, "failed", str(exc))
                if not disarms_live:
                    self._record_auto_degrade_if_engaged()
                return
            self._display("[SENT]", message)
            self._policy.record_success()
        elif decision.action != ACTION_DROP:
            self._display("[SHADOW]", message)

        self._record_decision(message, decision.action, decision.reason)

    def _record_decision(self, message: str, action: str, reason: str) -> None:
        recorder = self._event_recorder
        record = getattr(recorder, "record_send_decision", None)
        if callable(record):
            record(
                message=message,
                action=action,
                reason=reason,
                channel=self._target.identifier,
            )

    def _record_auto_degrade_if_engaged(self) -> None:
        try:
            snap = self._policy.snapshot()
        except AttributeError:
            return
        if not snap.kill_switch or self._event_recorder is None:
            return
        self._record_decision("", "auto_degrade", "kill_switch")
        record_transition = getattr(
            self._event_recorder, "record_send_transition", None
        )
        if callable(record_transition):
            record_transition(
                transition="kill_switch",
                actor="auto",
                reason="failure_threshold_reached",
            )
