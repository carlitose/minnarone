"""Schema del file di configurazione dell'agente.

Un unico file YAML dichiara come comporre e far girare l'agente. Include i
punti di estensione v2 (`disclosure`, `retention`, `auto_memory`): presenti
nello schema ma INERTI nell'MVP, così non vanno retrofittati in seguito.

La validazione è fatta a mano su dataclasses (errori chiari, indicano il
campo). Il parsing del file usa PyYAML (`yaml.safe_load`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .asr import AsrConfig, AsrConfigError
from .output import CommentatorStyle, OutputMode
from .speaker import (
    SpeakerClusteringConfig,
    SpeakerConfigError,
    SpeakerEmbeddingConfig,
)
from .twitch_audio import pcm_chunk_size_bytes
from .twitch_media import normalize_twitch_channel
from .twitch_video import validate_video_fps
from .vad import VadConfig, VadInputError
from .video import VideoConfigError, VideoPerceptionConfig
from .vlm import QwenVlConfig, QwenVlConfigError


class ConfigError(ValueError):
    """Configurazione mancante o non valida, con messaggio puntuale."""


def _coerce_commentator_style(value: object) -> CommentatorStyle:
    if isinstance(value, CommentatorStyle):
        return value
    try:
        return CommentatorStyle(value)
    except (TypeError, ValueError) as exc:
        accepted = ", ".join(style.value for style in CommentatorStyle)
        raise ConfigError(
            f"commentator.style {value!r} non valido (ammessi: {accepted})"
        ) from exc


@dataclass(frozen=True, slots=True)
class DisclosureConfig:
    """Punto v2 (inerte in MVP): se/come l'agente dichiara di essere un'AI."""

    announce_ai: bool = False


@dataclass(frozen=True, slots=True)
class RetentionConfig:
    """Punto v2 (inerte in MVP): per quanto tempo conservare i dati percepiti."""

    perceptions_days: int | None = None


@dataclass(frozen=True, slots=True)
class CommentatorConfig:
    """Modalità commentatore locale: commenti privati per l'operatore."""

    enabled: bool = False
    language: str = "it"
    idle_interval: float | None = None
    style: CommentatorStyle = CommentatorStyle.OPERATOR

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ConfigError("commentator.enabled deve essere booleano")
        object.__setattr__(self, "style", _coerce_commentator_style(self.style))
        if not isinstance(self.language, str) or not self.language.strip():
            raise ConfigError("commentator.language deve essere una stringa non vuota")
        object.__setattr__(self, "language", self.language.strip())
        if self.idle_interval is None:
            return
        if isinstance(self.idle_interval, bool):
            raise ConfigError("commentator.idle_interval deve essere > 0")
        try:
            interval = float(self.idle_interval)
        except (TypeError, ValueError) as exc:
            raise ConfigError("commentator.idle_interval deve essere > 0") from exc
        if interval <= 0:
            raise ConfigError("commentator.idle_interval deve essere > 0")
        object.__setattr__(self, "idle_interval", interval)

    @property
    def prompt_style(self) -> CommentatorStyle | None:
        """Style consumed by prompt/reaction code; None means disabled."""
        return self.style if self.enabled else None

    def idle_interval_or(self, default: float) -> float:
        """Return the commentator idle cadence when enabled, else default."""
        if self.enabled and self.idle_interval is not None:
            return self.idle_interval
        return default

    def uses_local_output(self, mode: OutputMode) -> bool:
        """Whether private mode should route commentator output locally."""
        return self.enabled and mode is OutputMode.PRIVATE

    def validate_for_mode(self, mode: OutputMode) -> None:
        """Validate commentator runtime policy against the selected output mode."""
        if self.style is CommentatorStyle.ORIGINAL_CHAT and (
            not self.enabled or mode is not OutputMode.PRIVATE
        ):
            raise ConfigError(
                "commentator.style: original_chat richiede "
                "commentator.enabled: true e mode: private"
            )
        if self.enabled and mode is not OutputMode.PRIVATE:
            raise ConfigError(
                "commentator.enabled richiede mode: private per evitare output pubblico"
            )


