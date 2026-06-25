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
    pixels = frame.pixels
    if isinstance(pixels, (bytes, bytearray, memoryview)):
        data = bytes(pixels)
    elif hasattr(pixels, "tobytes"):
        # numpy ndarray e simili: byte di contenuto, non repr troncato.
        data = pixels.tobytes()  # type: ignore[union-attr]
    else:
        try:
            data = bytes(memoryview(pixels))  # type: ignore[arg-type]
        except TypeError:
            # Stand-in di test opachi (str/int): repr come ultima risorsa.
            data = repr(pixels).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


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
        sample_every: int = 1,
    ) -> None:
        if sample_every < 1:
            raise ValueError("sample_every deve essere >= 1")
        self._store = store
        self._captioner = captioner
        self._sample_every = sample_every
        # Contatore dei frame visti, per il campionamento per conteggio.
        self._seen = 0
        # Hash dell'ultimo frame effettivamente descritto, per il dedup.
        self._last_hash: str | None = None

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

        # 2. Dedup via hashing: salta i frame identici all'ultimo descritto.
        digest = _frame_hash(frame)
        if digest == self._last_hash:
            return []

        # 3. Caption (stadio VLM).
        text = self._captioner.caption(frame).strip()
        if not text:
            # Il VLM non ha ricavato nulla di descrivibile: niente percezione.
            # Non aggiorniamo `_last_hash`: un frame "vuoto" non diventa il
            # riferimento per il dedup dei successivi.
            return []

        # Il frame è stato descritto: diventa il riferimento per il dedup.
        self._last_hash = digest
        perception = Perception(
            ts=frame.ts if frame.ts else time.time(),
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
