import asyncio
import time
from threading import Event, current_thread
from types import SimpleNamespace

import pytest

from minnarone.live_tui import run_live_tui


class _FakeLiveAgent:
    def __init__(self) -> None:
        self.started = Event()
        self.cancelled = Event()
        self.finished = Event()
        self.snapshot_calls = 0
        self.snapshot_ready = Event()
        self.snapshot_threads: list[str] = []

    async def run(self) -> None:
        self.started.set()
        try:
            while True:
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        finally:
            self.finished.set()

    def observability_snapshot(self) -> str:
        self.snapshot_calls += 1
        self.snapshot_threads.append(current_thread().name)
        state = f"dashboard-state-{self.snapshot_calls}"
        self.snapshot_ready.set()
        return state


def test_run_live_tui_runs_agent_in_background_and_stops_on_app_exit():
    agent = _FakeLiveAgent()
    rendered = []

    class FakeApp:
        def __init__(self, provider):
            self._provider = provider

        def run(self) -> None:
            assert agent.started.wait(timeout=1.0)
            assert agent.snapshot_ready.wait(timeout=1.0)
            rendered.append(self._provider())

    def build_app(provider):
        return FakeApp(provider)

    run_live_tui(agent, build_app=build_app)

    assert rendered == ["dashboard-state-1"]
    assert agent.snapshot_calls == 1
    assert agent.cancelled.wait(timeout=1.0)
    assert agent.finished.wait(timeout=1.0)


def test_run_live_tui_reads_cached_snapshot_from_foreground_thread():
    agent = _FakeLiveAgent()
    rendered = []

    class FakeApp:
        def __init__(self, provider):
            self._provider = provider

        def run(self) -> None:
            assert agent.started.wait(timeout=1.0)
            assert agent.snapshot_ready.wait(timeout=1.0)
            calls_before_render = agent.snapshot_calls
            rendered.append(self._provider())
            rendered.append(self._provider())
            assert agent.snapshot_calls == calls_before_render

    def build_app(provider):
        return FakeApp(provider)

    run_live_tui(agent, build_app=build_app, snapshot_interval=60.0)

    assert rendered == ["dashboard-state-1", "dashboard-state-1"]
    assert agent.snapshot_threads == ["minnarone-live-agent"]


def test_run_live_tui_shutdowns_app_and_reraises_background_failure():
    app_running = Event()
    shutdown_requested = Event()

    class BrokenAgent:
        def __init__(self) -> None:
            self.started = Event()
            self.snapshot_ready = Event()

        async def run(self) -> None:
            self.started.set()
            while not app_running.is_set():
                await asyncio.sleep(0.01)
            raise RuntimeError("runtime exploded")

        def observability_snapshot(self) -> str:
            self.snapshot_ready.set()
            return "dashboard-state"

    agent = BrokenAgent()
    apps = []

    class FakeApp:
        def __init__(self, provider):
            self._provider = provider
            self.call_from_thread_callbacks = []

        def run(self) -> None:
            assert agent.started.wait(timeout=1.0)
            assert agent.snapshot_ready.wait(timeout=1.0)
            assert self._provider() == "dashboard-state"
            app_running.set()
            assert shutdown_requested.wait(timeout=1.0)

        def call_from_thread(self, callback) -> None:
            self.call_from_thread_callbacks.append(callback)
            callback()

        def exit(self) -> None:
            shutdown_requested.set()

    def build_app(provider):
        app = FakeApp(provider)
        apps.append(app)
        return app

    with pytest.raises(RuntimeError, match="runtime exploded"):
        run_live_tui(agent, build_app=build_app)

    assert shutdown_requested.is_set()
    assert apps[0].call_from_thread_callbacks == [apps[0].exit]


