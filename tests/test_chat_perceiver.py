"""Test del ChatPerceiver: input testuale -> Perception(chat/msg) nello store."""

from minnarone.chat import ChatPerceiver
from minnarone.perception import Source
from minnarone.source import RawEvent
from minnarone.store import PerceptionStore


def test_perceive_writes_chat_msg_perception_to_store(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    perceiver = ChatPerceiver(store)

    perceiver.perceive("ciao minnarone", speaker="enkk", ts=10.0)

    perceptions = store.read_since(0.0)
    assert len(perceptions) == 1
    p = perceptions[0]
    assert p.source is Source.CHAT
    assert p.type == "msg"
    assert p.text == "ciao minnarone"
    assert p.speaker == "enkk"
    assert p.ts == 10.0


def test_perceive_event_uses_chat_raw_event_contract(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    perceiver = ChatPerceiver(store)
    event = RawEvent(
        channel="chat",
        payload={"text": "ciao chat", "speaker": "ada"},
        ts=12.0,
    )

    perception = perceiver.perceive_event(event)

    assert perception is not None
    assert perception.text == "ciao chat"
    assert perception.speaker == "ada"
    assert perception.ts == 12.0
