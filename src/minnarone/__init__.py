"""Minnarone Framework — contratti fondanti (slice 00).

Espone il contratto dati `Perception` e le interfacce astratte dei moduli che
verranno implementati negli slice successivi.
"""

from __future__ import annotations

from .chat import ChatPerceiver
from .config import Config, ConfigError, DisclosureConfig, RetentionConfig
from .console import ConsoleOutputRouter
from .llm import LLMError, LLMProvider, LLMResult, LLMTimeout
from .memory import FactsDelta, FileMemory, Memory, MemoryBlocks
from .output import OutputMode, OutputRouter
from .perception import Perception, Source
from .prompt import PromptBuilder
from .reactor import Reactor
from .senser import Senser, Trigger
from .source import RawEvent, SourceAdapter
from .store import PerceptionStore
from .summarizer import Summarizer

__all__ = [
    "Perception",
    "Source",
    "SourceAdapter",
    "RawEvent",
    "LLMProvider",
    "LLMResult",
    "LLMError",
    "LLMTimeout",
    "OutputRouter",
    "OutputMode",
    "Memory",
    "MemoryBlocks",
    "FactsDelta",
    "FileMemory",
    "Config",
    "ConfigError",
    "DisclosureConfig",
    "RetentionConfig",
    "PerceptionStore",
    "ChatPerceiver",
    "Senser",
    "Trigger",
    "PromptBuilder",
    "ConsoleOutputRouter",
    "Reactor",
    "Summarizer",
]
