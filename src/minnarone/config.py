"""Schema del file di configurazione dell'agente.

Un unico file YAML dichiara come comporre e far girare l'agente. Include i
punti di estensione v2 (`disclosure`, `retention`, `auto_memory`): presenti
nello schema ma INERTI nell'MVP, così non vanno retrofittati in seguito.

La validazione è fatta a mano su dataclasses (errori chiari, indicano il
campo). Il parsing del file usa PyYAML (`yaml.safe_load`).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import TypeVar, Union
from urllib.parse import urlsplit

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


_EnumT = TypeVar("_EnumT", bound=Enum)


def _coerce_enum(
    value: object,
    enum_cls: type[_EnumT],
    field_name: str,
    *,
    false_alias: _EnumT | None = None,
) -> _EnumT:
    """Coerce un valore di config in un membro dell'enum, con errore puntuale.

    `false_alias`: membro restituito quando il valore è il booleano False.
    Copre TUTTE le grafie falsy di YAML 1.1 (PyYAML): `off`, `no`, `false`,
    `n`, ... non quotate arrivano qui come False.
    """
    if isinstance(value, enum_cls):
        return value
    if false_alias is not None and value is False:
        return false_alias
    try:
        return enum_cls(value)
    except (TypeError, ValueError) as exc:
        accepted = ", ".join(member.value for member in enum_cls)
        raise ConfigError(
            f"{field_name} {value!r} non valido (ammessi: {accepted})"
        ) from exc


@dataclass(frozen=True, slots=True)
class DisclosureConfig:
    """Stance operativa: annuncio AI esplicito oppure non-proattivo e veritiero."""

    announce_ai: bool = False


@dataclass(frozen=True, slots=True)
class RetentionConfig:
    """Punto v2 (inerte in MVP): per quanto tempo conservare i dati percepiti."""

    perceptions_days: int | None = None


@dataclass(frozen=True, slots=True)
class CommentatorConfig:
    """Modalità commentatore locale: profili multipli per l'operatore.

    I profili attivi determinano lo stile del commentatore. Un dizionario
    vuoto equivale a commentatore disabilitato.
    """

    language: str = "it"
    profiles: dict[CommentatorStyle, "ProfileConfig"] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.language, str) or not self.language.strip():
            raise ConfigError("commentator.language deve essere una stringa non vuota")
        object.__setattr__(self, "language", self.language.strip())
        if not isinstance(self.profiles, dict):
            raise ConfigError("commentator.profiles deve essere un dizionario")

    def active_styles(self) -> list[CommentatorStyle]:
        """Return the list of active commentator styles (profile keys)."""
        return list(self.profiles.keys())

    def uses_local_output(self, mode: OutputMode) -> bool:
        """Whether private mode should route commentator output locally."""
        return len(self.profiles) > 0 and mode is OutputMode.PRIVATE

    _PRIVATE_ONLY_STYLES = frozenset(
        {CommentatorStyle.MEETING_SYNTHESIZER, CommentatorStyle.SUGGESTER}
    )

    def validate_for_mode(self, mode: OutputMode) -> None:
        """Validate commentator runtime policy against the selected output mode."""
        if mode is not OutputMode.PRIVATE:
            private_only = self._PRIVATE_ONLY_STYLES & self.profiles.keys()
            if private_only:
                names = ", ".join(sorted(s.value for s in private_only))
                raise ConfigError(f"profilo/i {names} richiede mode: private")


@dataclass(frozen=True, slots=True)
class OperatorProfileConfig:
    """Per-profile settings for the OPERATOR commentator style."""

    idle_interval: float | None = None

    def __post_init__(self) -> None:
        if self.idle_interval is not None:
            if isinstance(self.idle_interval, bool):
                raise ConfigError("OperatorProfileConfig.idle_interval deve essere > 0")
            try:
                interval = float(self.idle_interval)
            except (TypeError, ValueError) as exc:
                raise ConfigError(
                    "OperatorProfileConfig.idle_interval deve essere > 0"
                ) from exc
            if interval <= 0:
                raise ConfigError("OperatorProfileConfig.idle_interval deve essere > 0")
            object.__setattr__(self, "idle_interval", interval)


@dataclass(frozen=True, slots=True)
class OriginalChatProfileConfig:
    """Per-profile settings for the ORIGINAL_CHAT commentator style."""

    idle_interval: float | None = None

    def __post_init__(self) -> None:
        if self.idle_interval is not None:
            if isinstance(self.idle_interval, bool):
                raise ConfigError(
                    "OriginalChatProfileConfig.idle_interval deve essere > 0"
                )
            try:
                interval = float(self.idle_interval)
            except (TypeError, ValueError) as exc:
                raise ConfigError(
                    "OriginalChatProfileConfig.idle_interval deve essere > 0"
                ) from exc
            if interval <= 0:
                raise ConfigError(
                    "OriginalChatProfileConfig.idle_interval deve essere > 0"
                )
            object.__setattr__(self, "idle_interval", interval)


@dataclass(frozen=True, slots=True)
class MeetingSynthesizerProfileConfig:
    """Per-profile settings for the MEETING_SYNTHESIZER commentator style."""

    interval_s: float = 180.0

    def __post_init__(self) -> None:
        if isinstance(self.interval_s, bool):
            raise ConfigError(
                "MeetingSynthesizerProfileConfig.interval_s deve essere > 0"
            )
        try:
            interval = float(self.interval_s)
        except (TypeError, ValueError) as exc:
            raise ConfigError(
                "MeetingSynthesizerProfileConfig.interval_s deve essere > 0"
            ) from exc
        if interval <= 0:
            raise ConfigError(
                "MeetingSynthesizerProfileConfig.interval_s deve essere > 0"
            )
        object.__setattr__(self, "interval_s", interval)


@dataclass(frozen=True, slots=True)
class SuggesterProfileConfig:
    """Per-profile settings for the SUGGESTER commentator style (no fields yet)."""


#: Union type for all profile configuration dataclasses.
ProfileConfig = Union[
    OperatorProfileConfig,
    OriginalChatProfileConfig,
    MeetingSynthesizerProfileConfig,
    SuggesterProfileConfig,
]

#: Maps each commentator style to its ProfileConfig dataclass.
_STYLE_PROFILE_CLASS: dict[CommentatorStyle, type] = {
    CommentatorStyle.OPERATOR: OperatorProfileConfig,
    CommentatorStyle.ORIGINAL_CHAT: OriginalChatProfileConfig,
    CommentatorStyle.MEETING_SYNTHESIZER: MeetingSynthesizerProfileConfig,
    CommentatorStyle.SUGGESTER: SuggesterProfileConfig,
}


def _build_profile_from_dict(
    style: CommentatorStyle,
    data: dict[str, object],
) -> ProfileConfig:
    """Build a typed ProfileConfig from a raw dict, rejecting unknown keys."""
    config_cls = _STYLE_PROFILE_CLASS[style]
    allowed = {f.name for f in fields(config_cls)}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(
            f"campi commentator.profiles.{style.value} non riconosciuti: "
            + ", ".join(f"'{key}'" for key in unknown)
        )
    return config_cls(**data)  # type: ignore[return-value]


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


def _coerce_config_positive_int(value: object, field_name: str) -> int:
    """Valida un intero di config con minimo 1, rifiutando i booleani.

    Nota: i controlli equivalenti dei campi fratelli (`os_capture.monitor`,
    `perception_queue_size`) possono adottare questo helper in futuro.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(f"{field_name} deve essere un intero >= 1")
    return value


