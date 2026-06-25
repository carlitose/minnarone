"""`OSCaptureAdapter`: cattura a livello di sistema operativo come `SourceAdapter`.

Nell'MVP la sorgente è la cattura del SO (mic + audio di sistema), non un
connettore per-piattaforma. Questo adapter emette `RawEvent(channel="audio")`
il cui payload è un `AudioChunk` (vedi `audio.py`), che l'`AudioPerceiver`
consuma.

Iniettabilità del backend di cattura. Il *come* si arriva ai campioni audio è
un dettaglio del sistema operativo (sounddevice / CoreAudio / loopback di
sistema), e su macOS l'audio di sistema richiede permessi e tooling specifici
(vedi nota in fondo). Per non legare il core a un device reale — e per poterlo
testare offline — il backend è INIETTATO come un *capture source*: un iterabile
(sincrono o asincrono) di `AudioChunk`. L'adapter si limita a impacchettare ogni
chunk in un `RawEvent` rispettando il ciclo di vita `start()/stop()`.

Il backend reale di device NON viene importato al caricamento del modulo: è un
percorso opzionale documentato (`make_device_capture_source`) che importa la sua
dipendenza pesante solo se invocato. Così il modulo si carica e i test girano
senza alcun device né dipendenza ML.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable

from .audio import AudioChunk
from .source import RawEvent, SourceAdapter
from .video import VideoFrame

# Un capture source può essere un iterabile sincrono o asincrono di AudioChunk.
# Lo normalizziamo a runtime, così l'iniezione resta semplice per i test
# (lista in-memory) e flessibile per i backend reali (generatore async).
CaptureSource = Iterable[AudioChunk]

# Analogamente per il video: una sorgente di frame, iterabile sincrono o async.
FrameSource = Iterable[VideoFrame]


class OSCaptureAdapter(SourceAdapter):
    """Adapter di cattura audio del SO: `AudioChunk` -> `RawEvent(audio)`.

    Il backend di cattura è iniettato (`capture_source`): un iterabile sincrono
    o asincrono di `AudioChunk`. L'adapter non sa né gli importa da dove vengano
    i campioni; questo lo rende testabile con una sorgente in-memory.
    """

    def __init__(self, capture_source: object) -> None:
        self._capture_source = capture_source
        self._started = False

    def channels(self) -> set[str]:
        return {"audio"}

    async def start(self) -> None:
        """Avvia la cattura. Idempotente."""
        self._started = True

    async def stop(self) -> None:
        """Ferma la cattura. Sicura anche se non avviata."""
        self._started = False

    async def events(self) -> AsyncIterator[RawEvent]:
        """Stream di `RawEvent(channel="audio")` finché l'adapter è attivo.

        Ogni `AudioChunk` del capture source diventa un `RawEvent` con `ts`
        ereditato dal chunk. Se `stop()` viene chiamato lo stream si interrompe
        senza emettere altri eventi.
        """
        async for chunk in self._iter_chunks():
            # Controlla PRIMA di emettere: dopo stop() non si estrae né si
            # emette un ulteriore chunk (importante per sorgenti real-time).
            if not self._started:
                break
            yield RawEvent(channel="audio", payload=chunk, ts=chunk.ts)
            if not self._started:
                break

    async def _iter_chunks(self) -> AsyncIterator[AudioChunk]:
        """Normalizza il capture source (sync o async) a un async iterator."""
        source = self._capture_source
        if hasattr(source, "__aiter__"):
            async for chunk in source:  # type: ignore[union-attr]
                yield chunk
        else:
            for chunk in source:  # type: ignore[union-attr]
                yield chunk


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


class ScreenCaptureAdapter(SourceAdapter):
    """Adapter di cattura schermo: `VideoFrame` -> `RawEvent(video)`.

    Specchio dello `OSCaptureAdapter` audio per il canale "video". Il backend di
    cattura è iniettato (`frame_source`): un iterabile sincrono o asincrono di
    `VideoFrame`. L'adapter non sa né gli importa da dove vengano i frame; questo
    lo rende testabile con una sorgente in-memory e disaccoppia il core dal
    device dello schermo (che AFK non esiste).
    """

    def __init__(self, frame_source: object) -> None:
        self._frame_source = frame_source
        self._started = False

    def channels(self) -> set[str]:
        return {"video"}

    async def start(self) -> None:
        """Avvia la cattura. Idempotente."""
        self._started = True

    async def stop(self) -> None:
        """Ferma la cattura. Sicura anche se non avviata."""
        self._started = False

    async def events(self) -> AsyncIterator[RawEvent]:
        """Stream di `RawEvent(channel="video")` finché l'adapter è attivo.

        Ogni `VideoFrame` del frame source diventa un `RawEvent` con `ts`
        ereditato dal frame. Se `stop()` viene chiamato lo stream si interrompe
        senza estrarre né emettere un ulteriore frame (sorgenti real-time).
        """
        async for frame in self._iter_frames():
            # Controlla PRIMA di emettere: dopo stop() non si estrae né si
            # emette un ulteriore frame.
            if not self._started:
                break
            yield RawEvent(channel="video", payload=frame, ts=frame.ts)
            if not self._started:
                break

    async def _iter_frames(self) -> AsyncIterator[VideoFrame]:
        """Normalizza il frame source (sync o async) a un async iterator."""
        source = self._frame_source
        if hasattr(source, "__aiter__"):
            async for frame in source:  # type: ignore[union-attr]
                yield frame
        else:
            for frame in source:  # type: ignore[union-attr]
                yield frame


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
