"""Prompt observation at the LLM provider boundary."""

from __future__ import annotations

import json
import re
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from .config import TWITCH_SEND_TOKEN_ENV_VAR
from .llm import LLMProvider, LLMResult

PROMPT_CAPTURE_LIMIT = 50
PROMPT_RECORD_MAX_BYTES = 200 * 1024
PROMPT_TRUNCATION_MARKER = "\n[TRUNCATED: prompt debug record exceeded 200 KB]\n"

_TOKEN_METADATA_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")
_CACHE_METADATA_KEYS = ("cached_tokens", "cache_write_tokens", "cache_read_tokens")
_COST_KEYS = ("cost", "total_cost")
_REDACTED_SECRET_METADATA_VALUE = "[redacted]"
_TOKEN_USAGE_METADATA_KEYS = frozenset((*_TOKEN_METADATA_KEYS, *_CACHE_METADATA_KEYS))
_SECRET_METADATA_KEY_PARTS = {
    "auth",
    "authentication",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "credentials",
    "csrf",
    "header",
    "headers",
    "oauth",
    "password",
    "passwd",
    "pwd",
    "secret",
    "signature",
    "token",
}
_SECRET_METADATA_KEY_COMPACT_FRAGMENTS = (
    "apikey",
    "apisecret",
    "clientsecret",
    "csrftoken",
    "privatekey",
    "secretkey",
    "setcookie",
)

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"oauth:[A-Za-z0-9._~+\-/=]+", re.IGNORECASE),
        "[redacted-oauth-token]",
    ),
    (
        re.compile(r"\bauthorization\s*:\s*\S+\s+[^\r\n]+", re.IGNORECASE),
        "Authorization: [redacted-authorization]",
    ),
    (
        re.compile(r"\bbearer\s+[A-Za-z0-9._~+\-/=]+", re.IGNORECASE),
        "Bearer [redacted-token]",
    ),
    (
        re.compile(r"\bsk-or-[A-Za-z0-9._~+\-/=]+", re.IGNORECASE),
        "[redacted-openrouter-key]",
    ),
    (
        # Il token di SCRITTURA va nominato esplicitamente: non è coperto né da
        # `TWITCH_OAUTH_TOKEN` (non è una sua sottostringa) né da `\btoken`
        # (il `_` prima di TOKEN annulla il boundary).
        re.compile(
            rf"\b(OPENROUTER_API_KEY|{TWITCH_SEND_TOKEN_ENV_VAR}|"
            r"TWITCH_OAUTH_TOKEN|authorization|"
            r"api[_-]?key|token|password|secret)"
            r"\s*[:=]\s*"
            r"(?:\"[^\"]*\"|'[^']*'|[^,\r\n;]+)",
            re.IGNORECASE,
        ),
        r"\1=[redacted-secret]",
    ),
)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BYTES_REPR = re.compile(r"b(['\"])(?:\\.|(?!\1).){8,}\1")
_BINARY_FIELD = re.compile(
    r"\b(raw[_-]?(?:audio|frame)|frame|pixels|samples)"
    r"\s*[:=]\s*"
    r"(?:b(['\"])(?:\\.|(?!\2).){8,}\2|[A-Za-z0-9+/=]{128,})",
    re.IGNORECASE,
)
_PROMPT_CONTEXT: ContextVar[str | None] = ContextVar(
    "minnarone_prompt_observation_context",
    default=None,
)


@dataclass(frozen=True, slots=True)
class PromptObservation:
    """Redacted prompt and metadata for one LLM call."""

    prompt: str
    model: str
    status: str
    started_at: datetime
    completed_at: datetime
    context: str | None = None
    response_metadata: dict[str, object] = field(default_factory=dict)
    token_metadata: dict[str, object] = field(default_factory=dict)
    cache_metadata: dict[str, object] = field(default_factory=dict)
    cost: object | None = None
    error: str | None = None


