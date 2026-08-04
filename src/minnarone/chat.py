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
from .source import RawEvent
from .store import PerceptionStore


class ChatPerceiver:
    """Trasforma messaggi di chat testuali in percezioni nello store."""

    def __init__(self, store: PerceptionStore) -> None:
        self._store = store

    def perceive(
        self,
        text: str,
        *,
        speaker: str | None = None,
        speaker_id: str | None = None,
        ts: float | None = None,
    ) -> Perception:
        """Scrive `text` come `Perception(chat/msg)` nello store e la restituisce."""
        perception = Perception(
            ts=time.time() if ts is None else ts,
            source=Source.CHAT,
            type="msg",
            text=text,
            speaker=speaker,
            speaker_id=speaker_id,
        )
        self._store.append(perception)
        return perception

    def perceive_event(self, event: RawEvent) -> Perception | None:
        """Scrive un `RawEvent(channel="chat")` come percezione, se valido.

        Il payload chat canonico è `{"text": str, "speaker": str | None}`.
        Per retrocompatibilità con i fake dell'MVP accetta anche un payload
        stringa come testo senza speaker. Eventi di altri canali o payload senza
        testo vengono ignorati.
        """
        if event.channel != "chat":
            return None
        payload = event.payload
        if isinstance(payload, dict):
            text = payload.get("text")
            speaker = payload.get("speaker")
            speaker_id = payload.get("author_channel_id")
        else:
            text = payload if isinstance(payload, str) else None
            speaker = None
            speaker_id = None
        if not isinstance(text, str) or not text:
            return None
        return self.perceive(
            text,
            speaker=speaker if isinstance(speaker, str) else None,
            speaker_id=speaker_id if isinstance(speaker_id, str) else None,
            ts=event.ts,
        )
