"""Tests for the mark-current-streamer TUI command and wiring (issue 03).

The keybinding is the TUI's only speaker-side mutation; the rest of the view
stays read-only. Wiring tests verify run_live_tui builds a SpeakerCommandSurface
when the agent exposes a marking-capable tagger, and none otherwise.
"""

import asyncio
from threading import Event

import pytest

from minnarone.dashboard import DashboardState


def _result(accepted: bool, reason: str, cluster_id: int | None = None):
    from minnarone.speaker_commands import MarkStreamerResult

    return MarkStreamerResult(accepted=accepted, reason=reason, cluster_id=cluster_id)


class _RecordingSurface:
    def __init__(self, result) -> None:
        self._result = result
        self.calls = 0

    def mark_current_streamer(self):
        self.calls += 1
        return self._result


# --- Keybinding (S): invokes the surface ---


def test_mark_streamer_key_invokes_surface():
    pytest.importorskip("textual")
    from minnarone.dashboard_tui import build_dashboard_app

    surface = _RecordingSurface(_result(True, "streamer marcato", 3))
    app = build_dashboard_app(lambda: DashboardState(), speaker_commands=surface)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.press("s")
            await pilot.pause()

    asyncio.run(exercise())
    assert surface.calls == 1


def test_mark_streamer_shows_feedback_in_status_bar():
    pytest.importorskip("textual")
    from minnarone.dashboard_tui import build_dashboard_app

    surface = _RecordingSurface(_result(True, "streamer marcato", 3))
    app = build_dashboard_app(lambda: DashboardState(), speaker_commands=surface)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.press("s")
            await pilot.pause()
            return str(app.query_one("#status-bar").content)

    status = asyncio.run(exercise())
    assert "streamer" in status.lower()


def test_mark_streamer_rejection_shows_reason():
    pytest.importorskip("textual")
    from minnarone.dashboard_tui import build_dashboard_app

    surface = _RecordingSurface(_result(False, "nessuna utterance da marcare"))
    app = build_dashboard_app(lambda: DashboardState(), speaker_commands=surface)

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.press("s")
            await pilot.pause()
            return str(app.query_one("#status-bar").content)

    status = asyncio.run(exercise())
    assert "utterance" in status.lower()


def test_tui_without_speaker_commands_ignores_key():
    pytest.importorskip("textual")
    from minnarone.dashboard_tui import build_dashboard_app

    app = build_dashboard_app(lambda: DashboardState())

    async def exercise():
        async with app.run_test() as pilot:
            await pilot.press("s")
            await pilot.pause()

    asyncio.run(exercise())  # must not crash


# --- run_live_tui wiring ---


def _fake_agent(*, speaker_diagnostics):
    class FakeAgent:
        send_policy = None

        def __init__(self) -> None:
            self.speaker_diagnostics = speaker_diagnostics
            self.started = Event()
            self.snapshot_ready = Event()

        async def run(self) -> None:
            self.started.set()
            try:
                while True:
                    await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                raise

        def observability_snapshot(self) -> str:
            self.snapshot_ready.set()
            return "dashboard-state"

    return FakeAgent()


def _run_and_capture(agent):
    from minnarone.live_tui import run_live_tui

    received = []

    class FakeApp:
        def __init__(self, provider) -> None:
            self._provider = provider

        def run(self) -> None:
            assert agent.started.wait(timeout=1.0)
            assert agent.snapshot_ready.wait(timeout=1.0)
            self._provider()

    def build_app(provider, *, send_commands=None, speaker_commands=None):
        received.append(speaker_commands)
        return FakeApp(provider)

    run_live_tui(agent, build_app=build_app)
    return received


def test_run_live_tui_wires_speaker_commands_when_tagger_supports_marking():
    class FakeTagger:
        def mark_current_speaker_as_streamer(self):
            return 1

    received = _run_and_capture(_fake_agent(speaker_diagnostics=FakeTagger()))
    assert len(received) == 1
    assert received[0] is not None
    assert hasattr(received[0], "mark_current_streamer")


def test_run_live_tui_no_speaker_commands_when_tagger_absent():
    received = _run_and_capture(_fake_agent(speaker_diagnostics=None))
    assert len(received) == 1
    assert received[0] is None


def test_run_live_tui_no_speaker_commands_when_tagger_cannot_mark():
    class DiagnosticsOnly:  # no marking capability (older/console tagger)
        pass

    received = _run_and_capture(_fake_agent(speaker_diagnostics=DiagnosticsOnly()))
    assert len(received) == 1
    assert received[0] is None
