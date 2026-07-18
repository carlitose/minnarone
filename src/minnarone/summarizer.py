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
from .prompt_source import PromptSet, load_summarizer_prompt_set
from .store import PerceptionStore

# Quante percezioni recenti riassumere. La memoria a breve termine è una vista
# scorrevole della sessione, non l'intero log.
_DEFAULT_WINDOW = 50

# File del prompt-set che contiene il testo tunabile del summarizer (ticket 05):
# istruzione rolling, placeholder neutro, etichette di gruppo per fonte e
# intestazioni di scaffolding. Servito dal loader (`prompt_source`) con
# fail-fast; override per-file via `prompts_dir`.
_SUMMARIZER_FILE = "summarizer.md"

# Ordine dei gruppi "Eventi recenti" + CHIAVE dell'etichetta nel prompt-set. La
# MAPPATURA fonte→etichetta resta CABLATA qui (audio→streamer, video→schermo,
# chat→chat): solo il TESTO dell'etichetta è esternalizzato nel file. Un gruppo
# senza eventi viene omesso del tutto (niente intestazione vuota).
_SOURCE_LABEL_KEYS: tuple[tuple[Source, str], ...] = (
    (Source.AUDIO, "label_streamer"),
    (Source.VIDEO, "label_schermo"),
    (Source.CHAT, "label_chat"),
)


class Summarizer:
    """Produce e mantiene la memoria a breve termine della sessione."""

    def __init__(
        self,
        *,
        llm: LLMProvider,
        store: PerceptionStore,
        window: int = _DEFAULT_WINDOW,
        prompt_set: PromptSet | None = None,
    ) -> None:
        self._llm = llm
        self._store = store
        self._window = window
        # Prompt-set del summarizer (default impacchettati + override). Come per
        # `PromptBuilder`, se non iniettato si caricano SOLO i default nel wheel;
        # `app.py` inietta il set costruito da `config.prompts_dir`. La
        # validazione fail-fast avviene qui alla costruzione: un `summarizer.md`
        # malformato/incompleto solleva `PromptError` all'avvio, non a runtime.
        self._prompts = (
            prompt_set if prompt_set is not None else load_summarizer_prompt_set()
        )
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
        l'intestazione del riassunto corrente, così il sintetizzatore AGGIORNA
        invece di rifare da zero; al primissimo giro (vuoto) si usa il
        placeholder neutro. Testo (istruzione, intestazioni, placeholder) dal
        prompt-set. Gli eventi recenti sono raggruppati per fonte; i gruppi
        senza eventi sono omessi.
        """
        section = self._prompts.section
        previous = self._summary.strip() or section(
            _SUMMARIZER_FILE, "empty_placeholder"
        )
        events = self._render_events(perceptions)
        instruction = section(_SUMMARIZER_FILE, "instruction")
        current_header = section(_SUMMARIZER_FILE, "current_summary_header")
        events_header = section(_SUMMARIZER_FILE, "recent_events_header")
        update = section(_SUMMARIZER_FILE, "update_instruction")
        return (
            f"{instruction}\n\n"
            f"{current_header}\n{previous}\n\n"
            f"{events_header}\n{events}\n\n"
            f"{update}\n"
        )

    def _render_events(self, perceptions: list[Perception]) -> str:
        """Raggruppa le percezioni per fonte in blocchi STREAMER/SCHERMO/CHAT.

        Renderer DEDICATO del summarizer (non riusa `format_recent_line` né
        `format_perception_line`): ogni evento è una riga `- ...`. Per la CHAT si
        antepone lo speaker (`- <utente>: <testo>`), per audio/video basta il
        testo perché l'intestazione del gruppo già indica la fonte. Un gruppo
        senza eventi è omesso interamente. La mappa fonte→etichetta è cablata
        (`_SOURCE_LABEL_KEYS`); il testo dell'etichetta viene dal prompt-set.
        """
        blocks: list[str] = []
        for source, label_key in _SOURCE_LABEL_KEYS:
            group = [p for p in perceptions if p.source is source]
            if not group:
                continue
            header = self._prompts.section(_SUMMARIZER_FILE, label_key)
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
