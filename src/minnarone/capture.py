"""`StreamCaptureAdapter`: cattura generica per-canale come `SourceAdapter`.

Nell'MVP la sorgente è la cattura del SO (mic + audio di sistema, schermo), non
un connettore per-piattaforma. Un solo adapter parametrico impacchetta ogni
payload `Timestamped` (un `AudioChunk` per il canale "audio", un `VideoFrame`
per il canale "video") in un `RawEvent`, che il perceiver del canale consuma.

Iniettabilità del backend di cattura. Il *come* si arriva ai campioni (audio o
frame) è un dettaglio del sistema operativo (sounddevice / CoreAudio / loopback
per l'audio; mss / PyAV per lo schermo), e su macOS richiede permessi e tooling
specifici (vedi note in fondo). Per non legare il core a un device reale — e per
poterlo testare offline — il backend è INIETTATO come una *sorgente*: un
iterabile (sincrono o asincrono) di payload con `.ts`. L'adapter si limita a
impacchettare ogni payload in un `RawEvent` rispettando il ciclo di vita
`start()/stop()`.

Il backend reale di device NON viene importato al caricamento del modulo: è un
percorso opzionale documentato (`make_device_capture_source` /
`make_device_screen_capture_source`) che importa la sua dipendenza pesante solo
se invocato. Così il modulo si carica e i test girano senza alcun device né
dipendenza ML.

Costruttori ergonomici (`os_audio_capture` / `os_screen_capture`) conservano i
nomi di dominio per i chiamanti.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import Protocol, runtime_checkable

from .audio import AudioChunk
from .source import RawEvent, SourceAdapter
from .video import VideoFrame


@runtime_checkable
class Timestamped(Protocol):
    """Payload di cattura: deve esporre l'epoch di cattura `ts` in secondi.

    `AudioChunk` e `VideoFrame` lo soddisfano già.
    """

    @property
    def ts(self) -> float: ...


# Una sorgente di cattura è un iterabile sincrono o asincrono di payload
# `Timestamped`. La normalizziamo a runtime, così l'iniezione resta semplice per
# i test (lista in-memory) e flessibile per i backend reali (generatore async).
Captured = Iterable[Timestamped] | AsyncIterable[Timestamped]


async def _aiter(source: Captured) -> AsyncIterator[Timestamped]:
    """Normalizza una sorgente (sync o async) a un async iterator.

    Nasconde la differenza sync/async: chi consuma vede sempre un `async for`.
    """
    if isinstance(source, AsyncIterable):
        async for item in source:
            yield item
    else:
        for item in source:
            yield item


class StreamCaptureAdapter(SourceAdapter):
    """Adapter di cattura generico: payload `Timestamped` -> `RawEvent(channel)`.

    Parametrico sul `channel` ("audio", "video", ...). Il backend di cattura è
    iniettato (`source`): un iterabile sincrono o asincrono di payload con `.ts`.
    L'adapter non sa né gli importa da dove vengano i payload; questo lo rende
    testabile con una sorgente in-memory e disaccoppia il core dal device.
    """

    def __init__(self, channel: str, source: Captured) -> None:
        self._channel = channel
        self._source = source
        self._started = False

    def channels(self) -> set[str]:
        return {self._channel}

    async def start(self) -> None:
        """Avvia la cattura. Idempotente."""
        self._started = True

    async def stop(self) -> None:
        """Ferma la cattura. Sicura anche se non avviata."""
        self._started = False

    async def events(self) -> AsyncIterator[RawEvent]:
        """Stream di `RawEvent(channel=self._channel)` finché l'adapter è attivo.

        Ogni payload della sorgente diventa un `RawEvent` con `ts` ereditato dal
        payload. Se `stop()` viene chiamato lo stream si interrompe senza
        estrarre né emettere un ulteriore payload (importante per sorgenti
        real-time).
        """
        async for payload in _aiter(self._source):
            # Controlla PRIMA di emettere: dopo stop() non si estrae né si
            # emette un ulteriore payload (sorgenti real-time).
            if not self._started:
                break
            yield RawEvent(channel=self._channel, payload=payload, ts=payload.ts)
            if not self._started:
                break


def os_audio_capture(source: Captured) -> StreamCaptureAdapter:
    """Costruttore ergonomico: adapter di cattura audio del SO.

    `AudioChunk` (iniettato via `source`) -> `RawEvent(channel="audio")`.
    """
    return StreamCaptureAdapter("audio", source)


def os_screen_capture(source: Captured) -> StreamCaptureAdapter:
    """Costruttore ergonomico: adapter di cattura schermo del SO.

    `VideoFrame` (iniettato via `source`) -> `RawEvent(channel="video")`.
    """
    return StreamCaptureAdapter("video", source)


def make_device_capture_source(
    *, sample_rate: int = 16_000, source_label: str = "mic"
) -> AsyncIterator[AudioChunk]:
    """Percorso OPZIONALE: backend di cattura da device reale (NON usato AFK).

    Costruisce un capture source che legge dal device audio del sistema. Importa
    la dipendenza pesante (es. `sounddevice`) SOLO qui dentro, così il modulo si
    carica senza device né pacchetti audio installati. Questo percorso non è
    esercitato nei test (richiede hardware e permessi); è documentato come lo
    slot dove innestare la cattura reale.

    Note di permessi macOS:
        * Il microfono richiede il permesso "Microphone" in Privacy & Security.
        * L'audio di SISTEMA non è catturabile dalle API standard: serve un
          device di loopback (es. BlackHole / un Aggregate Device) instradato
          come input. Documentare il setup nell'app di riferimento.

    Sollevare a chi cabla l'app la scelta del backend concreto.
    """
    raise NotImplementedError(
        "make_device_capture_source è il percorso opzionale di cattura reale: "
        "cablare un backend di device (es. sounddevice + loopback di sistema) "
        "implementando un iterabile di AudioChunk. Non disponibile in ambiente "
        "senza device."
    )


def make_device_screen_capture_source(
    *, source_label: str = "screen", fps: float = 1.0
) -> AsyncIterator[VideoFrame]:
    """Percorso OPZIONALE: backend di cattura schermo reale (NON usato AFK).

    Costruisce un frame source che legge dallo schermo del sistema. Importa la
    dipendenza pesante (es. `mss`/`PyAV` per i frame, un VLM a valle per le
    caption) SOLO qui dentro, così il modulo si carica senza device né pacchetti
    di visione installati e senza scaricare modelli. Questo percorso non è
    esercitato nei test (richiede uno schermo e permessi); è documentato come lo
    slot dove innestare la cattura reale.

    Note di permessi macOS:
        * La cattura dello schermo richiede il permesso "Screen Recording" in
          Privacy & Security; senza, le API restituiscono frame vuoti/neri.
        * Il VLM per le caption (es. Qwen2-VL) è una dipendenza pesante a parte,
          iniettata come `Captioner` nel `VideoPerceiver`, non importata qui.

    Sollevare a chi cabla l'app la scelta del backend concreto.
    """
    raise NotImplementedError(
        "make_device_screen_capture_source è il percorso opzionale di cattura "
        "schermo reale: cablare un backend (es. mss/PyAV) implementando un "
        "iterabile di VideoFrame, e iniettare un Captioner VLM nel "
        "VideoPerceiver. Non disponibile in ambiente senza schermo/GPU."
    )


# Alias sottili di back-compat. La codebase è fresca e i nuovi chiamanti usano
# i costruttori ergonomici / la classe generica, ma i due nomi storici erano
# esportati ed esercitati dai test dei perceiver: li manteniamo come alias di
# costruzione equivalenti per non rompere il cablaggio esistente.
def OSCaptureAdapter(capture_source: Captured) -> StreamCaptureAdapter:
    """Alias storico di `os_audio_capture` (canale "audio")."""
    return StreamCaptureAdapter("audio", capture_source)


def ScreenCaptureAdapter(frame_source: Captured) -> StreamCaptureAdapter:
    """Alias storico di `os_screen_capture` (canale "video")."""
    return StreamCaptureAdapter("video", frame_source)