def _coerce_config_float(value: object, field_name: str) -> float:
    """Converte un valore numerico in float, rifiutando i booleani.

    Condivisa fra `TwitchConfig` e `OsCaptureConfig`: `True`/`False` sono
    interi in Python, quindi vanno rifiutati esplicitamente prima di `float()`.
    """
    if isinstance(value, bool):
        raise ConfigError(f"{field_name} deve essere numerico")
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{field_name} deve essere numerico") from exc


@dataclass(frozen=True, slots=True)
class TwitchConfig:
    """Configurazione dell'adapter Twitch.

    Le credenziali restano fuori dal file: `TWITCH_BOT_USERNAME` e
    `TWITCH_OAUTH_TOKEN` sono lette dall'ambiente dal runtime chat-only.
    """

    channel: str
    quality: str = "best"
    chat: bool = True
    audio: bool = False
    video: bool = False
    audio_chunk_seconds: float = 1.0
    video_fps: float = 1.0

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "channel", normalize_twitch_channel(self.channel))
        except (AttributeError, ValueError) as exc:
            raise ConfigError(f"twitch.channel: {exc}") from exc

        if not isinstance(self.quality, str) or not self.quality.strip():
            raise ConfigError("twitch.quality deve essere una stringa non vuota")
        object.__setattr__(self, "quality", self.quality.strip())

        for name in ("chat", "audio", "video"):
            if not isinstance(getattr(self, name), bool):
                raise ConfigError(f"twitch.{name} deve essere booleano")
        if not (self.chat or self.audio or self.video):
            raise ConfigError("twitch deve abilitare almeno chat, audio o video")

        audio_chunk_seconds = self._coerce_float(
            self.audio_chunk_seconds,
            "twitch.audio_chunk_seconds",
        )
        try:
            pcm_chunk_size_bytes(audio_chunk_seconds)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"twitch.audio_chunk_seconds: {exc}") from exc
        object.__setattr__(self, "audio_chunk_seconds", audio_chunk_seconds)

        raw_video_fps = self._coerce_float(self.video_fps, "twitch.video_fps")
        try:
            video_fps = validate_video_fps(raw_video_fps)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"twitch.video_fps: {exc}") from exc
        object.__setattr__(self, "video_fps", video_fps)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "TwitchConfig":
        """Costruisce e valida il blocco `twitch:` futuro."""
        allowed = {
            "channel",
            "quality",
            "chat",
            "audio",
            "video",
            "audio_chunk_seconds",
            "video_fps",
        }
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ConfigError(
                "campi twitch non riconosciuti: "
                + ", ".join(f"'{key}'" for key in unknown)
            )
        if "channel" not in data:
            raise ConfigError("campo obbligatorio 'twitch.channel' mancante")
        return cls(
            channel=data["channel"],  # type: ignore[arg-type]
            quality=data.get("quality", "best"),  # type: ignore[arg-type]
            chat=data.get("chat", True),  # type: ignore[arg-type]
            audio=data.get("audio", False),  # type: ignore[arg-type]
            video=data.get("video", False),  # type: ignore[arg-type]
            audio_chunk_seconds=data.get("audio_chunk_seconds", 1.0),  # type: ignore[arg-type]
            video_fps=data.get("video_fps", 1.0),  # type: ignore[arg-type]
        )

    @staticmethod
    def _coerce_float(value: object, field_name: str) -> float:
        return _coerce_config_float(value, field_name)


