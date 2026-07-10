"""Percezione audio: pipeline VAD -> ASR -> speaker tagging -> `Perception`.

Questo modulo è il *giunto* fra l'audio grezzo e il perception store. È un
modulo profondo: l'`AudioPerceiver` orchestra tre stadi e scrive percezioni,
ma la sua superficie pubblica è minima (`perceive_chunk` / `perceive_event`).

Pluggabilità (NFR05). I tre stadi della pipeline sono definiti come
`typing.Protocol`, NON come dipendenze concrete:

* `Vad` — voice activity detection: dato un chunk audio decide se contiene
  parlato ed estrae i segmenti vocali. Gatekeeper della pipeline: se non c'è
  parlato, l'ASR non viene nemmeno invocato (si salta il silenzio).
* `Asr` — automatic speech recognition: trascrive un segmento vocale in testo.
* `SpeakerTagger` — assegna un'etichetta di speaker a un segmento, distinguendo
  l'operatore locale ("streamer") dalle altre sorgenti (es. l'audio di un video
  riprodotto).

L'`AudioPerceiver` dipende SOLO da queste interfacce, mai da un modello
concreto. I backend reali (webrtcvad / faster-whisper / sherpa-onnx, una
diarizzazione basata su embedding) si innestano implementando i Protocol, senza
toccare il core e senza essere importati qui: restano un dettaglio del cablaggio
dell'applicazione. Per i test si usano i fake deterministici in `fakes.py`.

Il payload audio (`AudioChunk`) è volutamente opaco rispetto al formato: porta i
campioni grezzi e i metadati minimi (sample rate, canale di provenienza) di cui
gli stadi hanno bisogno. È il contratto fra lo `StreamCaptureAdapter` di canale
"audio" (costruito via `os_audio_capture`, che lo emette come
`RawEvent.payload`) e questa pipeline.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .perceiver import EventPerceiver
from .perception import Perception, Source
from .store import PerceptionStore

# Etichetta canonica per l'operatore locale (chi conduce la sessione). Le altre
# sorgenti audio (video riprodotti, ospiti, ecc.) NON devono mai ricevere questa
# etichetta: è il discrimine di EC02.
STREAMER = "streamer"
# Etichetta collettiva per ogni voce non-streamer. Il clustering interno resta
# per-cluster (cluster_id/centroidi), ma l'etichetta esposta collassa in
# un'unica identità "altro": si distingue solo l'operatore dal resto.
OTHER = "altro"
UNKNOWN_SPEAKER = "?"


@dataclass(frozen=True, slots=True)
class AudioChunk:
    """Un blocco di campioni audio grezzi, prima di VAD/ASR.

    È il `payload` dei `RawEvent` di canale "audio". Volutamente neutro rispetto
    al backend: `samples` è il dato opaco (PCM, bytes, ndarray, ...), gli altri
    campi sono i metadati minimi per gli stadi a valle.

    Attributi:
        samples: campioni audio grezzi (tipo concreto deciso dal backend).
        sample_rate: frequenza di campionamento in Hz.
        source_label: provenienza fisica del chunk, es. "mic" o "system",
            usata dallo `SpeakerTagger` per distinguere operatore e altre fonti.
        ts: epoch di cattura in secondi.
    """

    samples: object
    sample_rate: int = 16_000
    source_label: str = "mic"
    ts: float = 0.0


@dataclass(frozen=True, slots=True)
class SpeechSegment:
    """Un segmento di parlato estratto dal VAD, pronto per l'ASR.

    Porta con sé i metadati del chunk d'origine (`source_label`, `ts`) così che
    gli stadi a valle (ASR, speaker tagging) abbiano il contesto senza dover
    rileggere il chunk.
    """

    samples: object
    sample_rate: int = 16_000
    source_label: str = "mic"
    ts: float = 0.0


@runtime_checkable
class Vad(Protocol):
    """Voice activity detection: estrae i segmenti vocali da un chunk.

    Contratto: ritorna i segmenti di parlato presenti nel chunk. Un chunk di
    silenzio/rumore non vocale ritorna una sequenza vuota — è questo a impedire
    che l'ASR venga invocato sul silenzio.
    """

    def segments(self, chunk: AudioChunk) -> Sequence[SpeechSegment]:
        """I segmenti vocali nel chunk; vuoto se non c'è parlato."""
        ...


