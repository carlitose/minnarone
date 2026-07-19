"""Speaker command surface: mark the current speaker as streamer (issue 03).

The TUI is read-only by design, except for the send commands (promote/
kill-switch, see ``send_commands.py``) and this one speaker-side command:
mark the cluster of the most-recent assigned utterance as a manual streamer.

This mirrors ``SendCommandSurface`` — a Lock-guarded channel with a frozen
result dataclass and an event recorder — but stays separate: marking a streamer
is unrelated to send-path state, so it does not overload the send surface.

Automatic dominant-cluster freeze remains the fallback until the operator marks
someone; after the first manual pin the operator's choice wins and is never
overwritten. Marking different voices yields multiple streamers.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class MarkStreamerResult:
    """Outcome of a mark-current-streamer request."""

    accepted: bool
    reason: str
    cluster_id: int | None = None


class SpeakerCommandSurface:
    """Thread-safe command surface for manual streamer marking.

    Wraps a speaker tagger/clusterer that exposes
    ``mark_current_speaker_as_streamer()`` with a Lock so the TUI thread can
    mutate speaker labels safely while the agent event loop runs concurrently.
    """

    def __init__(
        self,
        tagger: object,
        event_recorder: object | None = None,
    ) -> None:
        self._tagger = tagger
        self._event_recorder = event_recorder
        self._lock = Lock()

    def mark_current_streamer(self) -> MarkStreamerResult:
        """Pin the current speaker's cluster as a manual streamer.

        Returns accepted=True with the pinned cluster id when an utterance has
        been assigned; rejected (with a reason for the display) when the tagger
        cannot mark or no utterance exists yet. Records the marking as a run
        event with actor=operator only when accepted.
        """
        with self._lock:
            mark = getattr(self._tagger, "mark_current_speaker_as_streamer", None)
            if not callable(mark):
                return MarkStreamerResult(
                    accepted=False,
                    reason="speaker tagging is unavailable",
                )
            cluster_id = mark()
            if cluster_id is None:
                return MarkStreamerResult(
                    accepted=False,
                    reason="no utterance is available to mark",
                )
            self._record(cluster_id)
            return MarkStreamerResult(
                accepted=True,
                reason="streamer marked",
                cluster_id=cluster_id,
            )

    def _record(self, cluster_id: int) -> None:
        if self._event_recorder is None:
            return
        record = getattr(self._event_recorder, "record_streamer_marked", None)
        if callable(record):
            record(
                cluster_id=cluster_id,
                actor="operator",
                reason="operator_marked_streamer",
            )