class PromptObservationRecorder:
    """Retains the latest prompt observations in memory."""

    def __init__(
        self,
        *,
        debug_dir: str | Path | None = None,
        retention_limit: int = PROMPT_CAPTURE_LIMIT,
    ) -> None:
        if (
            isinstance(retention_limit, bool)
            or not isinstance(retention_limit, int)
            or retention_limit < 1
        ):
            raise ValueError("retention_limit must be an integer >= 1")
        self._retention_limit = retention_limit
        self._observations: deque[PromptObservation] = deque(maxlen=retention_limit)
        self._prompt_dir = (
            Path(debug_dir) / "prompts" if debug_dir is not None else None
        )
        self._sequence = 0

    def record(self, observation: PromptObservation) -> None:
        observation = sanitize_observation(observation)
        self._observations.append(observation)
        if self._prompt_dir is not None:
            self._write_record(observation)

    def latest(self) -> PromptObservation | None:
        if not self._observations:
            return None
        return self._observations[-1]

    def observations(self) -> list[PromptObservation]:
        return list(self._observations)

    def _write_record(self, observation: PromptObservation) -> None:
        assert self._prompt_dir is not None
        self._prompt_dir.mkdir(parents=True, exist_ok=True)
        self._sequence += 1
        path = self._prompt_dir / (
            f"prompt-{self._sequence:06d}-"
            f"{_timestamp_for_filename(observation.started_at)}.json"
        )
        path.write_bytes(_serialize_observation(observation))
        self._prune_prompt_files()

    def _prune_prompt_files(self) -> None:
        assert self._prompt_dir is not None
        files = sorted(self._prompt_dir.glob("prompt-*.json"))
        for path in files[: max(len(files) - self._retention_limit, 0)]:
            path.unlink()


