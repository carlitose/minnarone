"""Local VLM captioning backend for Twitch video perceptions.

The core video pipeline depends only on `video.Captioner`. This module is the
optional heavy edge: it loads a local Qwen2-VL-compatible Hugging Face runtime
only when the backend is constructed, converts `VideoFrame` pixels to an image
in memory, and returns one concise caption.
"""

from __future__ import annotations

import math
import re
from contextlib import nullcontext
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Protocol

from .video import VideoFrame

DEFAULT_QWEN_VL_PROMPT = (
    "Describe the visible Twitch stream scene in one concise English sentence. "
    "Mention only observable gameplay, UI, people, and readable text. "
    "Do not speculate."
)


class QwenVlConfigError(ValueError):
    """Invalid local VLM configuration."""


class QwenVlCaptionError(RuntimeError):
    """Local VLM setup or inference failed."""


#: Backend di captioning ammessi nel blocco `vlm:`. `qwen` = runtime torch
#: locale (`Qwen2VlCaptioner`); `llamacpp` = istanza multimodale `llama-server`
#: condivisa (`LlamaCppCaptioner`, in `vlm_llamacpp.py`).
VLM_BACKENDS = ("qwen", "llamacpp")


@dataclass(frozen=True, slots=True)
class QwenVlConfig:
    """Runtime settings for the local Qwen2-VL-compatible caption backend."""

    backend: str = "qwen"
    model: str | Path | None = None
    device: str = "auto"
    device_map: str | None = "auto"
    torch_dtype: str | None = "auto"
    attn_implementation: str | None = None
    quantization: str | None = None
    max_new_tokens: int = 48
    timeout_seconds: float = 30.0
    language: str = "en"
    prompt: str = DEFAULT_QWEN_VL_PROMPT
    max_caption_chars: int = 240
    max_image_edge: int = 768
    max_image_pixels: int = 500_000

    def __post_init__(self) -> None:
        backend = _non_empty_str(self.backend, "backend")
        if backend not in VLM_BACKENDS:
            raise QwenVlConfigError(
                "backend deve essere 'qwen' o 'llamacpp' (non "
                f"{self.backend!r})"
            )
        object.__setattr__(self, "backend", backend)
        object.__setattr__(
            self,
            "model",
            _coerce_model_id(self.model),
        )
        device = _non_empty_str(self.device, "device")
        object.__setattr__(self, "device", device)
        raw_device_map = _optional_non_empty_str(self.device_map, "device_map")
        if device != "auto" and raw_device_map == "auto":
            raw_device_map = None
        if device != "auto" and raw_device_map is not None:
            raise QwenVlConfigError(
                "device_map deve essere null quando device è esplicito"
            )
        object.__setattr__(
            self,
            "device_map",
            raw_device_map,
        )
        object.__setattr__(
            self,
            "torch_dtype",
            _optional_non_empty_str(self.torch_dtype, "torch_dtype"),
        )
        object.__setattr__(
            self,
            "attn_implementation",
            _optional_non_empty_str(
                self.attn_implementation,
                "attn_implementation",
            ),
        )
        quantization = _optional_non_empty_str(self.quantization, "quantization")
        if quantization is not None and quantization not in {"4bit", "8bit"}:
            raise QwenVlConfigError(
                "quantization deve essere '4bit', '8bit' o null"
            )
        object.__setattr__(self, "quantization", quantization)
        language = _non_empty_str(self.language, "language")
        object.__setattr__(self, "language", language)
        prompt = _non_empty_str(self.prompt, "prompt")
        if prompt == DEFAULT_QWEN_VL_PROMPT and language.lower() not in {
            "en",
            "english",
        }:
            prompt = _default_prompt(language)
        object.__setattr__(self, "prompt", prompt)
        object.__setattr__(
            self,
            "max_new_tokens",
            _positive_int(self.max_new_tokens, "max_new_tokens"),
        )
        object.__setattr__(
            self,
            "max_caption_chars",
            _positive_int(self.max_caption_chars, "max_caption_chars"),
        )
        object.__setattr__(
            self,
            "max_image_edge",
            _positive_int(self.max_image_edge, "max_image_edge"),
        )
        object.__setattr__(
            self,
            "max_image_pixels",
            _positive_int(self.max_image_pixels, "max_image_pixels"),
        )
        timeout = _positive_float(self.timeout_seconds, "timeout_seconds")
        object.__setattr__(self, "timeout_seconds", timeout)


class _ModelFactory(Protocol):
    def __call__(self, model: str, **kwargs: object) -> object: ...


class _ProcessorFactory(Protocol):
    def __call__(self, model: str) -> object: ...


