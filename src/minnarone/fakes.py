"""Implementazioni fake dei contratti, per i test e per il walking skeleton.

Sono deterministiche e senza dipendenze esterne: permettono di esercitare il
core end-to-end (slice 01) prima che esistano le implementazioni reali.
"""

from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator, Sequence

from .audio import STREAMER, AudioChunk, SpeechSegment
from .llm import LLMProvider, LLMResult, LLMTimeout
from .memory import Memory, MemoryBlocks
from .output import OutputMode, OutputRouter
from .source import RawEvent, SourceAdapter
from .video import VideoFrame


class FakeSourceAdapter(SourceAdapter):
    """Riproduce una sequenza predefinita di `RawEvent`."""

    def __init__(
        self, events: list[RawEvent], channels: set[str] | None = None
    ) -> None:
        self._events = list(events)
        self._channels = channels or {e.channel for e in events}
        self._started = False

    def channels(self) -> set[str]:
        return set(self._channels)

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    async def events(self) -> AsyncIterator[RawEvent]:
        for event in self._events:
            yield event


class FakeLLMProvider(LLMProvider):
    """Ritorna un messaggio deterministico; può simulare un timeout."""

    def __init__(
        self,
        message: str = "ok",
        *,
        messages: Sequence[str] | None = None,
        raise_timeout: bool = False,
        model: str = "fake-llm",
        meta: dict[str, object] | None = None,
    ) -> None:
        self._message = message
        self._messages: deque[str] | None = (
            deque(messages) if messages is not None else None
        )
        self._raise_timeout = raise_timeout
        self.model = model
        self._meta = dict(meta or {})
        self.last_prompt: str | None = None
        self.prompts: list[str] = []

    async def complete(self, prompt: str) -> LLMResult:
        self.last_prompt = prompt
        self.prompts.append(prompt)
        if self._raise_timeout:
            raise LLMTimeout("timeout simulato")
        if self._messages is not None:
            if not self._messages:
                raise AssertionError("fake LLM messages exhausted")
            message = self._messages.popleft()
        else:
            message = self._message
        return LLMResult(message=message, meta=dict(self._meta))


class FakeMemory(Memory):
    """Memoria statica in-memory (senza file). `update` resta no-op."""

    def __init__(self, soul: str = "", facts: str = "") -> None:
        self._blocks = MemoryBlocks(soul=soul, facts=facts)

    def load(self) -> MemoryBlocks:
        return self._blocks


class FakeOutputRouter(OutputRouter):
    """Cattura i messaggi instradati, per le asserzioni nei test."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, OutputMode]] = []

    async def route(self, message: str, mode: OutputMode) -> None:
        self.sent.append((message, mode))


class FakeVad:
    """VAD deterministico: tratta un chunk come parlato o silenzio.

    Per default usa una euristica esplicita: il chunk è "silenzio" se i suoi
    `samples` sono falsy (None, "", lista vuota) o se `source_label`/payload
    contengono il marcatore "silence". Altrimenti emette un singolo
    `SpeechSegment` che eredita i metadati del chunk. Si può forzare il
    comportamento con `always_speech` / `never_speech`.

    Espone `calls` per asserire quante volte è stato invocato.
    """

    def __init__(
        self, *, always_speech: bool = False, never_speech: bool = False
    ) -> None:
        self._always = always_speech
        self._never = never_speech
        self.calls = 0

    def segments(self, chunk: AudioChunk) -> Sequence[SpeechSegment]:
        self.calls += 1
        if self._never or not self._has_speech(chunk):
            return []
        return [
            SpeechSegment(
                samples=chunk.samples,
                sample_rate=chunk.sample_rate,
                source_label=chunk.source_label,
                ts=chunk.ts,
            )
        ]

    def _has_speech(self, chunk: AudioChunk) -> bool:
        if self._always:
            return True
        if not chunk.samples:
            return False
        return "silence" not in str(chunk.samples).lower()


class FakeAsr:
    """ASR deterministico: trascrive in base ai `samples` del segmento.

    Per default ritorna `str(segment.samples)`, così il test controlla il testo
    fissando i campioni. Si può passare un dizionario `transcripts` per mappare
    `source_label` -> testo, o `text` per un testo fisso. Conta le invocazioni
    in `calls`, così i test verificano che l'ASR NON sia chiamato sul silenzio.
    """

    def __init__(
        self,
        text: str | None = None,
        *,
        transcripts: dict[str, str] | None = None,
    ) -> None:
        self._text = text
        self._transcripts = transcripts or {}
        self.calls = 0

    def transcribe(self, segment: SpeechSegment) -> str:
        self.calls += 1
        if segment.source_label in self._transcripts:
            return self._transcripts[segment.source_label]
        if self._text is not None:
            return self._text
        return str(segment.samples)


class FakeSpeakerTagger:
    """Speaker tagger deterministico basato su `source_label` (EC02).

    L'audio proveniente da `streamer_label` (default "mic") è taggato come
    `STREAMER`; tutto il resto riceve l'etichetta `other_label` (default
    "video"). Permette di asserire che l'operatore sia distinto dalle altre
    fonti. Si può passare una `mapping` esplicita source_label -> speaker.
    """

    def __init__(
        self,
        *,
        streamer_label: str = "mic",
        other_label: str = "video",
        mapping: dict[str, str | None] | None = None,
    ) -> None:
        self._streamer_label = streamer_label
        self._other_label = other_label
        self._mapping = mapping
        self.calls = 0

    def tag(self, segment: SpeechSegment) -> str | None:
        self.calls += 1
        if self._mapping is not None:
            return self._mapping.get(segment.source_label)
        if segment.source_label == self._streamer_label:
            return STREAMER
        return self._other_label


class FakeCaptioner:
    """Captioner (VLM) deterministico: descrive un frame dai suoi `pixels`.

    Per default ritorna `str(frame.pixels)`, così il test controlla la caption
    fissando i pixel. Si può passare `text` per una caption fissa, o un
    dizionario `captions` per mappare la rappresentazione dei pixel -> testo.
    Conta le invocazioni in `calls`, così i test verificano che il captioner NON
    sia chiamato sui frame saltati (sampling/hashing).
    """

    def __init__(
        self,
        text: str | None = None,
        *,
        captions: dict[str, str] | None = None,
    ) -> None:
        self._text = text
        self._captions = captions or {}
        self.calls = 0

    def caption(self, frame: VideoFrame) -> str:
        self.calls += 1
        key = str(frame.pixels)
        if key in self._captions:
            return self._captions[key]
        if self._text is not None:
            return self._text
        return key
