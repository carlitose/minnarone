"""Contratto dati centrale: la `Perception`.

Una percezione è un singolo evento osservato, normalizzato in testo e con
timestamp. È l'unità di dato che attraversa ogni layer del sistema: la
percezione la *scrive*, la reazione la *legge* (via il perception store).

Questo modulo non deve dipendere da nessun'altra parte del framework: è il
giunto su cui tutto il resto si appoggia.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum


class Source(str, Enum):
    """Canale da cui proviene una percezione."""

    CHAT = "chat"
    AUDIO = "audio"
    VIDEO = "video"
    EVENT = "event"


# `type` ammessi per ciascun `source`. Volutamente estendibile: serve a
# rilevare errori grossolani, non a vincolare per sempre il vocabolario.
VALID_TYPES: dict[Source, frozenset[str]] = {
    Source.CHAT: frozenset({"msg"}),
    Source.AUDIO: frozenset({"speech"}),
    Source.VIDEO: frozenset({"caption"}),
    Source.EVENT: frozenset({"join", "leave", "reaction"}),
}


@dataclass(frozen=True, slots=True)
class Perception:
    """Un evento percepito, normalizzato in testo.

    Attributi:
        ts: epoch in secondi (float). Ordina le percezioni nel tempo.
        source: canale di provenienza.
        type: sottotipo dipendente da `source` (es. "msg", "speech", "caption").
        text: contenuto testuale della percezione.
        speaker: chi ha prodotto l'evento, se noto (chat/audio diarizzato).
    """

    ts: float
    source: Source
    type: str
    text: str
    speaker: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ts, (int, float)):
            raise ValueError(f"ts deve essere numerico, ricevuto {type(self.ts)!r}")
        if not isinstance(self.source, Source):
            raise ValueError(f"source non valido: {self.source!r}")
        if not isinstance(self.type, str) or not self.type:
            raise ValueError("type deve essere una stringa non vuota")
        valid = VALID_TYPES[self.source]
        if self.type not in valid:
            raise ValueError(
                f"type {self.type!r} non valido per source {self.source.value!r} "
                f"(ammessi: {sorted(valid)})"
            )
        if not isinstance(self.text, str):
            raise ValueError("text deve essere una stringa")
        if self.speaker is not None and not isinstance(self.speaker, str):
            raise ValueError("speaker deve essere una stringa o None")

    def to_json(self) -> str:
        """Serializza in una singola riga JSON (formato del perception store)."""
        payload: dict[str, object] = {
            "ts": self.ts,
            "source": self.source.value,
            "type": self.type,
            "text": self.text,
        }
        if self.speaker is not None:
            payload["speaker"] = self.speaker
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> "Perception":
        """Deserializza da una riga JSON. Inverso di `to_json`."""
        data = json.loads(line)
        try:
            source = Source(data["source"])
        except (KeyError, ValueError) as exc:
            raise ValueError(f"source mancante o non valido in {line!r}") from exc
        return cls(
            ts=data["ts"],
            source=source,
            type=data["type"],
            text=data["text"],
            speaker=data.get("speaker"),
        )


def format_perception_line(p: Perception) -> str:
    """Resa testuale canonica di una percezione: ``"<speaker>: <text>"``.

    Quando lo speaker è ignoto si usa ``"anon"``. Questa è l'UNICA fonte del
    formato riga: sia il PromptBuilder (sezione conversazione recente /
    situazione) sia il Summarizer (lista eventi) la usano, così la resa resta
    byte-identica fra i due.
    """
    who = p.speaker if p.speaker else "anon"
    return f"{who}: {p.text}"
