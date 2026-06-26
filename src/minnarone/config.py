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

from .output import OutputMode
from .twitch_audio import pcm_chunk_size_bytes
from .twitch_media import normalize_twitch_channel
from .twitch_video import validate_video_fps


class ConfigError(ValueError):
    """Configurazione mancante o non valida, con messaggio puntuale."""


@dataclass(frozen=True, slots=True)
class DisclosureConfig:
    """Punto v2 (inerte in MVP): se/come l'agente dichiara di essere un'AI."""

    announce_ai: bool = False


@dataclass(frozen=True, slots=True)
class RetentionConfig:
    """Punto v2 (inerte in MVP): per quanto tempo conservare i dati percepiti."""

    perceptions_days: int | None = None


@dataclass(frozen=True, slots=True)
class TwitchConfig:
    """Configurazione futura dell'adapter Twitch.

    Le credenziali restano fuori dal file: `TWITCH_BOT_USERNAME` e
    `TWITCH_OAUTH_TOKEN` sono lette dall'ambiente quando l'integrazione runtime
    verra' cablata.
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
        if isinstance(value, bool):
            raise ConfigError(f"{field_name} deve essere numerico")
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{field_name} deve essere numerico") from exc


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
    # --- punti di estensione v2 (presenti ma inerti) ---
    disclosure: DisclosureConfig = field(default_factory=DisclosureConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    auto_memory: bool = False
    twitch: TwitchConfig | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, OutputMode):
            raise ConfigError(f"mode non valido: {self.mode!r}")
        for name in ("soul_path", "facts_dir", "adapter", "llm_provider", "agent_name"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ConfigError(f"campo obbligatorio '{name}' mancante o vuoto")
        if self.twitch is not None and not isinstance(self.twitch, TwitchConfig):
            raise ConfigError("twitch deve essere una TwitchConfig")
        if self.adapter == "twitch" and self.twitch is None:
            raise ConfigError("adapter 'twitch' richiede la sezione 'twitch'")
        if self.senser_interval <= 0:
            raise ConfigError("senser_interval deve essere > 0")
        if self.idle_interval <= 0:
            raise ConfigError("idle_interval deve essere > 0")
        if self.summarizer_interval <= 0:
            raise ConfigError("summarizer_interval deve essere > 0")
        if self.recent_chat_window <= 0:
            raise ConfigError("recent_chat_window deve essere > 0")

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

        try:
            return cls(
                mode=mode,
                soul_path=data.get("soul_path"),  # type: ignore[arg-type]
                facts_dir=data.get("facts_dir"),  # type: ignore[arg-type]
                adapter=data.get("adapter"),  # type: ignore[arg-type]
                llm_provider=data.get("llm_provider"),  # type: ignore[arg-type]
                twitch=twitch,
                agent_name=str(data.get("agent_name", "minnarone")),
                llm_params=dict(data.get("llm_params", {})),  # type: ignore[arg-type]
                senser_interval=float(data.get("senser_interval", 0.5)),
                idle_interval=float(data.get("idle_interval", 150.0)),
                summarizer_interval=float(data.get("summarizer_interval", 30.0)),
                recent_chat_window=int(data.get("recent_chat_window", 15)),
                disclosure=DisclosureConfig(
                    announce_ai=bool(disclosure_raw.get("announce_ai", False))
                ),
                retention=RetentionConfig(
                    perceptions_days=retention_raw.get("perceptions_days")
                ),
                auto_memory=bool(data.get("auto_memory", False)),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ConfigError):
                raise
            raise ConfigError(str(exc)) from exc

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
        return cls.from_dict(data)
