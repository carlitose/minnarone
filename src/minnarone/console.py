"""OutputRouter su console: stampa il messaggio dell'agente.

È l'implementazione di output dello slice 01: il canale pubblico è semplicemente
lo standard output. Whisper/TTS/azioni strutturate arriveranno in v2 dietro la
stessa interfaccia `OutputRouter`.
"""

from __future__ import annotations

import sys
from typing import TextIO

from .output import OutputMode, OutputRouter


class ConsoleOutputRouter(OutputRouter):
    """Instrada i messaggi stampandoli su uno stream di testo (default: stdout)."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream if stream is not None else sys.stdout

    async def route(self, message: str, mode: OutputMode) -> None:
        prefix = "[PUBLIC]" if mode is OutputMode.PUBLIC else "[PRIVATE]"
        print(f"{prefix} {message}", file=self._stream)
