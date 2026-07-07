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
from .reactor import Reactor
from .run_artifacts import RunSession
from .run_events import RunEventRecorder
from .senser import Senser
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
from .twitch_chat import ConnectIRC
from .twitch_stream import TwitchStreamAdapter
from .twitch_video import TwitchVideoStreamOpener, VideoFrameDecoder
from .vad import StreamingVad, WebRtcVadDetector
from .video import Captioner, VideoFrame, VideoPerceiver
from .vlm import Qwen2VlCaptioner, QwenVlCaptionError, QwenVlConfig

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
            "modalità 'private' (whisper) non implementata nell'MVP: "
            "il canale di output privato arriva in v2 dietro OutputRouter"
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
    # Audio/video passano da una queue bounded quando hanno backend iniettati;
    # chat resta diretta per non essere penalizzata da ASR/VLM lenti.
    perception_queue: BoundedLocalPerceptionQueue | None = None
    run_session: RunSession | None = None
    prompt_recorder: PromptObservationRecorder = field(
        default_factory=PromptObservationRecorder
    )
    minnarone_output: MinnaroneOutputStream | None = None
    speaker_diagnostics: object | None = None
    video_diagnostics: object | None = None

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
        return snapshot(
            store=self.store,
            senser=self.senser,
            reactor=self.reactor,
            minnarone_output=self.minnarone_output,
            perception_queue=self.perception_queue,
            speaker_tagger=self.speaker_diagnostics,
            video_perceiver=self.video_diagnostics,
            adapter=self.adapter,
            prompt_recorder=self.prompt_recorder,
            summarizer=self.summarizer,
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
            results = await asyncio.gather(
                reactor_task, summarizer_task, pump_task, return_exceptions=True
            )
            errors = _unexpected_shutdown_errors(results)
            if errors:
                _raise_shutdown_errors(errors)


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
    mode: OutputMode, *, commentator_style: CommentatorStyle | None = None
) -> OutputRouter:
    """Seleziona l'OutputRouter dalla modalità (config, non un fork di codice)."""
    if mode is OutputMode.PUBLIC:
        return ConsoleOutputRouter()
    if commentator_style is not None:
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


def _required_twitch_chat_credentials() -> tuple[str, str]:
    missing = [
        name
        for name in ("TWITCH_BOT_USERNAME", "TWITCH_OAUTH_TOKEN")
        if not os.environ.get(name)
    ]
    if missing:
        raise ConfigError(
            "credenziali Twitch chat mancanti: esporta " + ", ".join(missing)
        )
    return os.environ["TWITCH_BOT_USERNAME"], os.environ["TWITCH_OAUTH_TOKEN"]


def _required_twitch_send_credentials() -> None:
    """Gate fail-fast di `twitch.send.mode: live`: token di scrittura presente.

    Della variabile d'ambiente si verifica solo la PRESENZA: il valore non deve
    mai finire in messaggi d'errore, log o artefatti. Il controllo vive nel
    build (non nello schema di config) così `Config.load` resta puro rispetto
    all'ambiente, mentre `--check` — che costruisce l'agente — fallisce subito.
    """
    # `.strip()`: un token di soli spazi è assente a tutti gli effetti; il
    # valore serve solo al controllo di presenza e non viene mai propagato.
    if not (os.environ.get(TWITCH_SEND_TOKEN_ENV_VAR) or "").strip():
        raise ConfigError(
            "credenziali Twitch send mancanti: esporta "
            f"{TWITCH_SEND_TOKEN_ENV_VAR} (token Twitch con scope di "
            "scrittura, distinto dal token di lettura)"
        )


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
            f"{channel_key} richiede un backend locale non cablato nel runtime "
            f"main: iniettalo o disabilita il canale"
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
) -> VideoPerceiver:
    """Build the local video path (Qwen2-VL) shared by Twitch and os_capture."""
    def build_captioner() -> Captioner:
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
    video_stream_opener: TwitchVideoStreamOpener | None = None,
    video_frame_decoder: VideoFrameDecoder | None = None,
    os_capture_audio_source: Captured | None = None,
    os_capture_video_source: Captured | None = None,
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
    # Gate fail-fast dell'invio pubblico: `twitch.send.mode: live` richiede il
    # token di scrittura in ambiente, qualunque sia l'adapter iniettato.
    if config.twitch is not None and config.twitch.send.mode is TwitchSendMode.LIVE:
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
    # announce_ai è l'UNICO punto v2 cablato (coerente): fluisce nello stance.
    commentator_style = config.commentator.prompt_style
    prompt_builder = PromptBuilder(
        blocks,
        announce_ai=config.disclosure.announce_ai,
        commentator_language=config.commentator.language,
        commentator_style=commentator_style,
    )

    prompt_recorder = PromptObservationRecorder(
        debug_dir=run_session.debug_dir if run_session is not None else None
    )
    llm = ObservedLLMProvider(
        build_provider(config, transport=transport),
        recorder=prompt_recorder,
    )

    senser = Senser(
        store,
        agent_name=config.agent_name,
        idle_interval=config.commentator.idle_interval_or(config.idle_interval),
    )

    summarizer = Summarizer(llm=llm, store=store)
    human = HumanLikeness()
    event_recorder = (
        RunEventRecorder(run_session.debug_dir) if run_session is not None else None
    )
    active_minnarone_output: MinnaroneOutputStream | None = None
    if router is not None:
        out_router = router
        if isinstance(router, TuiPrivateOutputRouter):
            active_minnarone_output = router.stream
    elif (
        minnarone_output is not None
        and config.commentator.uses_local_output(config.mode)
    ):
        out_router = TuiPrivateOutputRouter(minnarone_output)
        active_minnarone_output = minnarone_output
    else:
        out_router = _build_router(config.mode, commentator_style=commentator_style)

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
        )

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
        event_recorder=event_recorder,
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
        )

    # NB: `config.retention` e `config.auto_memory` sono ACCETTATI ma INERTI:
    # non vengono cablati ad alcun comportamento nell'MVP (punti v2).
    return Agent(
        config=config,
        store=store,
        run_session=run_session,
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
        perception_queue=perception_queue,
        prompt_recorder=prompt_recorder,
        minnarone_output=active_minnarone_output,
        speaker_diagnostics=speaker_diagnostics,
        video_diagnostics=video_perceiver,
    )


def _speaker_diagnostics_from_audio_perceiver(audio_perceiver: object | None) -> object | None:
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
