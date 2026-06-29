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
        from textual.widgets import Footer, Header, Static  # noqa: F401
    except ImportError as exc:  # pragma: no cover - coperto via importorskip
        raise RuntimeError(_MISSING_TEXTUAL_MSG) from exc


def build_dashboard_app(
    snapshot_provider: Callable[[], DashboardState],
    *,
    refresh_interval: float = 0.5,
):
    """Costruisce l'app Textual che rende lo snapshot, aggiornandolo a intervalli.

    `snapshot_provider` è una callable zero-arg che restituisce un
    `DashboardState` fresco (tipicamente ``lambda: snapshot(store=..., ...)``):
    la vista NON conosce le sorgenti vive, le legge solo attraverso lo snapshot,
    in sola lettura. `refresh_interval` regola ogni quanto la TUI ridisegna.

    Solleva `RuntimeError` con un messaggio chiaro se `textual` non è presente.
    """
    _require_textual()

    from textual.app import App, ComposeResult
    from textual.widgets import Footer, Header, Static

    class _DashboardApp(App):
        TITLE = "Minnarone — Observability"

        def __init__(self) -> None:
            super().__init__()
            self._provider = snapshot_provider
            self._body: Static | None = None

        def compose(self) -> ComposeResult:
            yield Header()
            self._body = Static(id="snapshot")
            yield self._body
            yield Footer()

        def on_mount(self) -> None:
            self._render_snapshot()
            self.set_interval(refresh_interval, self._render_snapshot)

        def _render_snapshot(self) -> None:
            try:
                state = self._provider()
                text = state.render_text()
            except DashboardSnapshotNotReady as exc:
                text = str(exc)
            if self._body is not None:
                self._body.update(text)

    return _DashboardApp()


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
