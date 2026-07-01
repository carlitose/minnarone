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

import asyncio
import time
from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import Protocol

from .audio import AudioChunk
from .source import RawEvent, SourceAdapter
from .video import VideoFrame


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
    *,
    sample_rate: int = 16_000,
    source_label: str = "system",
    chunk_seconds: float = 1.0,
) -> AsyncIterator[AudioChunk]:
    """Percorso OPZIONALE: cattura reale dell'audio di SISTEMA (loopback).

    Backend concreto della cattura dell'uscita di default via `soundcard`
    (WASAPI su Windows, monitor PulseAudio su Linux). Emette `AudioChunk` in
    formato PCM mono 16 kHz signed 16-bit little-endian (quello atteso da
    VAD/ASR), con `source_label="system"` e `ts` corrente.

    Import LAZY: `soundcard` e `numpy` (extra `os-capture`) sono importati solo
    quando il generatore viene iterato, MAI al caricamento del modulo né alla
    costruzione. Il device di loopback si apre alla PRIMA iterazione, non alla
    chiamata: così `--check` e il build non toccano l'hardware. È il chiamante
    (la pompa di `start()`) a innescare l'apertura iterando.

    Args:
        sample_rate: frequenza dei chunk emessi (Hz); default 16 kHz.
        source_label: provenienza marcata sui chunk; default "system" (audio di
            sistema), distinto da "mic" per lo speaker tagging.
        chunk_seconds: durata approssimativa di ogni chunk (secondi).

    Errori operatore: se non esiste un device di loopback per l'uscita di
    default (nessun monitor / driver mancante) o i permessi lo negano, solleva
    `RuntimeError` con un messaggio chiaro alla prima iterazione.

    Note macOS: `soundcard` NON supporta il loopback su macOS; serve un device
    di loopback esterno (es. BlackHole) instradato come input. Documentato
    nell'app di riferimento.
    """

    async def _source() -> AsyncIterator[AudioChunk]:
        # Import pesante LAZY: valutato solo alla prima iterazione, non al
        # caricamento del modulo né alla costruzione del generatore.
        try:
            import numpy as np
            import soundcard as sc
        except ImportError as exc:  # pragma: no cover - richiede ambiente senza extra
            raise RuntimeError(
                "cattura audio di sistema non disponibile: installa l'extra "
                "'os-capture' (soundcard + numpy)"
            ) from exc

        # Apri il loopback dell'uscita di DEFAULT. Su Windows/Linux il device
        # monitor dello speaker di default si ottiene per nome con
        # include_loopback=True; macOS non lo supporta.
        try:
            speaker = sc.default_speaker()
            loopback = sc.get_microphone(
                str(speaker.name), include_loopback=True
            )
        except Exception as exc:  # noqa: BLE001 - fallback errore operatore chiaro
            raise RuntimeError(
                "nessun device di loopback per l'uscita di default: verifica "
                "driver/monitor audio e permessi (macOS non supporta il "
                "loopback: serve un device esterno come BlackHole)"
            ) from exc

        # numframes per chunk: durata * sample_rate, almeno 1 frame.
        numframes = max(1, int(round(sample_rate * chunk_seconds)))
        try:
            with loopback.recorder(samplerate=sample_rate, channels=1) as rec:
                while True:
                    # record() ritorna un array float32 frames×channels in
                    # [-1, 1]; è una chiamata BLOCCANTE finché numframes non
                    # sono disponibili, quindi la si esegue in un thread per non
                    # stallare l'event loop (che deve restare reattivo a video,
                    # reactor e a stop()/cancellazione durante il chunk).
                    frames = await asyncio.to_thread(rec.record, numframes)
                    yield AudioChunk(
                        samples=_to_pcm_s16le(frames, np),
                        sample_rate=sample_rate,
                        source_label=source_label,
                        ts=time.time(),
                    )
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001 - errore operatore chiaro
            raise RuntimeError(
                f"cattura del loopback fallita ({speaker.name}): permessi o "
                "device non disponibili"
            ) from exc

    return _source()


def _to_pcm_s16le(frames: object, np: object) -> bytes:
    """Converte un array float32 (frames×channels) in PCM mono s16le.

    `soundcard` consegna campioni float32 in [-1, 1]. Il downmix a mono media i
    canali, poi si scala a signed 16-bit little-endian (il formato opaco che i
    chunk audio portano fino a VAD/ASR).
    """
    arr = np.asarray(frames, dtype=np.float32)  # type: ignore[attr-defined]
    if arr.ndim > 1:
        # Downmix a mono: media sui canali.
        arr = arr.mean(axis=1)
    arr = np.clip(arr, -1.0, 1.0)  # type: ignore[attr-defined]
    # np.rint: arrotonda al più vicino (evita il bias di troncamento verso zero).
    return np.rint(arr * 32767.0).astype("<i2").tobytes()  # type: ignore[attr-defined]


