"""Tests for the speaker command surface (issue 03).

Mark-current-streamer is the TUI's speaker-side mutation channel, sibling to
promote/kill-switch (SendCommandSurface). Same pattern: Lock-guarded, a frozen
result dataclass, and event recording with actor=operator. It pins the cluster
of the most-recent *assigned* utterance as a manual streamer.
"""

import json
from threading import Lock

import pytest

from minnarone.speaker import OnlineSpeakerClusterer, SpeakerClusteringConfig


def _clusterer() -> OnlineSpeakerClusterer:
    return OnlineSpeakerClusterer(
        SpeakerClusteringConfig(
            threshold=0.8,
            warmup_seconds=999.0,
            min_update_seconds=0.0,
        )
    )


class _FakeTagger:
    """Minimal tagger exposing the clusterer's marking method (no audio)."""

    def __init__(self, clusterer: OnlineSpeakerClusterer) -> None:
        self._clusterer = clusterer

    def mark_current_speaker_as_streamer(self) -> int | None:
        return self._clusterer.mark_current_speaker_as_streamer()


# --- MarkStreamerResult dataclass ---


def test_mark_result_is_frozen():
    from minnarone.speaker_commands import MarkStreamerResult

    result = MarkStreamerResult(accepted=True, reason="ok", cluster_id=1)
    with pytest.raises(AttributeError):
        result.accepted = False  # type: ignore[misc]


# --- SpeakerCommandSurface: mark ---


def test_mark_accepted_when_utterance_exists():
    from minnarone.speaker_commands import SpeakerCommandSurface

    clusterer = _clusterer()
    first = clusterer.assign([1.0, 0.0], duration_seconds=1.0)
    surface = SpeakerCommandSurface(_FakeTagger(clusterer))

    result = surface.mark_current_streamer()
    assert result.accepted is True
    assert result.cluster_id == first.cluster_id
    assert clusterer.assign([1.0, 0.0], duration_seconds=1.0).label == "streamer"


def test_mark_rejected_when_no_utterance_yet():
    from minnarone.speaker_commands import SpeakerCommandSurface

    surface = SpeakerCommandSurface(_FakeTagger(_clusterer()))
    result = surface.mark_current_streamer()
    assert result.accepted is False
    assert result.cluster_id is None
    assert result.reason  # non-empty motivo for the display


def test_mark_supports_multiple_streamers():
    from minnarone.speaker_commands import SpeakerCommandSurface

    clusterer = _clusterer()
    surface = SpeakerCommandSurface(_FakeTagger(clusterer))
    clusterer.assign([1.0, 0.0], duration_seconds=1.0)
    assert surface.mark_current_streamer().accepted is True
    clusterer.assign([0.0, 1.0], duration_seconds=1.0)
    assert surface.mark_current_streamer().accepted is True

    assert clusterer.assign([1.0, 0.0], duration_seconds=1.0).label == "streamer"
    assert clusterer.assign([0.0, 1.0], duration_seconds=1.0).label == "streamer"


def test_mark_rejected_when_tagger_does_not_support_marking():
    from minnarone.speaker_commands import SpeakerCommandSurface

    class Bare:  # no mark method (e.g. a diagnostics-only object)
        pass

    result = SpeakerCommandSurface(Bare()).mark_current_streamer()
    assert result.accepted is False


# --- Event recording ---


def test_mark_records_event_with_actor_operator(tmp_path):
    from minnarone.run_events import RunEventRecorder
    from minnarone.speaker_commands import SpeakerCommandSurface

    recorder = RunEventRecorder(tmp_path)
    clusterer = _clusterer()
    clusterer.assign([1.0, 0.0], duration_seconds=1.0)
    surface = SpeakerCommandSurface(_FakeTagger(clusterer), event_recorder=recorder)

    surface.mark_current_streamer()

    events = [
        json.loads(line)
        for line in recorder.path.read_text(encoding="utf-8").strip().split("\n")
    ]
    assert len(events) == 1
    ev = events[0]
    assert ev["kind"] == "streamer_marked"
    assert ev["streamer_marked"]["actor"] == "operator"
    assert ev["streamer_marked"]["cluster_id"] == 1


def test_rejected_mark_does_not_record_event(tmp_path):
    from minnarone.run_events import RunEventRecorder
    from minnarone.speaker_commands import SpeakerCommandSurface

    recorder = RunEventRecorder(tmp_path)
    surface = SpeakerCommandSurface(_FakeTagger(_clusterer()), event_recorder=recorder)
    surface.mark_current_streamer()
    assert not recorder.path.exists()


def test_surface_is_thread_safe():
    from minnarone.speaker_commands import SpeakerCommandSurface

    surface = SpeakerCommandSurface(_FakeTagger(_clusterer()))
    assert isinstance(surface._lock, type(Lock()))