class Qwen2VlCaptioner:
    """Caption `VideoFrame` objects with a local Qwen2-VL-compatible model."""

    def __init__(
        self,
        config: QwenVlConfig,
        *,
        model_factory: _ModelFactory | None = None,
        processor_factory: _ProcessorFactory | None = None,
        torch_module: object | None = None,
        image_module: object | None = None,
    ) -> None:
        if config.model is None:
            raise QwenVlCaptionError(
                "vlm.model is required for the local Qwen2-VL caption backend"
            )
        self._config = config
        self._torch = torch_module if torch_module is not None else _import_torch()
        self._image_module = (
            image_module if image_module is not None else _import_pillow_image()
        )
        self._inference_lock = Lock()
        model_id = str(config.model)
        kwargs = self._model_kwargs()
        try:
            if model_factory is None:
                model_factory = _default_model_factory()
            if processor_factory is None:
                processor_factory = _default_processor_factory()
            with _TransformersProgressDisabled():
                self._model = model_factory(model_id, **kwargs)
                self._processor = processor_factory(model_id)
            self._place_model()
            eval_method = getattr(self._model, "eval", None)
            if eval_method is not None:
                eval_method()
        except Exception as exc:  # noqa: BLE001 - wrap backend-specific errors.
            raise QwenVlCaptionError(
                f"failed to initialize local Qwen2-VL caption backend: {exc}"
            ) from exc

    def caption(self, frame: VideoFrame) -> str:
        """Return one short caption for `frame`, or raise on backend failure."""
        return self._run_with_timeout(lambda: self._caption_frame(frame))

    def _caption_frame(self, frame: VideoFrame) -> str:
        image = frame_to_pil_image(frame, image_module=self._image_module)
        image = downscale_image_for_vlm(
            image,
            max_edge=self._config.max_image_edge,
            max_pixels=self._config.max_image_pixels,
            image_module=self._image_module,
        )
        return self._caption_image(image)

    def _model_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {}
        if self._config.device_map is not None:
            kwargs["device_map"] = self._config.device_map
        if self._config.torch_dtype is not None:
            kwargs["torch_dtype"] = self._resolve_torch_dtype(self._config.torch_dtype)
        if self._config.attn_implementation is not None:
            kwargs["attn_implementation"] = self._config.attn_implementation
        if self._config.quantization is not None:
            kwargs["quantization_config"] = self._build_quantization_config()
        return kwargs

    def _build_quantization_config(self) -> object:
        # bitsandbytes via transformers: NF4 4-bit (o 8-bit) per far stare il
        # modello in poca VRAM. Import lazy: dipendenza GPU opzionale.
        from transformers import BitsAndBytesConfig  # noqa: PLC0415 - lazy opzionale

        if self._config.quantization == "4bit":
            return BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=self._torch.float16,
            )
        return BitsAndBytesConfig(load_in_8bit=True)

    def _resolve_torch_dtype(self, value: str) -> object:
        if value == "auto":
            return "auto"
        return getattr(self._torch, value, value)

    def _place_model(self) -> None:
        if self._config.device == "auto" or self._config.device_map is not None:
            return
        to_method = getattr(self._model, "to", None)
        if to_method is not None:
            self._model = to_method(self._config.device)

    def _caption_image(self, image: object) -> str:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": self._config.prompt},
                ],
            }
        ]
        text = self._processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self._processor(
            text=[text],
            images=[image],
            padding=True,
            return_tensors="pt",
        )
        inputs = self._move_inputs(inputs)
        with _no_grad(self._torch):
            generated_ids = self._model.generate(
                **inputs,
                max_new_tokens=self._config.max_new_tokens,
                do_sample=False,
            )
        trimmed = _trim_generated_ids(generated_ids, _input_ids(inputs))
        decoded = self._processor.batch_decode(
            trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )
        return _normalize_caption(decoded[0] if decoded else "", self._config)

    def _move_inputs(self, inputs: object) -> object:
        target_device: object | None = None
        if self._config.device != "auto":
            target_device = self._config.device
        else:
            target_device = getattr(self._model, "device", None)
        if target_device is None:
            return inputs
        to_method = getattr(inputs, "to", None)
        if to_method is None:
            return inputs
        return to_method(target_device)

    def _run_with_timeout(self, work) -> str:
        if not self._inference_lock.acquire(blocking=False):
            raise QwenVlCaptionError(
                "local Qwen2-VL caption backend is still busy after a previous "
                "timeout"
            )
        results: Queue[tuple[bool, str | BaseException]] = Queue(maxsize=1)

        def target() -> None:
            try:
                results.put((True, work()))
            except BaseException as exc:  # noqa: BLE001 - forwarded to caller.
                results.put((False, exc))
            finally:
                self._inference_lock.release()

        thread = Thread(target=target, name="qwen2-vl-caption", daemon=True)
        try:
            thread.start()
        except BaseException:
            self._inference_lock.release()
            raise
        thread.join(self._config.timeout_seconds)
        if thread.is_alive():
            raise QwenVlCaptionError(
                "local Qwen2-VL caption timed out after "
                f"{self._config.timeout_seconds:g}s"
            )
        try:
            ok, value = results.get_nowait()
        except Empty as exc:
            raise QwenVlCaptionError("local Qwen2-VL caption produced no result") from exc
        if ok:
            return str(value)
        if isinstance(value, QwenVlCaptionError):
            raise value
        raise QwenVlCaptionError(f"local Qwen2-VL caption failed: {value}") from value