def _normalized_channel(value: object, field_name: str) -> str:
    """Normalizza un canale Twitch dichiarato in config, indicando il campo.

    Un valore non stringa è rifiutato esplicitamente come errore di schema,
    senza affidarsi all'`AttributeError` interno di `normalize_twitch_channel`.
    """
    if not isinstance(value, str):
        raise ConfigError(f"{field_name}: {value!r} non è un canale Twitch valido")
    try:
        return normalize_twitch_channel(value)
    except ValueError as exc:
        raise ConfigError(f"{field_name}: {exc}") from exc


#: Variabile d'ambiente del token di SCRITTURA per l'invio pubblico su Twitch.
#: Distinta dal token di lettura (`TWITCH_OAUTH_TOKEN`): una config read-only
#: non deve mai avere il potere di inviare. Ne viene verificata solo la
#: PRESENZA (al build dell'agente, vedi `app.build_agent`); il valore non
#: entra mai in messaggi d'errore, log o artefatti.
TWITCH_SEND_TOKEN_ENV_VAR = "TWITCH_SEND_OAUTH_TOKEN"


class TwitchSendMode(Enum):
    """Stato dell'invio pubblico: spento, prova senza rete, o invio reale."""

    OFF = "off"
    SHADOW = "shadow"
    LIVE = "live"


