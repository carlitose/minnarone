"""Percezione video: pipeline sampling -> hashing/dedup -> VLM caption -> `Perception`.

Questo modulo è il *giunto* fra i frame grezzi dello schermo e il perception
store. È un modulo profondo: il `VideoPerceiver` orchestra tre stadi e scrive
percezioni, ma la sua superficie pubblica è minima (`perceive_frame` /
`perceive_event`).

Pluggabilità (NFR05). Lo stadio costoso — la *caption* di un frame via VLM — è
definito come un `typing.Protocol`, NON come dipendenza concreta:

* `Captioner` — visione: dato un frame produce una descrizione testuale. È
  l'unico stadio che richiede un modello (Qwen2-VL / un VLM equivalente). Il
  `VideoPerceiver` dipende SOLO da questa interfaccia, mai da un modello
  concreto: il backend reale si innesta implementando il Protocol, senza essere
  importato qui. Per i test si usa il `FakeCaptioner` deterministico in
  `fakes.py`.

La parte di VALORE *senza modello* vive qui ed è reale e testata in modo
deterministico:

* **Sampling.** Il captioning è costoso e lento, quindi NON si fa per ogni
  frame: si considera un frame ogni `sample_every` (campionamento per conteggio).
  Gli altri vengono scartati prima ancora dell'hashing.
* **Hashing / dedup.** Anche fra i frame campionati, due frame consecutivi
  visivamente identici non aggiungono informazione: si calcola un hash stabile
  dei pixel e si salta il frame se l'hash coincide con quello dell'ultimo frame
  effettivamente descritto. Così niente caption duplicate su uno schermo fermo.

Il payload video (`VideoFrame`) è volutamente opaco rispetto al formato: porta i
pixel grezzi e i metadati minimi. È il contratto fra lo `StreamCaptureAdapter`
("video", costruito via `os_screen_capture`, che lo emette come
`RawEvent.payload`) e questa pipeline.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .perceiver import EventPerceiver
from .perception import Perception, Source
from .store import PerceptionStore


@dataclass(frozen=True, slots=True)
class VideoFrame:
    """Un frame catturato dallo schermo, prima del campionamento/caption.

    È il `payload` dei `RawEvent` di canale "video". Volutamente neutro rispetto
    al backend: `pixels` è il dato opaco (bytes, ndarray, un piccolo oggetto nei
    test, ...), gli altri campi sono i metadati minimi per gli stadi a valle.

    Attributi:
        pixels: dati grezzi del frame (tipo concreto deciso dal backend).
        source_label: provenienza del frame, es. "screen".
        ts: epoch di cattura in secondi.
    """

    pixels: object
    source_label: str = "screen"
    ts: float = 0.0


class VideoConfigError(ValueError):
    """Configurazione video non valida."""


@dataclass(frozen=True, slots=True)
class VideoPerceptionConfig:
    """Knob di campionamento e dedup per la percezione video locale."""

    sample_every: int = 1
    dedup_change_threshold: float = 0.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.sample_every, bool)
            or not isinstance(self.sample_every, int)
            or self.sample_every < 1
        ):
            raise VideoConfigError("sample_every must be an integer >= 1")
        threshold = _finite_float(
            self.dedup_change_threshold,
            "dedup_change_threshold",
        )
        if not 0.0 <= threshold < 1.0:
            raise VideoConfigError("dedup_change_threshold must be >= 0 and < 1")
        object.__setattr__(self, "dedup_change_threshold", threshold)


@dataclass(frozen=True, slots=True)
class VideoPerceptionStats:
    """Diagnostic counters for local video perception."""

    frames_seen: int = 0
    sampled: int = 0
    dedup_skipped: int = 0
    captioned: int = 0
    empty_captions: int = 0
    failed: int = 0


@runtime_checkable
class Captioner(Protocol):
    """Visione: descrive un frame in testo (stadio VLM).

    Contratto: ritorna una descrizione testuale del frame (può essere
    imperfetta) oppure una stringa vuota se non ne ricava nulla di utile.
    È l'unico stadio che richiede un modello; il `VideoPerceiver` non lo importa
    mai direttamente.
    """

    def caption(self, frame: VideoFrame) -> str:
        """Descrizione testuale del frame; "" se nulla di descrivibile."""
        ...


@runtime_checkable
class FrameDeduper(Protocol):
    """Decide se un frame è abbastanza nuovo da meritare caption."""

    def should_caption(self, frame: VideoFrame) -> bool:
        """True quando il frame va descritto."""
        ...

    def remember(self, frame: VideoFrame) -> None:
        """Aggiorna il riferimento visuale dopo una caption riuscita."""
        ...


@dataclass(slots=True)
class _FrameFingerprint:
    digest: str
    data: bytes


class ByteFrameDeduper:
    """Dedup visuale semplice basato sui byte dei pixel.

    `change_threshold=0.0` replica il comportamento storico: solo frame
    byte-identici vengono saltati. Soglie maggiori ignorano micro-variazioni:
    un nuovo frame passa solo se la frazione di byte cambiati è strettamente
    maggiore della soglia.
    """

    def __init__(self, *, change_threshold: float = 0.0) -> None:
        threshold = _finite_float(change_threshold, "change_threshold")
        if not 0.0 <= threshold < 1.0:
            raise ValueError("change_threshold must be >= 0 and < 1")
        self._change_threshold = threshold
        self._last: _FrameFingerprint | None = None

    def should_caption(self, frame: VideoFrame) -> bool:
        current = _frame_fingerprint(frame)
        previous = self._last
        if previous is None:
            return True
        if current.digest == previous.digest:
            return False
        if self._change_threshold == 0.0:
            return True
        return _byte_change_ratio(previous.data, current.data) > self._change_threshold

    def remember(self, frame: VideoFrame) -> None:
        self._last = _frame_fingerprint(frame)


def _frame_bytes(frame: VideoFrame) -> bytes:
    """Byte stabili dei pixel, senza timestamp né repr troncati."""
    pixels = frame.pixels
    if isinstance(pixels, (bytes, bytearray, memoryview)):
        return bytes(pixels)
    if hasattr(pixels, "tobytes"):
        # numpy ndarray e simili: byte di contenuto, non repr troncato.
        return pixels.tobytes()  # type: ignore[union-attr]
    try:
        return bytes(memoryview(pixels))  # type: ignore[arg-type]
    except TypeError:
        # Stand-in di test opachi (str/int): repr come ultima risorsa.
        return repr(pixels).encode("utf-8")


def _frame_fingerprint(frame: VideoFrame) -> _FrameFingerprint:
    data = _frame_bytes(frame)
    return _FrameFingerprint(digest=hashlib.sha256(data).hexdigest(), data=data)


def _byte_change_ratio(previous: bytes, current: bytes) -> float:
    width = max(len(previous), len(current))
    if width == 0:
        return 0.0
    changed = abs(len(previous) - len(current))
    changed += sum(
        1 for before, after in zip(previous, current, strict=False) if before != after
    )
    return changed / width


def _frame_hash(frame: VideoFrame) -> str:
    """Hash stabile dei pixel di un frame, per il dedup.

    Deterministico e indipendente dal `ts`: due frame con pixel identici hanno
    lo stesso hash anche se catturati in istanti diversi.

    L'hash si basa sui BYTE REALI dei pixel, mai sulla rappresentazione
    testuale: il payload canonico in produzione è un array immagine (es. numpy
    ndarray), il cui `repr()` è troncato per array grandi (frame diversi
    collassano allo stesso hash) e per oggetti opachi include l'indirizzo di
    memoria (oggetti uguali non deduplicano mai). Si estraggono quindi i byte
    via buffer protocol (`memoryview`) o `tobytes()`. Il fallback `repr()` resta
    SOLO per stand-in di test semplici (str/int) che non espongono byte.
    """
    return _frame_fingerprint(frame).digest


class VideoPerceiver(EventPerceiver):
    """Orchestra sampling -> hashing/dedup -> caption e scrive percezioni video.

    Modulo profondo: nasconde la pipeline dietro un'API semplice. Dipende solo
    dal `Captioner` iniettato, mai da un modello concreto. Eredita da
    `EventPerceiver` il dispatch `RawEvent` -> percezione (canale "video",
    payload `VideoFrame`).

    Args:
        store: dove scrivere le `Perception` prodotte.
        captioner: lo stadio VLM iniettato.
        sample_every: campiona un frame ogni `sample_every` (default 1 = ogni
            frame è candidato). Deve essere >= 1; è il freno costo/latenza.
    """

    channel = "video"
    payload_type = VideoFrame

    def __init__(
        self,
        store: PerceptionStore,
        captioner: Captioner,
        *,
        config: VideoPerceptionConfig | None = None,
        sample_every: int | None = None,
        dedup_change_threshold: float | None = None,
        deduper: FrameDeduper | None = None,
    ) -> None:
        effective_config = config or VideoPerceptionConfig()
        if sample_every is not None or dedup_change_threshold is not None:
            effective_config = VideoPerceptionConfig(
                sample_every=(
                    sample_every
                    if sample_every is not None
                    else effective_config.sample_every
                ),
                dedup_change_threshold=(
                    dedup_change_threshold
                    if dedup_change_threshold is not None
                    else effective_config.dedup_change_threshold
                ),
            )
        self._store = store
        self._captioner = captioner
        self._config = effective_config
        self._sample_every = effective_config.sample_every
        self._deduper = deduper or ByteFrameDeduper(
            change_threshold=effective_config.dedup_change_threshold
        )
        # Contatore dei frame visti, per il campionamento per conteggio.
        self._seen = 0
        self._sampled = 0
        self._dedup_skipped = 0
        self._captioned = 0
        self._empty_captions = 0
        self._failed = 0

    def stats(self) -> VideoPerceptionStats:
        """Snapshot read-only of video sampling/dedup/caption counters."""
        return VideoPerceptionStats(
            frames_seen=self._seen,
            sampled=self._sampled,
            dedup_skipped=self._dedup_skipped,
            captioned=self._captioned,
            empty_captions=self._empty_captions,
            failed=self._failed,
        )

    def perceive_frame(self, frame: VideoFrame) -> list[Perception]:
        """Processa un frame e scrive le percezioni risultanti (0 o 1).

        Pipeline:

        1. **Sampling.** Si considera un frame ogni `sample_every`; gli altri
           vengono scartati senza toccare hashing né captioner (costo/latenza).
        2. **Hashing / dedup.** Se l'hash del frame coincide con quello
           dell'ultimo frame descritto, è (quasi) identico: niente caption,
           niente percezione duplicata.
        3. **Caption.** Il `Captioner` descrive il frame. Una caption vuota
           (o soli spazi) non produce percezione (guardia `.strip()`).
        4. `Perception(source=VIDEO, type="caption")` nello store.

        Ritorna le percezioni create (0 o 1).
        """
        index = self._seen
        self._seen += 1

        # 1. Sampling per conteggio: solo gli indici multipli di sample_every
        #    sono candidati al captioning.
        if index % self._sample_every != 0:
            return []
        self._sampled += 1

        # 2. Dedup visuale: salta i frame non abbastanza diversi dall'ultimo
        #    effettivamente descritto.
        if not self._deduper.should_caption(frame):
            self._dedup_skipped += 1
            return []

        # 3. Caption (stadio VLM).
        try:
            text = self._captioner.caption(frame).strip()
        except Exception:
            # Anche un fallimento VLM diventa riferimento dedup: una scena
            # statica che manda in errore il modello non deve martellare la GPU
            # su ogni frame campionato. La queue registra comunque l'errore.
            self._deduper.remember(frame)
            self._failed += 1
            raise
        if not text:
            # Il VLM non ha ricavato nulla di descrivibile: niente percezione.
            # Il frame diventa comunque riferimento dedup: se una scena statica
            # resta non descrivibile, non richiamiamo il VLM all'infinito.
            self._deduper.remember(frame)
            self._empty_captions += 1
            return []

        # Il frame è stato descritto: diventa il riferimento per il dedup.
        self._deduper.remember(frame)
        self._captioned += 1
        perception = Perception(
            ts=frame.ts if frame.ts is not None else time.time(),
            source=Source.VIDEO,
            type="caption",
            text=text,
        )
        self._store.append(perception)
        return [perception]

    def _perceive_payload(self, payload: VideoFrame) -> list[Perception]:
        """Hook di `EventPerceiver`: delega alla pipeline video già testata.

        È l'aggancio fra lo `StreamCaptureAdapter` ("video") e la pipeline: gli eventi di
        canale "video" portano un `VideoFrame` come payload. La guardia su
        canale e tipo del payload vive in `EventPerceiver`.
        """
        return self.perceive_frame(payload)


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise VideoConfigError(f"{field_name} must be numeric")
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise VideoConfigError(f"{field_name} must be numeric") from exc
    if not math.isfinite(parsed):
        raise VideoConfigError(f"{field_name} must be finite")
    return parsed
