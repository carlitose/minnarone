"""Test del contratto dati `Perception` (comportamento esterno: round-trip + validazione)."""

import json

import pytest

from minnarone.perception import Perception, Source, format_perception_line


def test_roundtrip_preserves_fields():
    p = Perception(ts=1781057651.73, source=Source.AUDIO, type="speech",
                   text="ciao", speaker="streamer")
    assert Perception.from_json(p.to_json()) == p


def test_speaker_optional_and_omitted_when_none():
    p = Perception(ts=1.0, source=Source.VIDEO, type="caption", text="una stanza")
    assert "speaker" not in json.loads(p.to_json())
    assert Perception.from_json(p.to_json()).speaker is None


def test_all_sources_have_a_valid_type():
    cases = [
        (Source.CHAT, "msg"),
        (Source.AUDIO, "speech"),
        (Source.VIDEO, "caption"),
        (Source.EVENT, "join"),
    ]
    for source, type_ in cases:
        Perception(ts=0.0, source=source, type=type_, text="x")  # non solleva


def test_invalid_type_for_source_raises():
    with pytest.raises(ValueError):
        Perception(ts=0.0, source=Source.CHAT, type="speech", text="x")


def test_invalid_source_string_on_load_raises():
    line = json.dumps({"ts": 0.0, "source": "telepatia", "type": "msg", "text": "x"})
    with pytest.raises(ValueError):
        Perception.from_json(line)


def test_non_numeric_ts_raises():
    with pytest.raises(ValueError):
        Perception(ts="presto", source=Source.CHAT, type="msg", text="x")  # type: ignore[arg-type]


def test_unicode_text_survives_roundtrip():
    p = Perception(ts=2.0, source=Source.CHAT, type="msg", text="però 🐌 lumache")
    assert Perception.from_json(p.to_json()).text == "però 🐌 lumache"


def test_format_perception_line_uses_speaker():
    p = Perception(ts=1.0, source=Source.CHAT, type="msg", text="ciao", speaker="enkk")
    assert format_perception_line(p) == "enkk: ciao"


def test_format_perception_line_falls_back_to_anon_when_no_speaker():
    p = Perception(ts=1.0, source=Source.VIDEO, type="caption", text="una stanza")
    assert format_perception_line(p) == "anon: una stanza"
