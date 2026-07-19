"""Test della vista TUI sottile (slice 10).

La vista ha un import di `textual` GUARDATO: importare il pacchetto o il modello
di snapshot non lo richiede; costruire la vista senza textual installato deve
fallire con un errore chiaro. Lo smoke test della resa è saltato se textual non
c'è (`importorskip`), così la suite resta verde anche offline.
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta

import pytest

from minnarone.dashboard import DashboardState
from minnarone.perception import Perception, Source
from minnarone.prompt_observation import PromptObservation
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

    assert str(excinfo.value) == (
        "The TUI dashboard requires 'textual', which is not installed.\n"
        'Install it with:  pip install "minnarone[tui]"  '
        "(or: pip install textual).\n"
        "Note: the snapshot model (minnarone.dashboard) works without textual."
    )


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
        windows={"alice": ConversationWindow("alice", opened_at=1.0, last_seen=1.0)},
        messages=["Minnarone osserva"],
        memory_summary="memoria fake",
        channel="minnarone",
    )
    app = build_dashboard_app(lambda: state)

    assert app.panel_titles == [
        "IDLE",
        "CHAT WINDOW",
        "STREAMER",
        "CHAT",
        "EVENTS",
        "MINNARONE",
        "TRANSCRIPTION",
        "VIDEO",
        "MEMORY",
    ]

    async def exercise_app():
        async with app.run_test(size=(100, 30)):
            widgets = [w for w in app.query(".dashboard-panel") if w.display]
            content_widgets = [
                w
                for w in app.query(".dashboard-panel-content")
                if w.parent is not None and w.parent.display
            ]
            assert [widget.border_title for widget in widgets] == app.panel_titles
            return {
                container.border_title: str(content.content)
                for container, content in zip(widgets, content_widgets, strict=True)
            }

    updates = asyncio.run(exercise_app())
    assert "alice open since" in updates["CHAT WINDOW"]
    assert "chat live separata" in updates["CHAT"]
    assert "audio nel pannello" in updates["TRANSCRIPTION"]
    assert "video nel pannello" in updates["VIDEO"]
    assert "Minnarone osserva" in updates["MINNARONE"]
    assert "memoria fake" in updates["MEMORY"]


def test_view_has_separate_prompt_tab():
    textual_widgets = pytest.importorskip("textual.widgets")
    TabbedContent = textual_widgets.TabbedContent

    from minnarone.dashboard_tui import build_dashboard_app

    app = build_dashboard_app(lambda: DashboardState())

    async def exercise_app():
        async with app.run_test(size=(100, 30)):
            tabbed = app.query_one("#main-tabs", TabbedContent)
            assert tabbed.active == "dashboard-tab"
            assert app.query_one("#dashboard-grid") is not None
            assert app.query_one("#prompt-view") is not None

    asyncio.run(exercise_app())


def test_prompt_tab_renders_latest_prompt_and_metadata():
    textual_widgets = pytest.importorskip("textual.widgets")
    TabbedContent = textual_widgets.TabbedContent

    from minnarone.dashboard_tui import build_dashboard_app

    started = datetime(2026, 6, 29, 10, 30, tzinfo=UTC)
    prompt = (
        "## IDENTITA\n"
        "Sono Minnarone.\n"
        "\n"
        "## FATTI\n"
        "- token=[redacted-secret]\n"
        "\n"
        "## SITUAZIONE\n"
        "Reagisci a questo messaggio."
    )
    state = DashboardState(
        latest_prompt=PromptObservation(
            prompt=prompt,
            model="openrouter/fake-model",
            status="success",
            started_at=started,
            completed_at=started + timedelta(milliseconds=42),
            context="reactor:mention",
            token_metadata={"prompt_tokens": 123, "completion_tokens": 7},
            cache_metadata={"cached_tokens": 80, "cache_write_tokens": 20},
            cost=0.0007,
        )
    )
    app = build_dashboard_app(lambda: state)

    async def exercise_app():
        async with app.run_test(size=(120, 40)):
            app.query_one("#main-tabs", TabbedContent).active = "prompt-tab"
            content = app.query_one("#prompt-content")
            return str(content.content)

    rendered = asyncio.run(exercise_app())

    assert "trigger=reactor:mention" in rendered
    assert "status=success" in rendered
    assert "model=openrouter/fake-model" in rendered
    assert "prompt_tokens=123" in rendered
    assert "completion_tokens=7" in rendered
    assert "cached_tokens=80" in rendered
    assert "cache_write_tokens=20" in rendered
    assert "cost=0.0007" in rendered
    assert rendered.endswith(prompt)
    assert "token=[redacted-secret]" in rendered


def test_prompt_tab_adds_no_runtime_mutating_controls():
    textual_widgets = pytest.importorskip("textual.widgets")
    Button = textual_widgets.Button
    Input = textual_widgets.Input
    Select = textual_widgets.Select
    Switch = textual_widgets.Switch
    TabbedContent = textual_widgets.TabbedContent

    from minnarone.dashboard_tui import build_dashboard_app

    app = build_dashboard_app(lambda: DashboardState())

    async def exercise_app():
        async with app.run_test(size=(100, 30)):
            app.query_one("#main-tabs", TabbedContent).active = "prompt-tab"
            prompt_view = app.query_one("#prompt-view")
            assert list(prompt_view.query(Button)) == []
            assert list(prompt_view.query(Input)) == []
            assert list(prompt_view.query(Select)) == []
            assert list(prompt_view.query(Switch)) == []

    asyncio.run(exercise_app())


def test_prompt_tab_css_preserves_line_boundaries_with_horizontal_scroll():
    from minnarone import dashboard_tui

    assert "#prompt-view" in dashboard_tui._DASHBOARD_CSS
    assert "overflow-x: auto;" in dashboard_tui._DASHBOARD_CSS
    assert "#prompt-content" in dashboard_tui._DASHBOARD_CSS
    assert "width: auto;" in dashboard_tui._DASHBOARD_CSS
    assert "text-wrap: nowrap;" in dashboard_tui._DASHBOARD_CSS


def test_prompt_tab_long_lines_are_horizontally_scrollable():
    textual_widgets = pytest.importorskip("textual.widgets")
    TabbedContent = textual_widgets.TabbedContent

    from minnarone.dashboard_tui import build_dashboard_app

    started = datetime(2026, 6, 29, 10, 30, tzinfo=UTC)
    state = DashboardState(
        latest_prompt=PromptObservation(
            prompt="A" * 300,
            model="fake",
            status="success",
            started_at=started,
            completed_at=started,
        )
    )
    app = build_dashboard_app(lambda: state)

    async def exercise_app():
        async with app.run_test(size=(80, 24)) as pilot:
            app.query_one("#main-tabs", TabbedContent).active = "prompt-tab"
            await pilot.pause()
            prompt_view = app.query_one("#prompt-view")
            prompt_content = app.query_one("#prompt-content")

            assert prompt_content.styles.text_wrap == "nowrap"
            assert prompt_content.region.width > prompt_view.region.width
            assert prompt_view.max_scroll_x > 0

    asyncio.run(exercise_app())


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
            widgets = [w for w in app.query(".dashboard-panel") if w.display]
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
        lambda: (_ for _ in ()).throw(DashboardSnapshotNotReady("not ready"))
    )

    async def exercise_app():
        async with app.run_test(size=(80, 24)):
            contents = list(app.query(".dashboard-panel-content"))
            assert contents
            assert all(str(widget.content) == "not ready" for widget in contents)

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


def test_mark_streamer_feedback_uses_english_copy():
    from minnarone.dashboard_tui import _mark_streamer_feedback

    accepted = type("Result", (), {"accepted": True, "cluster_id": 7})()
    rejected = type("Result", (), {"accepted": False, "reason": "no speech"})()

    assert _mark_streamer_feedback(accepted) == "streamer marked (cluster 7)"
    assert _mark_streamer_feedback(rejected) == ("streamer marking rejected: no speech")


# --- Per-profile TUI panels (issue 13) ----------------------------------------


def test_tui_shows_sintetizzatore_panel_when_active():
    """SINTETIZZATORE panel appears in the TUI when synthesizer has messages."""
    pytest.importorskip("textual")

    from minnarone.dashboard_tui import build_dashboard_app

    state = DashboardState(
        synthesizer_messages=["Sintesi della riunione."],
    )
    app = build_dashboard_app(lambda: state)

    async def exercise_app():
        async with app.run_test(size=(100, 40)):
            visible = [w for w in app.query(".dashboard-panel") if w.display]
            titles = [w.border_title for w in visible]
            assert "SYNTHESIZER" in titles
            # Content should show the message.
            content = app.query_one("#panel-synthesizer .dashboard-panel-content")
            return str(content.content)

    rendered = asyncio.run(exercise_app())
    assert "Sintesi della riunione." in rendered


def test_tui_shows_suggerimenti_panel_when_active():
    """SUGGERIMENTI panel appears in the TUI when suggester has messages."""
    pytest.importorskip("textual")

    from minnarone.dashboard_tui import build_dashboard_app

    state = DashboardState(
        suggester_messages=["Suggerimento tattico."],
    )
    app = build_dashboard_app(lambda: state)

    async def exercise_app():
        async with app.run_test(size=(100, 40)):
            visible = [w for w in app.query(".dashboard-panel") if w.display]
            titles = [w.border_title for w in visible]
            assert "SUGGESTIONS" in titles
            content = app.query_one("#panel-suggestions .dashboard-panel-content")
            return str(content.content)

    rendered = asyncio.run(exercise_app())
    assert "Suggerimento tattico." in rendered


def test_tui_hides_conditional_panels_when_inactive():
    """SINTETIZZATORE and SUGGERIMENTI are hidden when no messages."""
    pytest.importorskip("textual")

    from minnarone.dashboard_tui import build_dashboard_app

    state = DashboardState()
    app = build_dashboard_app(lambda: state)

    async def exercise_app():
        async with app.run_test(size=(100, 30)):
            visible = [w for w in app.query(".dashboard-panel") if w.display]
            titles = [w.border_title for w in visible]
            return titles

    titles = asyncio.run(exercise_app())
    assert "SYNTHESIZER" not in titles
    assert "SUGGESTIONS" not in titles
    # Base panels are present.
    assert "MINNARONE" in titles
    assert "MEMORY" in titles


def test_tui_grid_adapts_to_panel_count():
    """Grid rows increase when conditional panels become active."""
    pytest.importorskip("textual")

    from minnarone.dashboard_tui import build_dashboard_app

    state = DashboardState(
        synthesizer_messages=["Sintesi."],
        suggester_messages=["Suggerimento."],
    )
    app = build_dashboard_app(lambda: state)

    async def exercise_app():
        async with app.run_test(size=(100, 50)):
            visible = [w for w in app.query(".dashboard-panel") if w.display]
            return len(visible)

    visible_count = asyncio.run(exercise_app())
    # 9 base + 2 conditional = 11 visible panels
    assert visible_count == 11