def test_run_live_tui_finalizes_async_generators_on_stop():
    generator_finalized = Event()

    async def unclosed_stream():
        try:
            yield "first"
            while True:
                await asyncio.sleep(0.01)
        finally:
            generator_finalized.set()

    class CleanupAgent:
        def __init__(self) -> None:
            self.started = Event()
            self.snapshot_ready = Event()

        async def run(self) -> None:
            stream = unclosed_stream()
            await anext(stream)
            self.started.set()
            while True:
                await asyncio.sleep(0.01)

        def observability_snapshot(self) -> str:
            self.snapshot_ready.set()
            return "dashboard-state"

    agent = CleanupAgent()

    class FakeApp:
        def __init__(self, provider):
            self._provider = provider

        def run(self) -> None:
            assert agent.started.wait(timeout=1.0)
            assert agent.snapshot_ready.wait(timeout=1.0)
            assert self._provider() == "dashboard-state"

    def build_app(provider):
        return FakeApp(provider)

    run_live_tui(agent, build_app=build_app)

    assert generator_finalized.wait(timeout=1.0)


def test_run_live_tui_reraises_agent_cleanup_failure_on_app_exit():
    class FailingCleanupAgent:
        def __init__(self) -> None:
            self.started = Event()
            self.snapshot_ready = Event()

        async def run(self) -> None:
            self.started.set()
            try:
                while True:
                    await asyncio.sleep(0.01)
            except asyncio.CancelledError as exc:
                raise RuntimeError("cleanup exploded") from exc

        def observability_snapshot(self) -> str:
            self.snapshot_ready.set()
            return "dashboard-state"

    agent = FailingCleanupAgent()

    class FakeApp:
        def __init__(self, provider):
            self._provider = provider

        def run(self) -> None:
            assert agent.started.wait(timeout=1.0)
            assert agent.snapshot_ready.wait(timeout=1.0)
            assert self._provider() == "dashboard-state"

    def build_app(provider):
        return FakeApp(provider)

    with pytest.raises(RuntimeError, match="cleanup exploded"):
        run_live_tui(agent, build_app=build_app)


def test_run_live_tui_bounds_agent_that_stalls_during_cleanup():
    class SlowCleanupAgent:
        def __init__(self) -> None:
            self.started = Event()
            self.finished = Event()
            self.snapshot_ready = Event()

        async def run(self) -> None:
            self.started.set()
            try:
                while True:
                    await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                await asyncio.sleep(0.2)
                raise
            finally:
                self.finished.set()

        def observability_snapshot(self) -> str:
            self.snapshot_ready.set()
            return "dashboard-state"

    agent = SlowCleanupAgent()

    class FakeApp:
        def __init__(self, provider):
            self._provider = provider

        def run(self) -> None:
            assert agent.started.wait(timeout=1.0)
            assert agent.snapshot_ready.wait(timeout=1.0)
            assert self._provider() == "dashboard-state"

    def build_app(provider):
        return FakeApp(provider)

    started_at = time.monotonic()
    with pytest.raises(RuntimeError, match="runtime live non arrestato"):
        run_live_tui(agent, build_app=build_app, shutdown_timeout=0.01)

    assert time.monotonic() - started_at < 0.15
    assert agent.finished.wait(timeout=1.0)


def test_run_live_tui_uses_configured_cleanup_budget_when_timeout_is_implicit():
    class ConfiguredCleanupAgent(_FakeLiveAgent):
        config = SimpleNamespace(perception_shutdown_timeout=0.01)

    agent = ConfiguredCleanupAgent()
    observed_elapsed = []

    class FakeApp:
        def __init__(self, provider):
            self._provider = provider

        def run(self) -> None:
            assert agent.started.wait(timeout=1.0)
            assert agent.snapshot_ready.wait(timeout=1.0)
            assert self._provider() == "dashboard-state-1"

    def build_app(provider):
        return FakeApp(provider)

    started_at = time.monotonic()
    run_live_tui(agent, build_app=build_app)
    observed_elapsed.append(time.monotonic() - started_at)

    assert observed_elapsed[0] < 1.0


