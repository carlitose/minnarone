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
  autorevole del `PromptBuilder`. Default False = niente annuncio proattivo,
  senza imporre una falsa negazione quando l'utente chiede direttamente.
- `retention` e `auto_memory` sono LETTI/ACCETTATI ma non fanno nulla nell'MVP.

Testabilità: il `transport` HTTP dell'LLM è iniettabile (fake nei test, nessuna
rete) e lo `store_path` è derivabile/sovrascrivibile (nessun device, `tmp_path`
nei test). La `SourceAdapter` è INIETTABILE in `build_agent`: nei test si passa
un `FakeSourceAdapter` in-memory; live, il backend device (`os_capture`) +
i modelli audio/video restano il passo manuale documentato nel README.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from .asr import AsrModelSetupError, FasterWhisperAsr
from .audio import AudioChunk, AudioPerceiver
from .capture import (
    Captured,
    make_device_capture_source,
    make_device_screen_capture_source,
)
from .chat import ChatPerceiver
from .config import (
    TWITCH_SEND_TOKEN_ENV_VAR,
    Config,
    ConfigError,
    OsCaptureConfig,
    TwitchSendMode,
)
from .console import ConsoleOutputRouter
from .dashboard import DashboardState, snapshot
from .human import HumanLikeness
from .llm import LLMProvider
from .memory import FileMemory, Memory
from .openrouter import Transport, build_provider
from .os_capture import OsCaptureAdapter
from .output import CommentatorStyle, OutputMode, OutputRouter
from .output_sink import MinnaroneOutputStream, TuiPrivateOutputRouter
from .perception_queue import (
    BoundedLocalPerceptionQueue,
    PerceptionQueueStats,
)
from .prompt import PromptBuilder
from .prompt_observation import ObservedLLMProvider, PromptObservationRecorder
from .prompt_source import load_prompt_set, load_summarizer_prompt_set
from .public_router import PublicOutputRouter
from .public_send import PublicSendMode, PublicSendPolicy, PublicTarget
from .reactor import Reactor
from .run_artifacts import RunSession
from .run_events import RunEventRecorder
from .senser import Senser
from .shadow_router import TwitchPublicOutputRouter
from .source import RawEvent, SourceAdapter
from .speaker import (
    EmbeddingSpeakerTagger,
    OnlineSpeakerClusterer,
    SherpaOnnxSpeakerEmbeddingBackend,
    SpeakerEmbeddingBackend,
    SpeakerEmbeddingConfig,
    SpeakerEmbeddingError,
)
from .store import PerceptionStore
from .summarizer import Summarizer
from .twitch_auth import TokenValidationTransport, TwitchLiveTokenGuard
from .twitch_chat import ConnectIRC, _connect_twitch_irc
from .twitch_chat_sender import TwitchChatSender
from .twitch_stream import TwitchStreamAdapter
from .twitch_video import TwitchVideoStreamOpener, VideoFrameDecoder
from .vad import StreamingVad, WebRtcVadDetector
from .video import Captioner, VideoFrame, VideoPerceiver
from .vlm import Qwen2VlCaptioner, QwenVlCaptionError, QwenVlConfig
from .vlm_llamacpp import LlamaCppCaptioner
from .youtube_chat import YouTubeApi, YouTubeLiveChatReader

# Una entry del dispatcher: data un `RawEvent`, lo trasforma in percezioni nello
# store. Una callable per canale ("chat"/"audio"/"video"), così aggiungere un
# canale è cablare una entry, non un ramo nel core.
PerceiveFn = Callable[[RawEvent], object | Awaitable[object]]


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
            "'private' mode (whisper) is not implemented in the MVP: "
            "the private output channel arrives in v2 behind OutputRouter"
        )


def _chat_dispatch(perceiver: ChatPerceiver) -> PerceiveFn:
    """Adatta `ChatPerceiver` (testo) al contratto `RawEvent` → percezioni.

    La semantica del payload chat vive in `ChatPerceiver.perceive_event`, così
    smoke Twitch e pompa dell'agente condividono lo stesso adattamento
    `RawEvent` -> `Perception`.
    """
    return perceiver.perceive_event


