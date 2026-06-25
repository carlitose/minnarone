"""Il PerceptionStore: spina dorsale append-only del loop.

Tutte le percezioni transitano da qui. La percezione le *scrive*, la reazione
le *legge*: il giunto è il file `perceptions.jsonl` (una riga JSON per
percezione), così il dato è durevole e ispezionabile fuori dal processo.

Durabilità: ogni `append` scrive una riga completa e la flussa su disco
(`flush` + `os.fsync`), in modo che un `tail` concorrente non perda righe e un
crash non lasci righe a metà.

Lettura incrementale: i lettori (il Senser) avanzano un *cursore di posizione*
opaco — un offset in byte nel file — anziché filtrare per `ts`. Così due
percezioni con lo stesso `ts` non si sovrascrivono e ogni tick legge solo le
righe nuove invece di riparsare l'intero file (vedi `read_from`).

`tail` evita di materializzare tutto il file a ogni chiamata mantenendo un
`deque` limitato delle ultime N percezioni; il file resta la fonte di verità
durevole, il deque è solo una vista in memoria del coda recente.
"""

from __future__ import annotations

import os
from collections import deque
from collections.abc import Iterable
from pathlib import Path

from .perception import Perception

# Quante percezioni recenti tenere in memoria per servire `tail` senza
# riparsare il file. Limita l'uso di memoria indipendentemente dalla crescita
# del log; richieste più grandi ricadono sulla lettura da file.
_TAIL_CACHE_SIZE = 256


class PerceptionStore:
    """Store append-only di `Perception` su file JSONL."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._recent: deque[Perception] = deque(maxlen=_TAIL_CACHE_SIZE)
        self._prime_recent()

    @property
    def path(self) -> Path:
        return self._path

    def _prime_recent(self) -> None:
        """Carica le ultime percezioni dal file nel deque (riapertura store)."""
        for perception in self._read_all():
            self._recent.append(perception)

    def append(self, perception: Perception) -> None:
        """Aggiunge una percezione come singola riga JSON, durevole."""
        line = perception.to_json()
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self._recent.append(perception)

    def _read_all(self) -> Iterable[Perception]:
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if line:
                    yield Perception.from_json(line)

    def read_since(self, ts: float) -> list[Perception]:
        """Percezioni con `ts` strettamente maggiore di `ts`, in ordine di file."""
        return [p for p in self._read_all() if p.ts > ts]

    def read_from(self, position: int) -> tuple[list[Perception], int]:
        """Percezioni a partire dall'offset `position`, con il nuovo offset.

        `position` è un cursore opaco (offset in byte) restituito da una
        precedente `read_from`; chi legge lo conserva e lo ripassa al tick
        successivo. La lettura è incrementale (seek + parse delle sole righe
        nuove) e indipendente dal `ts`: due percezioni con lo stesso `ts` sono
        entrambe lette. Solo le righe *complete* (terminate da `\\n`) vengono
        consumate; il cursore avanza fino alla fine dell'ultima riga completa,
        così una riga a metà scrittura viene ripresa al tick successivo.
        """
        if not self._path.exists():
            return [], position
        perceptions: list[Perception] = []
        with self._path.open("rb") as fh:
            fh.seek(position)
            consumed = position
            for raw in fh:
                if not raw.endswith(b"\n"):
                    # Riga incompleta: non consumarla, riprende al prossimo giro.
                    break
                consumed += len(raw)
                line = raw.decode("utf-8").strip()
                if line:
                    perceptions.append(Perception.from_json(line))
        return perceptions, consumed

    def tail(self, n: int) -> list[Perception]:
        """Le ultime `n` percezioni, in ordine cronologico di scrittura."""
        if n <= 0:
            return []
        if n <= len(self._recent):
            return list(self._recent)[-n:]
        # Richiesta più grande della cache: ricade sulla lettura da file.
        return list(self._read_all())[-n:]
