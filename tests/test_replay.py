import json

from minnarone.perception import Perception, Source


def test_replay_loads_run_directory_into_dashboard_state(tmp_path):
    from minnarone.replay import load_replay_state

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    log = run_dir / "perceptions.jsonl"
    log.write_text(
        "\n".join(
            [
                Perception(
                    ts=1.0,
                    source=Source.CHAT,
                    type="msg",
                    text="ciao Minnarone",
                    speaker="alice",
                ).to_json(),
                Perception(
                    ts=2.0,
                    source=Source.AUDIO,
                    type="speech",
                    text="sto preparando il boss",
                    speaker="streamer",
                ).to_json(),
                Perception(
                    ts=3.0,
                    source=Source.VIDEO,
                    type="caption",
                    text="menu del gioco aperto",
                ).to_json(),
                Perception(
                    ts=4.0,
                    source=Source.EVENT,
                    type="reaction",
                    text="Bella run, chat.",
                    speaker="Minnarone",
                ).to_json(),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    state = load_replay_state(run_dir)

    panels = {panel.title: panel.text for panel in state.render_panels()}
    assert "ciao Minnarone" in panels["CHAT"]
    assert "sto preparando il boss" in panels["TRASCRIZIONE"]
    assert "menu del gioco aperto" in panels["VIDEO"]
    assert "reaction <- Minnarone" in panels["EVENTI"]
    assert "Bella run, chat." in panels["MINNARONE"]
    assert "alice: ciao Minnarone" in panels["MEMORIA"]


def test_replay_loads_direct_perception_jsonl_path(tmp_path):
    from minnarone.replay import load_replay_state

    log = tmp_path / "perceptions.jsonl"
    log.write_text(
        Perception(
            ts=10.0,
            source=Source.CHAT,
            type="msg",
            text="direct path works",
            speaker="bob",
        ).to_json()
        + "\n",
        encoding="utf-8",
    )

    state = load_replay_state(log)

    assert [p.text for p in state.chat_messages] == ["direct path works"]


def test_replay_redacts_secrets_from_saved_perceptions_before_rendering(tmp_path):
    from minnarone.replay import load_replay_state

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rows = [
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="OPENROUTER_API_KEY=sk-or-chat-secret",
            speaker="Authorization: Bearer chat-speaker-token",
        ),
        Perception(
            ts=2.0,
            source=Source.AUDIO,
            type="speech",
            text="oauth:audiosecret raw_audio=b'\\x00\\x01\\x02\\x03\\x04\\x05\\x06\\x07'",
            speaker="streamer",
        ),
        Perception(
            ts=3.0,
            source=Source.VIDEO,
            type="caption",
            text="frame=YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXo="
            + ("A" * 128),
        ),
    ]
    (run_dir / "perceptions.jsonl").write_text(
        "\n".join(row.to_json() for row in rows) + "\n",
        encoding="utf-8",
    )

    state = load_replay_state(run_dir)

    panels = "\n".join(panel.text for panel in state.render_panels())
    combined = f"{panels}\n{state.render_status_bar()}"
    assert "sk-or-chat-secret" not in combined
    assert "chat-speaker-token" not in combined
    assert "audiosecret" not in combined
    assert "\\x01\\x02" not in combined
    assert "YWJjZGVmZ2hp" not in combined
    assert "[redacted" in combined


def test_replay_loads_latest_prompt_capture_from_run_directory(tmp_path):
    from minnarone.replay import load_replay_state

    run_dir = tmp_path / "run"
    prompt_dir = run_dir / "debug" / "prompts"
    prompt_dir.mkdir(parents=True)
    (run_dir / "perceptions.jsonl").write_text("", encoding="utf-8")
    for index, prompt in enumerate(("old prompt", "latest prompt"), start=1):
        (prompt_dir / f"prompt-{index:06d}-20260629T10300{index}000000Z.json").write_text(
            json.dumps(
                {
                    "prompt": prompt,
                    "model": "openrouter/fake",
                    "status": "success",
                    "started_at": f"2026-06-29T10:30:0{index}Z",
                    "completed_at": f"2026-06-29T10:30:0{index}Z",
                    "context": "reactor:mention",
                    "token_metadata": {"prompt_tokens": index},
                    "cache_metadata": {"cached_tokens": index},
                    "cost": 0.001,
                }
            ),
            encoding="utf-8",
        )

    state = load_replay_state(run_dir)

    assert state.latest_prompt is not None
    assert state.latest_prompt.prompt == "latest prompt"
    rendered = state.render_prompt_view()
    assert "trigger=reactor:mention" in rendered
    assert "prompt_tokens=2" in rendered
    assert rendered.endswith("latest prompt")
    assert "prompt=present" in state.render_status_bar()


def test_replay_surfaces_newest_prompt_capture_failure_without_fallback(tmp_path):
    from minnarone.replay import load_replay_state

    run_dir = tmp_path / "run"
    prompt_dir = run_dir / "debug" / "prompts"
    prompt_dir.mkdir(parents=True)
    (run_dir / "perceptions.jsonl").write_text("", encoding="utf-8")
    (prompt_dir / "prompt-000001-20260629T103000000000Z.json").write_text(
        json.dumps(
            {
                "prompt": "old prompt",
                "model": "openrouter/fake",
                "status": "success",
                "started_at": "2026-06-29T10:30:00Z",
                "completed_at": "2026-06-29T10:30:00Z",
            }
        ),
        encoding="utf-8",
    )
    (prompt_dir / "prompt-000002-20260629T103001000000Z.json").write_text(
        "{not-json",
        encoding="utf-8",
    )

    state = load_replay_state(run_dir)

    assert state.latest_prompt is None
    assert state.render_prompt_view() == "(nessun prompt catturato)"
    assert any(
        failure.channel == "replay"
        and failure.stage == "prompt"
        and "malformed prompt capture" in failure.message
        for failure in state.failures
    )
    status = state.render_status_bar()
    assert "prompt=missing" in status
    assert "latest_failure=malformed prompt capture" in status


def test_replay_direct_jsonl_discovers_sibling_prompt_captures(tmp_path):
    from minnarone.replay import load_replay_state

    run_dir = tmp_path / "run"
    prompt_dir = run_dir / "debug" / "prompts"
    prompt_dir.mkdir(parents=True)
    log = run_dir / "perceptions.jsonl"
    log.write_text("", encoding="utf-8")
    (prompt_dir / "prompt-000001-20260629T103000000000Z.json").write_text(
        json.dumps(
            {
                "prompt": "direct prompt",
                "model": "openrouter/fake",
                "status": "success",
                "started_at": "2026-06-29T10:30:00Z",
                "completed_at": "2026-06-29T10:30:00Z",
            }
        ),
        encoding="utf-8",
    )

    state = load_replay_state(log)

    assert state.latest_prompt is not None
    assert state.latest_prompt.prompt == "direct prompt"


def test_replay_keeps_source_tails_independent_of_global_tail(tmp_path):
    from minnarone.replay import load_replay_state

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rows = [
        Perception(
            ts=1.0,
            source=Source.AUDIO,
            type="speech",
            text="audio outside global tail",
            speaker="streamer",
        ),
        Perception(
            ts=2.0,
            source=Source.VIDEO,
            type="caption",
            text="video outside global tail",
        ),
        Perception(
            ts=3.0,
            source=Source.CHAT,
            type="msg",
            text="chat 1",
            speaker="alice",
        ),
        Perception(
            ts=4.0,
            source=Source.CHAT,
            type="msg",
            text="chat 2",
            speaker="alice",
        ),
    ]
    (run_dir / "perceptions.jsonl").write_text(
        "\n".join(row.to_json() for row in rows) + "\n",
        encoding="utf-8",
    )

    state = load_replay_state(run_dir, recent_perceptions=2)

    assert [p.text for p in state.perceptions] == ["chat 1", "chat 2"]
    assert [p.text for p in state.audio_transcriptions] == [
        "audio outside global tail"
    ]
    assert [p.text for p in state.video_captions] == ["video outside global tail"]


def test_replay_surfaces_malformed_jsonl_rows_as_events(tmp_path):
    from minnarone.replay import load_replay_state

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "perceptions.jsonl").write_text(
        "\n".join(
            [
                "{not-json",
                json.dumps(
                    {
                        "ts": 1.0,
                        "source": "unknown",
                        "type": "msg",
                        "text": "bad source",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    state = load_replay_state(run_dir)

    event_text = {panel.title: panel.text for panel in state.render_panels()}["EVENTI"]
    assert "replay/jsonl" in event_text
    assert "malformed perception row" in event_text


def test_replay_status_identifies_offline_replay_source(tmp_path):
    from minnarone.replay import load_replay_state

    log = tmp_path / "perceptions.jsonl"
    log.write_text("", encoding="utf-8")

    state = load_replay_state(log)

    status = state.render_status_bar()
    assert "mode=replay offline" in status
    assert "offline" in status
    assert "perceptions.jsonl" in status
    assert "replayed chat=0 audio=0 video=0 events=0 minnarone=0" in status
    assert "prompt=missing" in status
    assert "health" not in status
    assert "llm=" not in status


def test_replay_loads_run_event_artifacts_into_events_and_minnarone(tmp_path):
    from minnarone.replay import load_replay_state

    run_dir = tmp_path / "run"
    debug_dir = run_dir / "debug"
    debug_dir.mkdir(parents=True)
    (run_dir / "perceptions.jsonl").write_text("", encoding="utf-8")
    (debug_dir / "events.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema": "minnarone.run_event.v1",
                        "sequence": 1,
                        "recorded_at": 1.0,
                        "kind": "trigger",
                        "trigger": {
                            "reason": "mention",
                            "kind": "mention",
                            "interlocutor": "alice",
                            "perception": {
                                "ts": 1.0,
                                "source": "chat",
                                "type": "msg",
                                "text": "ehi minnarone",
                                "speaker": "alice",
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "schema": "minnarone.run_event.v1",
                        "sequence": 2,
                        "recorded_at": 2.0,
                        "kind": "minnarone_output",
                        "output": {
                            "message": "ciao alice",
                            "mode": "public",
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    state = load_replay_state(run_dir)

    panels = {panel.title: panel.text for panel in state.render_panels()}
    assert "mention <- alice" in panels["EVENTI"]
    assert panels["MINNARONE"] == "ciao alice"
    assert "events=1 minnarone=1" in state.render_status_bar()


def test_run_event_artifacts_preserve_multiline_minnarone_output(tmp_path):
    from minnarone.output import OutputMode
    from minnarone.replay import load_replay_state
    from minnarone.run_events import RunEventRecorder

    run_dir = tmp_path / "run"
    debug_dir = run_dir / "debug"
    debug_dir.mkdir(parents=True)
    (run_dir / "perceptions.jsonl").write_text("", encoding="utf-8")
    long_line = "x" * 260
    recorder = RunEventRecorder(debug_dir)
    recorder.record_minnarone_output(
        (
            "prima riga\n"
            "[parentesi leggibili]\n"
            f"{long_line}\n"
            "OPENROUTER_API_KEY=sk-or-secret"
        ),
        OutputMode.PRIVATE,
    )

    state = load_replay_state(run_dir)

    [message] = state.messages
    assert "prima riga\n[parentesi leggibili]\n" in message
    assert long_line in message
    assert "sk-or-secret" not in message
    assert "OPENROUTER_API_KEY=[redacted-secret]" in message


def test_replay_redacts_secrets_from_legacy_run_event_artifacts(tmp_path):
    from minnarone.replay import load_replay_state

    run_dir = tmp_path / "run"
    debug_dir = run_dir / "debug"
    debug_dir.mkdir(parents=True)
    (run_dir / "perceptions.jsonl").write_text("", encoding="utf-8")
    (debug_dir / "events.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "kind": "trigger",
                        "trigger": {
                            "reason": "mention",
                            "kind": "mention",
                            "interlocutor": "Authorization: Bearer event-speaker",
                            "perception": {
                                "ts": 1.0,
                                "source": "chat",
                                "type": "msg",
                                "text": "oauth:eventtoken",
                                "speaker": "alice",
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "kind": "minnarone_output",
                        "output": {
                            "message": "OPENROUTER_API_KEY=sk-or-event-secret",
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    state = load_replay_state(run_dir)

    panels = "\n".join(panel.text for panel in state.render_panels())
    assert "event-speaker" not in panels
    assert "eventtoken" not in panels
    assert "sk-or-event-secret" not in panels
    assert "[redacted" in panels


def test_run_replay_tui_uses_static_dashboard_provider(tmp_path):
    from minnarone.replay import run_replay_tui

    log = tmp_path / "perceptions.jsonl"
    log.write_text(
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="static replay",
            speaker="alice",
        ).to_json()
        + "\n",
        encoding="utf-8",
    )
    rendered = []

    class FakeApp:
        def __init__(self, provider):
            self._provider = provider

        def run(self):
            first = self._provider()
            second = self._provider()
            rendered.append(first)
            assert second is first

    run_replay_tui(log, build_app=FakeApp)

    assert len(rendered) == 1
    assert [p.text for p in rendered[0].chat_messages] == ["static replay"]
