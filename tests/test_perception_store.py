"""Test del PerceptionStore: append-only su perceptions.jsonl.

Verifica comportamento esterno: ordine per ts, durabilità riga-per-riga,
read_since filtra, tail restituisce gli ultimi N in ordine cronologico.
"""

from minnarone.perception import Perception, Source
from minnarone.store import PerceptionStore


def _p(ts: float, text: str) -> Perception:
    return Perception(ts=ts, source=Source.CHAT, type="msg", text=text)


def test_append_then_read_preserves_order_by_ts(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    store.append(_p(1.0, "uno"))
    store.append(_p(2.0, "due"))
    store.append(_p(3.0, "tre"))
    texts = [p.text for p in store.read_since(0.0)]
    assert texts == ["uno", "due", "tre"]


def test_read_since_filters_strictly_after_ts(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    store.append(_p(1.0, "uno"))
    store.append(_p(2.0, "due"))
    store.append(_p(3.0, "tre"))
    texts = [p.text for p in store.read_since(2.0)]
    assert texts == ["tre"]


def test_tail_returns_last_n_in_chronological_order(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    for i in range(1, 6):
        store.append(_p(float(i), f"m{i}"))
    assert [p.text for p in store.tail(2)] == ["m4", "m5"]


def test_read_on_missing_file_is_empty(tmp_path):
    store = PerceptionStore(tmp_path / "nuovo.jsonl")
    assert store.read_since(0.0) == []
    assert store.tail(3) == []


def test_reopened_store_sees_previously_appended_rows(tmp_path):
    path = tmp_path / "perceptions.jsonl"
    PerceptionStore(path).append(_p(1.0, "persisto"))
    reopened = PerceptionStore(path)
    assert [p.text for p in reopened.read_since(0.0)] == ["persisto"]


def test_read_from_returns_only_new_rows_and_advances_position(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    store.append(_p(1.0, "uno"))
    store.append(_p(2.0, "due"))

    first, pos = store.read_from(0)
    assert [p.text for p in first] == ["uno", "due"]

    # senza nuove scritture, da pos non esce nulla
    second, pos2 = store.read_from(pos)
    assert second == []
    assert pos2 == pos

    # una nuova scrittura: solo quella esce
    store.append(_p(3.0, "tre"))
    third, pos3 = store.read_from(pos2)
    assert [p.text for p in third] == ["tre"]
    assert pos3 > pos2


def test_read_from_does_not_drop_duplicate_ts(tmp_path):
    # Due percezioni con lo STESSO ts: entrambe devono essere lette (la
    # posizione è indipendente dal ts).
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    store.append(_p(5.0, "primo"))
    store.append(_p(5.0, "secondo"))
    rows, _ = store.read_from(0)
    assert [p.text for p in rows] == ["primo", "secondo"]


def test_read_from_on_missing_file_is_empty(tmp_path):
    store = PerceptionStore(tmp_path / "nuovo.jsonl")
    rows, pos = store.read_from(0)
    assert rows == []
    assert pos == 0


def test_reopened_store_tail_sees_previously_appended_rows(tmp_path):
    path = tmp_path / "perceptions.jsonl"
    s1 = PerceptionStore(path)
    for i in range(1, 4):
        s1.append(_p(float(i), f"m{i}"))
    reopened = PerceptionStore(path)
    assert [p.text for p in reopened.tail(2)] == ["m2", "m3"]
