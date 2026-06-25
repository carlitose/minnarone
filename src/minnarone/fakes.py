"""Implementazioni fake dei contratti, per i test e per il walking skeleton.

Sono deterministiche e senza dipendenze esterne: permettono di esercitare il
core end-to-end (slice 01) prima che esistano le implementazioni reali.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .llm import LLMProvider, LLMResult, LLMTimeout
from .memory import Memory, MemoryBlocks
from .output import OutputMode, OutputRouter
from .source import RawEvent, SourceAdapter


class FakeSourceAdapter(SourceAdapter):
    """Riproduce una sequenza predefinita di `RawEvent`."""

    def __init__(self, events: list[RawEvent], channels: set[str] | None = None) -> None:
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

    def __init__(self, message: str = "ok", *, raise_timeout: bool = False) -> None:
        self._message = message
        self._raise_timeout = raise_timeout
        self.last_prompt: str | None = None

    async def complete(self, prompt: str) -> LLMResult:
        self.last_prompt = prompt
        if self._raise_timeout:
            raise LLMTimeout("timeout simulato")
        return LLMResult(message=self._message)


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
