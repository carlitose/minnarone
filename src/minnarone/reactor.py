"""Il Reactor: orchestratore del loop senso-reazione.

Lega insieme i moduli dello slice 01:

    Senser (legge dallo store) -> PromptBuilder -> LLMProvider -> OutputRouter

A ogni tick chiede al Senser i nuovi trigger; per ciascun trigger costruisce un
prompt con la conversazione recente (letta *dallo store*, non passata
direttamente), interroga l'LLM e instrada il messaggio risultante. Reagisce
SOLO quando un trigger scatta. Gli errori dell'LLM sono tradotti in "salta
turno" (EC03): non viene mai inviato un messaggio stale.
"""

from __future__ import annotations

import asyncio

from .llm import LLMError, LLMProvider
from .output import OutputMode, OutputRouter
from .prompt import PromptBuilder
from .senser import Senser
from .store import PerceptionStore

# Quante percezioni di chat recenti includere nel prompt.
_DEFAULT_RECENT_WINDOW = 15


class Reactor:
    """Esegue il loop asincrono che fa reagire l'agente ai trigger."""

    def __init__(
        self,
        *,
        senser: Senser,
        prompt_builder: PromptBuilder,
        llm: LLMProvider,
        router: OutputRouter,
        store: PerceptionStore,
        mode: OutputMode = OutputMode.PUBLIC,
        recent_window: int = _DEFAULT_RECENT_WINDOW,
    ) -> None:
        self._senser = senser
        self._prompt_builder = prompt_builder
        self._llm = llm
        self._router = router
        self._store = store
        self._mode = mode
        self._recent_window = recent_window
        self._running = False

    async def run_once(self) -> None:
        """Esegue un singolo tick: rileva trigger e reagisce a ciascuno."""
        triggers = self._senser.tick()
        if not triggers:
            return
        # Lo store non muta entro il tick: leggi la finestra recente una volta.
        recent = self._store.tail(self._recent_window)
        for trigger in triggers:
            prompt = self._prompt_builder.build(recent=recent, trigger=trigger)
            try:
                result = await self._llm.complete(prompt)
            except LLMError:
                # Salta-turno: nessun output stale (EC03).
                continue
            await self._router.route(result.message, self._mode)

    async def run(self, *, interval: float = 0.5) -> None:
        """Esegue il loop finché `stop()` non viene chiamato."""
        self._running = True
        while self._running:
            await self.run_once()
            await asyncio.sleep(interval)

    def stop(self) -> None:
        """Richiede l'arresto del loop al prossimo giro."""
        self._running = False
