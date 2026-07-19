"""Base comune dei perceiver per-canale: il dispatch `RawEvent` -> percezione.

`AudioPerceiver` e `VideoPerceiver` condividono la stessa adattazione: dato un
`RawEvent`, scartano gli eventi di un altro canale, validano il tipo del payload
e delegano la trasformazione al metodo specifico già testato
(`perceive_chunk` / `perceive_frame`). Quella guardia ripetuta vive qui, una
volta sola; i perceiver concreti implementano solo `_perceive_payload`.

Modulo profondo e puro: nessuna dipendenza nuova, nessuna conoscenza del backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import ClassVar

from .perception import Perception
from .source import RawEvent


class EventPerceiver(ABC):
    """Possiede il dispatch per-canale + validazione payload + fold.

    Contratto (preservato dai perceiver concreti):

    * Un evento di canale diverso da `channel` viene ignorato -> lista vuota.
    * Un evento del canale giusto ma con payload non `payload_type` solleva
      `TypeError` (un payload del tipo sbagliato sullo stesso canale è un bug di
      cablaggio, non un evento da scartare silenziosamente).
    * Altrimenti delega a `_perceive_payload`, l'hook implementato dal concreto.

    Le sottoclassi dichiarano `channel` e `payload_type` come class var.
    """

    channel: ClassVar[str]
    payload_type: ClassVar[type]

    def perceive_event(self, event: RawEvent) -> list[Perception]:
        """Processa un `RawEvent` del canale di questo perceiver.

        Eventi di altri canali vengono ignorati (lista vuota); un payload del
        tipo sbagliato sul canale giusto è un errore di contratto (`TypeError`).
        """
        if event.channel != self.channel:
            return []
        payload = event.payload
        if not isinstance(payload, self.payload_type):
            raise TypeError(
                f"the payload of a {self.channel!r} RawEvent must be "
                f"{self.payload_type.__name__}; received {type(payload)!r}"
            )
        return self._perceive_payload(payload)

    def perceive_events(self, events: Iterable[RawEvent]) -> list[Perception]:
        """Processa una sequenza di `RawEvent`, concatenando le percezioni."""
        created: list[Perception] = []
        for event in events:
            created.extend(self.perceive_event(event))
        return created

    @abstractmethod
    def _perceive_payload(self, payload: object) -> list[Perception]:
        """Trasforma il payload (già validato come `payload_type`) in percezioni."""
