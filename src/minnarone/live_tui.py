"""Launch path for the live observability TUI.

This module intentionally does not import Textual at module import time. The
guarded import remains behind explicit TUI preflight/app construction and is
only reached when the operator explicitly requests the TUI.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from threading import Event, Lock, Thread
from typing import Protocol

from .dashboard_tui import DashboardSnapshotNotReady

_DEFAULT_SHUTDOWN_TIMEOUT = 5.0
_DEFAULT_STARTUP_TIMEOUT = 5.0
_DEFAULT_SNAPSHOT_INTERVAL = 0.5
_UNSET = object()


class LiveTuiDependencyError(RuntimeError):
    """Raised when the optional live TUI dependency set is unavailable."""


class _LiveAgent(Protocol):
    async def run(self) -> None: ...

    def observability_snapshot(self) -> object: ...


class _LiveTuiApp(Protocol):
    def run(self) -> object: ...


class _ObservabilitySnapshotBridge:
    """Thread-safe handoff from the live runtime loop to the foreground TUI."""

    def __init__(self, snapshot_factory: Callable[[], object]) -> None:
        self._snapshot_factory = snapshot_factory
        self._lock = Lock()
        self._ready = Event()
        self._snapshot: object = _UNSET
        self._fatal: BaseException | None = None

    def publish(self) -> None:
        snapshot = self._snapshot_factory()
        with self._lock:
            self._snapshot = snapshot
            self._ready.set()

    def fail(self, error: BaseException) -> None:
        with self._lock:
            self._fatal = error

    async def publish_forever(self, *, interval: float) -> None:
        while True:
            self.publish()
            await asyncio.sleep(interval)

    def provider(self) -> object:
        with self._lock:
            if self._fatal is not None:
                raise self._fatal
            if self._snapshot is _UNSET:
                raise DashboardSnapshotNotReady(
                    "live observability snapshot is not yet available"
                )
            return self._snapshot


class _BackgroundAgentRuntime:
    """Runs ``agent.run()`` on a private event loop in a background thread."""

    def __init__(
        self,
        agent: _LiveAgent,
        *,
        snapshots: _ObservabilitySnapshotBridge,
        snapshot_interval: float = _DEFAULT_SNAPSHOT_INTERVAL,
        request_shutdown: Callable[[], object] | None = None,
    ) -> None:
        self._agent = agent
        self._snapshots = snapshots
        self._snapshot_interval = snapshot_interval
        self._request_shutdown = request_shutdown
        self._ready = Event()
        self._thread = Thread(
            target=self._run,
            name="minnarone-live-agent",
            daemon=True,
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_future: asyncio.Future[None] | None = None
        self._stop_requested = Event()
        self._error: BaseException | None = None

    def start(self, *, timeout: float = _DEFAULT_STARTUP_TIMEOUT) -> None:
        self._thread.start()
        if not self._ready.wait(timeout=timeout):
            self._stop_requested.set()
            self._request_stop_from_thread()
            self._thread.join(timeout=timeout)
            raise RuntimeError("live runtime did not start before the timeout")
        self.raise_if_failed()

    def stop(
        self,
        *,
        timeout: float,
        ready_timeout: float = _DEFAULT_STARTUP_TIMEOUT,
    ) -> None:
        ready = self._ready.wait(timeout=ready_timeout)
        self._stop_requested.set()
        self._request_stop_from_thread()
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            if not ready:
                raise RuntimeError("live runtime is not ready to stop")
            raise RuntimeError("live runtime did not stop before the timeout")

    def raise_if_failed(self) -> None:
        if self._error is None:
            return
        error = self._error
        self._error = None
        raise error

    def _run(self) -> None:
        try:
            asyncio.run(self._run_until_stopped())
        except asyncio.CancelledError as exc:
            if not self._stop_requested.is_set():
                self._set_error(exc)
        except BaseException as exc:
            self._set_error(exc)
        finally:
            self._ready.set()
            if not self._stop_requested.is_set() and self._request_shutdown is not None:
                try:
                    self._request_shutdown()
                except BaseException as exc:
                    self._set_error(exc)

    async def _run_until_stopped(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop_future = self._loop.create_future()
        agent_task = asyncio.create_task(self._agent.run())
        snapshot_task = asyncio.create_task(
            self._snapshots.publish_forever(interval=self._snapshot_interval)
        )
        self._ready.set()

        done, pending = await asyncio.wait(
            {agent_task, snapshot_task, self._stop_future},
            return_when=asyncio.FIRST_COMPLETED,
        )

        errors = _unexpected_task_exceptions(agent_task, snapshot_task)
        for task in pending:
            task.cancel()
        if pending:
            results = await asyncio.gather(*pending, return_exceptions=True)
            errors.extend(_unexpected_results(results))
        if errors:
            _raise_errors(errors)

        if self._stop_future in done:
            return

        for task in (agent_task, snapshot_task):
            if task in done:
                await task

    def _request_stop(self) -> None:
        if self._stop_future is not None and not self._stop_future.done():
            self._stop_future.set_result(None)

    def _request_stop_from_thread(self) -> None:
        loop = self._loop
        if self._thread.is_alive() and loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(self._request_stop)

    def _set_error(self, error: BaseException) -> None:
        self._error = _combine_errors(self._error, error)
        self._snapshots.fail(self._error)


def _request_app_shutdown(app: object) -> None:
    exit_app = getattr(app, "exit", None)
    call_from_thread = getattr(app, "call_from_thread", None)
    errors: list[BaseException] = []
    if callable(call_from_thread):
        if not callable(exit_app):
            raise RuntimeError("TUI app does not expose a usable exit method")
        try:
            call_from_thread(exit_app)
            return
        except Exception as exc:  # noqa: BLE001 - surfaced as runtime failure.
            errors.append(exc)
            _raise_errors(errors)
    if callable(exit_app):
        try:
            exit_app()
            return
        except Exception as exc:  # noqa: BLE001 - surfaced as runtime failure.
            errors.append(exc)
    if errors:
        _raise_errors(errors)
    raise RuntimeError("TUI app does not expose a usable exit method")


def _unexpected_task_exceptions(
    *tasks: asyncio.Task[object],
) -> list[BaseException]:
    errors: list[BaseException] = []
    for task in tasks:
        if not task.done() or task.cancelled():
            continue
        exc = task.exception()
        if exc is not None:
            errors.append(exc)
    return errors


def _unexpected_results(results: list[object]) -> list[BaseException]:
    errors: list[BaseException] = []
    for result in results:
        if result is None or isinstance(result, asyncio.CancelledError):
            continue
        if isinstance(result, BaseException):
            errors.append(result)
    return errors


def _raise_errors(errors: list[BaseException]) -> None:
    if len(errors) == 1:
        raise errors[0]
    raise BaseExceptionGroup("live TUI runtime failures", errors)


def _combine_errors(
    current: BaseException | None,
    new: BaseException,
) -> BaseException:
    if current is None:
        return new
    if isinstance(current, BaseExceptionGroup):
        return BaseExceptionGroup(
            "live TUI runtime failures",
            [*current.exceptions, new],
        )
    return BaseExceptionGroup("live TUI runtime failures", [current, new])


def _positive_timeout(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{field_name} must be > 0")
    return float(value)


def _shutdown_timeout_for(agent: _LiveAgent, explicit: float | None) -> float:
    if explicit is not None:
        return _positive_timeout(explicit, "shutdown_timeout")

    config = getattr(agent, "config", None)
    configured = getattr(config, "perception_shutdown_timeout", None)
    if isinstance(configured, (int, float)) and not isinstance(configured, bool):
        return max(_DEFAULT_SHUTDOWN_TIMEOUT, float(configured) * 4.0)
    return _DEFAULT_SHUTDOWN_TIMEOUT


def ensure_live_tui_available() -> None:
    """Validate optional dependencies needed by the default live TUI."""
    try:
        from .dashboard_tui import _require_textual

        _require_textual()
    except RuntimeError as exc:
        raise LiveTuiDependencyError(str(exc)) from exc


def _call_build_app(
    build_app: Callable[..., _LiveTuiApp],
    provider: Callable[[], object],
    send_commands: object | None,
    speaker_commands: object | None,
) -> _LiveTuiApp:
    """Call build_app, passing the command surfaces the factory accepts.

    Existing callers (including tests) may have build_app factories that do not
    accept the ``send_commands`` and/or ``speaker_commands`` keywords. We inspect
    the factory signature and pass only the keywords it declares, then call it
    exactly once. Introspection (rather than a TypeError-cascade) means a genuine
    TypeError raised inside build_app's body surfaces instead of being swallowed
    and silently retried at lower arity.
    """
    try:
        params = inspect.signature(build_app).parameters
    except (TypeError, ValueError):
        # Builtins / C factories may not be introspectable; call as-is.
        return build_app(provider)
    accepts_var_keyword = any(
        param.kind is inspect.Parameter.VAR_KEYWORD for param in params.values()
    )
    kwargs: dict[str, object | None] = {}
    for name, value in (
        ("send_commands", send_commands),
        ("speaker_commands", speaker_commands),
    ):
        if accepts_var_keyword or name in params:
            kwargs[name] = value
    return build_app(provider, **kwargs)


def _build_send_commands(agent: _LiveAgent) -> object | None:
    """Build a SendCommandSurface if the agent exposes a send_policy.

    The surface is the TUI's narrow mutation channel: promote and kill-switch.
    When no send_policy is present (console runtime, mode off/shadow), the TUI
    stays fully read-only.
    """
    send_policy = getattr(agent, "send_policy", None)
    if send_policy is None:
        return None
    from .send_commands import SendCommandSurface

    # Try to find the event recorder for transition audit logging.
    event_recorder = None
    run_session = getattr(agent, "run_session", None)
    if run_session is not None:
        debug_dir = getattr(run_session, "debug_dir", None)
        if debug_dir is not None:
            from .run_events import RunEventRecorder

            event_recorder = RunEventRecorder(debug_dir)
    return SendCommandSurface(send_policy, event_recorder=event_recorder)


def _build_speaker_commands(agent: _LiveAgent) -> object | None:
    """Build a SpeakerCommandSurface if the agent exposes a marking-capable tagger.

    The surface is the TUI's speaker-side mutation channel: mark current
    streamer. When no marking-capable speaker tagger is present (console
    runtime, or an audio-less config), the TUI stays read-only on the speaker
    side.
    """
    tagger = getattr(agent, "speaker_diagnostics", None)
    if tagger is None:
        return None
    if not hasattr(tagger, "mark_current_speaker_as_streamer"):
        return None
    from .speaker_commands import SpeakerCommandSurface

    event_recorder = None
    run_session = getattr(agent, "run_session", None)
    if run_session is not None:
        debug_dir = getattr(run_session, "debug_dir", None)
        if debug_dir is not None:
            from .run_events import RunEventRecorder

            event_recorder = RunEventRecorder(debug_dir)
    return SpeakerCommandSurface(tagger, event_recorder=event_recorder)


def run_live_tui(
    agent: _LiveAgent,
    *,
    build_app: Callable[[Callable[[], object]], _LiveTuiApp] | None = None,
    shutdown_timeout: float | None = None,
    startup_timeout: float = _DEFAULT_STARTUP_TIMEOUT,
    snapshot_interval: float = _DEFAULT_SNAPSHOT_INTERVAL,
) -> None:
    """Run the live agent in the background and the Textual app in foreground."""
    run_session = getattr(agent, "run_session", None)
    runtime: _BackgroundAgentRuntime | None = None
    runtime_stopped = False
    errors: list[BaseException] = []
    try:
        if build_app is None:
            ensure_live_tui_available()
            from .dashboard_tui import build_dashboard_app as build_app

        resolved_shutdown_timeout = _shutdown_timeout_for(agent, shutdown_timeout)
        resolved_startup_timeout = _positive_timeout(
            startup_timeout,
            "startup_timeout",
        )
        snapshots = _ObservabilitySnapshotBridge(agent.observability_snapshot)
        send_commands = _build_send_commands(agent)
        speaker_commands = _build_speaker_commands(agent)
        app = _call_build_app(
            build_app, snapshots.provider, send_commands, speaker_commands
        )
        runtime = _BackgroundAgentRuntime(
            agent,
            snapshots=snapshots,
            snapshot_interval=snapshot_interval,
            request_shutdown=lambda: _request_app_shutdown(app),
        )
        runtime.start(timeout=resolved_startup_timeout)
        app.run()
    except BaseException as exc:
        errors.append(exc)
    finally:
        if runtime is not None:
            try:
                runtime.stop(
                    timeout=resolved_shutdown_timeout,
                    ready_timeout=resolved_startup_timeout,
                )
            except BaseException as exc:
                errors.append(exc)
            else:
                runtime_stopped = True
            try:
                runtime.raise_if_failed()
            except BaseException as exc:
                errors.append(exc)
        if run_session is not None and (runtime_stopped or runtime is None):
            try:
                run_session.mark_completed()
            except BaseException as exc:  # noqa: BLE001 - preserve cleanup failures.
                errors.append(exc)
    if errors:
        _raise_errors(errors)
