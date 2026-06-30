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
from collections import deque
from collections.abc import Awaitable, Callable

from .cadence import CadenceLoop
from .human import HumanLikeness
from .llm import LLMError, LLMProvider
from .original_chat_output import normalize_original_chat_response
from .output import CommentatorStyle, OutputMode, OutputRouter
from .perception import Perception, Source
from .prompt import ORIGINAL_CHAT_CONTEXT_SPECS, PromptBuilder
from .prompt_observation import prompt_observation_context
from .senser import Senser
from .store import PerceptionStore

# Quante percezioni di chat recenti includere nel prompt.
_DEFAULT_RECENT_WINDOW = 15

# Quanti messaggi propri recenti ricordare per il cancello di dedup
# (HumanLikeness). Piccola finestra scorrevole: basta per scartare i ricalchi
# immediati senza zavorrare la memoria.
_DEFAULT_SELF_HISTORY = 10


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
        summary_provider: Callable[[], str] | None = None,
        human: HumanLikeness | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        event_recorder=None,
    ) -> None:
        self._senser = senser
        self._prompt_builder = prompt_builder
        self._llm = llm
        self._router = router
        self._store = store
        self._mode = mode
        self._recent_window = recent_window
        # Stadio finale OPZIONALE prima dell'output: stima il typing delay, fa
        # dedup e interpreta `#end_conv`. Se None il comportamento è invariato
        # (slice 01): si instrada subito il messaggio dell'LLM. Lo sleep è
        # INIETTATO così il delay è testabile in modo deterministico e — per
        # design — non bloccante (await, non time.sleep).
        self._human = human
        self._sleep = sleep
        # Memoria scorrevole dei messaggi propri recenti, alimenta il cancello
        # di dedup di HumanLikeness. Vive qui (non nel Senser) perché serve solo
        # al filtro human-likeness; il Senser traccia il *tempo* dell'ultimo
        # messaggio (continuazione), non il testo.
        self._self_messages: deque[str] = deque(maxlen=_DEFAULT_SELF_HISTORY)
        # Fonte OPZIONALE della memoria a breve termine: una callable zero-arg che
        # restituisce il riassunto corrente (es. `summarizer.current_summary`).
        # Il Reactor la LEGGE soltanto al momento del build — non possiede né
        # avvia il ciclo del Summarizer (assemblaggio completo: issue 11). Se
        # None, il prompt non riceve alcun riassunto (comportamento invariato).
        self._summary_provider = summary_provider
        self._event_recorder = event_recorder
        # La cadenza del loop senso-reazione è delegata a un CadenceLoop interno
        # (creato in `run()`, quando si conosce l'intervallo). Lo skip-turno su
        # LLMError resta PER-TRIGGER dentro `run_once` (granularità più fine di
        # un ciclo), quindi il CadenceLoop non assorbe nulla.
        self._loop: CadenceLoop | None = None

    def recent_messages(self, n: int | None = None) -> list[str]:
        """Snapshot read-only degli ultimi messaggi instradati dall'agente.

        Vista in sola lettura della memoria scorrevole `_self_messages` (che il
        Reactor mantiene per il dedup). Serve alla dashboard di osservabilità:
        copia difensiva, non altera lo stato del Reactor. Con `n` restituisce
        solo gli ultimi `n`; senza, tutti quelli in memoria.
        """
        items = list(self._self_messages)
        if n is None:
            return items
        if n <= 0:
            return []
        return items[-n:]

    async def run_once(self) -> None:
        """Esegue un singolo tick: rileva trigger e reagisce a ciascuno."""
        triggers = self._senser.tick()
        if not triggers:
            return
        for trigger in triggers:
            self._record_trigger(trigger)
        # Lo store non muta entro il tick: leggi la finestra recente una volta.
        recent = self._recent_for_prompt()
        # Leggi il riassunto corrente (se c'è una fonte) una volta per tick.
        summary = self._summary_provider() if self._summary_provider else None
        for trigger in triggers:
            prompt = self._prompt_builder.build(
                recent=recent,
                trigger=trigger,
                summary=summary,
                self_messages=list(self._self_messages),
            )
            try:
                with prompt_observation_context(f"reactor:{trigger.kind}"):
                    result = await self._llm.complete(prompt)
            except LLMError:
                # Salta-turno: nessun output stale (EC03).
                continue
            await self._react(result.message, trigger)

    async def _react(self, message: str, trigger) -> None:
        """Stadio finale: applica HumanLikeness (se presente) poi instrada.

        Senza HumanLikeness il comportamento è quello dello slice 01: instrada
        subito il messaggio. Con HumanLikeness:

        - `#end_conv` chiude la finestra dell'interlocutore via il Senser e il
          sentinella NON esce come chat letterale;
        - un quasi-duplicato viene scartato (non instradato);
        - altrimenti si attende il typing delay (await dello sleep iniettato:
          non blocca il loop) e poi si instrada il testo ripulito.
        """
        if self._uses_original_chat_style():
            response = normalize_original_chat_response(message)
            await self._route_local_output(response.display_text)
            if response.message and not response.end_conversation:
                self._note_self_message(response.message)
            return

        if self._human is None:
            await self._route_and_note(message)
            return

        decision = self._human.process(message, list(self._self_messages))

        # `#end_conv`: chiudi la finestra corrispondente, qualunque sia l'esito
        # sull'invio del testo residuo.
        if decision.end_conv and trigger.interlocutor is not None:
            self._senser.close_window(trigger.interlocutor)

        if decision.drop:
            return

        if decision.delay > 0:
            # Attesa NON bloccante per design: await sullo sleep iniettato.
            await self._sleep(decision.delay)
        await self._route_and_note(decision.message)

    async def _route_and_note(self, message: str) -> None:
        """Instrada il messaggio, lo ricorda per il dedup e notifica il Senser."""
        await self._route_local_output(message)
        self._note_self_message(message)

    async def _route_local_output(self, message: str) -> None:
        """Instrada e registra il testo visibile localmente."""
        await self._router.route(message, self._mode)
        self._record_minnarone_output(message)

    def _note_self_message(self, message: str) -> None:
        """Ricorda un messaggio proprio effettivamente inviabile."""
        self._self_messages.append(message)
        # Notifica al Senser che l'agente ha appena parlato, così la
        # continuazione (UC03) funziona nel sistema assemblato. Si usa lo
        # STESSO clock del Senser (via `now()`) per restare deterministici.
        # Guardia `hasattr` per non rompere eventuali senser minimali/fake.
        if hasattr(self._senser, "note_agent_message") and hasattr(
            self._senser, "now"
        ):
            self._senser.note_agent_message(self._senser.now())

    async def run(self, *, interval: float = 0.5) -> None:
        """Esegue il loop finché `stop()` non viene chiamato.

        Proxy sottile su un `CadenceLoop` interno: a ogni giro esegue
        `run_once` poi attende `interval`. Lo skip-turno su LLMError vive in
        `run_once` (per-trigger), non qui.
        """
        self._loop = CadenceLoop(self.run_once, interval, sleep=asyncio.sleep)
        await self._loop.run()

    def stop(self) -> None:
        """Richiede l'arresto del loop al prossimo giro."""
        if self._loop is not None:
            self._loop.stop()

    def _record_trigger(self, trigger) -> None:
        if self._event_recorder is None:
            return
        try:
            self._event_recorder.record_trigger(trigger)
        except OSError:
            return

    def _record_minnarone_output(self, message: str) -> None:
        if self._event_recorder is None:
            return
        try:
            self._event_recorder.record_minnarone_output(message, self._mode)
        except OSError:
            return

    def _recent_for_prompt(self) -> list[Perception]:
        if not self._uses_original_chat_style():
            return self._store.tail(self._recent_window)

        recent: list[Perception] = []
        for spec in ORIGINAL_CHAT_CONTEXT_SPECS:
            recent.extend(self._tail_matching(spec.source, spec.type))
        return sorted(recent, key=lambda p: p.ts)

    def _tail_matching(self, source: Source, type_: str) -> list[Perception]:
        tail_matching = getattr(self._store, "tail_matching", None)
        if tail_matching is not None:
            return list(
                tail_matching(
                    self._recent_window,
                    source=source.value,
                    type=type_,
                )
            )
        return [
            p
            for p in self._store.tail(self._recent_window)
            if p.source is source and p.type == type_
        ]

    def _uses_original_chat_style(self) -> bool:
        return (
            getattr(self._prompt_builder, "commentator_style", None)
            is CommentatorStyle.ORIGINAL_CHAT
        )
