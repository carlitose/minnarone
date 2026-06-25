"""Il Senser: trasforma percezioni in `Trigger` che fanno reagire l'agente.

Versione minima dello slice 01: a ogni `tick` legge le percezioni comparse
*dopo* l'ultimo tick e produce un `Trigger` per ogni messaggio di chat che
nomina l'agente. Il tick è veloce e idempotente: una percezione già vista non
rigenera un trigger.

L'idempotenza si appoggia a un *cursore di posizione* dello store (offset in
byte), non al `ts`: così due percezioni con lo stesso `ts` vengono entrambe
viste e nessuna menzione va persa. La menzione è riconosciuta con una regex a
confine di parola, per non scattare dentro token più grandi (es.
"minnaroneitalia", URL, hashtag).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .perception import Perception, Source
from .store import PerceptionStore


@dataclass(frozen=True, slots=True)
class Trigger:
    """Motivo per cui l'agente dovrebbe reagire ora.

    `reason` etichetta il tipo di trigger ("mention" in MVP); `perception` è la
    percezione che lo ha originato.
    """

    reason: str
    perception: Perception


class Senser:
    """Rileva menzioni del nome dell'agente nelle percezioni di chat."""

    def __init__(self, store: PerceptionStore, *, agent_name: str) -> None:
        self._store = store
        self._mention = re.compile(rf"\b{re.escape(agent_name)}\b", re.IGNORECASE)
        self._position = 0

    def tick(self) -> list[Trigger]:
        """Esamina le nuove percezioni e restituisce i trigger rilevati."""
        new, self._position = self._store.read_from(self._position)
        triggers: list[Trigger] = []
        for p in new:
            if p.source is Source.CHAT and self._mention.search(p.text):
                triggers.append(Trigger(reason="mention", perception=p))
        return triggers
