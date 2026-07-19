"""Test dell'entrypoint CLI (slice 11): `python -m minnarone <config>`.

Si verifica che un config valido costruisca l'agente (dry-run, senza avviare il
loop bloccante né toccare rete/device) e che un config invalido dia un errore
chiaro con exit code != 0.
"""

import builtins
import os
import textwrap

import minnarone.cli as cli
from minnarone.cli import load_dotenv_file, main
from minnarone.config import ConfigError
from minnarone.twitch_auth import TwitchTokenValidationError
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


def test_cli_token_validation_error_returns_nonzero_without_traceback(
    tmp_path, capsys, monkeypatch
):
    class BrokenAgent:
        async def run(self):
            raise TwitchTokenValidationError(
                "read token Twitch: account o scope non validi"
            )

    monkeypatch.setattr(cli, "build_agent", lambda _config: BrokenAgent())

    code = main([str(_valid_config(tmp_path))])

    assert code == 1
    err = capsys.readouterr().err
    assert "credenziali Twitch" in err
    assert "account o scope non validi" in err
    assert "Traceback" not in err


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
    assert (
        (session.run_dir / ".minnarone-run")
        .read_text(encoding="utf-8")
        .endswith(":completed\n")
    )


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


def _twitch_send_config(tmp_path, send_block: str):
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
              send:
            """
        )
        + textwrap.indent(textwrap.dedent(send_block), "    "),
        encoding="utf-8",
    )
    return cfg


def test_cli_check_fails_for_live_send_without_write_token(
    tmp_path, capsys, monkeypatch
):
    # cwd isolata: la CLI ricarica `.env` dalla cwd, quindi un `.env` locale
    # dell'operatore (con TWITCH_SEND_OAUTH_TOKEN) vanificherebbe il delenv.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:read-token")
    monkeypatch.delenv("TWITCH_SEND_OAUTH_TOKEN", raising=False)
    cfg = _twitch_send_config(
        tmp_path,
        """
        mode: live
        allowed_channels: ["minnarone"]
        """,
    )

    code = main([str(cfg), "--check"])

    assert code == 2
    err = capsys.readouterr().err
    assert "errore di config" in err
    assert "TWITCH_SEND_OAUTH_TOKEN" in err


def test_cli_check_fails_for_live_send_without_read_token(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("TWITCH_SEND_OAUTH_TOKEN", "oauth:send-token")
    cfg = _twitch_send_config(
        tmp_path,
        """
        mode: live
        allowed_channels: ["minnarone"]
        """,
    )

    code = main([str(cfg), "--check"])

    assert code == 2
    assert "TWITCH_OAUTH_TOKEN" in capsys.readouterr().err


def test_cli_check_passes_for_shadow_send_without_write_token(
    tmp_path, capsys, monkeypatch
):
    # cwd isolata: vedi il test live qui sopra.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TWITCH_SEND_OAUTH_TOKEN", raising=False)
    cfg = _twitch_send_config(
        tmp_path,
        """
        mode: shadow
        """,
    )

    code = main([str(cfg), "--check"])

    assert code == 0
    assert "ok" in capsys.readouterr().out.lower()


# --- .env loader (comodità operatore) --------------------------------------


def test_load_dotenv_file_sets_keys(tmp_path, monkeypatch):
    for key in ("DOTENV_A", "DOTENV_B", "DOTENV_C", "DOTENV_D"):
        monkeypatch.delenv(key, raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "# commento\n"
        "\n"
        "DOTENV_A=uno\n"
        "export DOTENV_B=due\n"
        'DOTENV_C="tre con spazi"\n'
        "DOTENV_D='oauth:xyz'\n",
        encoding="utf-8",
    )

    loaded = load_dotenv_file(env)

    assert set(loaded) == {"DOTENV_A", "DOTENV_B", "DOTENV_C", "DOTENV_D"}
    assert os.environ["DOTENV_A"] == "uno"
    assert os.environ["DOTENV_B"] == "due"
    assert os.environ["DOTENV_C"] == "tre con spazi"
    assert os.environ["DOTENV_D"] == "oauth:xyz"


def test_load_dotenv_file_does_not_override_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("DOTENV_EXISTING", "dal-terminale")
    env = tmp_path / ".env"
    env.write_text("DOTENV_EXISTING=dal-file\n", encoding="utf-8")

    loaded = load_dotenv_file(env)

    assert "DOTENV_EXISTING" not in loaded
    assert os.environ["DOTENV_EXISTING"] == "dal-terminale"


def test_load_dotenv_file_missing_is_noop(tmp_path):
    assert load_dotenv_file(tmp_path / "assente.env") == []


def test_load_dotenv_file_ignores_malformed(tmp_path, monkeypatch):
    monkeypatch.delenv("DOTENV_OK", raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "senza uguale\n=valore-senza-chiave\nCHIAVE CON SPAZI=x\nDOTENV_OK=bene\n",
        encoding="utf-8",
    )

    loaded = load_dotenv_file(env)

    assert loaded == ["DOTENV_OK"]
    assert os.environ["DOTENV_OK"] == "bene"


def _twitch_chat_config(tmp_path):
    soul = tmp_path / "soul.md"
    soul.write_text("io", encoding="utf-8")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        textwrap.dedent(
            f"""
            mode: private
            soul_path: {soul}
            facts_dir: {facts_dir}
            adapter: twitch
            llm_provider: grok
            agent_name: minnarone
            twitch:
              channel: minnarone
              chat: true
              audio: false
              video: false
            """
        ),
        encoding="utf-8",
    )
    return cfg


# --- validate-prompts (validazione prompt-set senza avviare l'app) ----------


def test_cli_validate_prompts_default_set_ok(capsys):
    """Senza override i default impacchettati devono validare con exit 0."""
    code = main(["validate-prompts"])

    assert code == 0
    out = capsys.readouterr().out
    assert "ok" in out.lower()
    # Il riepilogo elenca i file controllati (entrambi i set) con l'origine.
    assert "situations.md" in out
    assert "summarizer.md" in out
    assert "default" in out


def test_cli_validate_prompts_reports_override_origin(tmp_path, capsys):
    """Un file valido nella dir di override è riportato con origine 'override'."""
    from importlib.resources import files

    override = tmp_path / "prompts"
    override.mkdir()
    intro = (files("minnarone.prompts") / "intro.md").read_text(encoding="utf-8")
    (override / "intro.md").write_text(intro, encoding="utf-8")

    code = main(["validate-prompts", "--prompts-dir", str(override)])

    assert code == 0
    out = capsys.readouterr().out
    assert "intro.md" in out
    assert "override" in out


def test_cli_validate_prompts_partial_override_notice(tmp_path, capsys):
    """Un override PARZIALE è segnalato esplicitamente (decisione FU-02).

    Niente strict-set bloccante: il fallback per-file resta, ma il riepilogo
    rende visibile il mix override/default (es. set inglese a metà).
    """
    from importlib.resources import files

    override = tmp_path / "prompts"
    override.mkdir()
    intro = (files("minnarone.prompts") / "intro.md").read_text(encoding="utf-8")
    (override / "intro.md").write_text(intro, encoding="utf-8")

    code = main(["validate-prompts", "--prompts-dir", str(override)])

    assert code == 0
    out = capsys.readouterr().out
    assert "override parziale" in out
    # 9 file totali (8 original-chat incluso headers.md + summarizer).
    assert "1 file da override, 8 dal default" in out


def test_cli_validate_prompts_full_override_has_no_partial_notice(tmp_path, capsys):
    """Se TUTTI i file vengono dall'override la nota di parzialità non appare."""
    from importlib.resources import files

    override = tmp_path / "prompts"
    override.mkdir()
    pkg = files("minnarone.prompts")
    for name in (
        "format.md",
        "rules.md",
        "intro.md",
        "situations.md",
        "headers.md",
        "operator.md",
        "meeting_synthesizer.md",
        "suggester.md",
        "summarizer.md",
    ):
        (override / name).write_text(
            (pkg / name).read_text(encoding="utf-8"), encoding="utf-8"
        )

    code = main(["validate-prompts", "--prompts-dir", str(override)])

    assert code == 0
    out = capsys.readouterr().out
    assert "override parziale" not in out


