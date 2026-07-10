"""Vista TUI (Textual) SOTTILE sopra lo snapshot puro di osservabilità.

Questa è la parte *dipendente* dello slice 10 e per design resta sottile: si
limita a rendere un `DashboardState` (vedi `dashboard.py`), che fa tutto il
lavoro di aggregazione in sola lettura. La logica testabile vive nello snapshot;
qui c'è solo la presentazione.

`textual` NON è una dipendenza obbligatoria del framework: importare `minnarone`
o il modello di snapshot non lo richiede. L'import di `textual` è **guardato** e
avviene SOLO quando si costruisce/avvia la vista. Se `textual` non è installato,
si solleva un errore chiaro e amichevole; il resto del pacchetto continua a
funzionare. Per installarlo: ``pip install "minnarone[tui]"``.
"""

from __future__ import annotations

from collections.abc import Callable

from .dashboard import DashboardState, snapshot

_MISSING_TEXTUAL_MSG = (
    "La dashboard TUI richiede 'textual', che non risulta installato.\n"
    "Installalo con:  pip install \"minnarone[tui]\"  "
    "(oppure: pip install textual).\n"
    "Nota: il modello di snapshot (minnarone.dashboard) funziona senza textual."
)

_DASHBOARD_CSS = """
Screen {
    background: #05080a;
    color: #d7e6e2;
}

#dashboard-grid {
    layout: grid;
    grid-size: 3 4;
    grid-rows: 1fr 1fr 1fr 1fr;
    grid-columns: 1fr 1fr 1fr;
    grid-gutter: 1 1;
    height: 1fr;
    padding: 0 1;
}

.dashboard-panel {
    border: solid #2f6f73;
    padding: 0 1;
    text-style: none;
}

.dashboard-panel-content {
    width: 1fr;
    height: auto;
    text-style: none;
}

#status-bar {
    height: 1;
    padding: 0 1;
    color: #d7e6e2;
    background: #102528;
}

#main-tabs {
    height: 1fr;
}

#prompt-view {
    height: 1fr;
    padding: 0 1;
    overflow-x: auto;
    overflow-y: auto;
}

#prompt-content {
    width: auto;
    text-wrap: nowrap;
}
"""


class DashboardSnapshotNotReady(RuntimeError):
    """Raised by live snapshot providers before the first cached state exists."""


def _require_textual():
    """Importa textual on-demand o solleva un errore chiaro se manca.

    L'import è dentro la funzione (non a livello di modulo) così importare
    questo modulo NON forza la presenza di textual: solo l'uso effettivo della
    vista lo richiede.
    """
    try:
        from textual.app import App, ComposeResult  # noqa: F401
        from textual.containers import Grid, VerticalScroll  # noqa: F401
        from textual.widgets import Header, Static, TabbedContent, TabPane  # noqa: F401
    except ImportError as exc:  # pragma: no cover - coperto via importorskip
        raise RuntimeError(_MISSING_TEXTUAL_MSG) from exc


# Panel titles that appear only when the corresponding profile is active.
# Compose creates widgets for all of them, but starts them hidden (display=False).
# _render_snapshot() shows/hides them based on the current DashboardState.
_CONDITIONAL_PANELS = {"SINTETIZZATORE", "SUGGERIMENTI"}

# All possible panel titles in visual order, including conditional ones.
_ALL_PANEL_TITLES = [
    "IDLE", "FINESTRA CHAT", "STREAMER", "CHAT", "EVENTI",
    "MINNARONE", "TRASCRIZIONE", "VIDEO", "MEMORIA",
    "SINTETIZZATORE", "SUGGERIMENTI",
]

_PROMOTE_CONFIRM_WINDOW = 3.0  # seconds to confirm a promote with second press


