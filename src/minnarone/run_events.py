"""Run-scoped replay event artifacts for triggers and Minnarone outputs."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from threading import Lock

from .output import OutputMode
from .perception import Perception
from .prompt_observation import redact_unsafe_text
from .senser import Trigger

RUN_EVENTS_FILENAME = "events.jsonl"
_SCHEMA = "minnarone.run_event.v1"


class RunEventRecorder:
    """Append-only local JSONL recorder for replayable runtime events."""

    def __init__(self, debug_dir: str | Path) -> None:
        self.path = Path(debug_dir) / RUN_EVENTS_FILENAME
        self._lock = Lock()
        self._sequence = 0

    def record_trigger(self, trigger: Trigger) -> None:
        self._append(
            {
                "kind": "trigger",
                "trigger": {
                    "reason": _safe_text(trigger.reason) or "unknown",
                    "kind": _safe_text(trigger.kind) or "unknown",
                    "interlocutor": _safe_text(trigger.interlocutor),
                    "perception": _perception_payload(trigger.perception),
                },
            }
        )

    def record_minnarone_output(self, message: str, mode: OutputMode) -> None:
        self._append(
            {
                "kind": "minnarone_output",
                "output": {
                    "message": _safe_text(message) or "",
                    "mode": _safe_text(mode.value) or str(mode),
                },
            }
        )

    def record_send_decision(
        self,
        *,
        message: str,
        action: str,
        reason: str,
        channel: str,
    ) -> None:
        """Record a public-send policy decision (shadow/drop) for audit replay."""
        self._append(
            {
                "kind": "send_decision",
                "send_decision": {
                    "message": _safe_text(message) or "",
                    "action": _safe_text(action) or "unknown",
                    "reason": _safe_text(reason) or "unknown",
                    "channel": _safe_text(channel) or "",
                },
            }
        )

    def record_send_transition(
        self,
        *,
        transition: str,
        actor: str,
        reason: str,
    ) -> None:
        """Record a send-state transition (promote/kill-switch/auto-degrade).

        Each transition carries an actor (``operator`` for manual actions,
        ``auto`` for auto-degrade) and a reason string for audit replay.
        """
        self._append(
            {
                "kind": "send_transition",
                "send_transition": {
                    "transition": _safe_text(transition) or "unknown",
                    "actor": _safe_text(actor) or "unknown",
                    "reason": _safe_text(reason) or "unknown",
                },
            }
        )

    def record_streamer_marked(
        self,
        *,
        cluster_id: int,
        actor: str,
        reason: str,
    ) -> None:
        """Record a manual streamer marking (issue 03) for audit replay.

        The operator pins a cluster as streamer from the TUI; ``actor`` is
        ``operator`` for these manual actions.
        """
        self._append(
            {
                "kind": "streamer_marked",
                "streamer_marked": {
                    "cluster_id": cluster_id,
                    "actor": _safe_text(actor) or "unknown",
                    "reason": _safe_text(reason) or "unknown",
                },
            }
        )

    def _append(self, payload: dict[str, object]) -> None:
        with self._lock:
            self._sequence += 1
            record = {
                "schema": _SCHEMA,
                "sequence": self._sequence,
                "recorded_at": time.time(),
                **payload,
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())


def _perception_payload(perception: Perception | None) -> dict[str, object] | None:
    if perception is None:
        return None
    payload: dict[str, object] = {
        "ts": perception.ts,
        "source": perception.source.value,
        "type": _safe_text(perception.type) or "unknown",
        "text": _safe_text(perception.text) or "",
    }
    speaker = _safe_text(perception.speaker)
    if speaker is not None:
        payload["speaker"] = speaker
    return payload


def _safe_text(value: object) -> str | None:
    if value is None:
        return None
    return redact_unsafe_text(value)
