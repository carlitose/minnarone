"""Test del PromptBuilder: prefisso stabile + messaggi recenti + situazione in coda."""

from minnarone.memory import MemoryBlocks
from minnarone.perception import Perception, Source
from minnarone.prompt import PromptBuilder
from minnarone.senser import Trigger


def _blocks():
    return MemoryBlocks(soul="Sono Minnarone.", facts="enkk ama il trap.")


def _msg(ts, text, speaker="enkk"):
    return Perception(ts=ts, source=Source.CHAT, type="msg", text=text, speaker=speaker)


def _trigger():
    return Trigger(reason="mention", perception=_msg(3.0, "ehi minnarone"))


def test_sections_in_order_prefix_then_recent_then_situation():
    builder = PromptBuilder(_blocks())
    recent = [_msg(1.0, "ciao"), _msg(2.0, "tutto bene?")]
    prompt = builder.build(recent=recent, trigger=_trigger())

    prefix = builder.stable_prefix()
    assert prompt.startswith(prefix)
    i_recent = prompt.index("ciao")
    i_situation = prompt.index("ehi minnarone")
    assert len(prefix) <= i_recent < i_situation


def test_stable_prefix_is_byte_identical_across_builds():
    b1 = PromptBuilder(_blocks())
    b2 = PromptBuilder(_blocks())
    assert b1.stable_prefix() == b2.stable_prefix()


def test_trigger_message_appears_once_in_prompt():
    # Il messaggio del trigger non deve essere duplicato: compare in SITUAZIONE
    # ma NON anche nella finestra recente.
    builder = PromptBuilder(_blocks())
    trigger = _trigger()  # testo "ehi minnarone"
    recent = [_msg(1.0, "ciao"), _msg(2.0, "tutto bene?"), trigger.perception]
    prompt = builder.build(recent=recent, trigger=trigger)
    assert prompt.count("ehi minnarone") == 1


def test_trigger_message_dedup_across_distinct_instances():
    # Scenario reale del Reactor: `trigger.perception` viene parsata FRESH dal
    # file JSONL (Senser.tick -> read_from), mentre `recent` arriva dal deque
    # in memoria (store.tail). I due oggetti NON sono la stessa istanza ma sono
    # uguali per valore. La deduplica deve reggere comunque (no identity check).
    builder = PromptBuilder(_blocks())
    in_window = _msg(3.0, "ehi minnarone")  # originale nel deque
    # round-trip JSON: simula la riparsing dal file (istanza distinta, == per valore)
    reparsed = Perception.from_json(in_window.to_json())
    assert reparsed is not in_window
    assert reparsed == in_window
    trigger = Trigger(reason="mention", perception=reparsed)
    recent = [_msg(1.0, "ciao"), _msg(2.0, "tutto bene?"), in_window]
    prompt = builder.build(recent=recent, trigger=trigger)
    assert prompt.count("ehi minnarone") == 1


def test_stable_prefix_contains_no_dynamic_data():
    builder = PromptBuilder(_blocks())
    prefix = builder.stable_prefix()
    # nessun timestamp / testo del trigger deve essere nel prefisso stabile
    assert "3.0" not in prefix
    assert "ehi minnarone" not in prefix
    # ma deve contenere la soul/facts (contesto stabile)
    assert "Sono Minnarone." in prefix
    assert "enkk ama il trap." in prefix


def test_summary_rendered_in_dynamic_section_before_recent():
    # Il riassunto (memoria a breve termine) è DINAMICO: va nella sezione
    # dinamica, dopo il prefisso stabile ma PRIMA dei messaggi recenti.
    builder = PromptBuilder(_blocks())
    recent = [_msg(1.0, "ciao"), _msg(2.0, "tutto bene?")]
    prompt = builder.build(
        recent=recent, trigger=_trigger(), summary="Prima enkk ha battuto il boss."
    )
    prefix = builder.stable_prefix()
    assert prompt.startswith(prefix)
    i_summary = prompt.index("Prima enkk ha battuto il boss.")
    i_recent = prompt.index("ciao")
    assert len(prefix) <= i_summary < i_recent


def test_stable_prefix_unaffected_by_summary():
    # Il riassunto non deve MAI finire nel prefisso cacheable: il prefisso resta
    # byte-identico a prescindere dal summary passato a build().
    builder = PromptBuilder(_blocks())
    recent = [_msg(1.0, "ciao")]
    trigger = _trigger()
    p_no_summary = builder.build(recent=recent, trigger=trigger)
    p_with_summary = builder.build(
        recent=recent, trigger=trigger, summary="qualcosa di volatile"
    )
    prefix = builder.stable_prefix()
    assert p_no_summary.startswith(prefix)
    assert p_with_summary.startswith(prefix)
    # il summary non deve essere comparso dentro il prefisso
    assert "qualcosa di volatile" not in prefix
