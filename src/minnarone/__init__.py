"""Minnarone Framework — contratti fondanti (slice 00).

Espone il contratto dati `Perception` e le interfacce astratte dei moduli che
verranno implementati negli slice successivi.
"""

from __future__ import annotations

from .config import Config, ConfigError, DisclosureConfig, RetentionConfig
from .llm import LLMError, LLMProvider, LLMResult, LLMTimeout
from .memory import FactsDelta, Memory, MemoryBlocks
from .output import OutputMode, OutputRouter
from .perception import Perception, Source
from .source import RawEvent, SourceAdapter

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
    "Config",
    "ConfigError",
    "DisclosureConfig",
    "RetentionConfig",
]
