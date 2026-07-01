"""Test dell'entrypoint CLI (slice 11): `python -m minnarone <config>`.

Si verifica che un config valido costruisca l'agente (dry-run, senza avviare il
loop bloccante né toccare rete/device) e che un config invalido dia un errore
chiaro con exit code != 0.
"""

import builtins
import textwrap

import minnarone.cli as cli
from minnarone.cli import main
from minnarone.config import ConfigError
from minnarone.twitch_stream import TwitchStreamRuntimeError


def _valid_config(tmp_path):
    soul = tmp_path / "soul.md"
    soul.write_text("io", encoding="utf-8")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        textwrap.dedent(
            f"""
            mode: public
            soul_path: {soul}
            facts_dir: {facts_dir}
            adapter: os_capture
            llm_provider: grok
            agent_name: minnarone
            os_capture:
              audio: false
              video: true
            """
        ),
        encoding="utf-8",
    )
    return cfg


def test_cli_check_builds_valid_config(tmp_path, capsys):
    cfg = _valid_config(tmp_path)
    code = main([str(cfg), "--check"])
    assert code == 0
    out = capsys.readouterr().out
    assert "ok" in out.lower() or "minnarone" in out.lower()


def test_cli_check_does_not_load_vlm_for_twitch_video_config(tmp_path, capsys):
    soul = tmp_path / "soul.md"
    soul.write_text("io", encoding="utf-8")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        textwrap.dedent(
            f"""
            mode: public
            soul_path: {soul}
            facts_dir: {facts_dir}
            adapter: twitch
            llm_provider: grok
            agent_name: minnarone
            twitch:
              channel: minnarone
              chat: false
              audio: false
              video: true
            vlm:
              model: null
            """
        ),
        encoding="utf-8",
    )

    code = main([str(cfg), "--check"])

    assert code == 0
    assert "ok" in capsys.readouterr().out.lower()


def test_cli_invalid_config_returns_nonzero(tmp_path, capsys):
    code = main([str(tmp_path / "missing.yaml"), "--check"])
    assert code != 0
    err = capsys.readouterr().err
    assert "config" in err.lower() or "non trovato" in err.lower()


def test_cli_invalid_mode_clear_error(tmp_path, capsys):
    soul = tmp_path / "soul.md"
    soul.write_text("io", encoding="utf-8")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        textwrap.dedent(
            f"""
            mode: telepathic
            soul_path: {soul}
            facts_dir: {facts_dir}
            adapter: os_capture
            llm_provider: grok
            """
        ),
        encoding="utf-8",
    )
    code = main([str(cfg), "--check"])
    assert code != 0
    err = capsys.readouterr().err
    assert "mode" in err.lower()


def test_cli_runtime_twitch_error_returns_nonzero(tmp_path, capsys, monkeypatch):
    class BrokenAgent:
        async def run(self):
            raise TwitchStreamRuntimeError("Login authentication failed")

    monkeypatch.setattr(cli, "build_agent", lambda _config: BrokenAgent())

    code = main([str(_valid_config(tmp_path))])

    assert code == 1
    err = capsys.readouterr().err
    assert "runtime Twitch" in err
    assert "Login authentication failed" in err


def test_cli_tui_launches_tui_branch(tmp_path, monkeypatch):
    class FakeAgent:
        async def run(self):
            raise AssertionError("normal live run should not be used for --tui")

    launched = []

    def fake_build_agent(_config, **_kwargs):
        return FakeAgent()

    def fake_run_live_tui(agent):
        launched.append(agent)

    monkeypatch.setattr(cli, "build_agent", fake_build_agent)
    monkeypatch.setattr(cli, "ensure_live_tui_available", lambda: None)
    monkeypatch.setattr(cli, "run_live_tui", fake_run_live_tui, raising=False)

    code = main([str(_valid_config(tmp_path)), "--tui"])

    assert code == 0
    assert len(launched) == 1
    assert isinstance(launched[0], FakeAgent)