@dataclass(frozen=True, slots=True)
class OsCaptureConfig:
    """Configurazione dell'adapter di cattura del sistema operativo.

    Osserva l'output audio/video della macchina locale (es. una call Teams)
    invece di uno stream remoto. Modella la sezione `os_capture:` del file YAML.
    """

    audio: bool = True
    video: bool = True
    audio_chunk_seconds: float = 1.0
    video_fps: float = 1.0
    monitor: int = 1

    def __post_init__(self) -> None:
        for name in ("audio", "video"):
            if not isinstance(getattr(self, name), bool):
                raise ConfigError(f"os_capture.{name} deve essere booleano")
        if not (self.audio or self.video):
            raise ConfigError("os_capture deve abilitare almeno audio o video")

        audio_chunk_seconds = _coerce_config_float(
            self.audio_chunk_seconds,
            "os_capture.audio_chunk_seconds",
        )
        try:
            pcm_chunk_size_bytes(audio_chunk_seconds)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"os_capture.audio_chunk_seconds: {exc}") from exc
        object.__setattr__(self, "audio_chunk_seconds", audio_chunk_seconds)

        raw_video_fps = _coerce_config_float(self.video_fps, "os_capture.video_fps")
        try:
            video_fps = validate_video_fps(raw_video_fps)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"os_capture.video_fps: {exc}") from exc
        object.__setattr__(self, "video_fps", video_fps)

        if (
            isinstance(self.monitor, bool)
            or not isinstance(self.monitor, int)
            or self.monitor < 1
        ):
            raise ConfigError("os_capture.monitor deve essere un intero >= 1")

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "OsCaptureConfig":
        """Costruisce e valida il blocco `os_capture:`, rifiutando campi ignoti."""
        allowed = {
            "audio",
            "video",
            "audio_chunk_seconds",
            "video_fps",
            "monitor",
        }
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ConfigError(
                "campi os_capture non riconosciuti: "
                + ", ".join(f"'{key}'" for key in unknown)
            )
        return cls(
            audio=data.get("audio", True),  # type: ignore[arg-type]
            video=data.get("video", True),  # type: ignore[arg-type]
            audio_chunk_seconds=data.get("audio_chunk_seconds", 1.0),  # type: ignore[arg-type]
            video_fps=data.get("video_fps", 1.0),  # type: ignore[arg-type]
            monitor=data.get("monitor", 1),  # type: ignore[arg-type]
        )


