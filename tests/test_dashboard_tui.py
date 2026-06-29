"""Test della vista TUI sottile (slice 10).

La vista ha un import di `textual` GUARDATO: importare il pacchetto o il modello
di snapshot non lo richiede; costruire la vista senza textual installato deve
fallire con un errore chiaro. Lo smoke test della resa è saltato se textual non
c'è (`importorskip`), così la suite resta verde anche offline.
"""

import asyncio
import sys

import pytest

from minnarone.dashboard import DashboardState
from minnarone.perception import Perception, Source
from minnarone.senser import ConversationWindow
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


def test_view_constructs_screenshot_dashboard_panels_with_fake_data():
    pytest.importorskip("textual")

    from minnarone.dashboard_tui import build_dashboard_app

    state = DashboardState(
        perceptions=[
            Perception(
                ts=1.0,
                source=Source.CHAT,
                type="msg",
                text="chat live separata",
                speaker="alice",
            ),
            Perception(
                ts=2.0,
                source=Source.AUDIO,
                type="speech",
                text="audio nel pannello",
                speaker="streamer",
            ),
            Perception(
                ts=3.0,
                source=Source.VIDEO,
                type="caption",
                text="video nel pannello",
            ),
        ],
        audio_transcriptions=[
            Perception(
                ts=2.0,
                source=Source.AUDIO,
                type="speech",
                text="audio nel pannello",
                speaker="streamer",
            )
        ],
        video_captions=[
            Perception(
                ts=3.0,
                source=Source.VIDEO,
                type="caption",
                text="video nel pannello",
            )
        ],
        windows={
            "alice": ConversationWindow("alice", opened_at=1.0, last_seen=1.0)
        },
        messages=["Minnarone osserva"],
        memory_summary="memoria fake",
        channel="minnarone",
    )
    app = build_dashboard_app(lambda: state)

    assert app.panel_titles == [
        "IDLE",
        "FINESTRA CHAT",
        "STREAMER",
        "CHAT",
        "EVENTI",
        "MINNARONE",
        "TRASCRIZIONE",
        "VIDEO",
        "MEMORIA",
    ]

    async def exercise_app():
        async with app.run_test(size=(100, 30)):
            widgets = list(app.query(".dashboard-panel"))
            content_widgets = list(app.query(".dashboard-panel-content"))
            assert [widget.border_title for widget in widgets] == app.panel_titles
            return {
                container.border_title: str(content.content)
                for container, content in zip(widgets, content_widgets, strict=True)
            }

    updates = asyncio.run(exercise_app())
    assert "alice aperta" in updates["FINESTRA CHAT"]
    assert "chat live separata" in updates["CHAT"]
    assert "audio nel pannello" in updates["TRASCRIZIONE"]
    assert "video nel pannello" in updates["VIDEO"]
    assert "Minnarone osserva" in updates["MINNARONE"]
    assert "memoria fake" in updates["MEMORIA"]


def test_view_renders_status_bar_from_snapshot():
    pytest.importorskip("textual")

    from minnarone.dashboard_tui import build_dashboard_app

    state = DashboardState(
        perceptions=[
            Perception(
                ts=1.0,
                source=Source.CHAT,
                type="msg",
                text="chat live",
                speaker="alice",
            )
        ],
        chat_messages=[
            Perception(
                ts=1.0,
                source=Source.CHAT,
                type="msg",
                text="chat live",
                speaker="alice",
            )
        ],
        channel="minnarone",
    )
    app = build_dashboard_app(lambda: state)

    async def exercise_app():
        async with app.run_test(size=(100, 30)):
            status = app.query_one("#status-bar")
            return str(status.content)

    status_text = asyncio.run(exercise_app())
    assert "channel=minnarone" in status_text
    assert "chat=ok" in status_text


def test_view_keeps_long_panel_content_bounded():
    pytest.importorskip("textual")

    from minnarone.dashboard_tui import build_dashboard_app

    long_line = "contenuto molto lungo " * 200
    state = DashboardState(
        perceptions=[
            Perception(
                ts=float(index),
                source=Source.CHAT,
                type="msg",
                text=f"{long_line} {index}",
                speaker="alice",
            )
            for index in range(20)
        ],
        messages=[long_line],
        memory_summary=long_line,
    )
    app = build_dashboard_app(lambda: state)

    async def exercise_app():
        async with app.run_test(size=(80, 24)):
            widgets = list(app.query(".dashboard-panel"))
            regions = [widget.region for widget in widgets]
            assert len(widgets) == 9
            assert len(set(regions)) == 9
            assert all(widget.can_focus for widget in widgets)
            assert all(widget.region.height > 0 for widget in widgets)
            assert any(widget.max_scroll_y > 0 for widget in widgets)

    asyncio.run(exercise_app())


def test_view_renders_bracketed_chat_as_plain_text():
    pytest.importorskip("textual")

    from minnarone.dashboard_tui import build_dashboard_app

    literal = "[red]literal chat tag[/]"
    state = DashboardState(
        perceptions=[
            Perception(
                ts=1.0,
                source=Source.CHAT,
                type="msg",
                text=literal,
                speaker="alice",
            )
        ]
    )
    app = build_dashboard_app(lambda: state)

    async def exercise_app():
        async with app.run_test(size=(80, 24)):
            content = app.query_one("#panel-chat .dashboard-panel-content")
            assert content._render_markup is False
            assert literal in str(content.content)

    asyncio.run(exercise_app())


def test_view_renders_snapshot_not_ready_placeholder():
    pytest.importorskip("textual")

    from minnarone.dashboard_tui import (
        DashboardSnapshotNotReady,
        build_dashboard_app,
    )

    app = build_dashboard_app(
        lambda: (_ for _ in ()).throw(DashboardSnapshotNotReady("non pronto"))
    )

    async def exercise_app():
        async with app.run_test(size=(80, 24)):
            contents = list(app.query(".dashboard-panel-content"))
            assert contents
            assert all(str(widget.content) == "non pronto" for widget in contents)

    asyncio.run(exercise_app())


def test_view_does_not_swallow_dashboard_runtime_errors():
    pytest.importorskip("textual")

    from minnarone.dashboard_tui import build_dashboard_app

    app = build_dashboard_app(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    async def exercise_app():
        with pytest.raises(RuntimeError, match="boom"):
            async with app.run_test(size=(80, 24)):
                pass

    asyncio.run(exercise_app())
