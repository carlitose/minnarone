"""App di riferimento "Minnarone": assembla l'SDK da un file di configurazione.

Questo è il capstone (slice 11): un UNICO punto che CABLA insieme i moduli già
implementati negli slice 00–10 a partire da una `Config`, e restituisce un
`Agent` eseguibile.

    PerceptionStore (giunto durevole)
        │
        ├─ SourceAdapter → dispatcher per canale → Perceiver (riempie lo store)
        ├─ Senser  (legge lo store; menzioni/finestre/idle/continuazione)
        ├─ Summarizer (memoria a breve termine via LLM)
        └─ Reactor (orchestratore):
               Senser → PromptBuilder(soul/facts + announce_ai) → LLMProvider
               → HumanLikeness → OutputRouter (per modalità)

`Agent.run()` fa girare CONCORRENTEMENTE tre coroutine sullo stesso store:
- il loop del Reactor (senso → reazione → output);
- il loop del Summarizer (rigenera periodicamente il riassunto, che il Reactor
  legge come `summary_provider`);
- la *pompa di percezione*: `async for event in adapter.events(): dispatch(event)`
  che instrada ogni `RawEvent` al perceiver del suo canale, riempiendo lo store.

Modalità come CONFIGURAZIONE, non due codebase (vedi `output.py`):
- `public`  → `ConsoleOutputRouter` operativo (canale pubblico).
- `private` → ACCETTATA in costruzione, ma instradata a
  `PrivateNotImplementedRouter` che segnala chiaramente "non implementato in
  MVP" SOLO quando si usa il percorso di output (non crasha al build).

Punti di estensione v2 PRESENTI ma INERTI:
- `disclosure.announce_ai` è l'unico cablato (coerente): fluisce nello stance
  del `PromptBuilder`. Default False = nessuna disclosure.
- `retention` e `auto_memory` sono LETTI/ACCETTATI ma non fanno nulla nell'MVP.

Testabilità: il `transport` HTTP dell'LLM è iniettabile (fake nei test, nessuna
rete) e lo `store_path` è derivabile/sovrascrivibile (nessun device, `tmp_path`
nei test). La `SourceAdapter` è INIETTABILE in `build_agent`: nei test si passa
un `FakeSourceAdapter` in-memory; live, il backend device (`os_capture`) +
i modelli audio/video restano il passo manuale documentato nel README.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .audio import AudioPerceiver
from .chat import ChatPerceiver
from .config import Config
from .console import ConsoleOutputRouter
from .human import HumanLikeness
from .llm import LLMProvider
from .memory import FileMemory, Memory
from .openrouter import Transport, build_provider
from .output import OutputMode, OutputRouter
from .prompt import PromptBuilder
from .reactor import Reactor
from .senser import Senser
from .source import RawEvent, SourceAdapter
from .store import PerceptionStore
from .summarizer import Summarizer
from .video import VideoPerceiver

# Una entry del dispatcher: data un `RawEvent`, lo trasforma in percezioni nello
# store. Una callable per canale ("chat"/"audio"/"video"), così aggiungere un
# canale è cablare una entry, non un ramo nel core.
PerceiveFn = Callable[[RawEvent], object]


class PrivateModeNotImplemented(NotImplementedError):
    """La modalità privata (whisper) non è implementata nell'MVP.

    Sollevata SOLO al momento dell'instradamento di un output, non in
    costruzione: la modalità privata è accettata e cablata (stesso motore), ma
    il canale di output dedicato arriva in v2 dietro `OutputRouter`.
    """


class PrivateNotImplementedRouter(OutputRouter):
    """`OutputRouter` per la modalità privata: segnala not-implemented in MVP.

    La costruzione NON crasha (la modalità è accettata e instradata qui), ma
    usare il percorso di output solleva un errore chiaro: il canale whisper/TTS
    arriverà in v2 dietro questa stessa interfaccia, senza forkare il codice.
    """

    async def route(self, message: str, mode: OutputMode) -> None:
        raise PrivateModeNotImplemented(
            "modalità 'private' (whisper) non implementata nell'MVP: "
            "il canale di output privato arriva in v2 dietro OutputRouter"
        )


def _chat_dispatch(perceiver: ChatPerceiver) -> PerceiveFn:
    """Adatta `ChatPerceiver` (testo) al contratto `RawEvent` → percezioni.

    Il payload di un `RawEvent` di canale "chat" è un dict opaco (contratto fra
    adapter e perceiver dello stesso canale): si estraggono `text` e l'opzionale
    `speaker`, usando il `ts` di cattura dell'evento. Un payload senza testo
    viene ignorato (nessuna percezione) anziché crashare la pompa.
    """

    def dispatch(event: RawEvent) -> object:
        payload = event.payload
        if isinstance(payload, dict):
            text = payload.get("text")
            speaker = payload.get("speaker")
        else:
            text = payload if isinstance(payload, str) else None
            speaker = None
        if not isinstance(text, str) or not text:
            return None
        return perceiver.perceive(
            text,
            speaker=speaker if isinstance(speaker, str) else None,
            ts=event.ts,
        )

    return dispatch


@dataclass(frozen=True, slots=True)
class Agent:
    """Handle eseguibile dell'agente assemblato.

    Espone i componenti cablati (per ispezione/osservabilità e test di wiring) e
    un `run` che avvia, CONCORRENTEMENTE: il loop di reazione, il loop del
    Summarizer e — se è stata iniettata una `SourceAdapter` — la pompa di
    percezione che instrada ogni `RawEvent` al perceiver del suo canale.
    """

    config: Config
    store: PerceptionStore
    memory: Memory
    prompt_builder: PromptBuilder
    llm: LLMProvider
    senser: Senser
    summarizer: Summarizer
    human: HumanLikeness
    router: OutputRouter
    reactor: Reactor
    # Pipeline di percezione iniettabili: l'adapter (sorgente di `RawEvent`) e il
    # dispatcher per-canale. AFK solo il canale "chat" è cablabile senza modelli;
    # "audio"/"video" compaiono solo se i loro backend sono iniettati.
    adapter: SourceAdapter | None = None
    perceivers: dict[str, PerceiveFn] = field(default_factory=dict)

    @property
    def mode(self) -> OutputMode:
        return self.config.mode

    def dispatch(self, event: RawEvent) -> object:
        """Instrada un `RawEvent` al perceiver del suo canale (se cablato).

        Canali senza perceiver configurato vengono SALTATI silenziosamente (es.
        "audio"/"video" senza backend iniettato): la pompa non crasha su un
        canale non gestito. Ritorna l'esito del perceiver (per i test), o None.
        """
        perceive = self.perceivers.get(event.channel)
        if perceive is None:
            return None
        return perceive(event)

    async def _pump_perceptions(self) -> None:
        """Consuma lo stream dell'adapter, instradando ogni evento al canale.

        Senza adapter è un no-op immediato (il loop live di cattura device è il
        passo manuale documentato). Con un adapter, rispetta `start()/stop()` e
        scorre `events()` finché lo stream non si esaurisce o non è cancellato.
        """
        adapter = self.adapter
        if adapter is None:
            return
        await adapter.start()
        try:
            async for event in adapter.events():
                self.dispatch(event)
        finally:
            await adapter.stop()

    async def run(self) -> None:
        """Avvia, CONCORRENTEMENTE, reazione + summarizer + pompa di percezione.

        Tre coroutine sullo stesso store, con arresto pulito:
        - il loop del Reactor (`interval=senser_interval`);
        - il loop del Summarizer (`interval=summarizer_interval`);
        - la pompa di percezione (`adapter.events()` → dispatcher per canale).

        La DURATA dipende dalla presenza di un adapter:

        - **Con adapter** (es. test, o una sorgente che termina): la pompa GUIDA.
          Quando lo stream è esaurito l'agente ha percepito tutto ciò che c'era;
          si lascia al Reactor un ultimo tick per reagire alle percezioni appena
          arrivate, poi si fermano i loop di Reactor e Summarizer.
        - **Senza adapter** (percorso live documentato: la cattura device è il
          passo manuale): la pompa è un no-op immediato, quindi GUIDA il loop del
          Reactor, che gira finché `reactor.stop()` — comportamento identico a
          prima del capstone, col Summarizer ora attivo in concorrenza.

        In entrambi i casi l'arresto è pulito: nessun task orfano, e una
        `CancelledError` (run() cancellato) ferma tutto e si propaga.
        """
        reactor_task = asyncio.create_task(
            self.reactor.run(interval=self.config.senser_interval)
        )
        summarizer_task = asyncio.create_task(
            self.summarizer.run(interval=self.config.summarizer_interval)
        )
        pump_task = asyncio.create_task(self._pump_perceptions())

        try:
            if self.adapter is not None:
                # La pompa guida la durata: attendi l'esaurimento dello stream,
                # poi un ultimo tick di reazione deterministico.
                await pump_task
                await self.reactor.run_once()
            else:
                # Nessuna sorgente: il loop di reazione guida (gira finché
                # `reactor.stop()`), col Summarizer attivo in concorrenza.
                await reactor_task
        finally:
            # Arresto pulito di tutti i loop, in ogni caso (anche su
            # cancellazione): nessun task orfano.
            self.reactor.stop()
            self.summarizer.stop()
            reactor_task.cancel()
            summarizer_task.cancel()
            pump_task.cancel()
            await asyncio.gather(
                reactor_task, summarizer_task, pump_task, return_exceptions=True
            )


def _build_router(mode: OutputMode) -> OutputRouter:
    """Seleziona l'OutputRouter dalla modalità (config, non un fork di codice)."""
    if mode is OutputMode.PUBLIC:
        return ConsoleOutputRouter()
    # private: accettata, ma il percorso di output segnala not-implemented.
    return PrivateNotImplementedRouter()