@dataclass(frozen=True, slots=True)
class Agent:
    """Handle eseguibile dell'agente assemblato.

    Espone i componenti cablati (per ispezione/osservabilità e test di wiring) e
    un `run` che avvia, CONCORRENTEMENTE: N loop di reazione (uno per profilo
    commentatore attivo), il loop del Summarizer e — se è stata iniettata una
    `SourceAdapter` — la pompa di percezione che instrada ogni `RawEvent` al
    perceiver del suo canale.

    **Multi-Reactor (issue 11):** ogni profilo attivo in
    ``config.commentator.profiles`` genera il proprio Reactor con Senser,
    PromptBuilder e OutputRouter dedicati; store, Summarizer e LLMProvider
    restano condivisi. ``reactors`` è la lista completa; ``reactor``,
    ``senser`` e ``prompt_builder`` puntano al *primo* Reactor per
    compatibilità con il codice e i test precedenti.
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
    # Multi-Reactor: lista di TUTTI i Reactor assemblati (uno per profilo
    # commentatore attivo). Può essere vuota (zero profili → solo pump +
    # summarizer). ``reactor`` sopra è il PRIMO elemento, per backward compat.
    reactors: list[Reactor] = field(default_factory=list)
    # Pipeline di percezione iniettabili: l'adapter (sorgente di `RawEvent`) e il
    # dispatcher per-canale. AFK solo il canale "chat" è cablabile senza modelli;
    # "audio"/"video" compaiono solo se i loro backend sono iniettati.
    adapter: SourceAdapter | None = None
    perceivers: dict[str, PerceiveFn] = field(default_factory=dict)
    # Audio/video passano da una queue bounded quando hanno backend iniettati;
    # chat resta diretta per non essere penalizzata da ASR/VLM lenti.
    perception_queue: BoundedLocalPerceptionQueue | None = None
    run_session: RunSession | None = None
    prompt_recorder: PromptObservationRecorder = field(
        default_factory=PromptObservationRecorder
    )
    minnarone_output: MinnaroneOutputStream | None = None
    output_streams: dict[CommentatorStyle, MinnaroneOutputStream] = field(
        default_factory=dict
    )
    speaker_diagnostics: object | None = None
    video_diagnostics: object | None = None
    send_policy: object | None = None
    sender: object | None = None
    token_guard: TwitchLiveTokenGuard | None = None

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

    def perception_queue_stats(self) -> PerceptionQueueStats:
        """Snapshot diagnostico della queue audio/video, se configurata."""
        if self.perception_queue is None:
            return PerceptionQueueStats(channels={})
        return self.perception_queue.stats()

    def observability_snapshot(self) -> DashboardState:
        """Read-only local perception diagnostics for dashboard/debug output."""
        channel = None
        started_at = None
        if self.run_session is not None:
            channel = self.run_session.channel
            started_at = self.run_session.started_at
        elif self.config.twitch is not None:
            channel = self.config.twitch.channel
        elif self.config.youtube is not None:
            channel = self.config.youtube.video_id
        return snapshot(
            store=self.store,
            senser=self.senser,
            reactor=self.reactor,
            minnarone_output=self.minnarone_output,
            output_streams=self.output_streams or None,
            perception_queue=self.perception_queue,
            speaker_tagger=self.speaker_diagnostics,
            video_perceiver=self.video_diagnostics,
            adapter=self.adapter,
            prompt_recorder=self.prompt_recorder,
            summarizer=self.summarizer,
            send_policy=self.send_policy,
            channel=channel,
            started_at=started_at,
        )

    async def _pump_perceptions(self) -> None:
        """Consuma lo stream dell'adapter, instradando ogni evento al canale.

        Senza adapter è un no-op immediato (il loop live di cattura device è il
        passo manuale documentato). Con un adapter, rispetta `start()/stop()` e
        scorre `events()` finché lo stream non si esaurisce o non è cancellato.
        """
        adapter = self.adapter
        if adapter is None:
            return
        queue = self.perception_queue
        if queue is not None:
            await queue.start()
        try:
            await adapter.start()
            try:
                async for event in adapter.events():
                    if queue is not None and queue.handles(event.channel):
                        queue.submit(event)
                    else:
                        self.dispatch(event)
            finally:
                await adapter.stop()
        finally:
            if queue is not None:
                await queue.stop()

    async def run(self) -> None:
        """Avvia, CONCORRENTEMENTE, N reazioni + summarizer + pompa di percezione.

        N+2 coroutine sullo stesso store, con arresto pulito:
        - N loop di Reactor (uno per profilo attivo, `interval=senser_interval`);
        - il loop del Summarizer (`interval=summarizer_interval`);
        - la pompa di percezione (`adapter.events()` → dispatcher per canale).

        La DURATA dipende dalla presenza di un adapter:

        - **Con adapter** (es. test, o una sorgente che termina): la pompa GUIDA.
          Quando lo stream è esaurito l'agente ha percepito tutto ciò che c'era;
          si lascia a ciascun Reactor un ultimo tick per reagire alle percezioni
          appena arrivate, poi si fermano tutti i loop.
        - **Senza adapter** (percorso live documentato: la cattura device è il
          passo manuale): la pompa è un no-op immediato, quindi GUIDANO i loop
          dei Reactor, che girano finché `reactor.stop()` — il primo che termina
          avvia lo shutdown di tutti gli altri.
        - **Zero Reactor** (zero profili): solo pump + summarizer.

        In tutti i casi l'arresto è pulito: nessun task orfano, e una
        `CancelledError` (run() cancellato) ferma tutto e si propaga.

        Il sender (se presente) viene avviato prima dei task e fermato nel
        finally; i fallimenti di stop vengono riportati come gli altri errori
        di shutdown dell'adapter, mai inghiottiti.

        In live, il token guard valida prima dell'avvio e poi alla prima deadline
        tra limite orario e scadenza OAuth con margine. Le deadline sono ancorate
        all'inizio/alla deadline precedente, quindi la latenza HTTP non causa
        drift; token già nel margine falliscono chiusi. Una revoca read ha
        priorità sul tick finale della pompa e arresta/disarma la run; una revoca
        send ferma il sender ma lascia la run operativa in shadow.
        """
        send_enabled = True
        if self.token_guard is not None:
            send_enabled = await self.token_guard.validate_startup()
            if not send_enabled:
                self._disable_live_send()

        if self.sender is not None and send_enabled:
            await self.sender.start()

        reactor_tasks = [
            asyncio.create_task(r.run(interval=self.config.senser_interval))
            for r in self.reactors
        ]
        summarizer_task = asyncio.create_task(
            self.summarizer.run(interval=self.config.summarizer_interval)
        )
        pump_task = asyncio.create_task(self._pump_perceptions())
        token_guard_task = (
            asyncio.create_task(
                self.token_guard.monitor(on_send_invalid=self._disable_live_send_async)
            )
            if self.token_guard is not None
            else None
        )

        try:
            if self.adapter is not None:
                # La pompa guida la durata: attendi l'esaurimento dello stream,
                # poi un ultimo tick di reazione deterministico per ogni Reactor.
                drivers = [pump_task]
                if token_guard_task is not None:
                    drivers.append(token_guard_task)
                done, _pending = await asyncio.wait(
                    drivers, return_when=asyncio.FIRST_COMPLETED
                )
                guard_finished = (
                    token_guard_task is not None and token_guard_task in done
                )
                if guard_finished:
                    self._disable_live_send()
                    await token_guard_task
                elif pump_task in done:
                    for r in self.reactors:
                        await r.run_once()
            else:
                # Nessuna sorgente: i loop di reazione guidano (girano finché
                # `reactor.stop()`), col Summarizer attivo in concorrenza.
                # Con N Reactor, il primo che termina avvia lo shutdown di tutti.
                # Con zero Reactor, niente da attendere (pump + summarizer only).
                drivers = list(reactor_tasks) or [summarizer_task]
                if token_guard_task is not None:
                    drivers.append(token_guard_task)
                done, _pending = await asyncio.wait(
                    drivers, return_when=asyncio.FIRST_COMPLETED
                )
                if token_guard_task is not None and token_guard_task in done:
                    self._disable_live_send()
                    await token_guard_task
        finally:
            # Arresto pulito di tutti i loop, in ogni caso (anche su
            # cancellazione): nessun task orfano.
            for r in self.reactors:
                r.stop()
            self.summarizer.stop()
            for task in reactor_tasks:
                task.cancel()
            summarizer_task.cancel()
            pump_task.cancel()
            if token_guard_task is not None:
                token_guard_task.cancel()
            # Stop sender before gathering child results; capture its error
            # so it can be reported alongside other shutdown failures.
            sender_error: BaseException | None = None
            if self.sender is not None:
                try:
                    await self.sender.stop()
                except BaseException as exc:
                    if isinstance(exc, asyncio.CancelledError):
                        sender_error = None
                    else:
                        sender_error = exc
            child_tasks = [*reactor_tasks, summarizer_task, pump_task]
            if token_guard_task is not None:
                child_tasks.append(token_guard_task)
            results = await asyncio.gather(*child_tasks, return_exceptions=True)
            errors = _unexpected_shutdown_errors(results)
            if sender_error is not None:
                errors.append(sender_error)
            if errors:
                _raise_shutdown_errors(errors)

    def _disable_live_send(self) -> None:
        policy = self.send_policy
        disable = getattr(policy, "disable_live", None)
        if callable(disable):
            disable()

    async def _disable_live_send_async(self) -> None:
        self._disable_live_send()
        sender = self.sender
        stop = getattr(sender, "stop", None)
        if callable(stop):
            await stop()


def _unexpected_shutdown_errors(results: list[object]) -> list[BaseException]:
    """Return child-task shutdown failures, ignoring expected cancellations."""
    errors: list[BaseException] = []
    for result in results:
        if result is None or isinstance(result, asyncio.CancelledError):
            continue
        if isinstance(result, BaseException):
            errors.append(result)
    return errors


def _raise_shutdown_errors(errors: list[BaseException]) -> None:
    if len(errors) == 1:
        raise errors[0]
    raise BaseExceptionGroup("agent shutdown failures", errors)


def _build_router(
    mode: OutputMode,
    *,
    commentator_style: CommentatorStyle | None = None,
    send_config: object | None = None,
    channel: str | None = None,
    target: PublicTarget | None = None,
    event_recorder: object | None = None,
    clock: Callable[[], float] | None = None,
    sender: object | None = None,
    echo: bool = True,
) -> tuple[OutputRouter, PublicSendPolicy | None]:
    """Seleziona l'OutputRouter dalla modalità (config, non un fork di codice).

    Returns (router, send_policy) where send_policy is non-None only when
    the send path is active. `echo=False` spegne la stampa dei marcatori su
    stdout del router pubblico: lo si usa quando il router è avvolto dal
    TuiPrivateOutputRouter (il display è del pannello TUI, non di stdout).
    """
    if mode is OutputMode.PUBLIC:
        if send_config is not None and (
            target is not None or send_config.mode is not PublicSendMode.OFF
        ):
            import time

            policy = PublicSendPolicy(
                send_config,
                clock=clock if clock is not None else time.monotonic,
                live_capability=sender is not None,
            )
            if target is not None:
                router = PublicOutputRouter(
                    policy=policy,
                    target=target,
                    event_recorder=event_recorder,
                    sender=sender,
                    echo=echo,
                )
            else:
                router = TwitchPublicOutputRouter(
                    policy=policy,
                    channel=channel or "",
                    event_recorder=event_recorder,
                    sender=sender,
                    echo=echo,
                )
            return router, policy
        return ConsoleOutputRouter(), None
    if commentator_style is not None:
        return ConsoleOutputRouter(), None
    # private: accettata, ma il percorso di output segnala not-implemented.
    return PrivateNotImplementedRouter(), None


def _default_store_path(config: Config) -> Path:
    """Posizione di default dello store: accanto alla directory dei fatti.

    Lo store è il giunto durevole del loop; lo si colloca in modo deterministico
    vicino allo workspace dichiarato in config, così riavvii dell'agente
    riprendono lo stesso log. Sovrascrivibile via `build_agent(store_path=...)`.
    """
    return Path(config.facts_dir).resolve().parent / "perceptions.jsonl"


def _twitch_token_is_effectively_empty(value: str | None) -> bool:
    """True se il token è assente o è solo il prefisso `oauth:` senza contenuto.

    Controllo offline: non valida che Twitch accetti il token, solo che ci sia
    davvero qualcosa dopo l'eventuale prefisso `oauth:` (il footgun classico è
    lasciare `TWITCH_OAUTH_TOKEN=oauth:` vuoto). Il valore non viene mai
    propagato in errori/log.
    """
    text = (value or "").strip()
    if text.lower().startswith("oauth:"):
        text = text[len("oauth:") :].strip()
    return not text


def _required_twitch_chat_credentials() -> tuple[str, str]:
    missing: list[str] = []
    if not (os.environ.get("TWITCH_BOT_USERNAME") or "").strip():
        missing.append("TWITCH_BOT_USERNAME")
    if _twitch_token_is_effectively_empty(os.environ.get("TWITCH_OAUTH_TOKEN")):
        missing.append("TWITCH_OAUTH_TOKEN")
    if missing:
        raise ConfigError(
            "missing or empty Twitch chat credentials: set "
            + ", ".join(missing)
            + " (the token must contain a value, not only the prefix)"
        )
    return os.environ["TWITCH_BOT_USERNAME"], os.environ["TWITCH_OAUTH_TOKEN"]


def _required_twitch_send_credentials() -> None:
    """Gate fail-fast di `twitch.send.mode: live`: token di scrittura presente.

    Della variabile d'ambiente si verifica solo la PRESENZA: il valore non deve
    mai finire in messaggi d'errore, log o artefatti. Il controllo vive nel
    build (non nello schema di config) così `Config.load` resta puro rispetto
    all'ambiente, mentre `--check` — che costruisce l'agente — fallisce subito.
    """
    # Un token di soli spazi o solo prefisso `oauth:` è assente a tutti gli
    # effetti; il valore serve solo al controllo e non viene mai propagato.
    if _twitch_token_is_effectively_empty(os.environ.get(TWITCH_SEND_TOKEN_ENV_VAR)):
        raise ConfigError(
            "missing or empty Twitch send credentials: export "
            f"{TWITCH_SEND_TOKEN_ENV_VAR} (a Twitch token with write scope, "
            "separate from the read token, with a real value and not only "
            "the prefix)"
        )


def _required_youtube_api_key() -> str:
    """Return the read-only API key without ever including it in diagnostics."""

    value = os.environ.get("YOUTUBE_API_KEY")
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(
            "missing or empty YouTube read credential: set YOUTUBE_API_KEY "
            "outside YAML; OAuth/write credentials are not used"
        )
    return value


def _require_media_perceiver(
    *, enabled: bool, perceiver: object | None, channel_key: str
) -> None:
    """Coerenza canale media: abilitato ma senza perceiver → ConfigError chiaro.

    Fattorizza il controllo che sia Twitch sia os_capture applicano ai canali
    "audio"/"video": se il canale è attivo in config ma il suo perceiver non è
    stato costruito/iniettato, il wiring non può instradare le percezioni e lo
    segnala subito (specularmente a come Twitch controlla le credenziali chat).
    """
    if enabled and perceiver is None:
        raise ConfigError(
            f"{channel_key} requires a local backend that is not wired into the "
            f"main runtime: inject it or disable the channel"
        )


def _lazy_device_audio_source(config: OsCaptureConfig) -> Captured:
    """Sorgente device audio LAZY: apre soundcard SOLO alla prima iterazione.

    Il backend reale (`make_device_capture_source`) NON è invocato al build né
    al `--check`: lo si chiama dentro il generatore async, così l'hardware si
    apre soltanto quando la pompa inizia a iterare dentro `start()`.
    """

    async def _source() -> AsyncIterator[AudioChunk]:
        async for chunk in make_device_capture_source(
            source_label="system", chunk_seconds=config.audio_chunk_seconds
        ):
            yield chunk

    return _source()


def _lazy_device_video_source(config: OsCaptureConfig) -> Captured:
    """Sorgente device schermo LAZY: apre mss/PyAV SOLO alla prima iterazione.

    Come per l'audio, `make_device_screen_capture_source` è invocato dentro il
    generatore async: nessun device né dipendenza di visione toccati al build.
    """

    async def _source() -> AsyncIterator[VideoFrame]:
        async for frame in make_device_screen_capture_source(
            monitor=config.monitor, source_label="screen", fps=config.video_fps
        ):
            yield frame

    return _source()


def _configured_adapter(
    config: Config,
    *,
    twitch_chat_connect: ConnectIRC | None = None,
    audio_perceiver: AudioPerceiver | None = None,
    video_perceiver: VideoPerceiver | None = None,
    video_stream_opener: TwitchVideoStreamOpener | None = None,
    video_frame_decoder: VideoFrameDecoder | None = None,
    os_capture_audio_source: Captured | None = None,
    os_capture_video_source: Captured | None = None,
    youtube_api: YouTubeApi | None = None,
) -> SourceAdapter | None:
    """Costruisce l'adapter runtime dichiarato in config, se oggi operativo."""
    if config.adapter == "os_capture" and config.os_capture is not None:
        return _configured_os_capture_adapter(
            config.os_capture,
            audio_perceiver=audio_perceiver,
            video_perceiver=video_perceiver,
            os_capture_audio_source=os_capture_audio_source,
            os_capture_video_source=os_capture_video_source,
        )
    if config.adapter == "youtube" and config.youtube is not None:
        youtube = config.youtube
        return YouTubeLiveChatReader(
            video_id=youtube.video_id,
            api_key=_required_youtube_api_key(),
            api=youtube_api,
            max_results=youtube.max_results,
            max_retries=youtube.max_retries,
            retry_base_seconds=youtube.retry_base_seconds,
            retry_max_seconds=youtube.retry_max_seconds,
            dedup_capacity=youtube.dedup_capacity,
            request_timeout_seconds=youtube.request_timeout_seconds,
        )
    if config.adapter != "twitch" or config.twitch is None:
        return None
    _require_media_perceiver(
        enabled=config.twitch.audio,
        perceiver=audio_perceiver,
        channel_key="twitch.audio",
    )
    _require_media_perceiver(
        enabled=config.twitch.video,
        perceiver=video_perceiver,
        channel_key="twitch.video",
    )
    username: str | None = None
    oauth_token: str | None = None
    if config.twitch.chat:
        username, oauth_token = _required_twitch_chat_credentials()
    return TwitchStreamAdapter(
        channel=config.twitch.channel,
        quality=config.twitch.quality,
        chat=config.twitch.chat,
        audio=config.twitch.audio,
        video=config.twitch.video,
        audio_chunk_seconds=config.twitch.audio_chunk_seconds,
        video_fps=config.twitch.video_fps,
        username=username,
        oauth_token=oauth_token,
        chat_connect=twitch_chat_connect,
        video_stream_opener=video_stream_opener,
        video_frame_decoder=video_frame_decoder,
    )


