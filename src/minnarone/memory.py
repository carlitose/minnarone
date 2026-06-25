"""Interfaccia astratta della memoria a lungo termine.

`load()` fornisce i blocchi di memoria permanente (identità + fatti) che il
PromptBuilder inietta nella parte cacheable del prompt. `update()` è l'hook
per l'auto-aggiornamento agentico cross-sessione (v2): nel MVP la sua
implementazione di default è un NO-OP documentato, così il punto di estensione
esiste senza alterare il comportamento.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


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
        del delta
        return None


class FileMemory(Memory):
    """Memoria permanente caricata da file su disco.

    `soul` viene letta da un singolo file (`soul_path`); `facts` viene
    composta concatenando TUTTI i file presenti in una directory
    (`facts_dir`), in ordine deterministico (alfabetico per nome file), con
    una piccola intestazione per entità (il nome del file senza estensione)
    così i fatti restano riconducibili a chi riguardano.

    Degrado con grazia: un file `soul` mancante o una `facts_dir`
    mancante/vuota producono blocchi vuoti (`""`), MAI un'eccezione — la
    memoria è un contesto opzionale, non un prerequisito.

    `update()` resta il NO-OP ereditato dalla base (auto-memoria = v2).
    """

    def __init__(self, *, soul_path: str | Path, facts_dir: str | Path) -> None:
        self._soul_path = Path(soul_path)
        self._facts_dir = Path(facts_dir)

    def load(self) -> MemoryBlocks:
        return MemoryBlocks(soul=self._load_soul(), facts=self._load_facts())

    def _load_soul(self) -> str:
        try:
            return self._soul_path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            # File assente, non leggibile o non-UTF-8: blocco vuoto, non crash.
            return ""

    def _load_facts(self) -> str:
        try:
            files = sorted(
                p for p in self._facts_dir.iterdir() if p.is_file()
            )
        except OSError:
            # Directory assente o non leggibile: blocco vuoto, non crash.
            return ""

        chunks: list[str] = []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeDecodeError):
                # File non leggibile o non-UTF-8: salta questo, non abortire.
                continue
            if not text:
                continue
            chunks.append(f"### {path.stem}\n{text}")
        return "\n\n".join(chunks)