class ObservedLLMProvider(LLMProvider):
    """LLM provider wrapper that records prompt observations without network I/O."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        recorder: PromptObservationRecorder,
        model: str | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider
        self._recorder = recorder
        self.model = model or str(
            getattr(provider, "model", provider.__class__.__name__)
        )
        self._clock = clock or _utcnow

    async def complete(self, prompt: str) -> LLMResult:
        started_at = self._clock()
        context = current_prompt_observation_context()
        try:
            result = await self._provider.complete(prompt)
        except Exception as exc:
            completed_at = self._clock()
            self._recorder.record(
                PromptObservation(
                    prompt=redact_unsafe_text(prompt),
                    model=self.model,
                    status="error",
                    started_at=started_at,
                    completed_at=completed_at,
                    context=context,
                    error=sanitize_error_text(exc),
                )
            )
            raise

        completed_at = self._clock()
        meta = sanitize_metadata(result.meta)
        self._recorder.record(
            PromptObservation(
                prompt=redact_unsafe_text(prompt),
                model=str(meta.get("model", self.model)),
                status="success",
                started_at=started_at,
                completed_at=completed_at,
                context=context,
                response_metadata=meta,
                token_metadata=_metadata_subset(meta, _TOKEN_METADATA_KEYS),
                cache_metadata=_metadata_subset(meta, _CACHE_METADATA_KEYS),
                cost=_first_metadata_value(meta, _COST_KEYS),
            )
        )
        return result


def _utcnow() -> datetime:
    return datetime.now(UTC)


@contextmanager
def prompt_observation_context(label: str):
    token = _PROMPT_CONTEXT.set(label)
    try:
        yield
    finally:
        _PROMPT_CONTEXT.reset(token)


def current_prompt_observation_context() -> str | None:
    return _PROMPT_CONTEXT.get()


def _serialize_observation(observation: PromptObservation) -> bytes:
    payload = {
        "prompt": observation.prompt,
        "model": observation.model,
        "status": observation.status,
        "started_at": _datetime_to_json(observation.started_at),
        "completed_at": _datetime_to_json(observation.completed_at),
        "context": observation.context,
        "response_metadata": observation.response_metadata,
        "token_metadata": observation.token_metadata,
        "cache_metadata": observation.cache_metadata,
        "cost": observation.cost,
        "error": observation.error,
        "truncated": False,
    }
    data = _json_bytes(payload)
    if len(data) <= PROMPT_RECORD_MAX_BYTES:
        return data
    return _truncate_prompt_payload(payload)


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode(
        "utf-8"
    )


def _truncate_prompt_payload(payload: dict[str, object]) -> bytes:
    prompt_bytes = str(payload.get("prompt", "")).encode("utf-8")
    low = 0
    high = len(prompt_bytes)
    best: bytes | None = None

    while low <= high:
        mid = (low + high) // 2
        candidate = dict(payload)
        candidate["prompt"] = (
            prompt_bytes[:mid].decode("utf-8", errors="ignore")
            + PROMPT_TRUNCATION_MARKER
        )
        candidate["truncated"] = True
        data = _json_bytes(candidate)
        if len(data) <= PROMPT_RECORD_MAX_BYTES:
            best = data
            low = mid + 1
        else:
            high = mid - 1

    if best is not None:
        return best

    minimal = dict(payload)
    minimal["prompt"] = PROMPT_TRUNCATION_MARKER
    minimal["model"] = _truncate_text_field(minimal.get("model"), max_chars=256)
    minimal["context"] = _truncate_text_field(minimal.get("context"), max_chars=256)
    minimal["error"] = _truncate_text_field(minimal.get("error"), max_chars=2048)
    minimal["cost"] = _truncate_text_field(minimal.get("cost"), max_chars=256)
    minimal["response_metadata"] = {}
    minimal["token_metadata"] = {}
    minimal["cache_metadata"] = {}
    minimal["truncated"] = True
    data = _json_bytes(minimal)
    if len(data) <= PROMPT_RECORD_MAX_BYTES:
        return data
    last_resort = {
        "prompt": PROMPT_TRUNCATION_MARKER,
        "model": "[truncated]",
        "status": payload.get("status", "unknown"),
        "started_at": payload.get("started_at"),
        "completed_at": payload.get("completed_at"),
        "context": None,
        "response_metadata": {},
        "token_metadata": {},
        "cache_metadata": {},
        "cost": None,
        "error": "[truncated]",
        "truncated": True,
    }
    return _json_bytes(last_resort)


def _truncate_text_field(value: object, *, max_chars: int) -> object:
    if value is None:
        return None
    text = str(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[TRUNCATED]\n"


def _datetime_to_json(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _timestamp_for_filename(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def redact_unsafe_text(value: object) -> str:
    """Redact secrets and unsafe payloads while preserving prompt newlines."""
    text = str(value).replace("\x1b", "")
    text = _CONTROL_CHARS.sub("", text)
    text = _BINARY_FIELD.sub(r"\1=[redacted-binary-payload]", text)
    text = _BYTES_REPR.sub("b'[redacted-binary-payload]'", text)
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_error_text(value: object) -> str:
    text = redact_unsafe_text(value)
    return " ".join(text.split())


def sanitize_observation(observation: PromptObservation) -> PromptObservation:
    return replace(
        observation,
        prompt=redact_unsafe_text(observation.prompt),
        model=redact_unsafe_text(observation.model),
        context=(
            redact_unsafe_text(observation.context)
            if observation.context is not None
            else None
        ),
        response_metadata=sanitize_metadata(observation.response_metadata),
        token_metadata=sanitize_metadata(observation.token_metadata),
        cache_metadata=sanitize_metadata(observation.cache_metadata),
        cost=_sanitize_metadata_value(observation.cost),
        error=(
            sanitize_error_text(observation.error)
            if observation.error is not None
            else None
        ),
    )


def sanitize_metadata(meta: Mapping[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in meta.items():
        safe_key = redact_unsafe_text(key)
        if safe_key in sanitized:
            safe_key = f"{safe_key}#{len(sanitized)}"
        if _is_secret_metadata_key(key):
            sanitized[safe_key] = _REDACTED_SECRET_METADATA_VALUE
        else:
            sanitized[safe_key] = _sanitize_metadata_value(value)
    return sanitized


def _is_secret_metadata_key(key: object) -> bool:
    raw = str(key)
    camel_split = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", raw)
    camel_split = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", camel_split)
    normalized = re.sub(r"[^a-z0-9]+", "_", camel_split.lower()).strip("_")
    compact = re.sub(r"[^a-z0-9]+", "", raw.lower())
    parts = [part for part in normalized.split("_") if part]

    if normalized in _TOKEN_USAGE_METADATA_KEYS:
        return False
    if any(part in _SECRET_METADATA_KEY_PARTS for part in parts):
        return True
    if any(fragment in compact for fragment in _SECRET_METADATA_KEY_COMPACT_FRAGMENTS):
        return True
    if compact.endswith(
        (
            "cookie",
            "credential",
            "credentials",
            "csrf",
            "header",
            "headers",
            "secret",
            "signature",
            "token",
        )
    ):
        return not compact.endswith("tokens")
    return False


def _sanitize_metadata_value(value: object) -> object:
    if isinstance(value, str):
        return redact_unsafe_text(value)
    if isinstance(value, bytes | bytearray | memoryview):
        return "[redacted-binary-payload]"
    if isinstance(value, Mapping):
        return sanitize_metadata(value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_sanitize_metadata_value(item) for item in value]
    return value


def _metadata_subset(
    meta: dict[str, object],
    keys: tuple[str, ...],
) -> dict[str, object]:
    return {key: meta[key] for key in keys if key in meta}


def _first_metadata_value(
    meta: dict[str, object],
    keys: tuple[str, ...],
) -> object | None:
    for key in keys:
        if key in meta and meta[key] is not None:
            return meta[key]
    return None
