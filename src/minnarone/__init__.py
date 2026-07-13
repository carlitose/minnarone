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
from .asr import AsrConfig, AsrModelSetupError, FasterWhisperAsr
from .audio import (
    STREAMER,
    UNKNOWN_SPEAKER,
    Asr,
    AudioChunk,
    AudioPerceiver,
    SpeakerTagger,
    SpeechSegment,
    UnknownSpeakerTagger,
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
from .config import (
    CommentatorConfig,
    Config,
    ConfigError,
    DisclosureConfig,
    ProfileConfig,
    RetentionConfig,
    TwitchConfig,
)
from .console import ConsoleOutputRouter
from .dashboard import (
    AdapterChannelDiagnostics,
    DashboardPanel,
    DashboardState,
    LocalFailure,
    QueueChannelDiagnostics,
    SpeakerClusterDiagnostics,
    SpeakerDiagnostics,
    VideoDiagnostics,
    snapshot,
)
from .human import END_CONV_SENTINEL, HumanDecision, HumanLikeness
from .llm import LLMError, LLMProvider, LLMResult, LLMTimeout
from .memory import FactsDelta, FileMemory, Memory, MemoryBlocks
from .output import OutputMode, OutputRouter
from .perceiver import EventPerceiver
from .perception import Perception, Source
from .prompt import PromptBuilder
from .prompt_observation import (
    ObservedLLMProvider,
    PromptObservation,
    PromptObservationRecorder,
)
from .reactor import Reactor
from .senser import ConversationWindow, Senser, Trigger
from .source import RawEvent, SourceAdapter
from .speaker import (
    EmbeddingSpeakerTagger,
    OnlineSpeakerClusterer,
    SherpaOnnxSpeakerEmbeddingBackend,
    SpeakerAssignment,
    SpeakerClusteringConfig,
    SpeakerClusterStats,
    SpeakerEmbeddingBackend,
    SpeakerEmbeddingConfig,
    SpeakerEmbeddingError,
    SpeakerTaggingStats,
)
from .store import PerceptionStore
from .summarizer import Summarizer
from .twitch_stream import TwitchStreamAdapter, TwitchStreamStats
from .video import (
    ByteFrameDeduper,
    Captioner,
    FrameDeduper,
    VideoConfigError,
    VideoFrame,
    VideoPerceiver,
    VideoPerceptionConfig,
    VideoPerceptionStats,
)
from .vlm import (
    DEFAULT_QWEN_VL_PROMPT,
    Qwen2VlCaptioner,
    QwenVlCaptionError,
    QwenVlConfig,
    QwenVlConfigError,
    frame_to_pil_image,
)

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
    "CommentatorConfig",
    "ProfileConfig",
    "TwitchConfig",
    "PerceptionStore",
    "EventPerceiver",
    "ChatPerceiver",
    "AudioPerceiver",
    "AudioChunk",
    "SpeechSegment",
    "Vad",
    "Asr",
    "AsrConfig",
    "FasterWhisperAsr",
    "AsrModelSetupError",
    "SpeakerEmbeddingBackend",
    "SpeakerEmbeddingConfig",
    "SpeakerEmbeddingError",
    "SherpaOnnxSpeakerEmbeddingBackend",
    "SpeakerClusteringConfig",
    "SpeakerAssignment",
    "SpeakerClusterStats",
    "SpeakerTaggingStats",
    "OnlineSpeakerClusterer",
    "EmbeddingSpeakerTagger",
    "SpeakerTagger",
    "UnknownSpeakerTagger",
    "STREAMER",
    "UNKNOWN_SPEAKER",
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
    "FrameDeduper",
    "ByteFrameDeduper",
    "VideoPerceptionConfig",
    "VideoPerceptionStats",
    "VideoConfigError",
    "QwenVlConfig",
    "QwenVlConfigError",
    "QwenVlCaptionError",
    "Qwen2VlCaptioner",
    "DEFAULT_QWEN_VL_PROMPT",
    "frame_to_pil_image",
    "Senser",
    "Trigger",
    "ConversationWindow",
    "PromptBuilder",
    "PromptObservation",
    "PromptObservationRecorder",
    "ObservedLLMProvider",
    "ConsoleOutputRouter",
    "Reactor",
    "Summarizer",
    "CadenceLoop",
    "HumanLikeness",
    "HumanDecision",
    "END_CONV_SENTINEL",
    "DashboardPanel",
    "DashboardState",
    "QueueChannelDiagnostics",
    "AdapterChannelDiagnostics",
    "LocalFailure",
    "SpeakerDiagnostics",
    "SpeakerClusterDiagnostics",
    "VideoDiagnostics",
    "snapshot",
    "Agent",
    "build_agent",
    "PrivateModeNotImplemented",
    "PrivateNotImplementedRouter",
]
