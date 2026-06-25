"""Boundary test della base `EventPerceiver`.

Verifica una volta sola il dispatch comune (routing per canale, scarto del
payload del tipo sbagliato, fold multi-evento) tramite un perceiver finto
minimale, così che i perceiver concreti (Audio/Video) non debbano riprovare la
stessa logica.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from minnarone.perceiver import EventPerceiver
from minnarone.perception import Perception, Source
from minnarone.source import RawEvent


@dataclass(frozen=True)
class _Payload:
    text: str


class _FakePerceiver(EventPerceiver):
    """Perceiver minimale: trasforma ogni `_Payload` in una `Perception`."""

    channel = "fake"
    payload_type = _Payload

    def _perceive_payload(self, payload: _Payload) -> list[Perception]:
        return [
            Perception(ts=0.0, source=Source.CHAT, type="msg", text=payload.text)
        ]


def test_wrong_channel_returns_empty():
    perceiver = _FakePerceiver()
    event = RawEvent(channel="other", payload=_Payload("ciao"), ts=1.0)
    assert perceiver.perceive_event(event) == []


def test_wrong_payload_type_raises_type_error():
    perceiver = _FakePerceiver()
    event = RawEvent(channel="fake", payload="not-a-payload", ts=1.0)
    with pytest.raises(TypeError):
        perceiver.perceive_event(event)


def test_correct_event_delegates_to_perceive_payload():
    perceiver = _FakePerceiver()
    event = RawEvent(channel="fake", payload=_Payload("ciao"), ts=1.0)
    created = perceiver.perceive_event(event)
    assert [p.text for p in created] == ["ciao"]


def test_perceive_events_folds_in_order_skipping_other_channels():
    perceiver = _FakePerceiver()
    events = [
        RawEvent(channel="fake", payload=_Payload("a"), ts=1.0),
        RawEvent(channel="other", payload=_Payload("ignored"), ts=2.0),
        RawEvent(channel="fake", payload=_Payload("b"), ts=3.0),
    ]
    created = perceiver.perceive_events(events)
    assert [p.text for p in created] == ["a", "b"]
