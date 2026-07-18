"""Test del PerceptionStore: append-only su perceptions.jsonl.

Verifica comportamento esterno: ordine per ts, durabilità riga-per-riga,
read_since filtra, tail restituisce gli ultimi N in ordine cronologico.
"""

from minnarone.perception import Perception, Source
from minnarone.store import _TAIL_CACHE_SIZE, PerceptionStore


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


def _write_corrupt_log(path) -> None:
    """Scrive un log con una riga corrotta fra due righe valide."""
    lines = [
        _p(1.0, "prima").to_json(),
        "{ questa riga e' corrotta",  # JSON malformato in mezzo
        _p(3.0, "ultima").to_json(),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_read_since_skips_corrupt_line(tmp_path):
    path = tmp_path / "perceptions.jsonl"
    _write_corrupt_log(path)
    store = PerceptionStore(path)
    assert [p.text for p in store.read_since(0.0)] == ["prima", "ultima"]


def test_tail_skips_corrupt_line(tmp_path):
    path = tmp_path / "perceptions.jsonl"
    _write_corrupt_log(path)
    store = PerceptionStore(path)
    # tail oltre la cache ricade sul file: deve comunque saltare la riga rotta.
    assert [p.text for p in store.tail(_TAIL_CACHE_SIZE + 1)] == ["prima", "ultima"]


def test_tail_matching_returns_recent_source_specific_perceptions(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    store.append(Perception(ts=1.0, source=Source.AUDIO, type="speech", text="audio"))
    store.append(Perception(ts=2.0, source=Source.VIDEO, type="caption", text="video"))
    for index in range(300):
        store.append(
            Perception(
                ts=3.0 + index,
                source=Source.CHAT,
                type="msg",
                text=f"chat {index}",
                speaker="alice",
            )
        )

    assert [p.text for p in store.tail_matching(1, source="audio", type="speech")] == [
        "audio"
    ]
    assert [p.text for p in store.tail_matching(1, source="video", type="caption")] == [
        "video"
    ]
    assert [p.text for p in store.tail_matching(2, source="chat", type="msg")] == [
        "chat 298",
        "chat 299",
    ]


def test_tail_matching_uses_source_cache_when_global_tail_is_busy(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    store.append(Perception(ts=1.0, source=Source.AUDIO, type="speech", text="audio"))
    for index in range(300):
        store.append(_p(2.0 + index, f"chat {index}"))

    def fail_read_all():
        raise AssertionError("tail_matching should not rescan the full log")

    store._read_all = fail_read_all

    assert [p.text for p in store.tail_matching(1, source="audio", type="speech")] == [
        "audio"
    ]


def test_read_from_skips_corrupt_line_and_advances_to_end(tmp_path):
    path = tmp_path / "perceptions.jsonl"
    _write_corrupt_log(path)
    store = PerceptionStore(path)
    rows, pos = store.read_from(0)
    assert [p.text for p in rows] == ["prima", "ultima"]
    # il cursore avanza fino alla fine, oltre la riga corrotta.
    assert pos == path.stat().st_size


def test_invalid_utf8_line_does_not_brick_reads_or_constructor(tmp_path):
    p = tmp_path / "perceptions.jsonl"
    # riga valida, riga con byte non-UTF-8, riga valida
    good1 = '{"ts": 1.0, "source": "chat", "type": "msg", "text": "prima"}\n'
    good2 = '{"ts": 2.0, "source": "chat", "type": "msg", "text": "dopo"}\n'
    with p.open("wb") as fh:
        fh.write(good1.encode("utf-8"))
        fh.write(b"\xff\xfe corrotta non-utf8\n")
        fh.write(good2.encode("utf-8"))

    # il costruttore non deve sollevare (prima brickava via _prime_recent)
    store = PerceptionStore(p)
    texts_since = [pc.text for pc in store.read_since(0.0)]
    assert texts_since == ["prima", "dopo"]  # salta la riga corrotta
    assert [pc.text for pc in store.tail(10)] == ["prima", "dopo"]
    rows, pos = store.read_from(0)
    assert [pc.text for pc in rows] == ["prima", "dopo"]
    assert pos == p.stat().st_size  # cursore a fine file
