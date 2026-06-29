"""Local ASR backends.

The core audio pipeline depends on the narrow `Asr` protocol in `audio.py`.
This module keeps model-specific code behind that protocol and imports
`faster_whisper` only when the backend is instantiated.
"""

from __future__ import annotations

import struct
from array import array
from collections.abc import Callable
from dataclasses import dataclass

from .audio import SpeechSegment

_DEFAULT_MODEL = "large-v3-turbo"
_DEFAULT_DEVICE = "auto"
_DEFAULT_COMPUTE_TYPE = "default"
_DEFAULT_BEAM_SIZE = 5


class AsrConfigError(ValueError):
    """Invalid local ASR configuration."""


class AsrInputError(ValueError):
    """Invalid ASR input audio."""


class AsrModelSetupError(RuntimeError):
    """The model backend could not be imported or initialized."""


@dataclass(frozen=True, slots=True)
class AsrConfig:
    """Configuration for one faster-whisper utterance transcription backend."""

    model: str = _DEFAULT_MODEL
    device: str = _DEFAULT_DEVICE
    compute_type: str = _DEFAULT_COMPUTE_TYPE
    language: str | None = None
    beam_size: int = _DEFAULT_BEAM_SIZE
    condition_on_previous_text: bool = False

    def __post_init__(self) -> None:
        model = _non_empty_string(self.model, "model")
        device = _non_empty_string(self.device, "device")
        compute_type = _non_empty_string(self.compute_type, "compute_type")
        language = self.language
        if language is not None:
            language = _non_empty_string(language, "language")
        if (
            isinstance(self.beam_size, bool)
            or not isinstance(self.beam_size, int)
            or self.beam_size < 1
        ):
            raise AsrConfigError("beam_size deve essere un intero >= 1")
        if not isinstance(self.condition_on_previous_text, bool):
            raise AsrConfigError("condition_on_previous_text deve essere booleano")
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "device", device)
        object.__setattr__(self, "compute_type", compute_type)
        object.__setattr__(self, "language", language)


class FasterWhisperAsr:
    """`Asr` implementation backed by `faster_whisper.WhisperModel`."""

    def __init__(
        self,
        config: AsrConfig | None = None,
        *,
        model_factory: Callable[..., object] | None = None,
    ) -> None:
        self._config = config or AsrConfig()
        factory = model_factory or _default_model_factory
        try:
            self._model = factory(
                self._config.model,
                device=self._config.device,
                compute_type=self._config.compute_type,
            )
        except AsrModelSetupError:
            raise
        except Exception as exc:  # noqa: BLE001 - wrap model-specific failures.
            raise AsrModelSetupError(
                "faster-whisper model setup failed "
                f"(model={self._config.model!r}, "
                f"device={self._config.device!r}, "
                f"compute_type={self._config.compute_type!r}): {exc}"
            ) from exc

    @property
    def config(self) -> AsrConfig:
        """Effective backend configuration."""
        return self._config

    def transcribe(self, segment: SpeechSegment) -> str:
        """Transcribe one VAD utterance and return normalized segment text."""
        if segment.sample_rate != 16_000:
            raise AsrInputError("SpeechSegment.sample_rate deve essere 16000 Hz")
        audio = pcm_s16le_to_float32(segment.samples)
        segments, _info = self._model.transcribe(
            audio,
            beam_size=self._config.beam_size,
            language=self._config.language,
            condition_on_previous_text=self._config.condition_on_previous_text,
        )
        return " ".join(
            text
            for text in (
                str(getattr(segment, "text", "")).strip() for segment in segments
            )
            if text
        ).strip()


def pcm_s16le_to_float32(samples: object) -> object:
    """Convert mono signed 16-bit little-endian PCM bytes to float32 samples."""
    if not isinstance(samples, (bytes, bytearray, memoryview)):
        raise AsrInputError("SpeechSegment.samples deve essere PCM bytes-like")
    raw = bytes(samples)
    if len(raw) % 2:
        raise AsrInputError("SpeechSegment.samples deve essere 16-bit aligned")
    floats = array(
        "f",
        (value / 32768.0 for (value,) in struct.iter_unpack("<h", raw)),
    )
    try:
        np = __import__("numpy")
    except ImportError:
        return floats
    return np.asarray(floats, dtype=np.float32)


def _default_model_factory(model: str, *, device: str, compute_type: str) -> object:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise AsrModelSetupError(
            "faster-whisper non installato: installa l'extra ASR locale "
            "o il pacchetto 'faster-whisper' prima di abilitare twitch.audio"
        ) from exc
    return WhisperModel(model, device=device, compute_type=compute_type)


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AsrConfigError(f"{field_name} deve essere una stringa non vuota")
    return value.strip()
