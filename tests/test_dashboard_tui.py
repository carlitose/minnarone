"""Test della vista TUI sottile (slice 10).

La vista ha un import di `textual` GUARDATO: importare il pacchetto o il modello
di snapshot non lo richiede; costruire la vista senza textual installato deve
fallire con un errore chiaro. Lo smoke test della resa è saltato se textual non
c'è (`importorskip`), così la suite resta verde anche offline.
"""

import sys

import pytest

from minnarone.perception import Perception, Source
from minnarone.store import PerceptionStore


def _store(tmp_path):
    return PerceptionStore(tmp_path / "perceptions.jsonl")


def test_importing_package_does_not_require_textual():
    # Né il pacchetto né il modello di snapshot devono trascinare textual.
    for name in list(sys.modules):
        if name == "textual" or name.startswith("textual."):
            del sys.modules[name]
    had_textual = "textual" in sys.modules
    import minnarone  # noqa: F401
    import minnarone.dashboard  # noqa: F401
    from minnarone.dashboard import DashboardState, snapshot

    assert ("textual" in sys.modules) is had_textual
    # Lo snapshot funziona senza textual.
    assert isinstance(snapshot(), DashboardState)


def test_building_view_without_textual_raises_clear_error(monkeypatch):
    # Simula l'assenza di textual: l'import deve fallire con un messaggio chiaro.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "textual" or name.startswith("textual."):
            raise ImportError("No module named 'textual'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    from minnarone.dashboard import DashboardState
    from minnarone.dashboard_tui import build_dashboard_app

    with pytest.raises(RuntimeError) as excinfo:
        build_dashboard_app(lambda: DashboardState())

    assert "textual" in str(excinfo.value).lower()


def test_view_renders_snapshot_smoke(tmp_path):
    # Skippato quando textual non è installato (resa live in terminale reale).
    pytest.importorskip("textual")

    from minnarone.dashboard import snapshot
    from minnarone.dashboard_tui import build_dashboard_app

    store = _store(tmp_path)
    store.append(
        Perception(ts=1.0, source=Source.CHAT, type="msg", text="ciao", speaker="alice")
    )
    app = build_dashboard_app(lambda: snapshot(store=store))
    # Costruzione senza crash è già il cuore dello smoke headless.
    assert app is not None
