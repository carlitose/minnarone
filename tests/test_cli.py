"""Test dell'entrypoint CLI (slice 11): `python -m minnarone <config>`.

Si verifica che un config valido costruisca l'agente (dry-run, senza avviare il
loop bloccante né toccare rete/device) e che un config invalido dia un errore
chiaro con exit code != 0.
"""

import textwrap

from minnarone.cli import main


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