def _coerce_send_mode(value: object) -> TwitchSendMode:
    # YAML 1.1 (PyYAML) interpreta le grafie truthy non quotate (`on`, `yes`,
    # `true`, ...) come booleano True: nessuna corrisponde a un modo valido,
    # quindi l'errore suggerisce esplicitamente di quotare il valore.
    if isinstance(value, bool) and value is True:
        quoted = [f"'{mode.value}'" for mode in TwitchSendMode]
        accepted = ", ".join(quoted[:-1]) + f" o {quoted[-1]}"
        raise ConfigError(
            f"twitch.send.mode: usa {accepted} (quota il valore: "
            "YAML interpreta on/yes/true come booleano)"
        )
    # `false_alias`: `mode: off` non quotato è la grafia naturale del default
    # e YAML lo parsa come False (insieme a ogni altra grafia falsy).
    return _coerce_enum(
        value, TwitchSendMode, "twitch.send.mode", false_alias=TwitchSendMode.OFF
    )


@dataclass(frozen=True, slots=True)
class TwitchSendConfig:
    """Configurazione dell'invio pubblico in chat Twitch (blocco `twitch.send`).

    Default conservativi: `mode: off` (nessun invio), allow-list vuota, budget
    ben sotto i limiti IRC di Twitch (1 msg/min, 20 msg/ora) e auto-degrado a
    shadow dopo 3 invii falliti consecutivi.
    """

    mode: TwitchSendMode = TwitchSendMode.OFF
    allowed_channels: tuple[str, ...] = ()
    max_per_minute: int = 1
    max_per_hour: int = 20
    failure_threshold: int = 3

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", _coerce_send_mode(self.mode))

        channels = self.allowed_channels
        if isinstance(channels, str) or not isinstance(channels, (list, tuple)):
            raise ConfigError(
                "twitch.send.allowed_channels deve essere una lista di canali"
            )
        normalized = tuple(
            _normalized_channel(channel, "twitch.send.allowed_channels")
            for channel in channels
        )
        object.__setattr__(self, "allowed_channels", normalized)

        for name in ("max_per_minute", "max_per_hour", "failure_threshold"):
            object.__setattr__(
                self,
                name,
                _coerce_config_positive_int(getattr(self, name), f"twitch.send.{name}"),
            )

    def validate_for_mode(self, mode: OutputMode) -> None:
        """Gate cross-field: l'invio pubblico ha senso solo con output public.

        Speculare a `CommentatorConfig.validate_for_mode`: chiamato da
        `Config.__post_init__`, dove il mode di root è noto.
        """
        if self.mode is not TwitchSendMode.OFF and mode is not OutputMode.PUBLIC:
            raise ConfigError(
                f"twitch.send.mode: '{self.mode.value}' richiede mode: public"
            )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "TwitchSendConfig":
        """Costruisce e valida il blocco `twitch.send:`, rifiutando campi ignoti."""
        allowed = {
            "mode",
            "allowed_channels",
            "max_per_minute",
            "max_per_hour",
            "failure_threshold",
        }
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ConfigError(
                "campi twitch.send non riconosciuti: "
                + ", ".join(f"'{key}'" for key in unknown)
            )
        return cls(
            mode=data.get("mode", TwitchSendMode.OFF),  # type: ignore[arg-type]
            allowed_channels=data.get("allowed_channels", ()),  # type: ignore[arg-type]
            max_per_minute=data.get("max_per_minute", 1),  # type: ignore[arg-type]
            max_per_hour=data.get("max_per_hour", 20),  # type: ignore[arg-type]
            failure_threshold=data.get("failure_threshold", 3),  # type: ignore[arg-type]
        )


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
    send: TwitchSendConfig = field(default_factory=TwitchSendConfig)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "channel", _normalized_channel(self.channel, "twitch.channel")
        )

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

        if not isinstance(self.send, TwitchSendConfig):
            raise ConfigError("twitch.send deve essere una TwitchSendConfig")
        self._validate_live_send_requirements()

    def _validate_live_send_requirements(self) -> None:
        """Gate cross-field di `mode: live`: il canale deve essere in allow-list.

        La PRESENZA del token di scrittura (`TWITCH_SEND_TOKEN_ENV_VAR`) è
        verificata al build dell'agente (vedi `app.build_agent`), non qui: lo
        schema resta puro rispetto allo stato del processo.
        """
        if self.send.mode is not TwitchSendMode.LIVE:
            return
        if self.channel not in self.send.allowed_channels:
            raise ConfigError(
                f"twitch.send.mode: live richiede che il canale "
                f"'{self.channel}' sia in twitch.send.allowed_channels"
            )

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
            "send",
        }
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ConfigError(
                "campi twitch non riconosciuti: "
                + ", ".join(f"'{key}'" for key in unknown)
            )
        if "channel" not in data:
            raise ConfigError("campo obbligatorio 'twitch.channel' mancante")
        send_raw = data.get("send")
        if send_raw is not None and not isinstance(send_raw, dict):
            raise ConfigError("'twitch.send' deve essere una tabella")
        send = TwitchSendConfig.from_dict(send_raw or {})
        return cls(
            channel=data["channel"],  # type: ignore[arg-type]
            quality=data.get("quality", "best"),  # type: ignore[arg-type]
            chat=data.get("chat", True),  # type: ignore[arg-type]
            audio=data.get("audio", False),  # type: ignore[arg-type]
            video=data.get("video", False),  # type: ignore[arg-type]
            audio_chunk_seconds=data.get("audio_chunk_seconds", 1.0),  # type: ignore[arg-type]
            video_fps=data.get("video_fps", 1.0),  # type: ignore[arg-type]
            send=send,
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


@dataclass(frozen=True, slots=True)
class LlamaCppConfig:
    """Blocco `llamacpp:`: dove trovare il `llama-server` locale.

    Il server è avviato A MANO dall'utente (minnarone non gestisce il
    processo): l'unica chiave è `base_url`. Niente `model` in config: il
    server serve il solo modello caricato e il campo verrebbe ignorato.
    La validazione è di sola forma (nessuna rete), così `--check` resta un
    dry-run; la raggiungibilità è verificata all'avvio del loop live.
    """

    base_url: str = "http://127.0.0.1:8080"

    def __post_init__(self) -> None:
        if not isinstance(self.base_url, str) or not self.base_url.strip():
            raise ConfigError(
                "llamacpp.base_url deve essere una stringa non vuota "
                "(es. 'http://127.0.0.1:8080')"
            )
        base_url = self.base_url.strip().rstrip("/")
        parsed = urlsplit(base_url)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ConfigError(
                f"llamacpp.base_url {self.base_url!r} non valido: la porta "
                "deve essere numerica (es. 'http://127.0.0.1:8080')"
            ) from exc
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ConfigError(
                f"llamacpp.base_url {self.base_url!r} non valido: serve un URL "
                "http(s) con host e porta esplicita (es. 'http://127.0.0.1:8080')"
            )
        # Solo scheme://host:porta: il provider aggiunge da sé `/v1/chat/...` e
        # il probe aggiunge `/health`. Un path (tipicamente il `/v1` della
        # convenzione dei client OpenAI), o una query/fragment, produrrebbero
        # URL sbagliati (`/v1/v1/chat/...`, `/v1/health` → 404) diagnosticabili
        # solo a runtime: meglio rifiutarli qui.
        if parsed.path or parsed.query or parsed.fragment:
            raise ConfigError(
                f"llamacpp.base_url {self.base_url!r} non valido: indica solo "
                "scheme://host:porta senza path (es. 'http://127.0.0.1:8080'), "
                "il provider aggiunge da sé i path (niente '/v1')"
            )
        # Porta esplicita consigliata: llama-server non gira sulle porte
        # standard 80/443, quindi un URL senza porta è quasi sempre un refuso.
        # `port == 0` non è connettibile: trattato come porta mancante.
        if not port:
            raise ConfigError(
                f"llamacpp.base_url {self.base_url!r} senza porta esplicita: "
                "indica la porta del llama-server (es. 'http://127.0.0.1:8080')"
            )
        object.__setattr__(self, "base_url", base_url)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "LlamaCppConfig":
        """Costruisce e valida il blocco `llamacpp:`, rifiutando campi ignoti."""
        allowed = {"base_url"}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ConfigError(
                "campi llamacpp non riconosciuti: "
                + ", ".join(f"'{key}'" for key in unknown)
            )
        # `base_url` assente → default del dataclass (unica fonte di verità,
        # niente literal duplicato qui).
        return cls(**data)  # type: ignore[arg-type]


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
            "campi asr non riconosciuti: " + ", ".join(f"asr.{key}" for key in unknown)
        )
    try:
        return AsrConfig(
            model=data.get("model", "large-v3-turbo"),  # type: ignore[arg-type]
            device=data.get("device", "auto"),  # type: ignore[arg-type]
            compute_type=data.get("compute_type", "default"),  # type: ignore[arg-type]
            language=data.get("language"),  # type: ignore[arg-type]
            beam_size=data.get("beam_size", 5),  # type: ignore[arg-type]
            condition_on_previous_text=data.get("condition_on_previous_text", False),  # type: ignore[arg-type]
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
        kwargs = {key: data[key] for key in allowed if key in data}
        return SpeakerClusteringConfig(**kwargs)  # type: ignore[arg-type]
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
            dedup_change_threshold=data.get("dedup_change_threshold", 0.0),  # type: ignore[arg-type]
        )
    except VideoConfigError as exc:
        raise ConfigError(f"video.{exc}") from exc


