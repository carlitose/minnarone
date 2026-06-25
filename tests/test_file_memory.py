"""Test della memoria a lungo termine concreta: `FileMemory`.

Carica `soul` (un file) e `facts` (tutti i file in una directory), li espone
come `MemoryBlocks`, e degrada con grazia quando i file mancano. L'hook
`update()` resta no-op (ereditato dalla base).
"""

from minnarone.memory import FactsDelta, FileMemory, MemoryBlocks
from minnarone.perception import Perception, Source
from minnarone.prompt import PromptBuilder
from minnarone.senser import Trigger


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_loads_soul_file_into_soul_block(tmp_path):
    soul = tmp_path / "soul.md"
    _write(soul, "Sono Minnarone, 24 anni, amo il trap.")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()

    blocks = FileMemory(soul_path=str(soul), facts_dir=str(facts_dir)).load()

    assert isinstance(blocks, MemoryBlocks)
    assert blocks.soul == "Sono Minnarone, 24 anni, amo il trap."


def test_concatenates_multiple_fact_files_in_deterministic_order(tmp_path):
    soul = tmp_path / "soul.md"
    _write(soul, "io")
    facts_dir = tmp_path / "facts"
    # Scritti fuori ordine di proposito: l'ordine atteso è per nome file.
    _write(facts_dir / "zeta.md", "fatto-z")
    _write(facts_dir / "alpha.md", "fatto-a")
    _write(facts_dir / "beta.md", "fatto-b")

    facts = FileMemory(soul_path=str(soul), facts_dir=str(facts_dir)).load().facts

    # Tutti i fatti presenti...
    assert "fatto-a" in facts
    assert "fatto-b" in facts
    assert "fatto-z" in facts
    # ...e in ordine alfabetico per nome file (deterministico).
    assert facts.index("fatto-a") < facts.index("fatto-b") < facts.index("fatto-z")


def test_load_is_deterministic_across_calls(tmp_path):
    soul = tmp_path / "soul.md"
    _write(soul, "io")
    facts_dir = tmp_path / "facts"
    _write(facts_dir / "a.md", "uno")
    _write(facts_dir / "b.md", "due")

    mem = FileMemory(soul_path=str(soul), facts_dir=str(facts_dir))
    assert mem.load() == mem.load()


def test_missing_soul_file_yields_empty_soul_no_crash(tmp_path):
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()

    blocks = FileMemory(
        soul_path=str(tmp_path / "nonexistent.md"), facts_dir=str(facts_dir)
    ).load()

    assert blocks.soul == ""


def test_missing_facts_dir_yields_empty_facts_no_crash(tmp_path):
    soul = tmp_path / "soul.md"
    _write(soul, "io")

    blocks = FileMemory(
        soul_path=str(soul), facts_dir=str(tmp_path / "nope")
    ).load()

    assert blocks.facts == ""


def test_empty_facts_dir_yields_empty_facts(tmp_path):
    soul = tmp_path / "soul.md"
    _write(soul, "io")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()

    blocks = FileMemory(soul_path=str(soul), facts_dir=str(facts_dir)).load()

    assert blocks.facts == ""


def test_blocks_appear_in_prompt_stable_cacheable_prefix(tmp_path):
    soul = tmp_path / "soul.md"
    _write(soul, "Sono Minnarone.")
    facts_dir = tmp_path / "facts"
    _write(facts_dir / "enkk.md", "enkk ama il trap.")

    blocks = FileMemory(soul_path=str(soul), facts_dir=str(facts_dir)).load()
    builder = PromptBuilder(blocks)

    prefix = builder.stable_prefix()
    assert "Sono Minnarone." in prefix
    assert "enkk ama il trap." in prefix

    # E il prefisso stabile deve essere il prefisso del prompt completo
    # (cioè la memoria sta nella parte cacheable, non nel dinamico).
    trigger = Trigger(
        reason="mention",
        perception=Perception(
            ts=1.0, source=Source.CHAT, type="msg", text="ehi", speaker="enkk"
        ),
    )
    prompt = builder.build(recent=[], trigger=trigger)
    assert prompt.startswith(prefix)


def test_update_is_noop_and_does_not_alter_load(tmp_path):
    soul = tmp_path / "soul.md"
    _write(soul, "io")
    facts_dir = tmp_path / "facts"
    _write(facts_dir / "a.md", "uno")

    mem = FileMemory(soul_path=str(soul), facts_dir=str(facts_dir))
    before = mem.load()
    assert mem.update(FactsDelta(entity="enkk", text="nuovo fatto")) is None
    after = mem.load()
    assert before == after


def test_non_utf8_soul_degrades_to_empty(tmp_path):
    soul = tmp_path / "soul.md"
    soul.write_bytes(b"\xff\xfe\x00binary garbage")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()

    blocks = FileMemory(soul_path=str(soul), facts_dir=str(facts_dir)).load()
    assert blocks.soul == ""  # non solleva UnicodeDecodeError


def test_non_utf8_fact_file_is_skipped_not_fatal(tmp_path):
    soul = tmp_path / "soul.md"
    _write(soul, "ok")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    (facts_dir / "bad.md").write_bytes(b"\xff\xfe\x00")
    _write(facts_dir / "good.md", "enkk ama il trap")

    blocks = FileMemory(soul_path=str(soul), facts_dir=str(facts_dir)).load()
    assert "enkk ama il trap" in blocks.facts  # il file buono sopravvive