@runtime_checkable
class Asr(Protocol):
    """Automatic speech recognition: trascrive un segmento vocale in testo.

    Contratto: ritorna il testo trascritto (può essere rumoroso/imperfetto,
    EC01) oppure una stringa vuota se non ne ricava nulla.
    """

    def transcribe(self, segment: SpeechSegment) -> str:
        """Testo trascritto dal segmento; "" se nulla di intelligibile."""
        ...


@runtime_checkable
class SpeakerTagger(Protocol):
    """Assegna un'etichetta di speaker a un segmento (diarizzazione).

    Contratto: ritorna l'etichetta dello speaker. Per l'operatore locale deve
    ritornare `STREAMER`; per le altre fonti un'etichetta diversa (EC02). Può
    ritornare `None` se lo speaker è ignoto.
    """

    def tag(self, segment: SpeechSegment) -> str | None:
        """Etichetta dello speaker (`STREAMER` per l'operatore), o `None`."""
        ...


class UnknownSpeakerTagger:
    """Minimal speaker tagger for the pre-diarization ASR slice."""

    def tag(self, segment: SpeechSegment) -> str:
        """Return an explicit unknown label until speaker clustering exists."""
        return UNKNOWN_SPEAKER


class AudioPerceiver(EventPerceiver):
    """Orchestra VAD -> ASR -> speaker tagging e scrive percezioni audio.

    Modulo profondo: nasconde la pipeline a tre stadi dietro un'API semplice.
    Dipende solo dai Protocol iniettati, mai da un modello concreto. Eredita da
    `EventPerceiver` il dispatch `RawEvent` -> percezione (canale "audio",
    payload `AudioChunk`).
    """

    channel = "audio"
    payload_type = AudioChunk

    def __init__(
        self,
        store: PerceptionStore,
        vad: Vad,
        asr: Asr,
        speaker_tagger: SpeakerTagger,
    ) -> None:
        self._store = store
        self._vad = vad
        self._asr = asr
        self._tagger = speaker_tagger

    @property
    def speaker_diagnostics(self) -> object:
        """Speaker tagger/clusterer diagnostics boundary for observability."""
        return self._tagger

    def perceive_chunk(self, chunk: AudioChunk) -> list[Perception]:
        """Processa un chunk audio e scrive le percezioni risultanti.

        Pipeline:

        1. VAD estrae i segmenti vocali. Nessun parlato -> nessuna percezione
           (e l'ASR non viene invocato: si salta il silenzio).
        2. Per ogni segmento, ASR -> testo. Un testo vuoto (nulla di
           intelligibile) non produce percezione.
        3. SpeakerTagger -> etichetta speaker (`STREAMER` per l'operatore).
        4. `Perception(source=AUDIO, type="speech")` nello store.

        Trascrizioni rumorose (EC01) non rompono nulla: il testo imperfetto
        viene comunque registrato. Ritorna le percezioni create (in ordine).
        """
        created: list[Perception] = []
        for segment in self._vad.segments(chunk):
            text = self._asr.transcribe(segment).strip()
            if not text:
                # ASR non ha ricavato nulla di utilizzabile (vuoto o soli
                # spazi/whitespace): niente percezione.
                continue
            speaker = self._tagger.tag(segment) or UNKNOWN_SPEAKER
            perception = Perception(
                ts=segment.ts if segment.ts else time.time(),
                source=Source.AUDIO,
                type="speech",
                text=text,
                speaker=speaker,
            )
            self._store.append(perception)
            created.append(perception)
        return created

    def _perceive_payload(self, payload: AudioChunk) -> list[Perception]:
        """Hook di `EventPerceiver`: delega alla pipeline audio già testata.

        È l'aggancio fra lo `StreamCaptureAdapter` ("audio") e la pipeline: gli eventi di
        canale "audio" portano un `AudioChunk` come payload. La guardia su
        canale e tipo del payload vive in `EventPerceiver`.
        """
        return self.perceive_chunk(payload)