def _configured_os_capture_adapter(
    os_capture: OsCaptureConfig,
    *,
    audio_perceiver: AudioPerceiver | None,
    video_perceiver: VideoPerceiver | None,
    os_capture_audio_source: Captured | None,
    os_capture_video_source: Captured | None,
) -> OsCaptureAdapter:
    """Compone l'`OsCaptureAdapter` dai canali abilitati, con sorgenti lazy.

    Per ogni canale attivo serve il rispettivo perceiver (già costruito riusando
    gli helper del path Twitch); se manca è un errore di coerenza. Le sorgenti
    device sono LAZY quando non iniettate: i test passano liste in-memory, il
    runtime live differisce l'apertura di soundcard/mss alla prima iterazione,
    così build e `--check` non toccano hardware.
    """
    audio_source: Captured | None = None
    if os_capture.audio:
        _require_media_perceiver(
            enabled=True, perceiver=audio_perceiver, channel_key="os_capture.audio"
        )
        audio_source = (
            os_capture_audio_source
            if os_capture_audio_source is not None
            else _lazy_device_audio_source(os_capture)
        )
    video_source: Captured | None = None
    if os_capture.video:
        _require_media_perceiver(
            enabled=True, perceiver=video_perceiver, channel_key="os_capture.video"
        )
        video_source = (
            os_capture_video_source
            if os_capture_video_source is not None
            else _lazy_device_video_source(os_capture)
        )
    return OsCaptureAdapter(
        os_capture,
        audio_source=audio_source,
        video_source=video_source,
    )