def build_dashboard_app(
    snapshot_provider: Callable[[], DashboardState],
    *,
    refresh_interval: float = 0.5,
    send_commands: object | None = None,
    speaker_commands: object | None = None,
):
    """Costruisce l'app Textual che rende lo snapshot, aggiornandolo a intervalli.

    `snapshot_provider` è una callable zero-arg che restituisce un
    `DashboardState` fresco (tipicamente ``lambda: snapshot(store=..., ...)``):
    la vista NON conosce le sorgenti vive, le legge solo attraverso lo snapshot,
    in sola lettura. `refresh_interval` regola ogni quanto la TUI ridisegna.

    `send_commands` is an optional ``SendCommandSurface`` for promote/kill-switch
    keybindings. When None the TUI stays fully read-only (no P/K keys).

    Solleva `RuntimeError` con un messaggio chiaro se `textual` non è presente.
    """
    _require_textual()

    import time as _time

    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Grid, VerticalScroll
    from textual.widgets import Header, Static, TabbedContent, TabPane

    class _DashboardApp(App):
        TITLE = "Minnarone — Observability"
        CSS = _DASHBOARD_CSS

        BINDINGS = [
            Binding("k", "kill_switch", "Kill-switch", show=send_commands is not None),
            Binding("p", "promote", "Promote", show=send_commands is not None),
            Binding(
                "s",
                "mark_streamer",
                "Marca streamer",
                show=speaker_commands is not None,
            ),
        ]

        def __init__(self) -> None:
            super().__init__()
            self._provider = snapshot_provider
            self._send_commands = send_commands
            self._speaker_commands = speaker_commands
            self._streamer_feedback: str | None = None
            self._panels: dict[str, Static] = {}
            self._panel_containers: dict[str, VerticalScroll] = {}
            self._status_bar: Static | None = None
            self._prompt_content: Static | None = None
            self._promote_pending_at: float | None = None

        @property
        def panel_titles(self) -> list[str]:
            return [panel.title for panel in DashboardState().render_panels()]

        def compose(self) -> ComposeResult:
            yield Header()
            self._status_bar = Static("(in attesa)", id="status-bar", markup=False)
            yield self._status_bar
            with TabbedContent(initial="dashboard-tab", id="main-tabs"):
                with TabPane("DASHBOARD", id="dashboard-tab"):
                    with Grid(id="dashboard-grid"):
                        for title in _ALL_PANEL_TITLES:
                            with VerticalScroll(
                                id=_panel_id(title),
                                classes="dashboard-panel",
                                can_focus=True,
                            ) as container:
                                container.border_title = title
                                # Conditional panels start hidden.
                                if title in _CONDITIONAL_PANELS:
                                    container.display = False
                                self._panel_containers[title] = container
                                content = Static(
                                    "(in attesa)",
                                    classes="dashboard-panel-content",
                                    markup=False,
                                )
                                self._panels[title] = content
                                yield content
                with TabPane("PROMPT", id="prompt-tab"):
                    with VerticalScroll(id="prompt-view", can_focus=True):
                        self._prompt_content = Static(
                            "(nessun prompt)",
                            id="prompt-content",
                            markup=False,
                        )
                        yield self._prompt_content

        def on_mount(self) -> None:
            self._render_snapshot()
            self.set_interval(refresh_interval, self._render_snapshot)

        # -- Keybinding actions -----------------------------------------------

        def action_kill_switch(self) -> None:
            """Kill-switch: instant, single press, no confirmation."""
            if self._send_commands is None:
                return
            kill = getattr(self._send_commands, "kill_switch", None)
            if callable(kill):
                kill()
            # Cancel any pending promote confirmation
            self._promote_pending_at = None

        def action_promote(self) -> None:
            """Promote: requires double-press within the confirm window."""
            if self._send_commands is None:
                return
            now = _time.monotonic()
            if (
                self._promote_pending_at is not None
                and (now - self._promote_pending_at) < _PROMOTE_CONFIRM_WINDOW
            ):
                # Second press within the window: confirm the promote
                self._promote_pending_at = None
                promote = getattr(self._send_commands, "promote", None)
                if callable(promote):
                    promote()
            else:
                # First press: enter pending-confirmation state
                self._promote_pending_at = now

        def action_mark_streamer(self) -> None:
            """Mark the current speaker as streamer: instant, single press.

            The only speaker-side mutation. Delegates to the speaker command
            surface (which pins the last utterance's cluster) and surfaces the
            accepted/rejected outcome in the status bar.
            """
            if self._speaker_commands is None:
                return
            mark = getattr(self._speaker_commands, "mark_current_streamer", None)
            if not callable(mark):
                return
            self._streamer_feedback = _mark_streamer_feedback(mark())
            # Re-render immediately so the operator sees the outcome now.
            self._render_snapshot()

        # -- Snapshot rendering -----------------------------------------------

        def _render_snapshot(self) -> None:
            try:
                state = self._provider()
                panels = state.render_panels()
            except DashboardSnapshotNotReady as exc:
                text = str(exc)
                if self._status_bar is not None:
                    self._status_bar.update(text)
                for panel in self._panels.values():
                    panel.update(text)
                if self._prompt_content is not None:
                    self._prompt_content.update(text)
                return
            if self._status_bar is not None:
                status_text = state.render_status_bar()
                if self._streamer_feedback:
                    status_text = f"{status_text} | {self._streamer_feedback}"
                self._status_bar.update(status_text)
            # Update panel content and toggle visibility for conditional panels.
            active_titles = {p.title for p in panels}
            for panel in panels:
                widget = self._panels.get(panel.title)
                if widget is not None:
                    widget.update(panel.text)
            for title in _CONDITIONAL_PANELS:
                container = self._panel_containers.get(title)
                if container is not None:
                    container.display = title in active_titles
            # Adapt grid rows to visible panel count.
            visible = sum(
                1 for t in _ALL_PANEL_TITLES
                if t not in _CONDITIONAL_PANELS or t in active_titles
            )
            rows = max((visible + 2) // 3, 1)
            try:
                grid = self.query_one("#dashboard-grid", Grid)
                grid.styles.grid_size_rows = rows
                grid.styles.grid_rows = "1fr " * rows
            except Exception:  # noqa: BLE001 - grid may not be mounted yet.
                pass
            if self._prompt_content is not None:
                self._prompt_content.update(state.render_prompt_view())

    return _DashboardApp()


def _panel_id(title: str) -> str:
    return f"panel-{title.lower().replace(' ', '-')}"


def _mark_streamer_feedback(result: object) -> str:
    """Format a mark-streamer outcome for the status bar."""
    if getattr(result, "accepted", False):
        cluster_id = getattr(result, "cluster_id", None)
        return f"streamer marcato (cluster {cluster_id})"
    reason = getattr(result, "reason", "") or "rifiutato"
    return f"marcatura streamer rifiutata: {reason}"


def run_dashboard(
    *,
    store=None,
    senser=None,
    reactor=None,
    refresh_interval: float = 0.5,
) -> None:  # pragma: no cover - richiede un terminale reale
    """Avvia la dashboard TUI live sulle sorgenti date (sola lettura).

    Comodità per l'operatore: assembla un `snapshot_provider` sulle sorgenti
    vive e fa partire l'app Textual. Richiede un terminale reale, quindi non è
    coperto dai test headless; la logica resa testabile è in `snapshot()` /
    `DashboardState.render_text()`.
    """

    def provider() -> DashboardState:
        return snapshot(store=store, senser=senser, reactor=reactor)

    app = build_dashboard_app(provider, refresh_interval=refresh_interval)
    app.run()
