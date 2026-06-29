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
from collections import defaultdict, deque
from collections.abc import Iterable
from pathlib import Path
from threading import RLock

from .perception import Perception
from .perception_work import current_perception_work_cancelled

# Quante percezioni recenti tenere in memoria per servire `tail` senza
# riparsare il file. Limita l'uso di memoria indipendentemente dalla crescita
# del log; richieste più grandi ricadono sulla lettura da file.
_TAIL_CACHE_SIZE = 256


class PerceptionStore:
    """Store append-only di `Perception` su file JSONL."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._recent: deque[Perception] = deque(maxlen=_TAIL_CACHE_SIZE)
        self._recent_by_source_type: defaultdict[
            tuple[str, str], deque[Perception]
        ] = defaultdict(lambda: deque(maxlen=_TAIL_CACHE_SIZE))
        self._prime_recent()

    @property
    def path(self) -> Path:
        return self._path

    def _prime_recent(self) -> None:
        """Carica le ultime percezioni dal file nel deque (riapertura store)."""
        for perception in self._read_all():
            self._remember_recent(perception)

    def append(self, perception: Perception) -> None:
        """Aggiunge una percezione come singola riga JSON, durevole."""
        if current_perception_work_cancelled():
            return
        line = perception.to_json()
        with self._lock:
            if current_perception_work_cancelled():
                return
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            self._remember_recent(perception)

    @staticmethod
    def _parse_or_skip(line: str) -> Perception | None:
        """Decodifica una riga, saltando (con `None`) quelle corrotte.

        Il log è append-only: una singola riga illeggibile (scrittura parziale,
        corruzione su disco, formato vecchio) non deve abortire l'intera lettura.
        Lo skip è SILENZIOSO per scelta deliberata (il repo non usa logging):
        la resilienza alla corruzione parziale prevale sull'osservabilità del
        singolo skip.
        """
        try:
            return Perception.from_json(line)
        except ValueError:
            return None

    def _read_all(self) -> Iterable[Perception]:
        if not self._path.exists():
            return
        # Apertura in BINARIO + decode per-riga: byte non-UTF-8 su disco non
        # devono abortire la lettura (coerente con read_from). Una riga non
        # decodificabile viene saltata come una riga corrotta.
        with self._path.open("rb") as fh:
            for raw in fh:
                try:
                    line = raw.decode("utf-8").strip()
                except UnicodeDecodeError:
                    continue
                if not line:
                    continue
                perception = self._parse_or_skip(line)
                if perception is not None:
                    yield perception

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
                try:
                    line = raw.decode("utf-8").strip()
                except UnicodeDecodeError:
                    # Riga non decodificabile come UTF-8: saltala ma avanza il
                    # cursore, così non resta bloccata al prossimo giro.
                    continue
                if not line:
                    continue
                perception = self._parse_or_skip(line)
                if perception is not None:
                    perceptions.append(perception)
        return perceptions, consumed

    def tail(self, n: int) -> list[Perception]:
        """Le ultime `n` percezioni, in ordine cronologico di scrittura."""
        if n <= 0:
            return []
        with self._lock:
            if n <= len(self._recent):
                return list(self._recent)[-n:]
        # Richiesta più grande della cache: ricade sulla lettura da file.
        return list(self._read_all())[-n:]

    def tail_matching(
        self,
        n: int,
        *,
        source: str | None = None,
        type: str | None = None,  # noqa: A002 - domain field name.
    ) -> list[Perception]:
        """Le ultime `n` percezioni che corrispondono a source/type.

        Serve alle viste per-sorgente: una chat molto intensa non deve far
        sparire trascrizioni audio o caption video solo perché la coda globale
        è dominata da messaggi chat.
        """
        if n <= 0:
            return []
        with self._lock:
            recent_matches = [
                p for p in self._recent if _matches_perception(p, source, type)
            ]
            if len(recent_matches) >= n:
                return recent_matches[-n:]
            if source is not None and type is not None:
                keyed = list(self._recent_by_source_type[(source, type)])
                return keyed[-n:]
        return [
            p for p in self._read_all() if _matches_perception(p, source, type)
        ][-n:]

    def _remember_recent(self, perception: Perception) -> None:
        self._recent.append(perception)
        self._recent_by_source_type[
            (perception.source.value, perception.type)
        ].append(perception)


def _matches_perception(
    perception: Perception,
    source: str | None,
    type_: str | None,
) -> bool:
    if source is not None and perception.source.value != source:
        return False
    if type_ is not None and perception.type != type_:
        return False
    return True
