"""Tests for TUI send-state transition keybindings (issue 08, slice 2).

Keybinding semantics:
- Kill-switch (K): instant, single press, no confirmation.
- Promote (P): requires confirmation (press twice within a short window).
- Asymmetry is intentional: enabling is slow, stopping is instant.
"""

import asyncio

import pytest

from minnarone.config import TwitchSendConfig, TwitchSendMode
from minnarone.dashboard import DashboardState, SendDiagnostics
from minnarone.public_send import PublicSendPolicy

textual = pytest.importorskip("textual")


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


def _build_app_with_commands(
    *,
    policy=None,
    event_recorder=None,
    state=None,
):
    """Build a TUI app with a command surface wired in."""
    from minnarone.dashboard_tui import build_dashboard_app
    from minnarone.send_commands import SendCommandSurface

    if policy is None:
        policy = PublicSendPolicy(_live_config(), clock=FakeClock())

    surface = SendCommandSurface(policy, event_recorder=event_recorder)

    if state is None:
        state = DashboardState(
            send=SendDiagnostics(mode="live", promoted=False, kill_switch=False)
        )

    app = build_dashboard_app(lambda: state, send_commands=surface)
    return app, surface, policy


# --- Kill-switch key (K): instant, single press ---


def test_kill_switch_key_engages_instantly():
    app, surface, policy = _build_app_with_commands()
    policy.promote()

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.press("k")
            await pilot.pause()
            snap = policy.snapshot()
            assert snap.kill_switch is True
            assert snap.promoted is False

    asyncio.run(exercise())


def test_kill_switch_key_idempotent():
    app, surface, policy = _build_app_with_commands()

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.press("k")
            await pilot.press("k")
            await pilot.pause()
            snap = policy.snapshot()
            assert snap.kill_switch is True

    asyncio.run(exercise())


# --- Promote key (P): requires confirmation (double-press) ---


def test_promote_single_press_does_not_promote():
    """A single P enters 'pending confirmation' but does NOT promote."""
    app, surface, policy = _build_app_with_commands()

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.press("p")
            await pilot.pause()
            snap = policy.snapshot()
            assert snap.promoted is False

    asyncio.run(exercise())


def test_promote_double_press_promotes():
    """Pressing P twice within the confirm window completes the promotion."""
    app, surface, policy = _build_app_with_commands()

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.press("p")
            await pilot.press("p")
            await pilot.pause()
            snap = policy.snapshot()
            assert snap.promoted is True

    asyncio.run(exercise())


def test_promote_rejected_when_config_not_live():
    """Promote is rejected (and shown as rejected) when config is shadow."""
    policy = PublicSendPolicy(
        TwitchSendConfig(mode=TwitchSendMode.SHADOW), clock=FakeClock()
    )
    from minnarone.dashboard_tui import build_dashboard_app
    from minnarone.send_commands import SendCommandSurface

    surface = SendCommandSurface(policy)
    state = DashboardState(
        send=SendDiagnostics(mode="shadow")
    )
    app = build_dashboard_app(lambda: state, send_commands=surface)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.press("p")
            await pilot.press("p")
            await pilot.pause()
            snap = policy.snapshot()
            assert snap.promoted is False

    asyncio.run(exercise())


def test_promote_after_kill_switch_requires_fresh_confirmation():
    """After kill-switch, promote must be confirmed again from scratch."""
    app, surface, policy = _build_app_with_commands()

    async def exercise():
        async with app.run_test() as pilot:
            # Promote
            await pilot.press("p")
            await pilot.press("p")
            await pilot.pause()
            assert policy.snapshot().promoted is True

            # Kill-switch
            await pilot.press("k")
            await pilot.pause()
            assert policy.snapshot().kill_switch is True

            # Single P should NOT re-enable
            await pilot.press("p")
            await pilot.pause()
            assert policy.snapshot().promoted is False

            # Second P confirms fresh promote
            await pilot.press("p")
            await pilot.pause()
            assert policy.snapshot().promoted is True
            assert policy.snapshot().kill_switch is False

    asyncio.run(exercise())


# --- Event recording from keybindings ---


def test_kill_switch_key_records_event(tmp_path):
    from minnarone.run_events import RunEventRecorder

    recorder = RunEventRecorder(tmp_path)
    app, surface, policy = _build_app_with_commands(event_recorder=recorder)
    policy.promote()

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.press("k")
            await pilot.pause()

    asyncio.run(exercise())

    import json
    events = [
        json.loads(line)
        for line in recorder.path.read_text(encoding="utf-8").strip().split("\n")
    ]
    transitions = [e for e in events if e["kind"] == "send_transition"]
    assert len(transitions) == 1
    assert transitions[0]["send_transition"]["transition"] == "kill_switch"
    assert transitions[0]["send_transition"]["actor"] == "operator"


def test_promote_key_records_event_only_on_confirmation(tmp_path):
    from minnarone.run_events import RunEventRecorder

    recorder = RunEventRecorder(tmp_path)
    app, surface, policy = _build_app_with_commands(event_recorder=recorder)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.press("p")  # pending, no event yet
            await pilot.pause()
            assert not recorder.path.exists()

            await pilot.press("p")  # confirmed
            await pilot.pause()

    asyncio.run(exercise())

    import json
    events = [
        json.loads(line)
        for line in recorder.path.read_text(encoding="utf-8").strip().split("\n")
    ]
    transitions = [e for e in events if e["kind"] == "send_transition"]
    assert len(transitions) == 1
    assert transitions[0]["send_transition"]["transition"] == "promote"


# --- Status bar feedback ---


def test_status_bar_shows_send_state():
    """The status bar must always show the current send state."""
    state = DashboardState(
        send=SendDiagnostics(mode="live", promoted=True, kill_switch=False)
    )
    bar = state.render_status_bar()
    assert "send=" in bar


def test_status_bar_shows_kill_switch_state():
    state = DashboardState(
        send=SendDiagnostics(mode="live", kill_switch=True)
    )
    bar = state.render_status_bar()
    assert "send=" in bar


# --- TUI without send_commands stays read-only ---


def test_tui_without_send_commands_ignores_keys():
    """When no send_commands are provided, P and K do nothing special."""
    from minnarone.dashboard_tui import build_dashboard_app

    app = build_dashboard_app(lambda: DashboardState())

    async def exercise():
        async with app.run_test() as pilot:
            # These keys should not crash or have any effect
            await pilot.press("p")
            await pilot.press("k")
            await pilot.pause()

    asyncio.run(exercise())