def _build_default_audio_perceiver(
    config: Config,
    store: PerceptionStore,
    *,
    asr_model_factory: Callable[..., object] | None = None,
    vad_detector: object | None = None,
    speaker_embedding_factory: Callable[
        [SpeakerEmbeddingConfig], SpeakerEmbeddingBackend
    ]
    | None = None,
    channel_label: str = "twitch.audio",
) -> AudioPerceiver:
    """Build the local audio path (VAD + ASR + speaker) for the given channel.

    Condiviso da Twitch e os_capture: `channel_label` compare nei messaggi di
    errore, così l'operatore vede quale canale ha fallito il setup del backend.
    """
    try:
        detector = vad_detector or WebRtcVadDetector(config.vad)
        vad = StreamingVad(config=config.vad, detector=detector)
    except Exception as exc:  # noqa: BLE001 - wrap backend setup for operators.
        raise ConfigError(f"{channel_label} VAD setup failed: {exc}") from exc
    try:
        asr = FasterWhisperAsr(config.asr, model_factory=asr_model_factory)
    except AsrModelSetupError as exc:
        raise ConfigError(f"{channel_label} ASR setup failed: {exc}") from exc
    try:
        if speaker_embedding_factory is None:
            embedding_backend = SherpaOnnxSpeakerEmbeddingBackend(
                config.speaker_embedding
            )
        else:
            embedding_backend = speaker_embedding_factory(config.speaker_embedding)
        speaker_tagger = EmbeddingSpeakerTagger(
            embedding_backend,
            OnlineSpeakerClusterer(config.speaker_clustering),
        )
    except SpeakerEmbeddingError as exc:
        raise ConfigError(
            f"{channel_label} speaker embedding setup failed: {exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - wrap injected/backend setup failures.
        raise ConfigError(
            f"{channel_label} speaker embedding setup failed: {exc}"
        ) from exc
    return AudioPerceiver(store, vad, asr, speaker_tagger)


class _LazyCaptioner:
    """Construct the heavy VLM backend only when the first frame needs it."""

    def __init__(self, factory: Callable[[], Captioner]) -> None:
        self._factory = factory
        self._captioner: Captioner | None = None
        self._failure: QwenVlCaptionError | None = None
        self._lock = Lock()

    def caption(self, frame):
        return self._get().caption(frame)

    def _get(self) -> Captioner:
        if self._captioner is not None:
            return self._captioner
        if self._failure is not None:
            raise self._failure
        with self._lock:
            if self._captioner is not None:
                return self._captioner
            if self._failure is not None:
                raise self._failure
            try:
                self._captioner = self._factory()
            except QwenVlCaptionError as exc:
                self._failure = exc
                raise
            except Exception as exc:  # noqa: BLE001 - preserve queue isolation.
                self._failure = QwenVlCaptionError(
                    f"local Qwen2-VL setup failed: {exc}"
                )
                raise self._failure from exc
            return self._captioner


def _build_default_video_perceiver(
    config: Config,
    store: PerceptionStore,
    *,
    qwen_captioner_factory: Callable[[QwenVlConfig], Captioner] | None = None,
    llamacpp_captioner_factory: Callable[[Config], Captioner] | None = None,
) -> VideoPerceiver:
    """Build the local video path shared by Twitch and os_capture.

    Il backend di captioning è selezionato da `config.vlm.backend`:
    - `qwen` (default) → `Qwen2VlCaptioner` (runtime torch locale);
    - `llamacpp` → `LlamaCppCaptioner` sull'istanza multimodale `llama-server`
      condivisa (riusa `config.llamacpp.base_url`).
    Entrambe le costruzioni sono iniettabili per i test.
    """

    def build_captioner() -> Captioner:
        if config.vlm.backend == "llamacpp":
            if llamacpp_captioner_factory is not None:
                return llamacpp_captioner_factory(config)
            return LlamaCppCaptioner(
                base_url=config.llamacpp.base_url,
                config=config.vlm,
            )
        return (
            qwen_captioner_factory(config.vlm)
            if qwen_captioner_factory is not None
            else Qwen2VlCaptioner(config.vlm)
        )

    return VideoPerceiver(store, _LazyCaptioner(build_captioner), config=config.video)


def build_agent(
    config: Config,
    *,
    transport: Transport | None = None,
    store_path: str | Path | None = None,
    run_session: RunSession | None = None,
    router: OutputRouter | None = None,
    minnarone_output: MinnaroneOutputStream | None = None,
    adapter: SourceAdapter | None = None,
    twitch_chat_connect: ConnectIRC | None = None,
    twitch_send_connect: ConnectIRC | None = None,
    twitch_token_transport: TokenValidationTransport | None = None,
    twitch_token_validation_interval: float = 60.0 * 60.0,
    audio_perceiver: AudioPerceiver | None = None,
    video_perceiver: VideoPerceiver | None = None,
    perception_queue: BoundedLocalPerceptionQueue | None = None,
    asr_model_factory: Callable[..., object] | None = None,
    vad_detector: object | None = None,
    speaker_embedding_factory: Callable[
        [SpeakerEmbeddingConfig], SpeakerEmbeddingBackend
    ]
    | None = None,
    qwen_captioner_factory: Callable[[QwenVlConfig], Captioner] | None = None,
    llamacpp_captioner_factory: Callable[[Config], Captioner] | None = None,
    video_stream_opener: TwitchVideoStreamOpener | None = None,
    video_frame_decoder: VideoFrameDecoder | None = None,
    os_capture_audio_source: Captured | None = None,
    os_capture_video_source: Captured | None = None,
    youtube_api: YouTubeApi | None = None,
) -> Agent:
    """Compone e cabla TUTTI i moduli da una `Config`, restituendo un `Agent`.

    `transport` è iniettato nel provider LLM (fake nei test → nessuna rete).
    `store_path` sovrascrive la posizione dello store. Senza `store_path`, una
    `run_session` live usa il suo `perception_log_path`; altrimenti il default
    resta derivato dalla config. `router` sovrascrive l'OutputRouter selezionato
    dalla modalità (per i test che catturano l'output); se None si usa il router
    della modalità (`public`/`private`).

    `adapter` è una `SourceAdapter` esplicita da cui la pompa di percezione legge
    i `RawEvent`. Se non è passata e `config.adapter == "twitch"`, il runtime
    costruisce il reader Twitch chat-only dalla config e dalle credenziali in
    ambiente. Per `os_capture` il runtime costruisce un `OsCaptureAdapter` con
    sorgenti device LAZY: nei test si iniettano `os_capture_audio_source` /
    `os_capture_video_source` (liste in-memory di `AudioChunk`/`VideoFrame`, zero
    hardware); live, la sorgente device si apre solo alla prima iterazione dentro
    `start()`, così build e `--check` non toccano soundcard/mss.

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
    # Gate fail-fast dell'invio pubblico: `twitch.send.mode: live` valida poi
    # entrambi i token, quindi richiede già al build username, read e send.
    if (
        config.adapter == "twitch"
        and config.twitch is not None
        and config.twitch.send.mode is TwitchSendMode.LIVE
    ):
        _required_twitch_chat_credentials()
        _required_twitch_send_credentials()

    path = (
        Path(store_path)
        if store_path is not None
        else run_session.perception_log_path
        if run_session is not None
        else _default_store_path(config)
    )
    store = PerceptionStore(path)

    memory = FileMemory(soul_path=config.soul_path, facts_dir=config.facts_dir)
    blocks = memory.load()

    # Prompt-source (ticket 03): un unico set caricato+validato all'avvio
    # (fail-fast), condiviso da tutti i PromptBuilder. Con `config.prompts_dir`
    # gli override per-file vincono sui default impacchettati.
    prompt_set = load_prompt_set(config.prompts_dir)

    # Il canale nel prompt ({{channel}} in rules.md/intro.md) segue
    # `twitch.channel` quando la sezione twitch è configurata; senza (run
    # non-Twitch) resta il default del PromptBuilder.
    prompt_channel_kwargs: dict[str, str] = {}
    if config.adapter == "twitch" and config.twitch is not None:
        prompt_channel_kwargs = {"channel": config.twitch.channel}
    elif config.adapter == "youtube" and config.youtube is not None:
        prompt_channel_kwargs = {"channel": config.youtube.video_id}

    prompt_recorder = PromptObservationRecorder(
        debug_dir=run_session.debug_dir if run_session is not None else None
    )
    llm = ObservedLLMProvider(
        build_provider(config, transport=transport),
        recorder=prompt_recorder,
    )

    # Self-echo filter: se l'invio pubblico è attivo, il bot_identity è lo
    # username del send-account (TWITCH_BOT_USERNAME). Le percezioni chat di
    # questo speaker vengono escluse dai trigger e dalla finestra recente del
    # prompt. Assente (send: off o non-Twitch) → nessun filtro.
    bot_identity: str | None = None
    if (
        config.adapter == "twitch"
        and config.twitch is not None
        and config.twitch.send.mode is not TwitchSendMode.OFF
    ):
        bot_identity = os.environ.get("TWITCH_BOT_USERNAME") or None

    # Prompt-set del summarizer (ticket 05): set SEPARATO da quello original-chat
    # (preoccupazione distinta, NON nel prefisso stabile in cache), caricato e
    # validato all'avvio (fail-fast) con gli stessi override per-file da
    # `config.prompts_dir`.
    summarizer_prompt_set = load_summarizer_prompt_set(config.prompts_dir)
    summarizer = Summarizer(llm=llm, store=store, prompt_set=summarizer_prompt_set)
    human = HumanLikeness()
    event_recorder = (
        RunEventRecorder(run_session.debug_dir) if run_session is not None else None
    )
    # Costruzione del sender: SOLO quando il config dichiara mode: live.
    # off/shadow non costruiscono il sender né leggono il token di scrittura.
    sender: TwitchChatSender | None = None
    token_guard: TwitchLiveTokenGuard | None = None
    if (
        config.adapter == "twitch"
        and config.twitch is not None
        and config.twitch.send.mode is TwitchSendMode.LIVE
    ):
        sender = TwitchChatSender(
            channel=config.twitch.channel,
            username=os.environ["TWITCH_BOT_USERNAME"],
            oauth_token=os.environ[TWITCH_SEND_TOKEN_ENV_VAR],
            connect=twitch_send_connect or _connect_twitch_irc,
        )
        token_guard = TwitchLiveTokenGuard(
            username=os.environ["TWITCH_BOT_USERNAME"],
            read_token=os.environ["TWITCH_OAUTH_TOKEN"],
            send_token=os.environ[TWITCH_SEND_TOKEN_ENV_VAR],
            transport=twitch_token_transport,
            interval=twitch_token_validation_interval,
        )

    # -- Determine styles to build Reactors for --------------------------------
    # Multi-Reactor wiring (issue 11): iterate over active commentator profiles
    # and build one Reactor per style. If no profiles, apply the twitch+public
    # fallback (ORIGINAL_CHAT) or build zero Reactors.
    active_styles = config.commentator.active_styles()
    styles_to_build: list[CommentatorStyle | None] = list(active_styles)
    if not styles_to_build:
        # Twitch + public: la persona pubblica È l'original_chat,
        # indipendentemente dal commentator. Il prompt usa il contratto
        # RE:/MSG:/#end_conv perché è il formato che il Reactor sa normalizzare
        # per l'output su chat pubblica.
        if config.adapter in {"twitch", "youtube"} and config.mode is OutputMode.PUBLIC:
            styles_to_build = [CommentatorStyle.ORIGINAL_CHAT]
        # Otherwise: zero profiles → zero Reactors (only pump + summarizer).

    # -- Router selection ----------------------------------------------------------
    # Per-profile routing (issue 12): when the TUI path is active, each profile
    # gets its own MinnaroneOutputStream + TuiPrivateOutputRouter.  The underlying
    # public_router (ConsoleOutputRouter or TwitchPublicOutputRouter) is shared.
    _first_style: CommentatorStyle | None = (
        styles_to_build[0] if styles_to_build else None
    )
    active_minnarone_output: MinnaroneOutputStream | None = None
    output_streams: dict[CommentatorStyle, MinnaroneOutputStream] = {}
    send_policy: PublicSendPolicy | None = None
    _per_profile_routers: dict[CommentatorStyle | None, OutputRouter] = {}
    if router is not None:
        out_router = router
        if isinstance(router, TuiPrivateOutputRouter):
            active_minnarone_output = router.stream
    elif minnarone_output is not None and styles_to_build:
        # Percorso TUI: c'è uno stream locale e almeno uno stile da instradare.
        # Vale sia per private (profili commentator) sia per public+twitch (la
        # persona original_chat, forzata da validazione). L'output pubblico passa
        # per il TuiPrivateOutputRouter che avvolge il public_router e cattura i
        # marcatori [SHADOW]/[SENT] nel pannello MINNARONE; per questo il
        # public_router è costruito con echo=False (niente stdout sotto la TUI).
        send_config = (
            config.twitch.send
            if config.adapter == "twitch" and config.twitch is not None
            else config.youtube.send
            if config.adapter == "youtube" and config.youtube is not None
            else None
        )
        twitch_channel = (
            config.twitch.channel
            if config.adapter == "twitch" and config.twitch is not None
            else None
        )
        public_target = (
            PublicTarget("youtube", config.youtube.video_id)
            if config.adapter == "youtube" and config.youtube is not None
            else None
        )
        public_router, send_policy = _build_router(
            config.mode,
            commentator_style=_first_style,
            send_config=send_config,
            channel=twitch_channel,
            target=public_target,
            event_recorder=event_recorder,
            sender=sender,
            echo=False,
        )
        for style in styles_to_build:
            style_stream = MinnaroneOutputStream()
            output_streams[style] = style_stream
            _per_profile_routers[style] = TuiPrivateOutputRouter(
                style_stream,
                public_router=public_router,
            )
        if output_streams:
            active_minnarone_output = next(iter(output_streams.values()))
        else:
            active_minnarone_output = minnarone_output
        out_router = _per_profile_routers.get(_first_style) or TuiPrivateOutputRouter(
            minnarone_output,
            public_router=public_router,
        )
    else:
        send_config = (
            config.twitch.send
            if config.adapter == "twitch" and config.twitch is not None
            else config.youtube.send
            if config.adapter == "youtube" and config.youtube is not None
            else None
        )
        twitch_channel = (
            config.twitch.channel
            if config.adapter == "twitch" and config.twitch is not None
            else None
        )
        public_target = (
            PublicTarget("youtube", config.youtube.video_id)
            if config.adapter == "youtube" and config.youtube is not None
            else None
        )
        out_router, send_policy = _build_router(
            config.mode,
            commentator_style=_first_style,
            send_config=send_config,
            channel=twitch_channel,
            target=public_target,
            event_recorder=event_recorder,
            sender=sender,
        )

    # -- Build N Reactors (one per active style) --------------------------------
    reactors: list[Reactor] = []
    first_senser: Senser | None = None
    first_prompt_builder: PromptBuilder | None = None

    for style in styles_to_build:
        # Per-profile idle interval: override global config when the profile has
        # its own idle_interval setting.
        style_idle = config.idle_interval
        if style is not None and style in config.commentator.profiles:
            _profile_idle = getattr(
                config.commentator.profiles[style], "idle_interval", None
            )
            if _profile_idle is not None:
                style_idle = _profile_idle

        # Per-profile trigger mode and periodic interval.
        style_trigger_mode = "reactive"
        style_periodic_interval_s: float | None = None
        if style is CommentatorStyle.MEETING_SYNTHESIZER:
            _ms_profile = config.commentator.profiles[
                CommentatorStyle.MEETING_SYNTHESIZER
            ]
            style_trigger_mode = "periodic"
            style_periodic_interval_s = _ms_profile.interval_s
        elif style is CommentatorStyle.SUGGESTER:
            style_trigger_mode = "on_perception"

        style_senser = Senser(
            store,
            agent_name=config.agent_name,
            bot_identity=bot_identity,
            idle_interval=style_idle,
            trigger_mode=style_trigger_mode,
            interval_s=style_periodic_interval_s,
        )

        style_prompt_builder = PromptBuilder(
            blocks,
            announce_ai=config.disclosure.announce_ai,
            commentator_language=config.commentator.language,
            commentator_style=style,
            prompt_set=prompt_set,
            **prompt_channel_kwargs,
        )

        style_router = _per_profile_routers.get(style, out_router)
        style_reactor = Reactor(
            senser=style_senser,
            prompt_builder=style_prompt_builder,
            llm=llm,
            router=style_router,
            store=store,
            mode=config.mode,
            recent_window=config.recent_chat_window,
            human=human,
            summary_provider=lambda: summarizer.current_summary,
            event_recorder=event_recorder,
            bot_identity=bot_identity,
        )

        reactors.append(style_reactor)
        if first_senser is None:
            first_senser = style_senser
            first_prompt_builder = style_prompt_builder

    # Backward compat: when no styles are built, create a default Senser and
    # PromptBuilder so the Agent's `senser` and `prompt_builder` fields are
    # always populated (existing tests and observability depend on them).
    if first_senser is None:
        first_senser = Senser(
            store,
            agent_name=config.agent_name,
            bot_identity=bot_identity,
            idle_interval=config.idle_interval,
        )
    if first_prompt_builder is None:
        first_prompt_builder = PromptBuilder(
            blocks,
            announce_ai=config.disclosure.announce_ai,
            commentator_language=config.commentator.language,
            commentator_style=None,
            prompt_set=prompt_set,
            **prompt_channel_kwargs,
        )
    first_reactor: Reactor
    if reactors:
        first_reactor = reactors[0]
    else:
        first_reactor = Reactor(
            senser=first_senser,
            prompt_builder=first_prompt_builder,
            llm=llm,
            router=out_router,
            store=store,
            mode=config.mode,
            recent_window=config.recent_chat_window,
            human=human,
            summary_provider=lambda: summarizer.current_summary,
            event_recorder=event_recorder,
            bot_identity=bot_identity,
        )

    # I perceiver audio/video si costruiscono con GLI STESSI helper per Twitch e
    # os_capture: il canale è cablato se l'adapter dichiarato lo abilita.
    if _adapter_enables_audio(config) and audio_perceiver is None:
        audio_perceiver = _build_default_audio_perceiver(
            config,
            store,
            asr_model_factory=asr_model_factory,
            vad_detector=vad_detector,
            speaker_embedding_factory=speaker_embedding_factory,
            channel_label=f"{config.adapter}.audio",
        )
    speaker_diagnostics = _speaker_diagnostics_from_audio_perceiver(audio_perceiver)

    if _adapter_enables_video(config) and video_perceiver is None:
        video_perceiver = _build_default_video_perceiver(
            config,
            store,
            qwen_captioner_factory=qwen_captioner_factory,
            llamacpp_captioner_factory=llamacpp_captioner_factory,
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

    if perception_queue is None:
        media_processors = {
            channel: perceivers[channel]
            for channel in ("audio", "video")
            if channel in perceivers
        }
        if media_processors:
            perception_queue = BoundedLocalPerceptionQueue(
                media_processors,
                capacity=config.perception_queue_size,
                shutdown_timeout=config.perception_shutdown_timeout,
            )

    if adapter is None:
        adapter = _configured_adapter(
            config,
            twitch_chat_connect=twitch_chat_connect,
            audio_perceiver=audio_perceiver,
            video_perceiver=video_perceiver,
            video_stream_opener=video_stream_opener,
            video_frame_decoder=video_frame_decoder,
            os_capture_audio_source=os_capture_audio_source,
            os_capture_video_source=os_capture_video_source,
            youtube_api=youtube_api,
        )

    # NB: `config.retention` e `config.auto_memory` sono ACCETTATI ma INERTI:
    # non vengono cablati ad alcun comportamento nell'MVP (punti v2).
    return Agent(
        config=config,
        store=store,
        run_session=run_session,
        memory=memory,
        prompt_builder=first_prompt_builder,
        llm=llm,
        senser=first_senser,
        summarizer=summarizer,
        human=human,
        router=out_router,
        reactor=first_reactor,
        reactors=reactors,
        adapter=adapter,
        perceivers=perceivers,
        perception_queue=perception_queue,
        prompt_recorder=prompt_recorder,
        minnarone_output=active_minnarone_output,
        output_streams=output_streams,
        speaker_diagnostics=speaker_diagnostics,
        video_diagnostics=video_perceiver,
        send_policy=send_policy,
        sender=sender,
        token_guard=token_guard,
    )


def _speaker_diagnostics_from_audio_perceiver(
    audio_perceiver: object | None,
) -> object | None:
    if audio_perceiver is None:
        return None
    return getattr(audio_perceiver, "speaker_diagnostics", None)


def _adapter_enables_audio(config: Config) -> bool:
    """Whether the configured adapter enables the local audio channel."""
    if config.adapter == "twitch" and config.twitch is not None:
        return config.twitch.audio
    if config.adapter == "os_capture" and config.os_capture is not None:
        return config.os_capture.audio
    return False


def _adapter_enables_video(config: Config) -> bool:
    """Whether the configured adapter enables the local video channel."""
    if config.adapter == "twitch" and config.twitch is not None:
        return config.twitch.video
    if config.adapter == "os_capture" and config.os_capture is not None:
        return config.os_capture.video
    return False
