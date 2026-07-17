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
from .perception import Perception, Source
from .prompt_observation import prompt_observation_context
from .store import PerceptionStore

# Quante percezioni recenti riassumere. La memoria a breve termine è una vista
# scorrevole della sessione, non l'intero log.
_DEFAULT_WINDOW = 50

# Istruzione del "sintetizzatore": riassunto ROLLING/incrementale. Il testo
# core (istruzione, "Riassunto attuale:", "Eventi recenti:", "Aggiorna il
# riassunto.") è fedele alla trascrizione degli screenshot (ticket 01).
#
# RICOSTRUZIONE (best-effort): la riga che chiede di strutturare la risposta in
# STREAM / CONVERSAZIONI CON LO STREAMER / CONVERSAZIONI IN CHAT NON è confermata
# parola-per-parola dalla trascrizione (gli screenshot mostrano quelle
# sotto-sezioni nell'OUTPUT `[MEMORIA]`, ma non è certo che sia il PROMPT a
# dettarle). La aggiungiamo qui perché è ciò che riproduce l'output osservato;
# va riconfermata con uno screenshot ad alta risoluzione.
_PROMPT_INSTRUCTION = (
    "Sei un sintetizzatore. Mantieni un riassunto breve in italiano di come sta\n"
    "evolvendo la live: cosa fa e dice lo streamer, di cosa parla la chat, "
    "l'atmosfera.\n"
    "Integra i nuovi eventi, tieni cio' che e' ancora rilevante e scarta il vecchio.\n"
    "Solo il riassunto, niente preamboli.\n"
    "Struttura il riassunto in tre sotto-sezioni: STREAM (cosa succede nello "
    "stream),\n"
    "CONVERSAZIONI CON LO STREAMER (scambi con lo streamer), CONVERSAZIONI IN "
    "CHAT\n"
    "(con chi ha parlato minnarone e di cosa).\n"
)

# Placeholder neutro per il primissimo giro, quando non c'è ancora un riassunto
# precedente da reiniettare: evita di lasciare una riga vuota sotto
# "Riassunto attuale:".
_EMPTY_SUMMARY_PLACEHOLDER = "(ancora niente: e' l'inizio della sessione)"

# Ordine e intestazione dei gruppi "Eventi recenti", per fonte. Un gruppo senza
# eventi viene omesso del tutto (niente intestazione vuota).
_SOURCE_GROUPS: tuple[tuple[Source, str], ...] = (
    (Source.AUDIO, "STREAMER ha detto:"),
    (Source.VIDEO, "SCHERMO:"),
    (Source.CHAT, "CHAT:"),
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
        """Compone il prompt rolling: istruzione + riassunto precedente + eventi.

        Il riassunto precedente (`self._summary`) è reiniettato sotto
        "Riassunto attuale:", così il sintetizzatore AGGIORNA invece di rifare da
        zero; al primissimo giro (vuoto) si usa un placeholder neutro. Gli eventi
        recenti sono raggruppati per fonte (STREAMER/SCHERMO/CHAT); i gruppi
        senza eventi sono omessi.
        """
        previous = self._summary.strip() or _EMPTY_SUMMARY_PLACEHOLDER
        events = self._render_events(perceptions)
        return (
            f"{_PROMPT_INSTRUCTION}\n"
            f"Riassunto attuale:\n{previous}\n\n"
            f"Eventi recenti:\n{events}\n\n"
            "Aggiorna il riassunto.\n"
        )

    @staticmethod
    def _render_events(perceptions: list[Perception]) -> str:
        """Raggruppa le percezioni per fonte in blocchi STREAMER/SCHERMO/CHAT.

        Renderer DEDICATO del summarizer (non riusa `format_recent_line` né
        `format_perception_line`): ogni evento è una riga `- ...`. Per la CHAT si
        antepone lo speaker (`- <utente>: <testo>`), per audio/video basta il
        testo perché l'intestazione del gruppo già indica la fonte. Un gruppo
        senza eventi è omesso interamente.
        """
        blocks: list[str] = []
        for source, header in _SOURCE_GROUPS:
            group = [p for p in perceptions if p.source is source]
            if not group:
                continue
            lines = [Summarizer._render_event_line(p) for p in group]
            blocks.append(header + "\n" + "\n".join(lines))
        return "\n".join(blocks)

    @staticmethod
    def _render_event_line(p: Perception) -> str:
        if p.source is Source.CHAT:
            who = p.speaker if p.speaker else "anon"
            return f"- {who}: {p.text}"
        return f"- {p.text}"

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
        with prompt_observation_context("summarizer"):
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
