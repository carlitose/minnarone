"""Test del ChatPerceiver: input testuale -> Perception(chat/msg) nello store."""

from minnarone.chat import ChatPerceiver
from minnarone.perception import Source
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