def _vad_config_from_dict(data: dict[str, object]) -> VadConfig:
    allowed = {
        "mode",
        "frame_ms",
        "padding_ms",
        "max_utterance_seconds",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(
            "campi vad non riconosciuti: " + ", ".join(f"'{key}'" for key in unknown)
        )
    try:
        return VadConfig(
            mode=data.get("mode", 2),  # type: ignore[arg-type]
            frame_ms=data.get("frame_ms", 30),  # type: ignore[arg-type]
            padding_ms=data.get("padding_ms", 300),  # type: ignore[arg-type]
            max_utterance_seconds=data.get("max_utterance_seconds", 30.0),  # type: ignore[arg-type]
        )
    except VadInputError as exc:
        raise ConfigError(f"vad.{exc}") from exc


def _asr_config_from_dict(data: dict[str, object]) -> AsrConfig:
    allowed = {
        "model",
        "device",
        "compute_type",
        "language",
        "beam_size",
        "condition_on_previous_text",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(
            "campi asr non riconosciuti: "
            + ", ".join(f"asr.{key}" for key in unknown)
        )
    try:
        return AsrConfig(
            model=data.get("model", "large-v3-turbo"),  # type: ignore[arg-type]
            device=data.get("device", "auto"),  # type: ignore[arg-type]
            compute_type=data.get("compute_type", "default"),  # type: ignore[arg-type]
            language=data.get("language"),  # type: ignore[arg-type]
            beam_size=data.get("beam_size", 5),  # type: ignore[arg-type]
            condition_on_previous_text=data.get(
                "condition_on_previous_text", False
            ),  # type: ignore[arg-type]
        )
    except AsrConfigError as exc:
        raise ConfigError(f"asr.{exc}") from exc


def _speaker_embedding_config_from_dict(
    data: dict[str, object],
) -> SpeakerEmbeddingConfig:
    allowed = {
        "model_path",
        "provider",
        "num_threads",
        "dimension",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(
            "campi speaker_embedding non riconosciuti: "
            + ", ".join(f"speaker_embedding.{key}" for key in unknown)
        )
    try:
        return SpeakerEmbeddingConfig(
            model_path=data.get("model_path"),  # type: ignore[arg-type]
            provider=data.get("provider", "cpu"),  # type: ignore[arg-type]
            num_threads=data.get("num_threads", 1),  # type: ignore[arg-type]
            dimension=data.get("dimension", 192),  # type: ignore[arg-type]
        )
    except SpeakerConfigError as exc:
        raise ConfigError(f"speaker_embedding.{exc}") from exc


def _speaker_clustering_config_from_dict(
    data: dict[str, object],
) -> SpeakerClusteringConfig:
    allowed = {
        "threshold",
        "warmup_seconds",
        "min_update_seconds",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(
            "campi speaker_clustering non riconosciuti: "
            + ", ".join(f"speaker_clustering.{key}" for key in unknown)
        )
    try:
        return SpeakerClusteringConfig(
            threshold=data.get("threshold", 0.6),  # type: ignore[arg-type]
            warmup_seconds=data.get("warmup_seconds", 60.0),  # type: ignore[arg-type]
            min_update_seconds=data.get(
                "min_update_seconds", 1.0
            ),  # type: ignore[arg-type]
        )
    except SpeakerConfigError as exc:
        raise ConfigError(f"speaker_clustering.{exc}") from exc


def _video_config_from_dict(data: dict[str, object]) -> VideoPerceptionConfig:
    allowed = {
        "sample_every",
        "dedup_change_threshold",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(
            "campi video non riconosciuti: "
            + ", ".join(f"video.{key}" for key in unknown)
        )
    try:
        return VideoPerceptionConfig(
            sample_every=data.get("sample_every", 1),  # type: ignore[arg-type]
            dedup_change_threshold=data.get(
                "dedup_change_threshold", 0.0
            ),  # type: ignore[arg-type]
        )
    except VideoConfigError as exc:
        raise ConfigError(f"video.{exc}") from exc


def _vlm_config_from_dict(data: dict[str, object]) -> QwenVlConfig:
    allowed = {
        "model",
        "device",
        "device_map",
        "torch_dtype",
        "attn_implementation",
        "max_new_tokens",
        "timeout_seconds",
        "language",
        "prompt",
        "max_caption_chars",
        "max_image_edge",
        "max_image_pixels",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(
            "campi vlm non riconosciuti: " + ", ".join(f"vlm.{key}" for key in unknown)
        )
    try:
        return QwenVlConfig(
            model=data.get("model"),  # type: ignore[arg-type]
            device=data.get("device", "auto"),  # type: ignore[arg-type]
            device_map=data.get("device_map", "auto"),  # type: ignore[arg-type]
            torch_dtype=data.get("torch_dtype", "auto"),  # type: ignore[arg-type]
            attn_implementation=data.get("attn_implementation"),  # type: ignore[arg-type]
            max_new_tokens=data.get("max_new_tokens", 48),  # type: ignore[arg-type]
            timeout_seconds=data.get("timeout_seconds", 30.0),  # type: ignore[arg-type]
            language=data.get("language", "en"),  # type: ignore[arg-type]
            prompt=data.get("prompt", QwenVlConfig().prompt),  # type: ignore[arg-type]
            max_caption_chars=data.get("max_caption_chars", 240),  # type: ignore[arg-type]
            max_image_edge=data.get("max_image_edge", 768),  # type: ignore[arg-type]
            max_image_pixels=data.get("max_image_pixels", 500_000),  # type: ignore[arg-type]
        )
    except QwenVlConfigError as exc:
        raise ConfigError(f"vlm.{exc}") from exc


def _commentator_config_from_dict(data: dict[str, object]) -> CommentatorConfig:
    allowed = {
        "enabled",
        "language",
        "idle_interval",
        "style",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(
            "campi commentator non riconosciuti: "
            + ", ".join(f"commentator.{key}" for key in unknown)
        )
    return CommentatorConfig(
        enabled=data.get("enabled", False),  # type: ignore[arg-type]
        language=data.get("language", "it"),  # type: ignore[arg-type]
        idle_interval=data.get("idle_interval"),  # type: ignore[arg-type]
        style=data.get("style", CommentatorStyle.OPERATOR),  # type: ignore[arg-type]
    )


@dataclass(frozen=True, slots=True)
class Config:
    """Configurazione completa dell'agente.

    Campi MVP operativi + punti v2 inerti (`disclosure`, `retention`,
    `auto_memory`).
    """

    mode: OutputMode
    soul_path: str
    facts_dir: str
    adapter: str
    llm_provider: str
    # Nome a cui l'agente risponde (rilevamento menzioni nel Senser). OPZIONALE
    # e additivo: se omesso usa un default sensato, così le config minimali
    # restano valide. È il nome che l'agente riconosce come rivolto a sé.
    agent_name: str = "minnarone"
    llm_params: dict[str, object] = field(default_factory=dict)
    senser_interval: float = 0.5
    idle_interval: float = 150.0
    # Cadenza del loop del Summarizer (memoria a breve termine): ogni quanti
    # secondi rigenerare il riassunto della sessione. Additivo e opzionale.
    summarizer_interval: float = 30.0
    recent_chat_window: int = 15
    # Work queue locale per percezioni audio/video model-backed: impedisce che
    # ASR/VLM lenti facciano crescere memoria senza limiti.
    perception_queue_size: int = 32
    perception_shutdown_timeout: float = 5.0
    # --- punti di estensione v2 (presenti ma inerti) ---
    disclosure: DisclosureConfig = field(default_factory=DisclosureConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    auto_memory: bool = False
    twitch: TwitchConfig | None = None
    os_capture: OsCaptureConfig | None = None
    vad: VadConfig = field(default_factory=VadConfig)
    asr: AsrConfig = field(default_factory=AsrConfig)
    speaker_embedding: SpeakerEmbeddingConfig = field(
        default_factory=SpeakerEmbeddingConfig
    )
    speaker_clustering: SpeakerClusteringConfig = field(
        default_factory=SpeakerClusteringConfig
    )
    video: VideoPerceptionConfig = field(default_factory=VideoPerceptionConfig)
    vlm: QwenVlConfig = field(default_factory=QwenVlConfig)
    commentator: CommentatorConfig = field(default_factory=CommentatorConfig)

    def __post_init__(self) -> None:
        if not isinstance(self.mode, OutputMode):
            raise ConfigError(f"mode non valido: {self.mode!r}")
        for name in ("soul_path", "facts_dir", "adapter", "llm_provider", "agent_name"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ConfigError(f"campo obbligatorio '{name}' mancante o vuoto")
        if self.twitch is not None and not isinstance(self.twitch, TwitchConfig):
            raise ConfigError("twitch deve essere una TwitchConfig")
        if self.os_capture is not None and not isinstance(
            self.os_capture, OsCaptureConfig
        ):
            raise ConfigError("os_capture deve essere una OsCaptureConfig")
        if not isinstance(self.vad, VadConfig):
            raise ConfigError("vad deve essere una VadConfig")
        if not isinstance(self.asr, AsrConfig):
            raise ConfigError("asr deve essere una AsrConfig")
        if not isinstance(self.speaker_embedding, SpeakerEmbeddingConfig):
            raise ConfigError("speaker_embedding deve essere una SpeakerEmbeddingConfig")
        if not isinstance(self.speaker_clustering, SpeakerClusteringConfig):
            raise ConfigError(
                "speaker_clustering deve essere una SpeakerClusteringConfig"
            )
        if not isinstance(self.video, VideoPerceptionConfig):
            raise ConfigError("video deve essere una VideoPerceptionConfig")
        if not isinstance(self.vlm, QwenVlConfig):
            raise ConfigError("vlm deve essere una QwenVlConfig")
        if not isinstance(self.commentator, CommentatorConfig):
            raise ConfigError("commentator deve essere una CommentatorConfig")
        self.commentator.validate_for_mode(self.mode)
        if self.adapter == "twitch" and self.twitch is None:
            raise ConfigError("adapter 'twitch' richiede la sezione 'twitch'")
        if self.adapter == "os_capture" and self.os_capture is None:
            raise ConfigError("adapter 'os_capture' richiede la sezione 'os_capture'")
        if self.senser_interval <= 0:
            raise ConfigError("senser_interval deve essere > 0")
        if self.idle_interval <= 0:
            raise ConfigError("idle_interval deve essere > 0")
        if self.summarizer_interval <= 0:
            raise ConfigError("summarizer_interval deve essere > 0")
        if self.recent_chat_window <= 0:
            raise ConfigError("recent_chat_window deve essere > 0")
        if (
            isinstance(self.perception_queue_size, bool)
            or not isinstance(self.perception_queue_size, int)
            or self.perception_queue_size < 1
        ):
            raise ConfigError("perception_queue_size deve essere un intero >= 1")
        if (
            isinstance(self.perception_shutdown_timeout, bool)
            or not isinstance(self.perception_shutdown_timeout, (int, float))
            or self.perception_shutdown_timeout <= 0
        ):
            raise ConfigError("perception_shutdown_timeout deve essere > 0")

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Config":
        """Costruisce e valida una Config da un dizionario (es. TOML parsato)."""
        if "mode" not in data:
            raise ConfigError("campo obbligatorio 'mode' mancante")
        try:
            mode = OutputMode(data["mode"])
        except ValueError as exc:
            raise ConfigError(
                f"mode {data['mode']!r} non valido (ammessi: public, private)"
            ) from exc

        disclosure_raw = data.get("disclosure", {})
        retention_raw = data.get("retention", {})
        if not isinstance(disclosure_raw, dict) or not isinstance(retention_raw, dict):
            raise ConfigError("'disclosure' e 'retention' devono essere tabelle")
        twitch_raw = data.get("twitch")
        if twitch_raw is not None and not isinstance(twitch_raw, dict):
            raise ConfigError("'twitch' deve essere una tabella")
        twitch = TwitchConfig.from_dict(twitch_raw) if twitch_raw is not None else None
        os_capture_raw = data.get("os_capture")
        if os_capture_raw is not None and not isinstance(os_capture_raw, dict):
            raise ConfigError("'os_capture' deve essere una tabella")
        os_capture = (
            OsCaptureConfig.from_dict(os_capture_raw)
            if os_capture_raw is not None
            else None
        )
        vad_raw = data.get("vad", {})
        if not isinstance(vad_raw, dict):
            raise ConfigError("'vad' deve essere una tabella")
        vad = _vad_config_from_dict(vad_raw)
        asr_raw = data.get("asr", {})
        if not isinstance(asr_raw, dict):
            raise ConfigError("'asr' deve essere una tabella")
        asr = _asr_config_from_dict(asr_raw)
        speaker_embedding_raw = data.get("speaker_embedding", {})
        if not isinstance(speaker_embedding_raw, dict):
            raise ConfigError("'speaker_embedding' deve essere una tabella")
        speaker_embedding = _speaker_embedding_config_from_dict(speaker_embedding_raw)
        speaker_clustering_raw = data.get("speaker_clustering", {})
        if not isinstance(speaker_clustering_raw, dict):
            raise ConfigError("'speaker_clustering' deve essere una tabella")
        speaker_clustering = _speaker_clustering_config_from_dict(
            speaker_clustering_raw
        )
        video_raw = data.get("video", {})
        if not isinstance(video_raw, dict):
            raise ConfigError("'video' deve essere una tabella")
        video = _video_config_from_dict(video_raw)
        vlm_raw = data.get("vlm", {})
        if not isinstance(vlm_raw, dict):
            raise ConfigError("'vlm' deve essere una tabella")
        vlm = _vlm_config_from_dict(vlm_raw)
        commentator_raw = data.get("commentator", {})
        if not isinstance(commentator_raw, dict):
            raise ConfigError("'commentator' deve essere una tabella")
        commentator = _commentator_config_from_dict(commentator_raw)

        try:
            return cls(
                mode=mode,
                soul_path=data.get("soul_path"),  # type: ignore[arg-type]
                facts_dir=data.get("facts_dir"),  # type: ignore[arg-type]
                adapter=data.get("adapter"),  # type: ignore[arg-type]
                llm_provider=data.get("llm_provider"),  # type: ignore[arg-type]
                twitch=twitch,
                os_capture=os_capture,
                agent_name=str(data.get("agent_name", "minnarone")),
                llm_params=dict(data.get("llm_params", {})),  # type: ignore[arg-type]
                senser_interval=float(data.get("senser_interval", 0.5)),
                idle_interval=float(data.get("idle_interval", 150.0)),
                summarizer_interval=float(data.get("summarizer_interval", 30.0)),
                recent_chat_window=int(data.get("recent_chat_window", 15)),
                perception_queue_size=cls._positive_int(
                    data.get("perception_queue_size", 32),
                    "perception_queue_size",
                ),
                perception_shutdown_timeout=cls._positive_float(
                    data.get("perception_shutdown_timeout", 5.0),
                    "perception_shutdown_timeout",
                ),
                disclosure=DisclosureConfig(
                    announce_ai=bool(disclosure_raw.get("announce_ai", False))
                ),
                retention=RetentionConfig(
                    perceptions_days=retention_raw.get("perceptions_days")
                ),
                auto_memory=bool(data.get("auto_memory", False)),
                vad=vad,
                asr=asr,
                speaker_embedding=speaker_embedding,
                speaker_clustering=speaker_clustering,
                video=video,
                vlm=vlm,
                commentator=commentator,
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ConfigError):
                raise
            raise ConfigError(str(exc)) from exc

    @staticmethod
    def _positive_int(value: object, field_name: str) -> int:
        if isinstance(value, bool):
            raise ConfigError(f"{field_name} deve essere un intero >= 1")
        if isinstance(value, float) and not value.is_integer():
            raise ConfigError(f"{field_name} deve essere un intero >= 1")
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{field_name} deve essere un intero >= 1") from exc
        if parsed < 1:
            raise ConfigError(f"{field_name} deve essere un intero >= 1")
        return parsed

    @staticmethod
    def _positive_float(value: object, field_name: str) -> float:
        if isinstance(value, bool):
            raise ConfigError(f"{field_name} deve essere > 0")
        try:
            parsed = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{field_name} deve essere > 0") from exc
        if parsed <= 0:
            raise ConfigError(f"{field_name} deve essere > 0")
        return parsed

    @staticmethod
    def _with_config_relative_memory_paths(
        data: dict[str, object],
        config_dir: Path,
    ) -> dict[str, object]:
        resolved = dict(data)
        for field_name in ("soul_path", "facts_dir"):
            value = resolved.get(field_name)
            if not isinstance(value, str) or not value:
                continue
            path = Path(value)
            if not path.is_absolute():
                resolved[field_name] = str(config_dir / path)
        return resolved

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        """Carica e valida una Config da un file YAML."""
        p = Path(path)
        if not p.is_file():
            raise ConfigError(f"file di config non trovato: {p}")
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if data is None:
            raise ConfigError(f"file di config vuoto: {p}")
        if not isinstance(data, dict):
            raise ConfigError("la radice del file di config deve essere una mappa")
        return cls.from_dict(
            cls._with_config_relative_memory_paths(data, p.resolve().parent)
        )
