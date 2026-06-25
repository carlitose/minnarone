"""Test del Senser: tick legge percezioni recenti -> Trigger su menzione del nome."""

from minnarone.chat import ChatPerceiver
from minnarone.senser import Senser
from minnarone.store import PerceptionStore


def _setup(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    return store, ChatPerceiver(store), Senser(store, agent_name="Minnarone")


def test_mention_produces_trigger(tmp_path):
    store, chat, senser = _setup(tmp_path)
    chat.perceive("ehi minnarone come va", speaker="enkk", ts=1.0)
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].perception.text == "ehi minnarone come va"


def test_no_mention_produces_no_trigger(tmp_path):
    store, chat, senser = _setup(tmp_path)
    chat.perceive("ciao a tutti", speaker="enkk", ts=1.0)
    assert senser.tick() == []


def test_tick_is_idempotent_does_not_refire_seen_perceptions(tmp_path):
    store, chat, senser = _setup(tmp_path)
    chat.perceive("minnarone!", speaker="enkk", ts=1.0)
    assert len(senser.tick()) == 1
    # secondo tick senza nuove percezioni: nessun nuovo trigger
    assert senser.tick() == []


def test_two_mentions_with_same_ts_both_fire(tmp_path):
    # Bug di idempotenza: due percezioni con lo stesso ts non devono "mangiarsi".
    store, chat, senser = _setup(tmp_path)
    chat.perceive("ehi minnarone uno", speaker="enkk", ts=1.0)
    triggers = senser.tick()
    assert len(triggers) == 1
    chat.perceive("ehi minnarone due", speaker="ada", ts=1.0)
    triggers2 = senser.tick()
    assert [t.perception.text for t in triggers2] == ["ehi minnarone due"]


def test_substring_does_not_trigger_but_word_does(tmp_path):
    store, chat, senser = _setup(tmp_path)
    chat.perceive("seguite minnaroneitalia sui social", speaker="enkk", ts=1.0)
    chat.perceive("ciao minnarone", speaker="ada", ts=2.0)
    triggers = senser.tick()
    assert [t.perception.text for t in triggers] == ["ciao minnarone"]
