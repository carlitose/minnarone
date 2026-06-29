"""Offline replay loading for saved Minnarone run artifacts."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .dashboard import DashboardState, LocalFailure, VideoDiagnostics
from .perception import Perception, Source, format_perception_line
from .prompt_observation import (
    PromptObservation,
    redact_unsafe_text,
    sanitize_observation,
)
from .run_events import RUN_EVENTS_FILENAME
from .senser import Trigger

_DEFAULT_REPLAY_LIMIT = 200


def run_replay_tui(
    source: str | Path,
    *,
    build_app: Callable[[Callable[[], DashboardState]], object] | None = None,
) -> None:
    """Run the dashboard TUI against a static offline replay state."""
    state = load_replay_state(source)
    if build_app is None:
        from .dashboard_tui import build_dashboard_app as build_app

    app = build_app(lambda: state)
    app.run()


def load_replay_state(
    source: str | Path,
    *,
    recent_perceptions: int = _DEFAULT_REPLAY_LIMIT,
) -> DashboardState:
    """Load saved artifacts into the same pure state consumed by the live TUI."""
    replay_source = Path(source)
    perception_log = _perception_log_path(replay_source)
    loaded = _read_perceptions(perception_log)
    prompt = _latest_prompt_observation(_prompt_dir_for_source(replay_source))
    events = _read_run_events(_event_log_path_for_source(replay_source))
    failures = [*loaded.failures, *prompt.failures, *events.failures]

    all_perceptions = loaded.perceptions
    perceptions = _tail(all_perceptions, recent_perceptions)
    chat_messages = _tail(
        [p for p in all_perceptions if p.source is Source.CHAT and p.type == "msg"],
        recent_perceptions,
    )
    audio_transcriptions = _tail(
        [
            p
            for p in all_perceptions
            if p.source is Source.AUDIO and p.type == "speech"
        ],
        recent_perceptions,
    )
    video_captions = _tail(
        [
            p
            for p in all_perceptions
            if p.source is Source.VIDEO and p.type == "caption"
        ],
        recent_perceptions,
    )
    event_perceptions = _tail(
        [p for p in all_perceptions if p.source is Source.EVENT],
        recent_perceptions,
    )
    triggers = _tail(
        [
            *events.triggers,
            *[
                Trigger(
                    reason=event.type,
                    perception=event,
                    kind=event.type,
                    interlocutor=event.speaker,
                )
                for event in event_perceptions
            ],
        ],
        recent_perceptions,
    )
    messages = _tail(
        [
            *events.minnarone_messages,
            *[p.text for p in event_perceptions if p.type == "reaction"],
        ],
        recent_perceptions,
    )

    return DashboardState(
        perceptions=perceptions,
        chat_messages=chat_messages,
        audio_transcriptions=audio_transcriptions,
        video_captions=video_captions,
        triggers=triggers,
        messages=messages,
        failures=failures,
        video=VideoDiagnostics(
            frames_seen=len(video_captions),
            sampled=len(video_captions),
            captioned=len(video_captions),
        ),
        latest_prompt=prompt.observation,
        memory_summary=_memory_summary(perceptions),
        replay_source=str(replay_source),
    )


def _perception_log_path(source: Path) -> Path:
    if source.is_dir():
        return source / "perceptions.jsonl"
    return source


def _prompt_dir_for_source(source: Path) -> Path:
    run_dir = source if source.is_dir() else source.parent
    return run_dir / "debug" / "prompts"


def _event_log_path_for_source(source: Path) -> Path:
    run_dir = source if source.is_dir() else source.parent
    return run_dir / "debug" / RUN_EVENTS_FILENAME


class _ReplayPerceptions:
    def __init__(
        self,
        *,
        perceptions: list[Perception],
        failures: list[LocalFailure],
    ) -> None:
        self.perceptions = perceptions
        self.failures = failures


def _read_perceptions(path: Path) -> _ReplayPerceptions:
    if not path.exists():
        raise FileNotFoundError(f"perception log not found: {path}")
    perceptions: list[Perception] = []
    failures: list[LocalFailure] = []
    with path.open("rb") as fh:
        for line_number, raw in enumerate(fh, start=1):
            try:
                line = raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                failures.append(_malformed_row(line_number))
                continue
            if not line:
                continue
            try:
                perceptions.append(_sanitize_perception(Perception.from_json(line)))
            except ValueError:
                failures.append(_malformed_row(line_number))
                continue
    return _ReplayPerceptions(perceptions=perceptions, failures=failures)


def _malformed_row(line_number: int) -> LocalFailure:
    return LocalFailure(
        channel="replay",
        stage="jsonl",
        message=f"malformed perception row {line_number}",
    )


def _sanitize_perception(perception: Perception) -> Perception:
    return Perception(
        ts=perception.ts,
        source=perception.source,
        type=redact_unsafe_text(perception.type),
        text=redact_unsafe_text(perception.text),
        speaker=(
            redact_unsafe_text(perception.speaker)
            if perception.speaker is not None
            else None
        ),
    )


def _memory_summary(perceptions: list[Perception]) -> str:
    return "\n".join(format_perception_line(p) for p in perceptions)


class _ReplayPrompt:
    def __init__(
        self,
        *,
        observation: PromptObservation | None,
        failures: list[LocalFailure],
    ) -> None:
        self.observation = observation
        self.failures = failures


def _latest_prompt_observation(prompt_dir: Path) -> _ReplayPrompt:
    if not prompt_dir.is_dir():
        return _ReplayPrompt(observation=None, failures=[])
    files = sorted(prompt_dir.glob("prompt-*.json"))
    if not files:
        return _ReplayPrompt(observation=None, failures=[])
    latest = files[-1]
    try:
        observation = _read_prompt_observation(latest)
    except ValueError as exc:
        return _ReplayPrompt(
            observation=None,
            failures=[
                LocalFailure(
                    channel="replay",
                    stage="prompt",
                    message=f"malformed prompt capture {latest.name}: {exc}",
                )
            ],
        )
    except OSError as exc:
        return _ReplayPrompt(
            observation=None,
            failures=[
                LocalFailure(
                    channel="replay",
                    stage="prompt",
                    message=f"unreadable prompt capture {latest.name}: {exc}",
                )
            ],
        )
    return _ReplayPrompt(observation=observation, failures=[])


def _read_prompt_observation(path: Path) -> PromptObservation:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("invalid json") from exc
    if not isinstance(payload, dict):
        raise ValueError("payload is not an object")
    started_at = _parse_datetime(payload.get("started_at"))
    completed_at = _parse_datetime(payload.get("completed_at"))
    if started_at is None or completed_at is None:
        raise ValueError("started_at/completed_at missing or invalid")
    return sanitize_observation(
        PromptObservation(
            prompt=str(payload.get("prompt", "")),
            model=str(payload.get("model", "")),
            status=str(payload.get("status", "")),
            started_at=started_at,
            completed_at=completed_at,
            context=_optional_str(payload.get("context")),
            response_metadata=_dict_payload(payload.get("response_metadata")),
            token_metadata=_dict_payload(payload.get("token_metadata")),
            cache_metadata=_dict_payload(payload.get("cache_metadata")),
            cost=payload.get("cost"),
            error=_optional_str(payload.get("error")),
        )
    )


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _dict_payload(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


class _ReplayEvents:
    def __init__(
        self,
        *,
        triggers: list[Trigger],
        minnarone_messages: list[str],
        failures: list[LocalFailure],
    ) -> None:
        self.triggers = triggers
        self.minnarone_messages = minnarone_messages
        self.failures = failures


def _read_run_events(path: Path) -> _ReplayEvents:
    if not path.exists():
        return _ReplayEvents(triggers=[], minnarone_messages=[], failures=[])
    triggers: list[Trigger] = []
    messages: list[str] = []
    failures: list[LocalFailure] = []
    with path.open("rb") as fh:
        for line_number, raw in enumerate(fh, start=1):
            try:
                line = raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                failures.append(_malformed_event_row(line_number))
                continue
            if not line:
                continue
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError("row is not an object")
                kind = payload.get("kind")
                if kind == "trigger":
                    triggers.append(_trigger_from_event_payload(payload))
                elif kind == "minnarone_output":
                    messages.append(_message_from_event_payload(payload))
                else:
                    raise ValueError("unknown event kind")
            except (ValueError, TypeError, KeyError):
                failures.append(_malformed_event_row(line_number))
                continue
    return _ReplayEvents(
        triggers=triggers,
        minnarone_messages=messages,
        failures=failures,
    )


def _malformed_event_row(line_number: int) -> LocalFailure:
    return LocalFailure(
        channel="replay",
        stage="events",
        message=f"malformed replay event row {line_number}",
    )


def _trigger_from_event_payload(payload: dict[str, object]) -> Trigger:
    trigger = payload["trigger"]
    if not isinstance(trigger, dict):
        raise ValueError("trigger payload is not an object")
    return Trigger(
        reason=_safe_required_str(trigger.get("reason")),
        perception=_optional_perception(trigger.get("perception")),
        kind=_safe_required_str(trigger.get("kind")),
        interlocutor=_safe_optional_str(trigger.get("interlocutor")),
    )


def _message_from_event_payload(payload: dict[str, object]) -> str:
    output = payload["output"]
    if not isinstance(output, dict):
        raise ValueError("output payload is not an object")
    return _safe_required_str(output.get("message"))


def _optional_perception(value: object) -> Perception | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("perception payload is not an object")
    return _sanitize_perception(
        Perception(
            ts=value.get("ts"),
            source=Source(value.get("source")),
            type=_required_str(value.get("type")),
            text=_required_str(value.get("text")),
            speaker=_optional_str(value.get("speaker")),
        )
    )


def _required_str(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("expected non-empty string")
    return value


def _safe_required_str(value: object) -> str:
    return redact_unsafe_text(_required_str(value))


def _safe_optional_str(value: object) -> str | None:
    text = _optional_str(value)
    return redact_unsafe_text(text) if text is not None else None


def _tail(items: list, limit: int) -> list:
    if limit <= 0:
        return []
    return items[-limit:]
