"""Il Summarizer: memoria a BREVE termine della sessione.

Osserva periodicamente le percezioni e produce, via LLM, un blocchetto di
riassunto di cosa è successo finora (stream, conversazioni con lo streamer,
chat). Il riassunto viene poi iniettato nella sezione DINAMICA del prompt (vedi
`PromptBuilder.build(..., summary=...)`), così l'agente fa riferimenti coerenti
a eventi precedenti senza rileggere tutto.

Il passo puro di riassunto (`summarize`) è separato dalla cadenza (`run`/`stop`),
così è testabile in isolamento. La cadenza rispecchia il pattern del Reactor: un
loop asincrono fermabile, un riassunto alla volta (niente pile-up di chiamate
sotto carico, perché `summarize` è awaited prima dello `sleep` successivo).

Robustezza: input vuoto -> riassunto neutro senza chiamare l'LLM; un `LLMError`
(timeout incluso) durante un giro periodico viene assorbito (si salta il ciclo)
e il riassunto precedente resta valido — mai un crash del loop, mai un summary a
metà.
"""

from __future__ import annotations

import asyncio

from .cadence import CadenceLoop
from .llm import LLMError, LLMProvider
from .perception import Perception, format_perception_line
from .store import PerceptionStore

# Quante percezioni recenti riassumere. La memoria a breve termine è una vista
# scorrevole della sessione, non l'intero log.
_DEFAULT_WINDOW = 50

_PROMPT_HEADER = (
    "Riassumi in modo conciso cosa è successo finora nella sessione "
    "(stream, conversazioni, chat). Tollera trascrizioni imperfette o rumorose. "
    "Scrivi solo il riassunto, in italiano.\n\n"
    "## EVENTI\n"
)


class Summarizer:
    """Produce e mantiene la memoria a breve termine della sessione."""

    def __init__(
        self,
        *,
        llm: LLMProvider,
        store: PerceptionStore,
        window: int = _DEFAULT_WINDOW,
    ) -> None:
        self._llm = llm
        self._store = store
        self._window = window
        self._summary = ""
        # La cadenza è delegata a un CadenceLoop interno (creato in `run()`,
        # quando si conosce l'intervallo). Lo skip-turno su LLMError — timeout
        # incluso, perché LLMTimeout è sottotipo di LLMError — è assorbito dal
        # loop via `swallow`, conservando il riassunto precedente.
        self._loop: CadenceLoop | None = None

    @property
    def current_summary(self) -> str:
        """L'ultimo riassunto prodotto (vuoto finché non se ne è prodotto uno)."""
        return self._summary

    def _build_prompt(self, perceptions: list[Perception]) -> str:
        body = "\n".join(format_perception_line(p) for p in perceptions)
        return f"{_PROMPT_HEADER}{body}\n"

    async def summarize(self) -> str:
        """Legge le percezioni recenti, chiede all'LLM un riassunto e lo memorizza.

        Store vuoto -> riassunto vuoto, nessuna chiamata LLM sprecata: il valore
        precedente resta. In caso di successo aggiorna `current_summary` e lo
        restituisce.
        """
        perceptions = self._store.tail(self._window)
        if not perceptions:
            return self._summary
        prompt = self._build_prompt(perceptions)
        result = await self._llm.complete(prompt)
        self._summary = result.message
        return self._summary

    async def run(self, *, interval: float = 30.0) -> None:
        """Esegue il riassunto su cadenza finché `stop()` non viene chiamato.

        Proxy sottile su un `CadenceLoop` interno. Un giro alla volta:
        `summarize` è awaited prima del prossimo `sleep`, così le chiamate non
        si accumulano sotto carico. Gli errori dell'LLM sono assorbiti dal loop
        (`swallow=(LLMError,)`): si salta il ciclo, si conserva il riassunto
        precedente, niente crash. `on_skip` è None → skip silenzioso come prima.
        """
        self._loop = CadenceLoop(
            self.summarize,
            interval,
            sleep=asyncio.sleep,
            swallow=(LLMError,),
        )
        await self._loop.run()

    def stop(self) -> None:
        """Richiede l'arresto del loop al prossimo giro."""
        if self._loop is not None:
            self._loop.stop()