def test_run_live_tui_startup_is_not_gated_by_initial_snapshot():
    release_snapshot = Event()
    app_started = Event()

    class SlowStartupAgent:
        async def run(self) -> None:
            while True:
                await asyncio.sleep(0.01)

        def observability_snapshot(self) -> str:
            release_snapshot.wait(timeout=1.0)
            return "dashboard-state"

    class FakeApp:
        def __init__(self, provider):
            self._provider = provider

        def run(self) -> None:
            app_started.set()
            release_snapshot.set()

    def build_app(provider):
        return FakeApp(provider)

    started_at = time.monotonic()
    run_live_tui(
        SlowStartupAgent(),
        build_app=build_app,
        startup_timeout=0.01,
        shutdown_timeout=1.0,
    )

    assert time.monotonic() - started_at < 0.2
    assert app_started.is_set()


def test_run_live_tui_surfaces_app_shutdown_request_failure():
    app_running = Event()
    snapshot_ready = Event()
    provider_failed = Event()

    class BrokenAgent:
        async def run(self) -> None:
            while not app_running.is_set():
                await asyncio.sleep(0.01)
            raise RuntimeError("runtime exploded")

        def observability_snapshot(self) -> str:
            snapshot_ready.set()
            return "dashboard-state"

    class FakeApp:
        def __init__(self, provider):
            self._provider = provider

        def run(self) -> None:
            assert snapshot_ready.wait(timeout=1.0)
            assert self._provider() == "dashboard-state"
            app_running.set()
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                try:
                    self._provider()
                except BaseException:
                    provider_failed.set()
                    return
                time.sleep(0.01)
            raise AssertionError("provider never exposed runtime failure")

        def call_from_thread(self, callback) -> None:
            raise RuntimeError("call_from_thread rejected")

        def exit(self) -> None:
            raise RuntimeError("exit rejected")

    def build_app(provider):
        return FakeApp(provider)

    with pytest.raises(BaseExceptionGroup) as exc_info:
        run_live_tui(BrokenAgent(), build_app=build_app)

    assert provider_failed.is_set()
    assert "live TUI runtime failures" in str(exc_info.value)
    assert any(
        "runtime exploded" in str(error)
        for error in exc_info.value.exceptions
    )
    assert any(
        "call_from_thread rejected" in str(error)
        for error in exc_info.value.exceptions
    )


def test_run_live_tui_does_not_call_textual_exit_directly_after_thread_hop_failure():
    app_running = Event()
    snapshot_ready = Event()
    direct_exit_called = Event()

    class BrokenAgent:
        async def run(self) -> None:
            while not app_running.is_set():
                await asyncio.sleep(0.01)
            raise RuntimeError("runtime exploded")

        def observability_snapshot(self) -> str:
            snapshot_ready.set()
            return "dashboard-state"

    class FakeTextualApp:
        def __init__(self, provider):
            self._provider = provider

        def run(self) -> None:
            assert snapshot_ready.wait(timeout=1.0)
            assert self._provider() == "dashboard-state"
            app_running.set()
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                try:
                    self._provider()
                except BaseException:
                    return
                time.sleep(0.01)
            raise AssertionError("provider never exposed runtime failure")

        def call_from_thread(self, callback) -> None:
            del callback
            raise RuntimeError("thread hop failed")

        def exit(self) -> None:
            direct_exit_called.set()

    def build_app(provider):
        return FakeTextualApp(provider)

    with pytest.raises(BaseExceptionGroup):
        run_live_tui(BrokenAgent(), build_app=build_app)

    assert not direct_exit_called.is_set()


def test_run_live_tui_invalid_startup_timeout_fails_before_thread_start():
    class Agent:
        async def run(self) -> None:
            raise AssertionError("agent should not start")

        def observability_snapshot(self) -> str:
            return "dashboard-state"

    class FakeApp:
        def __init__(self, provider):
            self._provider = provider

        def run(self) -> None:
            raise AssertionError("app should not start")

    def build_app(provider):
        return FakeApp(provider)

    with pytest.raises(ValueError, match="startup_timeout"):
        run_live_tui(Agent(), build_app=build_app, startup_timeout=0)
