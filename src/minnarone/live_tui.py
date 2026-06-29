"""Launch path for the live observability TUI.

This module intentionally does not import Textual at module import time. The
guarded import remains behind explicit TUI preflight/app construction and is
only reached when the operator explicitly requests the TUI.
"""

from __future__ import annotations

import asyncio
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
    async def run(self) -> None:
        ...

    def observability_snapshot(self) -> object:
        ...


class _LiveTuiApp(Protocol):
    def run(self) -> object:
        ...


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
                    "snapshot osservabilità live non ancora disponibile"
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
            raise RuntimeError("runtime live non avviato entro il timeout")
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
                raise RuntimeError("runtime live non pronto per l'arresto")
            raise RuntimeError("runtime live non arrestato entro il timeout")

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
            raise RuntimeError("app TUI non espone un metodo exit utilizzabile")
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
    raise RuntimeError("app TUI non espone un metodo exit utilizzabile")


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
        raise ValueError(f"{field_name} deve essere > 0")
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


def run_live_tui(
    agent: _LiveAgent,
    *,
    build_app: Callable[[Callable[[], object]], _LiveTuiApp] | None = None,
    shutdown_timeout: float | None = None,
    startup_timeout: float = _DEFAULT_STARTUP_TIMEOUT,
    snapshot_interval: float = _DEFAULT_SNAPSHOT_INTERVAL,
) -> None:
    """Run the live agent in the background and the Textual app in foreground."""
    if build_app is None:
        ensure_live_tui_available()
        from .dashboard_tui import build_dashboard_app as build_app

    snapshots = _ObservabilitySnapshotBridge(agent.observability_snapshot)
    app = build_app(snapshots.provider)
    runtime = _BackgroundAgentRuntime(
        agent,
        snapshots=snapshots,
        snapshot_interval=snapshot_interval,
        request_shutdown=lambda: _request_app_shutdown(app),
    )
    resolved_shutdown_timeout = _shutdown_timeout_for(agent, shutdown_timeout)
    resolved_startup_timeout = _positive_timeout(startup_timeout, "startup_timeout")
    errors: list[BaseException] = []
    try:
        runtime.start(timeout=resolved_startup_timeout)
        app.run()
    except BaseException as exc:
        errors.append(exc)
    finally:
        try:
            runtime.stop(
                timeout=resolved_shutdown_timeout,
                ready_timeout=resolved_startup_timeout,
            )
        except BaseException as exc:
            errors.append(exc)
        try:
            runtime.raise_if_failed()
        except BaseException as exc:
            errors.append(exc)
    if errors:
        _raise_errors(errors)