def frame_to_pil_image(frame: VideoFrame, *, image_module: object | None = None) -> object:
    """Convert a `VideoFrame` payload to a PIL image without writing files."""
    image_api = image_module if image_module is not None else _import_pillow_image()
    pixels = frame.pixels
    if _is_pil_like_image(pixels, image_api):
        return pixels.convert("RGB")  # type: ignore[union-attr]
    if isinstance(pixels, (bytes, bytearray, memoryview)):
        return image_api.open(BytesIO(bytes(pixels))).convert("RGB")  # type: ignore[attr-defined]
    return image_api.fromarray(pixels).convert("RGB")  # type: ignore[attr-defined]

def downscale_image_for_vlm(
    image: object,
    *,
    max_edge: int,
    max_pixels: int,
    image_module: object | None = None,
) -> object:
    """Return `image` or a resized copy that fits the VLM input budget."""
    width, height = _image_size(image)
    scale = min(
        1.0,
        max_edge / max(width, height),
        math.sqrt(max_pixels / (width * height)),
    )
    if scale >= 1.0:
        return image
    target_size = _bounded_size(
        width=width,
        height=height,
        scale=scale,
        max_edge=max_edge,
        max_pixels=max_pixels,
    )
    return image.resize(  # type: ignore[union-attr]
        target_size,
        resample=_resize_filter(image_module),
    )

def _bounded_size(
    *,
    width: int,
    height: int,
    scale: float,
    max_edge: int,
    max_pixels: int,
) -> tuple[int, int]:
    target_width = max(1, int(width * scale))
    target_height = max(1, int(height * scale))
    while (
        max(target_width, target_height) > max_edge
        or target_width * target_height > max_pixels
    ):
        if target_width >= target_height and target_width > 1:
            target_width -= 1
        elif target_height > 1:
            target_height -= 1
        else:
            break
    return target_width, target_height

def _image_size(image: object) -> tuple[int, int]:
    size = getattr(image, "size", None)
    if (
        isinstance(size, tuple)
        and len(size) == 2
        and all(isinstance(value, int) for value in size)
        and size[0] > 0
        and size[1] > 0
    ):
        return size
    width = getattr(image, "width", None)
    height = getattr(image, "height", None)
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        return width, height
    raise QwenVlCaptionError("VLM image has no valid pixel size")

def _resize_filter(image_module: object | None) -> object:
    image_api = image_module if image_module is not None else _import_pillow_image()
    resampling = getattr(image_api, "Resampling", None)
    if resampling is not None:
        return resampling.LANCZOS  # type: ignore[union-attr]
    return image_api.LANCZOS  # type: ignore[union-attr]


def _is_pil_like_image(pixels: object, image_module: object) -> bool:
    image_class = getattr(image_module, "Image", None)
    if image_class is not None and isinstance(pixels, image_class):
        return True
    return hasattr(pixels, "convert")


def _default_model_factory() -> _ModelFactory:
    transformers = _import_transformers()
    model_class = getattr(transformers, "Qwen2VLForConditionalGeneration", None)
    if model_class is None:
        model_class = getattr(transformers, "AutoModelForVision2Seq", None)
    if model_class is None:
        raise QwenVlCaptionError(
            "transformers does not expose a Qwen2-VL-compatible model class"
        )

    def factory(model: str, **kwargs: object) -> object:
        return model_class.from_pretrained(model, **kwargs)

    return factory


def _default_processor_factory() -> _ProcessorFactory:
    transformers = _import_transformers()
    processor_class = getattr(transformers, "AutoProcessor", None)
    if processor_class is None:
        raise QwenVlCaptionError("transformers does not expose AutoProcessor")

    def factory(model: str) -> object:
        return processor_class.from_pretrained(model)

    return factory


def _import_transformers() -> object:
    try:
        import transformers
    except ModuleNotFoundError as exc:  # pragma: no cover - environment-specific.
        raise QwenVlCaptionError(
            "local Qwen2-VL captioning requires transformers; install the vlm extra"
        ) from exc
    return transformers


