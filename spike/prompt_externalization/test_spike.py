"""Demo eseguibile dello spike: 5 scenari che provano il contratto prompt-source.

    uv run pytest spike/prompt_externalization/test_spike.py -v

Lo spike NON è installato come package: aggiungiamo la sua dir-genitore a
sys.path così `prompt_externalization` è importabile e `importlib.resources`
può leggere il set default impacchettato.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prompt_externalization.loader import (  # noqa: E402
    PromptError,
    PromptSet,
    language_name,
    render,
)
from prompt_externalization.sets import (  # noqa: E402
    DEFAULT_PKG,
    ORIGINAL_CHAT_SET,
    SITUATION_KEYS,
)

_SPIKE_DIR = Path(__file__).resolve().parent


def _load(override: str | None = None) -> PromptSet:
    return PromptSet(
        ORIGINAL_CHAT_SET,
        default_pkg=DEFAULT_PKG,
        override_dir=str(_SPIKE_DIR / override) if override else None,
    )


# 1) SET DEFAULT impacchettato: si carica via importlib.resources e rende in it.
def test_default_set_loads_and_renders_italian() -> None:
    ps = _load()
    rules = ps.text("rules.md", channel="enkk", language=language_name("it"))
    assert "nel canale di enkk" in rules
    assert "in italiano" in rules
    # I 6 trigger sono tutti presenti.
    assert ps.keys("situations.md") == SITUATION_KEYS
    # #end_conv sopravvive nella situazione.
    idle = ps.section("situations.md", "idle")
    assert "#end_conv" in idle


# 2) OVERRIDE per-file: rules.md dall'override, il resto dal default (precedenza).
def test_partial_override_precedence() -> None:
    ps = _load("override_partial")
    rules = ps.text("rules.md", channel="enkk", language=language_name("it"))
    assert "REGOLE PERSONALIZZATE" in rules  # viene dall'override
    # situations.md NON è nell'override → cade sul default impacchettato.
    assert ps.keys("situations.md") == SITUATION_KEYS
    assert "butta li'" in ps.section("situations.md", "idle")


# 3) TEMPLATING sicuro: {{...}} sostituiti, graffe singole letterali intatte,
#    nessuna ri-espansione del valore iniettato (niente injection).
def test_templating_is_safe() -> None:
    ps = _load()
    chat = ps.section("situations.md", "chat_mention", user="mario", mention="@mario")
    assert "mario ti ha scritto" in chat
    assert "@mario" in chat

    # Le graffe SINGOLE letterali sopravvivono; solo {{...}} è un placeholder.
    assert render("codice { non toccato } e {{x}}", {"x": "OK"}) == (
        "codice { non toccato } e OK"
    )
    # Il valore iniettato NON viene ri-scansionato: {{y}} dentro il valore resta
    # letterale (un contenuto ostile non può iniettare nuovi placeholder).
    assert render("{{x}}", {"x": "{{y}} letterale"}) == "{{y}} letterale"

    # Placeholder senza valore → errore (fail-fast), mai stringa vuota.
    with pytest.raises(PromptError):
        render("ciao {{ignoto}}", {})


# 4) VALIDAZIONE fail-fast: il set rotto solleva PromptError all'avvio.
def test_broken_set_missing_placeholder_fails_fast() -> None:
    # broken_set/rules.md (validato per primo): manca il placeholder
    # obbligatorio {{channel}} → fail-fast sul placeholder.
    with pytest.raises(PromptError, match="channel"):
        _load("broken_set")


def test_missing_control_token_fails_fast() -> None:
    # broken_set/situations.md: la sezione ## idle non contiene #end_conv.
    # Lo isoliamo con un set-spec di un solo file per raggiungere il check
    # del token (rules.md fallirebbe prima nel set completo).
    from prompt_externalization.loader import PromptSetSpec, PromptSpec

    spec = PromptSetSpec(
        specs=(
            PromptSpec(
                filename="situations.md",
                allowed_placeholders=frozenset({"user", "mention", "reason"}),
                required_tokens=("#end_conv",),
                keyed=True,
                required_keys=SITUATION_KEYS,
            ),
        )
    )
    with pytest.raises(PromptError, match="#end_conv"):
        PromptSet(
            spec,
            default_pkg=DEFAULT_PKG,
            override_dir=str(_SPIKE_DIR / "broken_set"),
        )


def test_missing_required_file_fails_fast(tmp_path: Path) -> None:
    # Un override che esiste ma... il default copre tutto, quindi per forzare il
    # "file mancante" usiamo un set-spec che richiede un file inesistente.
    from prompt_externalization.loader import PromptSetSpec, PromptSpec

    spec = PromptSetSpec(specs=(PromptSpec(filename="inesistente.md"),))
    with pytest.raises(PromptError, match="obbligatorio mancante"):
        PromptSet(spec, default_pkg=DEFAULT_PKG)


def test_empty_required_content_not_silent(tmp_path: Path) -> None:
    (tmp_path / "format.md").write_text("   \n", encoding="utf-8")
    from prompt_externalization.loader import PromptSetSpec, PromptSpec

    spec = PromptSetSpec(specs=(PromptSpec(filename="format.md"),))
    with pytest.raises(PromptError, match="vuoto"):
        PromptSet(spec, default_pkg=DEFAULT_PKG, override_dir=str(tmp_path))


# 5) SWAP LINGUA "gratis": stesso codice, si punta prompts_dir al set inglese.
def test_language_swap_serves_english_set() -> None:
    ps = _load("override_en")
    rules = ps.text("rules.md", channel="enkk", language=language_name("en"))
    assert "in {{channel}}'s channel".replace("{{channel}}", "enkk") in rules
    assert "in inglese" in rules  # {{language}} mappato a "inglese"
    # Le situazioni sono in inglese ma i 6 trigger e #end_conv restano.
    assert ps.keys("situations.md") == SITUATION_KEYS
    idle = ps.section("situations.md", "idle")
    assert "MSG: #end_conv" in idle
    assert "Nobody has addressed you" in idle
