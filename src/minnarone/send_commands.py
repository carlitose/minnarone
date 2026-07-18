"""Send command surface: narrow, thread-safe mutation channel for the TUI (issue 08).

The TUI is read-only by design, except for exactly two operator commands:
promote (shadow -> live) and kill-switch (live -> shadow). This module wraps
those two transitions behind a Lock-guarded surface that the foreground TUI
thread can call safely while the agent event loop runs in the background.

Design constraints from the PRD:
- Promote requires a confirmation step (handled by the TUI, not here).
- Kill-switch is instant (single call, no confirmation).
- No keybinding may disengage the kill-switch implicitly: returning to live
  is always a fresh, confirmed promote.
- All transitions are recorded with actor and reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class TransitionResult:
    """Outcome of a send-state transition request."""

    accepted: bool
    reason: str


class SendCommandSurface:
    """Thread-safe command surface for promote/kill-switch transitions.

    Wraps a ``PublicSendPolicy`` with a Lock so the TUI thread can safely
    mutate the send state while the agent event loop runs concurrently.
    """

    def __init__(
        self,
        policy: object,
        event_recorder: object | None = None,
    ) -> None:
        self._policy = policy
        self._event_recorder = event_recorder
        self._lock = Lock()

    def promote(self) -> TransitionResult:
        """Request promotion to live send (shadow -> live).

        Returns accepted=True only if the policy's config arms live mode.
        Records the transition as a run event with actor=operator.
        """
        with self._lock:
            accepted = self._policy.promote()
            if not accepted:
                return TransitionResult(
                    accepted=False,
                    reason="config does not arm live",
                )
            self._record_transition("promote", "operator", "operator_promoted")
            return TransitionResult(accepted=True, reason="promoted")

    def kill_switch(self) -> TransitionResult:
        """Engage the kill-switch: live -> shadow, instant, no confirmation.

        Always accepted (idempotent). Records the transition as a run event
        with actor=operator.
        """
        with self._lock:
            self._policy.engage_kill_switch()
            self._record_transition("kill_switch", "operator", "operator_kill_switch")
            return TransitionResult(accepted=True, reason="kill_switch_engaged")

    def _record_transition(self, transition: str, actor: str, reason: str) -> None:
        if self._event_recorder is None:
            return
        record = getattr(self._event_recorder, "record_send_transition", None)
        if callable(record):
            record(transition=transition, actor=actor, reason=reason)