def make_device_screen_capture_source(
    *,
    monitor: int = 1,
    source_label: str = "screen",
    fps: float = 1.0,
) -> AsyncIterator[VideoFrame]:
    """Percorso OPZIONALE: backend di cattura schermo reale via `mss`.

    Costruisce un frame source che legge lo schermo del sistema con `mss`,
    emettendo `VideoFrame` con i pixel in `ndarray` RGB `HxWx3` uint8 —
    esattamente il formato che il `Captioner` Qwen2-VL già consuma (come il
    percorso video Twitch via PyAV). Con `source_label="screen"` e `ts` corrente.

    Import LAZY: `mss` e `numpy` (extra `os-capture`) sono importati solo quando
    il generatore viene iterato, MAI al caricamento del modulo né alla
    costruzione. Lo schermo si apre alla PRIMA iterazione, non alla chiamata:
    così `--check` e il build non toccano il device. È il chiamante (la pompa di
    `start()`) a innescare l'apertura iterando.

    Args:
        monitor: indice del monitor `mss` da catturare. La lista `sct.monitors`
            ha indice 0 = tutti i monitor uniti, indice 1 = monitor primario
            (default, allineato a `OsCaptureConfig.monitor`).
        source_label: provenienza marcata sui frame; default "screen".
        fps: frame al secondo emessi; fra un frame e l'altro si attende `1/fps`.

    Errori operatore: se manca l'extra, se l'indice `monitor` non esiste, o se la
    cattura fallisce (permessi negati / nessuno schermo), solleva `RuntimeError`
    con un messaggio chiaro alla prima iterazione.

    Note di permessi macOS:
        * La cattura dello schermo richiede il permesso "Screen Recording" in
          Privacy & Security; senza, le API restituiscono frame vuoti/neri.
        * Il VLM per le caption (es. Qwen2-VL) è una dipendenza pesante a parte,
          iniettata come `Captioner` nel `VideoPerceiver`, non importata qui.
    """

    async def _source() -> AsyncIterator[VideoFrame]:
        # Import pesante LAZY: valutato solo alla prima iterazione, non al
        # caricamento del modulo né alla costruzione del generatore.
        try:
            import mss as mss_module
            import numpy as np
        except ImportError as exc:  # pragma: no cover - richiede ambiente senza extra
            raise RuntimeError(
                "cattura schermo non disponibile: installa l'extra "
                "'os-capture' (mss + numpy)"
            ) from exc

        # Apri lo schermo alla PRIMA iterazione e seleziona il monitor per
        # indice. sct.monitors[0] = tutti i monitor uniti, [1] = primario.
        try:
            with mss_module.mss() as sct:
                # Guardia esplicita: l'indicizzazione negativa di Python NON
                # solleverebbe IndexError (monitor=-1 prenderebbe l'ultimo), ma
                # il contratto promette un errore chiaro per ogni indice inesistente.
                if monitor < 0 or monitor >= len(sct.monitors):
                    raise RuntimeError(
                        f"monitor {monitor} inesistente: sono disponibili gli "
                        f"indici 0..{len(sct.monitors) - 1} "
                        "(0 = tutti i monitor, 1 = primario)"
                    )
                target = sct.monitors[monitor]

                # Pacing: attende 1/fps fra un frame e l'altro (fps > 0).
                delay = 1.0 / fps if fps > 0 else 0.0
                while True:
                    # sct.grab() è BLOCCANTE: la si esegue in un thread per non
                    # stallare l'event loop (che deve restare reattivo a stop()
                    # e cancellazione fra un frame e l'altro).
                    shot = await asyncio.to_thread(sct.grab, target)
                    yield VideoFrame(
                        pixels=_screen_shot_to_rgb(shot, np),
                        source_label=source_label,
                        ts=time.time(),
                    )
                    if delay:
                        await asyncio.sleep(delay)
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001 - errore operatore chiaro
            raise RuntimeError(
                "cattura dello schermo fallita: verifica i permessi (macOS: "
                "'Screen Recording' in Privacy & Security) e la presenza di uno "
                "schermo"
            ) from exc

    return _source()


def _screen_shot_to_rgb(shot: object, np: object) -> object:
    """Converte uno `ScreenShot` `mss` (BGRA) in un `ndarray` RGB `HxWx3` uint8.

    `mss` consegna i pixel in BGRA (4 canali). Si scarta il canale alfa e si
    inverte l'ordine dei canali BGR->RGB con `np.flip(..., 2)`: è la variante
    numpy più efficiente e produce l'`HxWx3` uint8 atteso a valle dal
    `Captioner` (via `Image.fromarray`), coerente col percorso video PyAV.
    """
    frame = np.asarray(shot, dtype=np.uint8)  # type: ignore[attr-defined]
    # Scarta alfa (primi 3 canali) e inverte BGR->RGB sull'ultimo asse.
    return np.ascontiguousarray(np.flip(frame[:, :, :3], 2))  # type: ignore[attr-defined]


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