def _default_store_path(config: Config) -> Path:
    """Posizione di default dello store: accanto alla directory dei fatti.

    Lo store è il giunto durevole del loop; lo si colloca in modo deterministico
    vicino allo workspace dichiarato in config, così riavvii dell'agente
    riprendono lo stesso log. Sovrascrivibile via `build_agent(store_path=...)`.
    """
    return Path(config.facts_dir).resolve().parent / "perceptions.jsonl"


def build_agent(
    config: Config,
    *,
    transport: Transport | None = None,
    store_path: str | Path | None = None,
    router: OutputRouter | None = None,
    adapter: SourceAdapter | None = None,
    audio_perceiver: AudioPerceiver | None = None,
    video_perceiver: VideoPerceiver | None = None,
) -> Agent:
    """Compone e cabla TUTTI i moduli da una `Config`, restituendo un `Agent`.

    `transport` è iniettato nel provider LLM (fake nei test → nessuna rete).
    `store_path` sovrascrive la posizione dello store (default derivato dalla
    config); nei test si passa un path sotto `tmp_path`. `router` sovrascrive
    l'OutputRouter selezionato dalla modalità (per i test che catturano l'output);
    se None si usa il router della modalità (`public`/`private`).

    `adapter` è la `SourceAdapter` da cui la pompa di percezione legge i
    `RawEvent`. È INIETTABILE perché il backend device reale (`os_capture`) è
    differito (passo manuale live); nei test si passa un `FakeSourceAdapter`. Se
    None, `Agent.run()` non pompa percezioni (gira solo il motore di reazione +
    summarizer): è il percorso live documentato.

    Canali di percezione:
    - "chat" è SEMPRE cablato (nessun modello richiesto): `ChatPerceiver`.
    - "audio"/"video" sono cablati SOLO se il rispettivo perceiver è iniettato
      (richiedono backend VAD/ASR/VLM): senza, quei canali vengono saltati.

    Cablaggio:
    - `FileMemory(soul_path, facts_dir).load()` → `MemoryBlocks` →
      `PromptBuilder(blocks, announce_ai=config.disclosure.announce_ai)`.
    - `build_provider(config, transport)` → `LLMProvider` (grok/deepseek).
    - `Senser(store, agent_name=config.agent_name, idle_interval=...)`.
    - `Summarizer(llm, store)` → fornisce `current_summary` al Reactor.
    - `HumanLikeness()` come stadio finale del Reactor.
    - `OutputRouter` selezionato dalla modalità (`public`/`private`).
    - `Reactor(...)` che lega tutto insieme.
    """
    path = Path(store_path) if store_path is not None else _default_store_path(config)
    store = PerceptionStore(path)

    memory = FileMemory(soul_path=config.soul_path, facts_dir=config.facts_dir)
    blocks = memory.load()
    # announce_ai è l'UNICO punto v2 cablato (coerente): fluisce nello stance.
    prompt_builder = PromptBuilder(
        blocks, announce_ai=config.disclosure.announce_ai
    )

    llm = build_provider(config, transport=transport)

    senser = Senser(
        store,
        agent_name=config.agent_name,
        idle_interval=config.idle_interval,
    )

    summarizer = Summarizer(llm=llm, store=store)
    human = HumanLikeness()
    out_router = router if router is not None else _build_router(config.mode)

    reactor = Reactor(
        senser=senser,
        prompt_builder=prompt_builder,
        llm=llm,
        router=out_router,
        store=store,
        mode=config.mode,
        recent_window=config.recent_chat_window,
        human=human,
        # Il Reactor LEGGE il riassunto corrente (non possiede il loop del
        # Summarizer): la callable zero-arg punta a `current_summary`.
        summary_provider=lambda: summarizer.current_summary,
    )

    # Dispatcher di percezione per-canale. "chat" è sempre disponibile (nessun
    # modello). "audio"/"video" solo se il backend è iniettato.
    perceivers: dict[str, PerceiveFn] = {
        "chat": _chat_dispatch(ChatPerceiver(store)),
    }
    if audio_perceiver is not None:
        perceivers["audio"] = audio_perceiver.perceive_event
    if video_perceiver is not None:
        perceivers["video"] = video_perceiver.perceive_event

    # NB: `config.retention` e `config.auto_memory` sono ACCETTATI ma INERTI:
    # non vengono cablati ad alcun comportamento nell'MVP (punti v2).
    return Agent(
        config=config,
        store=store,
        memory=memory,
        prompt_builder=prompt_builder,
        llm=llm,
        senser=senser,
        summarizer=summarizer,
        human=human,
        router=out_router,
        reactor=reactor,
        adapter=adapter,
        perceivers=perceivers,
    )
