"""Interfaccia astratta della memoria a lungo termine.

`load()` fornisce i blocchi di memoria permanente (identità + fatti) che il
PromptBuilder inietta nella parte cacheable del prompt. `update()` è l'hook
per l'auto-aggiornamento agentico cross-sessione (v2): nel MVP la sua
implementazione di default è un NO-OP documentato, così il punto di estensione
esiste senza alterare il comportamento.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MemoryBlocks:
    """Blocchi di memoria permanente pronti per il prompt.

    `soul`: chi è l'agente (nome, età, gusti, background).
    `facts`: fatti su interlocutori/canale, concatenati in un unico blocco.
    """

    soul: str
    facts: str


@dataclass(frozen=True, slots=True)
class FactsDelta:
    """Aggiornamento proposto ai fatti (usato dall'auto-memoria v2).

    Tenuto minimale di proposito: in MVP non viene mai applicato.
    """

    entity: str
    text: str


class Memory(ABC):
    """Carica la memoria permanente; espone un hook di aggiornamento (v2)."""

    @abstractmethod
    def load(self) -> MemoryBlocks:
        """Carica `soul` e `facts` come blocchi di prompt.

        L'assenza di un file deve degradare con grazia (blocco vuoto), non
        sollevare eccezioni.
        """

    def update(self, delta: FactsDelta) -> None:
        """Hook v2 per l'auto-aggiornamento della memoria.

        Implementazione di default: NO-OP. Le sottoclassi MVP non lo
        sovrascrivono; l'auto-memoria v2 lo implementerà.
        """
        return None
