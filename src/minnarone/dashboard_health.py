"""Normalized health and status formatting for the observability dashboard."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SourceHealth:
    """Normalized operator-facing health for one source or subsystem."""

    status: str = "unknown"
    detail: str = ""


@dataclass(frozen=True, slots=True)
class SourceCounts:
    """Inspectable source counters for compact dashboard status output."""

    chat_messages: int = 0
    audio_transcriptions: int = 0
    video_captions: int = 0


def source_counts(state) -> SourceCounts:
    return SourceCounts(
        chat_messages=len(state.chat_messages),
        audio_transcriptions=len(state.audio_transcriptions),
        video_captions=len(state.video_captions),
    )


def source_health(state) -> dict[str, SourceHealth]:
    health: dict[str, SourceHealth] = {
        "chat": _chat_health(state),
        "audio": _audio_health(state),
        "video": _video_health(state),
        "asr": _asr_health(state),
        "speaker": _speaker_health(state),
        "vlm": _vlm_health(state),
        "llm": _llm_health(state),
        "queue": _queue_health(state),
        "adapter": _adapter_health(state),
    }
    send = _send_health(state)
    if send is not None:
        health["send"] = send
    syn = _profile_health(getattr(state, "synthesizer_messages", []))
    if syn is not None:
        health["syn"] = syn
    sug = _profile_health(getattr(state, "suggester_messages", []))
    if sug is not None:
        health["sug"] = sug
    return health


def latest_failure(state) -> str | None:
    if state.latest_prompt is not None and state.latest_prompt.status == "error":
        return state.latest_prompt.error or "llm error"
    if state.failures:
        return state.failures[-1].message
    for channel, stats in reversed(state.queue.items()):
        if stats.last_error and _failed_queue(stats):
            stage = stage_from_error(channel, stats.last_error)
            return f"{channel}/{stage}: {stats.last_error}"
    health = state.source_health
    for name in ("video", "vlm", "asr", "speaker", "queue", "adapter"):
        item = health[name]
        if item.status == "failed" and item.detail:
            return f"{name}: {item.detail}"
    return None


def render_status_bar(state) -> str:
    """Render one compact pure status line for the live TUI."""
    if getattr(state, "replay_source", None):
        return _render_replay_status_bar(state)
    counts = state.source_counts
    health = state.source_health
    health_names = (
        "chat",
        "audio",
        "video",
        "asr",
        "speaker",
        "vlm",
        "llm",
        "queue",
        "adapter",
        "send",
        "syn",
        "sug",
    )
    health_text = " ".join(
        f"{name}={health[name].status}"
        for name in health_names
        if name in health and health[name].status != "unknown"
    )
    if not health_text:
        health_text = "unknown"
    queue_depth = sum(stats.queue_depth for stats in state.queue.values())
    queue_failed = sum(stats.failed for stats in state.queue.values())
    queue_dropped = sum(stats.dropped for stats in state.queue.values())
    queue_abandoned = sum(stats.abandoned for stats in state.queue.values())
    queue_cleanup = sum(stats.cleanup_failures for stats in state.queue.values())
    adapter_dropped = sum(stats.dropped for stats in state.adapter.values())
    parts = []
    parts.extend(
        [
            f"channel={_compact(safe_status_value(state.channel) or '-', 32)}",
            f"uptime={_format_uptime(state.started_at, state.now)}",
            f"health {health_text}",
            _prompt_status(state.latest_prompt),
        ]
    )
    failure = state.latest_failure
    if failure:
        parts.append(f"latest_failure={_compact(failure, 80)}")
    parts.extend(
        [
            (
                "counts "
                f"chat={counts.chat_messages} "
                f"audio={counts.audio_transcriptions} "
                f"video={counts.video_captions}"
            ),
            f"queue_depth={queue_depth}",
            (
                "queue "
                f"failed={queue_failed} dropped={queue_dropped} "
                f"abandoned={queue_abandoned} cleanup={queue_cleanup}"
            ),
            f"adapter_dropped={adapter_dropped}",
        ]
    )
    send = getattr(state, "send", None)
    if send is not None:
        parts.append(f"budget={send.minute_remaining}/{send.hour_remaining}")
    return _compact(" | ".join(part for part in parts if part), 320)


def _render_replay_status_bar(state) -> str:
    source = _compact_path(safe_status_value(state.replay_source) or "-", 80)
    prompt = "present" if state.latest_prompt is not None else "missing"
    failure = state.latest_failure
    parts = [
        "mode=replay offline",
        f"source={source}",
        (
            "replayed "
            f"chat={len(state.chat_messages)} "
            f"audio={len(state.audio_transcriptions)} "
            f"video={len(state.video_captions)} "
            f"events={len(state.triggers)} "
            f"minnarone={len(state.messages)}"
        ),
        f"prompt={prompt}",
        f"failures={len(state.failures)}",
    ]
    if failure:
        parts.append(f"latest_failure={_compact(failure, 80)}")
    return _compact(" | ".join(parts), 320)


def technical_event_lines(state) -> list[str]:
    lines = [
        f"{failure.channel}/{failure.stage}: {failure.message}"
        for failure in state.failures
    ]
    for channel, stats in state.queue.items():
        if stats.dropped:
            lines.append(f"{channel}/queue: dropped={stats.dropped}")
        if stats.cancelled:
            lines.append(f"{channel}/queue: cancelled={stats.cancelled}")
    for channel, stats in state.adapter.items():
        if stats.dropped:
            lines.append(f"{channel}/adapter: dropped={stats.dropped}")
    if _missing_video_captions_are_suspicious(state):
        lines.append("video/vlm: suspicious: sampled video has no captions")
    latest = state.latest_prompt
    if latest is not None and latest.status == "error":
        stage = "openrouter" if _mentions_openrouter(latest) else "llm"
        lines.append(f"llm/{stage}: {latest.error or 'llm error'}")
    return lines


def safe_status_value(value: object) -> str | None:
    safe = safe_message(value)
    return safe.replace("\\[", "[").replace("\\]", "]") if safe is not None else None


def safe_message(message: object) -> str | None:
    if message is None:
        return None
    text = str(message).replace("\x1b", "")
    text = _CONTROL_CHARS.sub("", text)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[redacted]", text)
    text = _BYTES_REPR.sub("b'[redacted-bytes]'", text)
    text = _CENTROID_RE.sub("[redacted-vector]", text)
    text = text.replace("[", "\\[").replace("]", "\\]")
    text = " ".join(text.split())
    if len(text) <= 200:
        return text
    return text[:200].rstrip()


def stage_from_error(channel: str, message: str | None) -> str:
    lowered = (message or "").lower()
    stages = (
        "capture",
        "vad",
        "asr",
        "embedding",
        "clustering",
        "pyav",
        "dedup",
        "vlm",
        "output",
    )
    for stage in stages:
        if stage in lowered:
            return stage
    if "timeout" in lowered or "queue" in lowered or "cleanup" in lowered:
        return "queue"
    return "unknown"


def _chat_health(state) -> SourceHealth:
    adapter = state.adapter.get("chat")
    if adapter is not None and adapter.failure:
        return SourceHealth("failed", adapter.failure)
    if adapter is not None and adapter.dropped:
        return SourceHealth("failed", f"{adapter.dropped} dropped")
    if state.chat_messages:
        return SourceHealth("ok", f"{len(state.chat_messages)} messages")
    if adapter is not None and adapter.produced:
        return SourceHealth("ok", f"{adapter.produced} raw events")
    return SourceHealth("unknown")


def _audio_health(state) -> SourceHealth:
    stats = state.queue.get("audio")
    adapter = state.adapter.get("audio")
    if adapter is not None and adapter.failure:
        return SourceHealth("failed", adapter.failure)
    if adapter is not None and adapter.dropped:
        return SourceHealth("failed", f"{adapter.dropped} dropped")
    if _failed_queue(stats):
        return SourceHealth("failed", stats.last_error or "audio queue failure")
    if stats is not None and stats.queue_depth:
        return SourceHealth("busy", f"depth={stats.queue_depth}")
    if state.audio_transcriptions:
        return SourceHealth("ok", f"{len(state.audio_transcriptions)} transcriptions")
    if adapter is not None and adapter.produced:
        return SourceHealth("idle", f"{adapter.produced} raw events")
    return SourceHealth("unknown")


def _video_health(state) -> SourceHealth:
    stats = state.queue.get("video")
    adapter = state.adapter.get("video")
    if adapter is not None and adapter.failure:
        return SourceHealth("failed", adapter.failure)
    if adapter is not None and adapter.dropped:
        return SourceHealth("failed", f"{adapter.dropped} dropped")
    if _failed_queue(stats) or state.video.failed:
        detail = stats.last_error if stats is not None else None
        return SourceHealth("failed", detail or "video caption failure")
    if stats is not None and stats.queue_depth:
        return SourceHealth("busy", f"depth={stats.queue_depth}")
    if state.video_captions or state.video.captioned:
        caption_count = state.video.captioned or len(state.video_captions)
        return SourceHealth("ok", f"{caption_count} captions")
    if _missing_video_captions_are_suspicious(state):
        return SourceHealth("idle", "suspicious: video observed without captions")
    if state.video.frames_seen or (adapter is not None and adapter.produced):
        return SourceHealth("idle", "video observed without captions yet")
    if stats is not None and (stats.queued or stats.dropped):
        # Frame di schermo entrati in coda ma non ancora descritti (es. warm-up
        # del VLM): resta visibile come "busy" invece di sparire come "unknown".
        return SourceHealth("busy", "video queued, awaiting captions")
    return SourceHealth("unknown")


def _asr_health(state) -> SourceHealth:
    stats = state.queue.get("audio")
    failure = _failure_for_stage(state, "audio", {"asr"})
    if failure is not None:
        return SourceHealth("failed", failure.message)
    if _failed_queue(stats) and _queue_error_stage("audio", stats) == "asr":
        return SourceHealth("failed", stats.last_error or "audio queue failure")
    if stats is not None and stats.queue_depth:
        return SourceHealth("busy", f"depth={stats.queue_depth}")
    if state.audio_transcriptions:
        return SourceHealth("ok", f"{len(state.audio_transcriptions)} transcriptions")
    if stats is not None:
        return SourceHealth("idle")
    return SourceHealth("unknown")


def _speaker_health(state) -> SourceHealth:
    failure = _failure_for_stage(state, "audio", {"embedding", "clustering"})
    if failure is not None:
        return SourceHealth("failed", failure.message)
    if state.speaker.total_utterances:
        if state.speaker.clustered_utterances:
            return SourceHealth("ok", f"{state.speaker.clustered_utterances} clustered")
        return SourceHealth("idle", f"{state.speaker.unknown_utterances} unknown")
    if state.audio_transcriptions:
        return SourceHealth("idle", "transcriptions without speaker clusters")
    return SourceHealth("unknown")


def _vlm_health(state) -> SourceHealth:
    stats = state.queue.get("video")
    failure = _failure_for_stage(state, "video", {"vlm"})
    if failure is not None:
        return SourceHealth("failed", failure.message)
    if state.video.failed:
        detail = stats.last_error if stats is not None else None
        return SourceHealth("failed", detail or "vlm caption failure")
    if _failed_queue(stats) and _queue_error_stage("video", stats) == "vlm":
        detail = stats.last_error if stats is not None else None
        return SourceHealth("failed", detail or "vlm caption failure")
    if stats is not None and stats.queue_depth:
        return SourceHealth("busy", f"depth={stats.queue_depth}")
    if state.video.captioned or state.video_captions:
        caption_count = state.video.captioned or len(state.video_captions)
        return SourceHealth("ok", f"{caption_count} captioned")
    if _missing_video_captions_are_suspicious(state):
        return SourceHealth("idle", "suspicious: sampled video has no captions")
    if state.video.sampled:
        return SourceHealth("idle", "sampled without captions yet")
    if stats is not None and (stats.queued or stats.dropped):
        # Frame in coda per il captioner ma nessuna caption ancora (es. il
        # modello si sta caricando): visibile come "busy", non "unknown".
        return SourceHealth("busy", "captioning in progress")
    return SourceHealth("unknown")


def _llm_health(state) -> SourceHealth:
    latest = state.latest_prompt
    if latest is None:
        return SourceHealth("unknown")
    if latest.status == "error":
        return SourceHealth("failed", latest.error or "llm error")
    if latest.status == "running":
        return SourceHealth("busy")
    if latest.status == "success":
        return SourceHealth("ok", latest.model)
    return SourceHealth("unknown", latest.status)


def _queue_health(state) -> SourceHealth:
    if not state.queue:
        return SourceHealth("unknown")
    failed = sum(
        stats.failed + stats.cleanup_failures + stats.abandoned
        for stats in state.queue.values()
    )
    last_error = next(
        (stats.last_error for stats in state.queue.values() if stats.last_error),
        None,
    )
    if last_error:
        return SourceHealth("failed", last_error)
    if failed:
        return SourceHealth("failed", f"{failed} failures")
    depth = sum(stats.queue_depth for stats in state.queue.values())
    if depth:
        return SourceHealth("busy", f"depth={depth}")
    processed = sum(stats.processed for stats in state.queue.values())
    if processed:
        return SourceHealth("ok", f"{processed} processed")
    dropped = sum(stats.dropped for stats in state.queue.values())
    if dropped:
        return SourceHealth("idle", f"{dropped} dropped")
    return SourceHealth("idle")


def _adapter_health(state) -> SourceHealth:
    if not state.adapter:
        return SourceHealth("unknown")
    failures = [stats.failure for stats in state.adapter.values() if stats.failure]
    if failures:
        return SourceHealth("failed", failures[-1] or "adapter failure")
    dropped = sum(stats.dropped for stats in state.adapter.values())
    if dropped:
        return SourceHealth("failed", f"{dropped} dropped")
    produced = sum(stats.produced for stats in state.adapter.values())
    if produced:
        return SourceHealth("ok", f"{produced} produced")
    return SourceHealth("idle")


def _send_health(state) -> SourceHealth | None:
    send = getattr(state, "send", None)
    if send is None:
        return None
    if send.kill_switch:
        return SourceHealth("failed", "kill_switch")
    if send.consecutive_failures:
        return SourceHealth("failed", f"{send.consecutive_failures} consecutive failures")
    if send.last_action is None:
        return SourceHealth("idle")
    if send.last_action == "drop":
        reason = send.last_reason or "dropped"
        return SourceHealth("idle", reason)
    return SourceHealth("ok", f"mode={send.mode}")


def _profile_health(messages: list[str]) -> SourceHealth | None:
    """Health for a per-profile output stream (syn/sug).

    Returns None when the profile is inactive (no messages), so the segment
    is omitted from the status bar entirely.
    """
    if not messages:
        return None
    return SourceHealth("ok", f"{len(messages)} messages")


def _failed_queue(stats) -> bool:
    return bool(
        stats is not None
        and (
            stats.failed
            or stats.cleanup_failures
            or stats.abandoned
            or stats.last_error
        )
    )


def _queue_error_stage(channel: str, stats) -> str:
    return stage_from_error(channel, stats.last_error)


def _failure_for_stage(state, channel: str, stages: set[str]):
    for failure in reversed(state.failures):
        if failure.channel == channel and failure.stage in stages:
            return failure
    return None


def _missing_video_captions_are_suspicious(state) -> bool:
    if state.video_captions or state.video.captioned:
        return False
    if state.video.failed:
        return False
    enough_video = state.video.sampled >= 2 or state.video.frames_seen >= 3
    video_adapter = state.adapter.get("video")
    enough_adapter_video = video_adapter is not None and video_adapter.produced >= 3
    active_other_sources = bool(state.chat_messages or state.audio_transcriptions)
    processed_video = state.queue.get("video")
    processed = processed_video is not None and processed_video.processed >= 2
    return (enough_video or enough_adapter_video) and (active_other_sources or processed)


def _mentions_openrouter(observation) -> bool:
    text = f"{observation.model} {observation.error or ''}".lower()
    return "openrouter" in text


def _prompt_status(prompt) -> str:
    if prompt is None:
        return "llm=unknown"
    parts = [f"llm={_compact(str(prompt.status), 16)}", f"model={_compact(str(prompt.model), 48)}"]
    token_text = _metadata_summary(prompt.token_metadata)
    if token_text:
        parts.append(f"tokens={token_text}")
    cache_text = _metadata_summary(prompt.cache_metadata)
    if cache_text:
        parts.append(f"cache={cache_text}")
    return " ".join(parts)


def _metadata_summary(metadata: dict[str, object]) -> str:
    return _compact(",".join(f"{key}:{value}" for key, value in metadata.items()), 80)


def _format_uptime(started_at: datetime | None, now: datetime | None) -> str:
    if started_at is None or now is None:
        return "-"
    elapsed = max(int((now - started_at).total_seconds()), 0)
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _compact(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."


def _compact_path(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    path = Path(value)
    tail = str(path.name or value[-max_chars:])
    prefix_budget = max_chars - len(tail) - 4
    if prefix_budget <= 0:
        return "..." + tail[-(max_chars - 3) :]
    return f"{value[:prefix_budget]}.../{tail}"


_SECRET_PATTERNS = (
    re.compile(r"oauth:[A-Za-z0-9._~+\-/=]+", re.IGNORECASE),
    re.compile(r"bearer\s+[A-Za-z0-9._~+\-/=]+", re.IGNORECASE),
    re.compile(r"\bsk-or-[A-Za-z0-9._~+\-/=]+", re.IGNORECASE),
    re.compile(r"\bauthorization\s*:\s*\S+\s+[^\r\n]+", re.IGNORECASE),
    # "TWITCH_SEND_OAUTH_TOKEN" è letterale di proposito (questo modulo resta
    # senza import di progetto): deve restare allineato a
    # `config.TWITCH_SEND_TOKEN_ENV_VAR`, il token di SCRITTURA per l'invio.
    re.compile(
        r"(OPENROUTER_API_KEY|TWITCH_SEND_OAUTH_TOKEN|TWITCH_OAUTH_TOKEN|"
        r"api[_-]?key|token)"
        r"\s*[:=]\s*['\"]?[^'\",\s;]+['\"]?",
        re.IGNORECASE,
    ),
)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BYTES_REPR = re.compile(r"b(['\"])(?:\\.|(?!\1).){8,}\1")
_CENTROID_RE = re.compile(
    r"\b(?:centroid|embedding)\s*[:=]\s*\([^)]{10,}\)",
    re.IGNORECASE,
)
