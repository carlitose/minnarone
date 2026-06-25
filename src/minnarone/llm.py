"""Interfaccia astratta del provider LLM di reazione.

Lo slice 01 userà un fake; lo slice 02 implementerà i provider reali
(Grok 4.3 / DeepSeek V4 Flash via OpenRouter). Gli errori sono modellati come
eccezioni: il Reactor le cattura e le traduce in "salta turno" (EC03), così non
viene mai inviato un messaggio stale.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class LLMResult:
    """Esito di una generazione riuscita."""

    message: str
    # Metadati opzionali (token, costo, quota in cache…): popolati dai provider
    # reali, ignorati dal core. Tenuti generici per non vincolare i provider.
    meta: dict[str, object] = field(default_factory=dict)


class LLMError(Exception):
    """Errore generico del provider. Il Reactor deve tradurlo in salto-turno."""


class LLMTimeout(LLMError):
    """Latenza oltre soglia. Sottotipo distinto per metriche/salto-turno (EC03)."""


class LLMProvider(ABC):
    """Trasforma un prompt in un messaggio."""

    @abstractmethod
    async def complete(self, prompt: str) -> LLMResult:
        """Genera un messaggio dal prompt.

        Solleva `LLMTimeout` se supera la soglia di latenza configurata, o
        `LLMError` per qualsiasi altro fallimento. Non deve mai restituire un
        risultato parziale silenzioso.
        """