def _vlm_config_from_dict(data: dict[str, object]) -> QwenVlConfig:
    allowed = {
        "backend",
        "model",
        "device",
        "device_map",
        "torch_dtype",
        "attn_implementation",
        "quantization",
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
            backend=data.get("backend", "qwen"),  # type: ignore[arg-type]
            model=data.get("model"),  # type: ignore[arg-type]
            device=data.get("device", "auto"),  # type: ignore[arg-type]
            device_map=data.get("device_map", "auto"),  # type: ignore[arg-type]
            torch_dtype=data.get("torch_dtype", "auto"),  # type: ignore[arg-type]
            attn_implementation=data.get("attn_implementation"),  # type: ignore[arg-type]
            quantization=data.get("quantization"),  # type: ignore[arg-type]
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
        "language",
        "profiles",
    }
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(
            "campi commentator non riconosciuti: "
            + ", ".join(f"commentator.{key}" for key in unknown)
        )

    profiles_raw = data.get("profiles")
    if profiles_raw is None:
        profiles_raw = {}
    if not isinstance(profiles_raw, dict):
        raise ConfigError("commentator.profiles deve essere una tabella")

    parsed_profiles: dict[CommentatorStyle, ProfileConfig] = {}
    for key, value in profiles_raw.items():
        style = _coerce_enum(key, CommentatorStyle, "commentator.profiles")
        if value is None:
            value = {}
        if not isinstance(value, dict):
            raise ConfigError(f"commentator.profiles.{key} deve essere una tabella")
        parsed_profiles[style] = _build_profile_from_dict(style, value)

    return CommentatorConfig(
        language=data.get("language", "it"),  # type: ignore[arg-type]
        profiles=parsed_profiles,
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
    # Directory di override dei prompt tunabili (ticket 03), gemella opzionale di
    # soul_path/facts_dir. Se assente → SOLO i default impacchettati nel wheel.
    # Se relativa, risolta rispetto alla dir del file di config (come le memory
    # path). Punta a un set `.md` (anche parziale, anche in un'altra lingua):
    # abilita lo swap-lingua senza toccare il codice. Collocata DOPO llm_params
    # per preservare il contratto posizionale del costruttore (test).
    prompts_dir: str | None = None
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
    # Disclosure è cablata; retention e auto_memory restano estensioni inerti.
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
    # Server llama.cpp locale (usato solo con `llm_provider: llamacpp`).
    llamacpp: LlamaCppConfig = field(default_factory=LlamaCppConfig)

    def __post_init__(self) -> None:
        if not isinstance(self.mode, OutputMode):
            raise ConfigError(f"mode non valido: {self.mode!r}")
        for name in ("soul_path", "facts_dir", "adapter", "llm_provider", "agent_name"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ConfigError(f"campo obbligatorio '{name}' mancante o vuoto")
        # prompts_dir è opzionale: se dato deve essere una stringa non vuota.
        if self.prompts_dir is not None and (
            not isinstance(self.prompts_dir, str) or not self.prompts_dir
        ):
            raise ConfigError("prompts_dir deve essere una stringa non vuota")
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
            raise ConfigError(
                "speaker_embedding deve essere una SpeakerEmbeddingConfig"
            )
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
        if not isinstance(self.llamacpp, LlamaCppConfig):
            raise ConfigError("llamacpp deve essere una LlamaCppConfig")
        self.commentator.validate_for_mode(self.mode)
        self._validate_public_twitch_persona()
        if self.twitch is not None:
            self.twitch.send.validate_for_mode(self.mode)
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

    def _validate_public_twitch_persona(self) -> None:
        """Su Twitch in modalità public la persona È l'original_chat.

        La chat pubblica usa il contratto RE:/MSG:/#end_conv che solo lo stile
        `original_chat` produce; un profilo `operator` (telecronista) parlerebbe
        all'operatore invece di scrivere in chat. Questo controllo trasforma una
        combinazione incoerente in un errore chiaro al `--check`, invece di
        lasciar generare messaggi telecronista sull'output pubblico. Va qui (a
        livello Config) perché serve la terna mode + adapter + commentator.
        """
        if self.adapter != "twitch" or self.mode is not OutputMode.PUBLIC:
            return
        offending = [
            style
            for style in self.commentator.active_styles()
            if style is not CommentatorStyle.ORIGINAL_CHAT
        ]
        if offending:
            names = ", ".join(style.value for style in offending)
            raise ConfigError(
                "su Twitch in modalità public la persona è sempre 'original_chat': "
                f"il profilo commentator '{names}' non è ammesso. Usa "
                "commentator.profiles.original_chat oppure rimuovi i profili "
                "(il default per twitch+public è original_chat)."
            )

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
        llamacpp_raw = data.get("llamacpp", {})
        if not isinstance(llamacpp_raw, dict):
            raise ConfigError("'llamacpp' deve essere una tabella")
        llamacpp = LlamaCppConfig.from_dict(llamacpp_raw)

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
                prompts_dir=data.get("prompts_dir"),  # type: ignore[arg-type]
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
                llamacpp=llamacpp,
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
        for field_name in ("soul_path", "facts_dir", "prompts_dir"):
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
