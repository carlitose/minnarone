"""Interfaccia astratta del canale di output.

Lo stesso motore serve modalità diverse: `PUBLIC` (messaggio visibile a tutti,
come Minnarone su Twitch) e `PRIVATE` (whisper riservato all'operatore). La
differenza è una CONFIGURAZIONE, non due codebase. L'MVP implementa solo il
canale pubblico; whisper/TTS/azioni strutturate arrivano in v2 dietro questa
stessa interfaccia.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


class OutputMode(str, Enum):
    """Dove va l'output dell'agente."""

    PUBLIC = "public"
    PRIVATE = "private"


class OutputRouter(ABC):
    """Instrada un messaggio verso il canale appropriato per la modalità."""

    @abstractmethod
    async def route(self, message: str, mode: OutputMode) -> None:
        """Consegna `message` sul canale corrispondente a `mode`."""