def test_cli_validate_prompts_broken_section_names_file_and_section(tmp_path, capsys):
    """`#end_conv` mancante in UNA sezione: l'errore nomina file E sezione."""
    from importlib.resources import files

    override = tmp_path / "prompts"
    override.mkdir()
    default = (files("minnarone.prompts") / "situations.md").read_text(encoding="utf-8")
    (override / "situations.md").write_text(
        default.replace(
            "## idle",
            "## idle\nSe non hai nulla da dire taci.\n\n## _idle_originale",
            1,
        ),
        encoding="utf-8",
    )

    code = main(["validate-prompts", "--prompts-dir", str(override)])

    assert code != 0
    err = capsys.readouterr().err
    assert "situations.md" in err
    assert "sezione 'idle'" in err
    assert "#end_conv" in err


def test_cli_validate_prompts_broken_override_returns_nonzero(tmp_path, capsys):
    """Un override rotto (senza #end_conv né chiavi) fallisce nominando il file."""
    override = tmp_path / "prompts"
    override.mkdir()
    (override / "situations.md").write_text(
        "## idle\nsituazione senza token di fine\n", encoding="utf-8"
    )

    code = main(["validate-prompts", "--prompts-dir", str(override)])

    assert code != 0
    err = capsys.readouterr().err
    assert "situations.md" in err


