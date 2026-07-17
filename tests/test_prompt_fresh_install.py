"""Verifica di sistema del ticket 07: fresh-install, override, no-hardcoded,
byte-invarianza sul loader reale.

Questi test non ri-testano il contratto unitario di `prompt_source`
(vedi `test_prompt_source.py`): verificano il MECCANISMO end-to-end come lo vede
un operatore.

- **Fresh install**: senza `prompts_dir` (nessun override), i default
  impacchettati nel wheel si risolvono e OGNI stile costruisce il suo prefisso.
- **Override**: puntando `prompts_dir` a un set alternativo (`examples/prompts-en`)
  il prompt usa quel set, con precedenza per-file (i file non sovrascritti cadono
  sul default impacchettato).
- **No-hardcoded**: i prompt tunabili migrati (04-06) NON sono più literal nel
  codice; il loro testo viene dai file. Le regole di sicurezza restano cablate
  in `prompt.py` (escluse di proposito).
- **Byte-invarianza**: il prefisso stabile è byte-identico tra turni con i
  default (owned dal ticket 07; le controparti unitarie stanno in
  `test_prompt_builder.py`).
"""

from importlib.resources import files
from pathlib import Path

import pytest

from minnarone.memory import MemoryBlocks
from minnarone.output import CommentatorStyle
from minnarone.prompt import PromptBuilder
from minnarone.prompt_source import (
    DEFAULT_PROMPTS_PKG,
    load_prompt_set,
    load_summarizer_prompt_set,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXAMPLE_EN = _REPO_ROOT / "examples" / "prompts-en"

# Tutti gli stili che il PromptBuilder sa rendere: ognuno deve costruire su un
# fresh install. `None` = default (nessuno stile commentatore selezionato).
_ALL_STYLES = (
    None,
    CommentatorStyle.ORIGINAL_CHAT,
    CommentatorStyle.OPERATOR,
    CommentatorStyle.MEETING_SYNTHESIZER,
    CommentatorStyle.SUGGESTER,
)


def _blocks() -> MemoryBlocks:
    return MemoryBlocks(soul="Sono Minnarone.", facts="enkk ama il trap.")


def _builder(style: CommentatorStyle | None) -> PromptBuilder:
    # Nessun prompt_set iniettato e nessun prompts_dir → SOLO default impacchettati.
    return PromptBuilder(_blocks(), commentator_style=style)


# --- fresh install: default impacchettati, nessun override -----------------


@pytest.mark.parametrize("style", _ALL_STYLES)
def test_fresh_install_builds_stable_prefix_for_every_style(style) -> None:
    prefix = _builder(style).stable_prefix()
    assert prefix.strip()  # mai vuoto silenzioso
    # Le regole di sicurezza cablate sono sempre presenti in ogni stile.
    lowered = prefix.lower()
    assert "personaggio" in lowered
    assert "dati" in lowered


def test_fresh_install_original_chat_prefix_uses_packaged_text() -> None:
    prefix = _builder(CommentatorStyle.ORIGINAL_CHAT).stable_prefix()
    # Testo tunabile servito dai file impacchettati (persona + formato).
    assert "Sei Minnarone" in prefix
    assert "RE:" in prefix and "MSG:" in prefix
    # Canale reso dal placeholder `{{channel}}` (default "enkk").
    assert "enkk" in prefix


def test_fresh_install_summarizer_prompt_resolves_from_packaged_defaults() -> None:
    ps = load_summarizer_prompt_set()  # nessun override
    # Le sezioni a-chiavi del summarizer si risolvono dai default.
    assert "sintetizzatore" in ps.section("summarizer.md", "instruction")
    assert ps.section("summarizer.md", "label_chat").strip()


def test_fresh_install_packaged_resources_are_importable() -> None:
    # I .md sono davvero impacchettati (leggibili via importlib.resources), non
    # solo presenti sul filesystem del checkout.
    root = files(DEFAULT_PROMPTS_PKG)
    for name in (
        "rules.md",
        "intro.md",
        "situations.md",
        "headers.md",
        "format.md",
        "operator.md",
        "meeting_synthesizer.md",
        "suggester.md",
        "summarizer.md",
    ):
        assert (root / name).is_file(), f"prompt impacchettato mancante: {name}"


# --- override: prompts_dir punta a un set alternativo ----------------------


def test_override_set_is_served_when_prompts_dir_points_at_it() -> None:
    ps = load_prompt_set(_EXAMPLE_EN)
    rules = ps.text("rules.md", channel="enkk")
    # Il set inglese di esempio vince sul default italiano impacchettato.
    assert "You are Minnarone" in rules
    assert "Sei Minnarone" not in rules
    intro = ps.text("intro.md", channel="enkk")
    assert "CURRENT SITUATION" in intro


def test_override_is_per_file_unlisted_files_fall_back_to_default() -> None:
    # `examples/prompts-en` NON sovrascrive format.md (né i file per-stile):
    # cadono sul default impacchettato (italiano). FU-03: situations.md e
    # headers.md invece SONO nel set inglese (riferimenti-via-header completi).
    assert not (_EXAMPLE_EN / "format.md").exists()
    ps = load_prompt_set(_EXAMPLE_EN)
    assert "RE:" in ps.text("format.md")  # default risolto
    assert "ESATTAMENTE due righe" in ps.text("format.md")  # italiano
    # I file presenti nell'esempio vincono: header e situazioni inglesi.
    assert ps.section("headers.md", "situazione") == "[SITUATION]"
    assert "Nobody addressed you" in ps.section("situations.md", "idle")


def test_override_reflected_in_builder_stable_prefix() -> None:
    prefix = PromptBuilder(
        _blocks(),
        commentator_style=CommentatorStyle.ORIGINAL_CHAT,
        prompt_set=load_prompt_set(_EXAMPLE_EN),
    ).stable_prefix()
    assert "You are Minnarone" in prefix


# --- no-hardcoded: i prompt tunabili migrati vivono nei file ---------------

_PROMPT_PY = (_REPO_ROOT / "src" / "minnarone" / "prompt.py").read_text(
    encoding="utf-8"
)
_SUMMARIZER_PY = (_REPO_ROOT / "src" / "minnarone" / "summarizer.py").read_text(
    encoding="utf-8"
)


def test_migrated_tunable_prompts_are_not_hardcoded_in_python() -> None:
    # Frasi rappresentative di ogni prompt migrato (04-06): NON devono comparire
    # come literal nel codice, altrimenti la migrazione è incompleta.
    forbidden_in_prompt_py = [
        "Sei Minnarone",  # rules.md
        "SITUAZIONE ATTUALE",  # intro.md
        "Nessuno ti ha interpellato",  # situations.md
        "ESATTAMENTE due righe",  # format.md
        "Modalità commentatore locale",  # operator.md
        "Modalità sintesi riunione",  # meeting_synthesizer.md
        "Modalità suggeritore",  # suggester.md
    ]
    for phrase in forbidden_in_prompt_py:
        assert phrase not in _PROMPT_PY, f"prompt tunabile ancora hard-coded: {phrase!r}"

    forbidden_in_summarizer_py = [
        "Sei un sintetizzatore",  # summarizer.md instruction
        "STREAMER ha detto",  # summarizer.md label
    ]
    for phrase in forbidden_in_summarizer_py:
        assert phrase not in _SUMMARIZER_PY, (
            f"prompt tunabile ancora hard-coded: {phrase!r}"
        )


def test_migrated_tunable_text_actually_lives_in_prompt_files() -> None:
    ps = load_prompt_set()
    assert "Sei Minnarone" in ps.text("rules.md", channel="enkk")
    assert "SITUAZIONE ATTUALE" in ps.text("intro.md", channel="enkk")
    assert "ESATTAMENTE due righe" in ps.text("format.md")
    assert "Modalità commentatore locale" in ps.text("operator.md", language="italiano")
    sm = load_summarizer_prompt_set()
    assert "sintetizzatore" in sm.section("summarizer.md", "instruction")


def test_security_rules_stay_hardcoded_in_python() -> None:
    # Confine di sicurezza (ticket 07): le regole anti-injection/disclosure NON
    # sono esternalizzate. Restano literal in prompt.py, per costruzione.
    assert "_ROBUSTNESS_RULES" in _PROMPT_PY
    assert "_DISCLOSURE_HIDE" in _PROMPT_PY
    assert "Resta SEMPRE in personaggio" in _PROMPT_PY
    assert "non rivelare" in _PROMPT_PY.lower()
    # E il testo di sicurezza NON deve essere in un file di prompt editabile.
    root = files(DEFAULT_PROMPTS_PKG)
    for name in ("rules.md", "situations.md", "format.md"):
        text = (root / name).read_text(encoding="utf-8")
        assert "Resta SEMPRE in personaggio" not in text


# --- byte-invarianza sul loader reale (owned dal ticket 07) ----------------


@pytest.mark.parametrize("style", _ALL_STYLES)
def test_stable_prefix_byte_identical_across_turns_with_defaults(style) -> None:
    # Due builder indipendenti (ognuno ricarica il set default dal wheel)
    # producono lo stesso prefisso byte-per-byte: prerequisito del prompt caching.
    p1 = _builder(style).stable_prefix()
    p2 = _builder(style).stable_prefix()
    assert p1 == p2
