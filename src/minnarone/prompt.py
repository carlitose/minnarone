"""Il PromptBuilder: assembla il prompt di reazione in tre sezioni.

Struttura, dall'alto in basso:

1. **Prefisso stabile** (cacheable): identità (`soul`) e fatti permanenti
   (`facts`). Deve essere BYTE-IDENTICO tra build con lo stesso contesto
   stabile — niente timestamp né altri dati dinamici — così il prompt caching
   dei provider reali (slice 02) può riusarlo.
2. **Messaggi recenti**: la finestra di chat corrente.
3. **Situazione / trigger**: in coda, la parte più volatile (perché l'agente
   sta reagendo *adesso*).

Mettere il volatile in fondo massimizza il prefisso condiviso fra turni.
"""

from __future__ import annotations

from collections.abc import Sequence

from .memory import MemoryBlocks
from .perception import Perception
from .senser import Trigger


class PromptBuilder:
    """Costruisce il prompt da memoria stabile + messaggi recenti + trigger."""

    def __init__(self, blocks: MemoryBlocks) -> None:
        self._blocks = blocks

    def stable_prefix(self) -> str:
        """La parte cacheable del prompt: solo dati stabili (soul + facts)."""
        return (
            "## IDENTITÀ\n"
            f"{self._blocks.soul}\n\n"
            "## FATTI\n"
            f"{self._blocks.facts}\n"
        )

    @staticmethod
    def _format_message(p: Perception) -> str:
        who = p.speaker if p.speaker else "anon"
        return f"{who}: {p.text}"

    def build(self, *, recent: Sequence[Perception], trigger: Trigger) -> str:
        """Assembla il prompt completo per il turno corrente.

        La finestra recente fa da storia *precedente* il trigger: la percezione
        che ha innescato la reazione viene esclusa, perché è già renderizzata
        sotto SITUAZIONE (evita di duplicarla nel prompt).

        L'esclusione usa l'uguaglianza per VALORE (non l'identità): nel flusso
        live `trigger.perception` è parsata fresh dal file JSONL mentre `recent`
        proviene dal deque in memoria, quindi sono istanze diverse ma uguali.
        Un check `is` non escluderebbe nulla e duplicherebbe il messaggio.
        Nota: se la storia contenesse un messaggio legittimamente identico per
        valore al trigger, verrebbe anch'esso escluso; preferiamo la dedup del
        trigger (la resa in SITUAZIONE è quella canonica).
        """
        history = [p for p in recent if p != trigger.perception]
        recent_block = "\n".join(self._format_message(p) for p in history)
        situation = self._format_message(trigger.perception)
        return (
            f"{self.stable_prefix()}\n"
            "## CONVERSAZIONE RECENTE\n"
            f"{recent_block}\n\n"
            "## SITUAZIONE\n"
            f"Reagisci a questo messaggio ({trigger.reason}):\n"
            f"{situation}\n"
        )