def test_cli_validate_prompts_reports_all_broken_files(tmp_path, capsys):
    """Più file rotti → una riga di errore per ciascuno (non solo il primo)."""
    override = tmp_path / "prompts"
    override.mkdir()
    (override / "situations.md").write_text("## idle\nsenza token\n", encoding="utf-8")
    (override / "rules.md").write_text("regole senza canale\n", encoding="utf-8")

    code = main(["validate-prompts", "--prompts-dir", str(override)])

    assert code != 0
    err = capsys.readouterr().err
    assert "situations.md" in err
    assert "rules.md" in err


def test_cli_validate_prompts_config_reads_prompts_dir(tmp_path, capsys):
    """`--config` legge `prompts_dir` dal YAML (risolto rispetto al config)."""
    override = tmp_path / "prompts"
    override.mkdir()
    (override / "summarizer.md").write_text(
        "## instruction\nsolo una\n", encoding="utf-8"
    )
    cfg = tmp_path / "config.yaml"
    cfg.write_text("prompts_dir: prompts\n", encoding="utf-8")

    code = main(["validate-prompts", "--config", str(cfg)])

    assert code != 0
    err = capsys.readouterr().err
    assert "summarizer.md" in err


def test_cli_validate_prompts_missing_config_returns_config_error(tmp_path, capsys):
    code = main(["validate-prompts", "--config", str(tmp_path / "assente.yaml")])

    assert code == 2
    assert "config" in capsys.readouterr().err.lower()


def test_cli_check_reads_twitch_credentials_from_dotenv(tmp_path, capsys, monkeypatch):
    # Ambiente pulito: le credenziali arrivano SOLO dal .env accanto al config.
    monkeypatch.delenv("TWITCH_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)
    cfg = _twitch_chat_config(tmp_path)
    (tmp_path / ".env").write_text(
        "TWITCH_BOT_USERNAME=bot_user\nTWITCH_OAUTH_TOKEN=oauth:token\n",
        encoding="utf-8",
    )

    code = main([str(cfg), "--check"])

    assert code == 0
    assert "ok" in capsys.readouterr().out.lower()