def test_cli_tui_builds_agent_with_run_local_artifacts(tmp_path, monkeypatch):
    class FakeAgent:
        pass

    captured = {}

    def fake_build_agent(_config, **kwargs):
        captured.update(kwargs)
        return FakeAgent()

    monkeypatch.setattr(cli, "build_agent", fake_build_agent)
    monkeypatch.setattr(cli, "ensure_live_tui_available", lambda: None)
    monkeypatch.setattr(cli, "run_live_tui", lambda _agent: None, raising=False)

    code = main([str(_valid_config(tmp_path)), "--tui"])

    assert code == 0
    session = captured["run_session"]
    assert session.run_dir.is_dir()
    assert session.run_dir.parent == tmp_path / ".local" / "minnarone" / "runs"
    assert session.perception_log_path == session.run_dir / "perceptions.jsonl"


def test_cli_tui_builds_agent_with_minnarone_output_stream(tmp_path, monkeypatch):
    from minnarone.output_sink import MinnaroneOutputStream

    class FakeAgent:
        pass

    captured = {}

    def fake_build_agent(_config, **kwargs):
        captured.update(kwargs)
        return FakeAgent()

    monkeypatch.setattr(cli, "build_agent", fake_build_agent)
    monkeypatch.setattr(cli, "ensure_live_tui_available", lambda: None)
    monkeypatch.setattr(cli, "run_live_tui", lambda _agent: None, raising=False)

    code = main([str(_valid_config(tmp_path)), "--tui"])

    assert code == 0
    assert isinstance(captured["minnarone_output"], MinnaroneOutputStream)


def test_cli_tui_marks_run_completed_when_agent_build_fails(
    tmp_path, capsys, monkeypatch
):
    captured = {}

    def fake_build_agent(_config, **kwargs):
        captured.update(kwargs)
        raise ConfigError("build failed")

    monkeypatch.setattr(cli, "build_agent", fake_build_agent)
    monkeypatch.setattr(cli, "ensure_live_tui_available", lambda: None)

    code = main([str(_valid_config(tmp_path)), "--tui"])

    assert code == 2
    assert "build failed" in capsys.readouterr().err
    session = captured["run_session"]
    assert (session.run_dir / ".minnarone-run").read_text(
        encoding="utf-8"
    ).endswith(":completed\n")


def test_cli_tui_runtime_twitch_error_returns_nonzero(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli, "build_agent", lambda _config, **_kwargs: object())
    monkeypatch.setattr(cli, "ensure_live_tui_available", lambda: None)

    def broken_tui(_agent):
        raise TwitchStreamRuntimeError("Login authentication failed")

    monkeypatch.setattr(cli, "run_live_tui", broken_tui)

    code = main([str(_valid_config(tmp_path)), "--tui"])

    assert code == 1
    err = capsys.readouterr().err
    assert "runtime Twitch" in err
    assert "Login authentication failed" in err


def test_cli_tui_missing_textual_returns_clear_error_before_build(
    tmp_path, capsys, monkeypatch
):
    built = []

    class FakeAgent:
        async def run(self):
            raise AssertionError("agent should not run without textual")

        def observability_snapshot(self):
            return "dashboard-state"

    def fake_build_agent(_config):
        built.append(True)
        return FakeAgent()

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "textual" or name.startswith("textual."):
            raise ImportError("No module named 'textual'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(cli, "build_agent", fake_build_agent)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    code = main([str(_valid_config(tmp_path)), "--tui"])

    assert code == 1
    assert built == []
    err = capsys.readouterr().err
    assert "textual" in err.lower()
    assert "minnarone[tui]" in err


def test_cli_replay_launches_without_config_or_live_agent(tmp_path, monkeypatch):
    log = tmp_path / "perceptions.jsonl"
    log.write_text("", encoding="utf-8")
    launched = []

    def forbidden_build_agent(*_args, **_kwargs):
        raise AssertionError("replay must not build a live agent")

    def forbidden_config_load(*_args, **_kwargs):
        raise AssertionError("replay must not load live config")

    monkeypatch.setattr(cli, "build_agent", forbidden_build_agent)
    monkeypatch.setattr(cli.Config, "load", forbidden_config_load)
    monkeypatch.setattr(cli, "ensure_live_tui_available", lambda: None)
    monkeypatch.setattr(cli, "run_replay_tui", lambda path: launched.append(path))

    code = main(["--replay", str(log)])

    assert code == 0
    assert launched == [str(log)]
