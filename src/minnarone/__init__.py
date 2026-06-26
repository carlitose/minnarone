"""Minnarone Framework — contratti fondanti (slice 00).

Espone il contratto dati `Perception` e le interfacce astratte dei moduli che
verranno implementati negli slice successivi.
"""

from __future__ import annotations

from .app import (
    Agent,
    PrivateModeNotImplemented,
    PrivateNotImplementedRouter,
    build_agent,
)
from .audio import (
    STREAMER,
    Asr,
    AudioChunk,
    AudioPerceiver,
    SpeakerTagger,
    SpeechSegment,
    Vad,
)
from .cadence import CadenceLoop
from .capture import (
    OSCaptureAdapter,
    ScreenCaptureAdapter,
    StreamCaptureAdapter,
    make_device_capture_source,
    make_device_screen_capture_source,
    os_audio_capture,
    os_screen_capture,
)
from .chat import ChatPerceiver
from .config import Config, ConfigError, DisclosureConfig, RetentionConfig, TwitchConfig
from .console import ConsoleOutputRouter
from .dashboard import DashboardState, snapshot
from .human import END_CONV_SENTINEL, HumanDecision, HumanLikeness
from .llm import LLMError, LLMProvider, LLMResult, LLMTimeout
from .memory import FactsDelta, FileMemory, Memory, MemoryBlocks
from .output import OutputMode, OutputRouter
from .perceiver import EventPerceiver
from .perception import Perception, Source
from .prompt import PromptBuilder
from .reactor import Reactor
from .senser import ConversationWindow, Senser, Trigger
from .source import RawEvent, SourceAdapter
from .store import PerceptionStore
from .summarizer import Summarizer
from .twitch_stream import TwitchStreamAdapter, TwitchStreamStats
from .video import Captioner, VideoFrame, VideoPerceiver

__all__ = [
    "Perception",
    "Source",
    "SourceAdapter",
    "RawEvent",
    "TwitchStreamAdapter",
    "TwitchStreamStats",
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
    "TwitchConfig",
    "PerceptionStore",
    "EventPerceiver",
    "ChatPerceiver",
    "AudioPerceiver",
    "AudioChunk",
    "SpeechSegment",
    "Vad",
    "Asr",
    "SpeakerTagger",
    "STREAMER",
    "StreamCaptureAdapter",
    "os_audio_capture",
    "os_screen_capture",
    "OSCaptureAdapter",
    "make_device_capture_source",
    "ScreenCaptureAdapter",
    "make_device_screen_capture_source",
    "VideoPerceiver",
    "VideoFrame",
    "Captioner",
    "Senser",
    "Trigger",
    "ConversationWindow",
    "PromptBuilder",
    "ConsoleOutputRouter",
    "Reactor",
    "Summarizer",
    "CadenceLoop",
    "HumanLikeness",
    "HumanDecision",
    "END_CONV_SENTINEL",
    "DashboardState",
    "snapshot",
    "Agent",
    "build_agent",
    "PrivateModeNotImplemented",
    "PrivateNotImplementedRouter",
]
