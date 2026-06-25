"""Test dello schema di configurazione: caricamento valido, errori chiari, punti v2 inerti."""

import textwrap

import pytest

from minnarone.config import Config, ConfigError
from minnarone.output import OutputMode

VALID_YAML = textwrap.dedent(
    """
    mode: public
    soul_path: soul.md
    facts_dir: facts
    adapter: os_capture
    llm_provider: grok
    llm_params:
      thinking: low
    disclosure:
      announce_ai: true
    retention:
      perceptions_days: 7
    """
)

MINIMAL_YAML = textwrap.dedent(
    """
    mode: public
    soul_path: soul.md
    facts_dir: facts
    adapter: os_capture
    llm_provider: grok
    """
)


def _write(tmp_path, content):
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return p


def test_load_valid_config(tmp_path):
    cfg = Config.load(_write(tmp_path, VALID_YAML))
    assert cfg.mode is OutputMode.PUBLIC
    assert cfg.adapter == "os_capture"
    assert cfg.llm_params["thinking"] == "low"


def test_defaults_applied_when_omitted(tmp_path):
    cfg = Config.load(_write(tmp_path, MINIMAL_YAML))
    assert cfg.senser_interval == 0.5
    assert cfg.idle_interval == 150.0
    assert cfg.summarizer_interval == 30.0
    assert cfg.recent_chat_window == 15


def test_summarizer_interval_parsed_and_validated(tmp_path):
    cfg = Config.load(_write(tmp_path, MINIMAL_YAML + "summarizer_interval: 5\n"))
    assert cfg.summarizer_interval == 5.0
    with pytest.raises(ConfigError, match="summarizer_interval"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "summarizer_interval: 0\n"))


def test_v2_points_present_and_inert_by_default(tmp_path):
    cfg = Config.load(_write(tmp_path, MINIMAL_YAML))
    assert cfg.disclosure.announce_ai is False
    assert cfg.retention.perceptions_days is None
    assert cfg.auto_memory is False


def test_v2_points_parsed_when_present(tmp_path):
    cfg = Config.load(_write(tmp_path, VALID_YAML))
    assert cfg.disclosure.announce_ai is True
    assert cfg.retention.perceptions_days == 7


def test_invalid_mode_raises_clear_error(tmp_path):
    bad = VALID_YAML.replace("mode: public", "mode: telepathic")
    with pytest.raises(ConfigError, match="mode"):
        Config.load(_write(tmp_path, bad))


def test_missing_required_field_raises(tmp_path):
    bad = textwrap.dedent(
        """
        mode: public
        facts_dir: facts
        adapter: os_capture
        llm_provider: grok
        """
    )
    with pytest.raises(ConfigError, match="soul_path"):
        Config.load(_write(tmp_path, bad))


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="non trovato"):
        Config.load(tmp_path / "nope.yaml")


def test_empty_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="vuoto"):
        Config.load(_write(tmp_path, ""))


def test_non_positive_interval_raises(tmp_path):
    bad = MINIMAL_YAML + "senser_interval: 0\n"
    with pytest.raises(ConfigError, match="senser_interval"):
        Config.load(_write(tmp_path, bad))
