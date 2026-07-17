"""Test del modulo `prompt_source`: loader reale promosso dallo spike (ticket 03).

Copre il contratto deciso nel ticket 02: formato markdown-only, templating
`{{nome}}` sicuro, packaging via `importlib.resources` + override per-file da
`prompts_dir`, validazione fail-fast (mai vuoto silenzioso).
"""

from pathlib import Path

import pytest

from minnarone.prompt_source import (
    DEFAULT_PROMPTS_PKG,
    ORIGINAL_CHAT_SET,
    PromptError,
    PromptSet,
    PromptSetSpec,
    PromptSpec,
    find_placeholders,
    language_name,
    load_prompt_set,
    render,
)

# --- default impacchettato (importlib.resources) ---


def test_default_set_loads_packaged_format() -> None:
    ps = load_prompt_set()
    text = ps.text("format.md")
    assert "RE:" in text
    assert "MSG:" in text
    assert "#end_conv" in text


def test_default_set_has_no_override() -> None:
    # Senza prompts_dir → solo default impacchettati (fresh install).
    ps = PromptSet(ORIGINAL_CHAT_SET, default_pkg=DEFAULT_PROMPTS_PKG)
    assert "ESATTAMENTE due righe" in ps.text("format.md")


# --- override per-file (precedenza) ---


def test_override_file_wins_over_default(tmp_path: Path) -> None:
    (tmp_path / "format.md").write_text(
        "RE: x\nMSG: y oppure #end_conv\nOVERRIDE\n", encoding="utf-8"
    )
    ps = PromptSet(
        ORIGINAL_CHAT_SET, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path
    )
    assert "OVERRIDE" in ps.text("format.md")


def test_missing_override_file_falls_back_to_default(tmp_path: Path) -> None:
    # override_dir esiste ma è vuoto → format.md cade sul default impacchettato.
    ps = PromptSet(
        ORIGINAL_CHAT_SET, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path
    )
    assert "ESATTAMENTE due righe" in ps.text("format.md")


# --- templating sicuro ---


def test_render_substitutes_double_brace() -> None:
    assert render("ciao {{nome}}", {"nome": "mondo"}) == "ciao mondo"


def test_render_single_braces_and_angles_survive() -> None:
    assert render("codice { non toccato } e <x> e {{y}}", {"y": "OK"}) == (
        "codice { non toccato } e <x> e OK"
    )


def test_render_injected_value_is_not_rescanned() -> None:
    # Un valore che contiene {{z}} NON viene ri-espanso: niente injection.
    assert render("{{x}}", {"x": "{{z}} letterale"}) == "{{z}} letterale"


def test_render_missing_placeholder_fails_fast() -> None:
    with pytest.raises(PromptError):
        render("ciao {{ignoto}}", {})


def test_find_placeholders() -> None:
    assert find_placeholders("{{a}} e {{ b }} e { c }") == {"a", "b"}


def test_language_name_maps_known_codes() -> None:
    assert language_name("it") == "italiano"
    assert language_name("en") == "inglese"
    assert language_name("xx") == "xx"


# --- validazione fail-fast ---


def test_missing_required_file_fails_fast() -> None:
    spec = PromptSetSpec(specs=(PromptSpec(filename="inesistente.md"),))
    with pytest.raises(PromptError, match="obbligatorio mancante"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG)


def test_empty_required_content_not_silent(tmp_path: Path) -> None:
    (tmp_path / "format.md").write_text("   \n", encoding="utf-8")
    spec = PromptSetSpec(specs=(PromptSpec(filename="format.md"),))
    with pytest.raises(PromptError, match="vuoto"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


def test_unknown_placeholder_fails_fast(tmp_path: Path) -> None:
    (tmp_path / "format.md").write_text("RE: MSG: #end_conv {{boom}}\n", encoding="utf-8")
    spec = PromptSetSpec(
        specs=(PromptSpec(filename="format.md", allowed_placeholders=frozenset()),)
    )
    with pytest.raises(PromptError, match="ignoti"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


def test_missing_required_placeholder_fails_fast(tmp_path: Path) -> None:
    (tmp_path / "format.md").write_text("RE: MSG: #end_conv\n", encoding="utf-8")
    spec = PromptSetSpec(
        specs=(
            PromptSpec(
                filename="format.md",
                allowed_placeholders=frozenset({"channel"}),
                required_placeholders=frozenset({"channel"}),
            ),
        )
    )
    with pytest.raises(PromptError, match="channel"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


def test_missing_control_token_fails_fast(tmp_path: Path) -> None:
    (tmp_path / "format.md").write_text("nessun token qui\n", encoding="utf-8")
    spec = PromptSetSpec(
        specs=(PromptSpec(filename="format.md", required_tokens=("#end_conv",)),)
    )
    with pytest.raises(PromptError, match="#end_conv"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


def test_missing_required_key_fails_fast(tmp_path: Path) -> None:
    (tmp_path / "keyed.md").write_text("## a\ncorpo a\n", encoding="utf-8")
    spec = PromptSetSpec(
        specs=(
            PromptSpec(
                filename="keyed.md",
                keyed=True,
                required_keys=frozenset({"a", "b"}),
            ),
        )
    )
    with pytest.raises(PromptError, match="chiave"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


# --- accesso a sezioni a-chiavi ---


def test_keyed_sections_parsed_and_rendered(tmp_path: Path) -> None:
    (tmp_path / "keyed.md").write_text(
        "## a\nciao {{nome}}\n\n## b\naltro corpo\n", encoding="utf-8"
    )
    spec = PromptSetSpec(
        specs=(
            PromptSpec(
                filename="keyed.md",
                allowed_placeholders=frozenset({"nome"}),
                keyed=True,
                required_keys=frozenset({"a", "b"}),
            ),
        )
    )
    ps = PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)
    assert ps.keys("keyed.md") == frozenset({"a", "b"})
    assert ps.section("keyed.md", "a", nome="mondo") == "ciao mondo"