class _TransformersProgressDisabled:
    def __init__(self) -> None:
        self._logging: object | None = None
        self._was_enabled = False

    def __enter__(self):
        transformers = _import_transformers()
        utils = getattr(transformers, "utils", None)
        logging = getattr(utils, "logging", None)
        if logging is None:
            try:
                from transformers.utils import logging as imported_logging
            except (ImportError, AttributeError):
                return self
            logging = imported_logging
        is_enabled = getattr(logging, "is_progress_bar_enabled", None)
        disable = getattr(logging, "disable_progress_bar", None)
        if callable(is_enabled):
            self._was_enabled = bool(is_enabled())
        if callable(disable):
            disable()
            self._logging = logging
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> bool:
        if self._was_enabled and self._logging is not None:
            enable = getattr(self._logging, "enable_progress_bar", None)
            if callable(enable):
                enable()
        return False


def _import_torch() -> object:
    try:
        import torch
    except ModuleNotFoundError as exc:  # pragma: no cover - environment-specific.
        raise QwenVlCaptionError(
            "local Qwen2-VL captioning requires torch; install the vlm extra"
        ) from exc
    return torch


def _import_pillow_image() -> object:
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:  # pragma: no cover - environment-specific.
        raise QwenVlCaptionError(
            "local Qwen2-VL captioning requires Pillow; install the vlm extra"
        ) from exc
    return Image


def _no_grad(torch_module: object):
    no_grad = getattr(torch_module, "no_grad", None)
    if no_grad is None:
        return nullcontext()
    return no_grad()


def _input_ids(inputs: object) -> object:
    if hasattr(inputs, "input_ids"):
        return inputs.input_ids  # type: ignore[union-attr]
    if isinstance(inputs, dict):
        return inputs["input_ids"]
    return inputs["input_ids"]  # type: ignore[index]


def _trim_generated_ids(generated_ids: object, input_ids: object) -> list[object]:
    trimmed: list[object] = []
    for prompt_ids, output_ids in zip(input_ids, generated_ids, strict=False):  # type: ignore[arg-type]
        piece = output_ids[len(prompt_ids) :]  # type: ignore[index]
        tolist = getattr(piece, "tolist", None)
        trimmed.append(tolist() if tolist is not None else piece)
    return trimmed


def _normalize_caption(text: str, config: QwenVlConfig) -> str:
    caption = re.sub(r"\s+", " ", text).strip()
    if len(caption) <= config.max_caption_chars:
        return caption
    return caption[: config.max_caption_chars].rstrip()


def _default_prompt(language: str) -> str:
    language_name = _language_name(language)
    return (
        "Describe the visible Twitch stream scene in one "
        f"concise {language_name} sentence. Mention only observable gameplay, UI, "
        "people, and readable text. Do not speculate."
    )


def _language_name(language: str) -> str:
    names = {
        "en": "English",
        "eng": "English",
        "english": "English",
        "it": "Italian",
        "ita": "Italian",
        "italian": "Italian",
        "es": "Spanish",
        "spa": "Spanish",
        "spanish": "Spanish",
        "fr": "French",
        "fra": "French",
        "french": "French",
    }
    return names.get(language.lower(), language)


def _coerce_model_id(value: str | Path | None) -> str | None:
    """Normalizza `vlm.model`: repo id HF (es. 'Qwen/Qwen2-VL-2B-Instruct') o
    path locale. NON va trattato come path del filesystem: su Windows
    `str(Path("a/b"))` diventa `a\\b`, corrompendo i repo id HF. Si preserva la
    stringa (i Path in ingresso usano le '/' POSIX, accettate da from_pretrained).
    """
    if value is None:
        return None
    if isinstance(value, Path):
        text = value.as_posix()
    elif isinstance(value, str):
        text = value.strip()
    else:
        raise QwenVlConfigError("model deve essere una stringa o path")
    if not text:
        raise QwenVlConfigError("model deve essere non vuoto")
    return text


def _optional_non_empty_str(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _non_empty_str(value, field_name)


def _non_empty_str(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise QwenVlConfigError(f"{field_name} deve essere una stringa non vuota")
    stripped = value.strip()
    if not stripped:
        raise QwenVlConfigError(f"{field_name} deve essere una stringa non vuota")
    return stripped


def _positive_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise QwenVlConfigError(f"{field_name} deve essere un intero >= 1")
    if isinstance(value, float) and not value.is_integer():
        raise QwenVlConfigError(f"{field_name} deve essere un intero >= 1")
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise QwenVlConfigError(f"{field_name} deve essere un intero >= 1") from exc
    if parsed < 1:
        raise QwenVlConfigError(f"{field_name} deve essere un intero >= 1")
    return parsed


def _positive_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise QwenVlConfigError(f"{field_name} deve essere > 0")
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise QwenVlConfigError(f"{field_name} deve essere > 0") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise QwenVlConfigError(f"{field_name} deve essere > 0")
    return parsed
