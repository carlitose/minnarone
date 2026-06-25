"""Interfaccia astratta delle sorgenti di percezione.

Un `SourceAdapter` si aggancia a una fonte (cattura a livello di sistema
operativo nell'MVP; connettori per-piattaforma in v2) e produce eventi grezzi
(`RawEvent`) che le pipeline di percezione trasformeranno in `Perception`.

L'interfaccia deve restare NEUTRA: nessun dettaglio specifico di Twitch, Zoom o
del SO deve trapelare qui, altrimenti i connettori v2 non potranno innestarsi
senza riscrivere il core.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RawEvent:
    """Dato grezzo emesso da un adapter, prima della trasformazione in testo.

    `channel` indica quale pipeline di percezione lo consumerà
    ("audio", "video", "chat", "event"). `payload` è opaco rispetto al core:
    il suo tipo concreto è un contratto fra adapter e perceiver dello stesso
    canale (es. un chunk PCM per l'audio, un frame per il video, un dict per la
    chat). `ts` è l'epoch di cattura in secondi.
    """

    channel: str
    payload: object
    ts: float


class SourceAdapter(ABC):
    """Ciclo di vita di una sorgente e stream di eventi grezzi."""

    @abstractmethod
    def channels(self) -> set[str]:
        """I canali forniti da questo adapter (sottoinsieme di audio/video/chat/event)."""

    @abstractmethod
    async def start(self) -> None:
        """Avvia la cattura. Idempotente: una seconda chiamata non deve raddoppiare."""

    @abstractmethod
    async def stop(self) -> None:
        """Ferma la cattura e rilascia le risorse. Sicura anche se non avviata."""

    @abstractmethod
    def events(self) -> AsyncIterator[RawEvent]:
        """Stream asincrono degli eventi grezzi catturati, finché non si chiama `stop`."""
