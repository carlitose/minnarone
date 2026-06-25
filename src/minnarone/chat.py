"""Percezione di chat minima: testo -> `Perception(chat/msg)` nello store.

È la sorgente di percezione più semplice possibile: nessun modello ML, nessun
adapter di rete. Trasforma un input testuale (da stdin, file o test) in una
percezione di chat e la deposita nel `PerceptionStore`, da cui il resto del
loop legge. Le pipeline reali (audio, video) seguiranno la stessa forma negli
slice successivi.
"""

from __future__ import annotations

import time

from .perception import Perception, Source
from .store import PerceptionStore


class ChatPerceiver:
    """Trasforma messaggi di chat testuali in percezioni nello store."""

    def __init__(self, store: PerceptionStore) -> None:
        self._store = store

    def perceive(
        self, text: str, *, speaker: str | None = None, ts: float | None = None
    ) -> Perception:
        """Scrive `text` come `Perception(chat/msg)` nello store e la restituisce."""
        perception = Perception(
            ts=time.time() if ts is None else ts,
            source=Source.CHAT,
            type="msg",
            text=text,
            speaker=speaker,
        )
        self._store.append(perception)
        return perception
