"""Tests for the send command surface (issue 08, slice 1).

The command surface is the narrow channel through which the TUI mutates
the send-path state: promote (shadow -> live) and kill-switch (live -> shadow).
Thread-safe by construction (Lock-guarded), so the TUI foreground thread can
call it while the agent event loop runs in the background.
"""

from threading import Lock

import pytest

from minnarone.config import TwitchSendConfig, TwitchSendMode
from minnarone.public_send import PublicSendPolicy


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def _live_config(**kwargs) -> TwitchSendConfig:
    kwargs.setdefault("allowed_channels", ("canale",))
    kwargs.setdefault("max_per_minute", 1000)
    kwargs.setdefault("max_per_hour", 1000)
    return TwitchSendConfig(mode=TwitchSendMode.LIVE, **kwargs)


# --- TransitionResult dataclass ---


def test_transition_result_is_frozen():
    from minnarone.send_commands import TransitionResult

    result = TransitionResult(accepted=True, reason="promoted")
    with pytest.raises(AttributeError):
        result.accepted = False  # type: ignore[misc]


# --- SendCommandSurface: promote ---


def test_promote_accepted_when_config_arms_live():
    from minnarone.send_commands import SendCommandSurface

    policy = PublicSendPolicy(_live_config(), clock=FakeClock())
    surface = SendCommandSurface(policy)
    result = surface.promote()
    assert result.accepted is True
    assert "promote" in result.reason.lower()


def test_promote_rejected_when_mode_shadow():
    from minnarone.send_commands import SendCommandSurface

    policy = PublicSendPolicy(
        TwitchSendConfig(mode=TwitchSendMode.SHADOW), clock=FakeClock()
    )
    surface = SendCommandSurface(policy)
    result = surface.promote()
    assert result.accepted is False


def test_promote_rejected_when_mode_off():
    from minnarone.send_commands import SendCommandSurface

    policy = PublicSendPolicy(
        TwitchSendConfig(mode=TwitchSendMode.OFF), clock=FakeClock()
    )
    surface = SendCommandSurface(policy)
    result = surface.promote()
    assert result.accepted is False


# --- SendCommandSurface: kill-switch ---


def test_kill_switch_always_accepted():
    from minnarone.send_commands import SendCommandSurface

    policy = PublicSendPolicy(_live_config(), clock=FakeClock())
    surface = SendCommandSurface(policy)
    result = surface.kill_switch()
    assert result.accepted is True
    assert "kill" in result.reason.lower()


def test_kill_switch_engages_policy():
    from minnarone.send_commands import SendCommandSurface

    policy = PublicSendPolicy(_live_config(), clock=FakeClock())
    policy.promote()
    surface = SendCommandSurface(policy)
    surface.kill_switch()
    snap = policy.snapshot()
    assert snap.kill_switch is True
    assert snap.promoted is False


def test_promote_after_kill_switch_re_enables():
    from minnarone.send_commands import SendCommandSurface

    policy = PublicSendPolicy(_live_config(), clock=FakeClock())
    surface = SendCommandSurface(policy)
    surface.promote()
    surface.kill_switch()
    assert policy.snapshot().kill_switch is True
    result = surface.promote()
    assert result.accepted is True
    snap = policy.snapshot()
    assert snap.promoted is True
    assert snap.kill_switch is False


# --- Event recording ---


def test_promote_records_transition_event(tmp_path):
    from minnarone.run_events import RunEventRecorder
    from minnarone.send_commands import SendCommandSurface

    recorder = RunEventRecorder(tmp_path)
    policy = PublicSendPolicy(_live_config(), clock=FakeClock())
    surface = SendCommandSurface(policy, event_recorder=recorder)
    surface.promote()

    import json

    events = [
        json.loads(line)
        for line in recorder.path.read_text(encoding="utf-8").strip().split("\n")
    ]
    assert len(events) == 1
    ev = events[0]
    assert ev["kind"] == "send_transition"
    assert ev["send_transition"]["transition"] == "promote"
    assert ev["send_transition"]["actor"] == "operator"


def test_kill_switch_records_transition_event(tmp_path):
    from minnarone.run_events import RunEventRecorder
    from minnarone.send_commands import SendCommandSurface

    recorder = RunEventRecorder(tmp_path)
    policy = PublicSendPolicy(_live_config(), clock=FakeClock())
    surface = SendCommandSurface(policy, event_recorder=recorder)
    surface.kill_switch()

    import json

    events = [
        json.loads(line)
        for line in recorder.path.read_text(encoding="utf-8").strip().split("\n")
    ]
    assert len(events) == 1
    ev = events[0]
    assert ev["kind"] == "send_transition"
    assert ev["send_transition"]["transition"] == "kill_switch"
    assert ev["send_transition"]["actor"] == "operator"


def test_rejected_promote_does_not_record_event(tmp_path):
    from minnarone.run_events import RunEventRecorder
    from minnarone.send_commands import SendCommandSurface

    recorder = RunEventRecorder(tmp_path)
    policy = PublicSendPolicy(
        TwitchSendConfig(mode=TwitchSendMode.SHADOW), clock=FakeClock()
    )
    surface = SendCommandSurface(policy, event_recorder=recorder)
    surface.promote()

    assert not recorder.path.exists()


def test_surface_is_thread_safe():
    """The command surface uses a lock for thread safety."""
    from minnarone.send_commands import SendCommandSurface

    policy = PublicSendPolicy(_live_config(), clock=FakeClock())
    surface = SendCommandSurface(policy)
    assert isinstance(surface._lock, type(Lock()))
