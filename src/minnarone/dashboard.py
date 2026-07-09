"""Modello di osservabilità: uno snapshot PURO dello stato del sistema.

La dashboard di osservabilità (slice 10) mostra in tempo reale, in **sola
lettura**, cosa sta facendo l'agente: le percezioni in arrivo, i trigger/eventi
prodotti dal Senser, le finestre di conversazione aperte e i messaggi inviati.

Questo modulo contiene la parte *pura e senza dipendenze* del lavoro:
`DashboardState` e `snapshot()` aggregano le sorgenti già esistenti in dati
semplici (dataclass / liste / stringhe) pronti per essere resi. NON dipende da
`textual`: la vista TUI vive in `dashboard_tui.py` con un import guardato.

Vincolo fondamentale — **strettamente READ-ONLY**: `snapshot()` usa solo gli
accessor di sola lettura delle sorgenti (`store.tail`,
`senser.window_snapshot`, `senser.recent_triggers`, `reactor.recent_messages`,
queue/adapter `stats()`). Non chiama `tick()`, non fa avanzare cursori, non
instrada nulla: produrre uno snapshot non interferisce con il loop del Reactor
né muta lo stato osservato.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from .audio import STREAMER
from .dashboard_health import (
    SourceCounts,
    SourceHealth,
)
from .dashboard_health import (
    latest_failure as _latest_failure,
)
from .dashboard_health import (
    render_status_bar as _render_status_bar,
)
from .dashboard_health import (
    safe_message as _safe_message,
)
from .dashboard_health import (
    safe_status_value as _safe_status_value,
)
from .dashboard_health import (
    source_counts as _source_counts,
)
from .dashboard_health import (
    source_health as _source_health,
)
from .dashboard_health import (
    stage_from_error as _stage_from_error,
)
from .dashboard_health import (
    technical_event_lines as _technical_event_lines,
)
from .output import CommentatorStyle
from .perception import Perception, format_perception_line
from .prompt_observation import PromptObservation, sanitize_observation
from .senser import ConversationWindow, Trigger

# Quante percezioni recenti includere di default nello snapshot.
_DEFAULT_RECENT_PERCEPTIONS = 20

# Quanti trigger e messaggi recenti includere di default.
_DEFAULT_RECENT_TRIGGERS = 20
_DEFAULT_RECENT_MESSAGES = 20
_PROMPT_TOKEN_METADATA_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")
_PROMPT_CACHE_REQUIRED_METADATA_KEYS = ("cached_tokens", "cache_write_tokens")
_PROMPT_CACHE_OPTIONAL_METADATA_KEYS = ("cache_read_tokens",)


@dataclass(frozen=True, slots=True)
class QueueChannelDiagnostics:
    """Operator-visible bounded queue counters for one local media channel."""

    queued: int = 0
    processed: int = 0
    dropped: int = 0
    failed: int = 0
    cancelled: int = 0
    cleanup_failures: int = 0
    abandoned: int = 0
    queue_depth: int = 0
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class LocalFailure:
    """Sanitized local perception failure for dashboard/debug output."""

    channel: str
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class SpeakerClusterDiagnostics:
    """Speaker cluster state without raw embeddings/centroids."""

    cluster_id: int
    label: str
    talk_time_seconds: float
    updates: int


@dataclass(frozen=True, slots=True)
class SpeakerDiagnostics:
    """Speaker diarization state safe for operator display."""

    total_utterances: int = 0
    clustered_utterances: int = 0
    unknown_utterances: int = 0
    streamer_cluster_id: int | None = None
    clusters: list[SpeakerClusterDiagnostics] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class VideoDiagnostics:
    """Video sampling/dedup/caption counters safe for dashboard display."""

    frames_seen: int = 0
    sampled: int = 0
    dedup_skipped: int = 0
    captioned: int = 0
    empty_captions: int = 0
    failed: int = 0


@dataclass(frozen=True, slots=True)
class SendDiagnostics:
    """Plain read-only send-path state for dashboard display (issue 04).

    Mirrors ``PolicySnapshot`` as simple data: no reference to the live
    policy object, so the dashboard stays read-only by design.
    """

    mode: str = "off"
    promoted: bool = False
    kill_switch: bool = False
    consecutive_failures: int = 0
    minute_remaining: int = 0
    hour_remaining: int = 0
    last_action: str | None = None
    last_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AdapterChannelDiagnostics:
    """Capture adapter counters for one channel."""

    produced: int = 0
    dropped: int = 0
    failure: str | None = None


@dataclass(frozen=True, slots=True)
class DashboardPanel:
    """Formatted read-only content for one operator dashboard panel."""

    title: str
    text: str


@dataclass(frozen=True, slots=True)
class DashboardState:
    """Vista immutabile e pura dello stato osservabile del sistema.

    Tutti i campi sono dati semplici (copie difensive delle sorgenti), così la
    state è disaccoppiata dagli oggetti vivi: chi la rende non può alterare il
    loop. È volutamente serializzabile e facile da testare offline.

    Attributi:
        perceptions: ultime percezioni viste (ordine cronologico di scrittura).
        triggers: ultimi trigger/eventi emessi dal Senser.
        windows: finestre di conversazione attualmente aperte (interlocutore ->
            finestra).
        messages: ultimi messaggi instradati dall'agente.
    """

    perceptions: list[Perception] = field(default_factory=list)
    chat_messages: list[Perception] = field(default_factory=list)
    audio_transcriptions: list[Perception] = field(default_factory=list)
    video_captions: list[Perception] = field(default_factory=list)
    triggers: list[Trigger] = field(default_factory=list)
    windows: dict[str, ConversationWindow] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)
    queue: dict[str, QueueChannelDiagnostics] = field(default_factory=dict)
    adapter: dict[str, AdapterChannelDiagnostics] = field(default_factory=dict)
    failures: list[LocalFailure] = field(default_factory=list)
    speaker: SpeakerDiagnostics = field(default_factory=SpeakerDiagnostics)
    video: VideoDiagnostics = field(default_factory=VideoDiagnostics)
    latest_prompt: PromptObservation | None = None
    memory_summary: str = ""
    send: SendDiagnostics | None = None
    synthesizer_messages: list[str] = field(default_factory=list)
    suggester_messages: list[str] = field(default_factory=list)
    channel: str | None = None
    started_at: datetime | None = None
    now: datetime | None = None
    replay_source: str | None = None

    @property
    def source_counts(self) -> SourceCounts:
        return _source_counts(self)

    @property
    def source_health(self) -> dict[str, SourceHealth]:
        return _source_health(self)

    @property
    def latest_failure(self) -> str | None:
        return _latest_failure(self)

    def render_status_bar(self) -> str:
        return _render_status_bar(self)

    def render_panels(self) -> list[DashboardPanel]:
        """Render the screenshot-faithful dashboard panels in visual row order.

        The base 9 panels always appear. SINTETIZZATORE and SUGGERIMENTI are
        appended only when the corresponding profile is active (has messages).
        """
        panels = [
            DashboardPanel("IDLE", self._render_idle_panel()),
            DashboardPanel("FINESTRA CHAT", self._render_chat_window_panel()),
            DashboardPanel("STREAMER", self._render_streamer_panel()),
            DashboardPanel("CHAT", self._render_chat_panel()),
            DashboardPanel("EVENTI", self._render_events_panel()),
            DashboardPanel("MINNARONE", self._render_minnarone_panel()),
            DashboardPanel("TRASCRIZIONE", self._render_transcription_panel()),
            DashboardPanel("VIDEO", self._render_video_panel()),
            DashboardPanel("MEMORIA", self._render_memory_panel()),
        ]
        if self.synthesizer_messages:
            panels.append(
                DashboardPanel("SINTETIZZATORE", self._render_synthesizer_panel())
            )
        if self.suggester_messages:
            panels.append(
                DashboardPanel("SUGGERIMENTI", self._render_suggester_panel())
            )
        return panels

    def _render_idle_panel(self) -> str:
        idle_triggers = [t for t in self.triggers if t.kind == "idle_comment"]
        if not idle_triggers:
            return "(nessun idle)"
        return "\n".join(f"{t.kind} <- {t.interlocutor or '-'}" for t in idle_triggers)

    def _render_chat_window_panel(self) -> str:
        lines = [
            _format_window(window)
            for who, window in self.windows.items()
            if who != STREAMER
        ]
        return "\n".join(lines) if lines else "(nessuna finestra chat)"

    def _render_streamer_panel(self) -> str:
        window = self.windows.get(STREAMER)
        if window is None:
            return "(nessuna finestra streamer)"
        return _format_window(window)

    def _render_chat_panel(self) -> str:
        source = self.chat_messages or [
            p for p in self.perceptions if p.source.value == "chat"
        ]
        lines = [
            f"{p.ts:.3f} {format_perception_line(p)}"
            for p in source
        ]
        return "\n".join(lines) if lines else "(nessuna chat)"

    def _render_events_panel(self) -> str:
        lines = [
            f"{t.kind} <- {t.interlocutor if t.interlocutor else '-'}"
            for t in self.triggers
        ]
        lines.extend(_technical_event_lines(self))
        return "\n".join(lines) if lines else "(nessun evento)"

    def _render_minnarone_panel(self) -> str:
        return "\n".join(self.messages) if self.messages else "(nessuno)"

    def _render_transcription_panel(self) -> str:
        lines = [
            f"{p.ts:.3f} {p.speaker or '?'}: {p.text}"
            for p in self.audio_transcriptions
        ]
        return "\n".join(lines) if lines else "(nessuna trascrizione)"

    def _render_video_panel(self) -> str:
        diagnostics = (
            "frames="
            f"{self.video.frames_seen} sampled={self.video.sampled} "
            f"captioned={self.video.captioned} failed={self.video.failed}"
        )
        captions = [f"{p.ts:.3f} {p.text}" for p in self.video_captions]
        return "\n".join([diagnostics, *captions])

    def _render_memory_panel(self) -> str:
        summary = self.memory_summary.strip()
        return summary if summary else "(nessuna memoria)"

    def _render_synthesizer_panel(self) -> str:
        return "\n".join(self.synthesizer_messages) if self.synthesizer_messages else "(nessuna sintesi)"

    def _render_suggester_panel(self) -> str:
        return "\n".join(self.suggester_messages) if self.suggester_messages else "(nessun suggerimento)"

    def render_prompt_view(self) -> str:
        """Render the latest redacted prompt observation for the TUI prompt tab."""
        latest = self.latest_prompt
        if latest is None:
            return "(nessun prompt catturato)"
        latest = sanitize_observation(latest)

        lines = [
            "== PROMPT ==",
            (
                f"trigger={latest.context or 'unknown'} "
                f"status={latest.status or 'unknown'} "
                f"model={latest.model or 'unknown'}"
            ),
        ]
        lines.extend(
            _format_schema_metadata(
                "tokens",
                latest.token_metadata,
                required_keys=_PROMPT_TOKEN_METADATA_KEYS,
            )
        )
        lines.extend(
            _format_schema_metadata(
                "cache",
                latest.cache_metadata,
                required_keys=_PROMPT_CACHE_REQUIRED_METADATA_KEYS,
                optional_keys=_PROMPT_CACHE_OPTIONAL_METADATA_KEYS,
            )
        )
        lines.append(f"cost={latest.cost}" if latest.cost is not None else "cost=unknown")
        if latest.error:
            lines.append(f"error={latest.error}")
        lines.extend(["", "== BODY ==", latest.prompt])
        return "\n".join(lines)

    def render_text(self) -> str:
        """Resa testuale dello snapshot, senza alcuna dipendenza da textual.

        Mantiene il dump legacy verificabile in modo headless. La vista Textual
        principale usa invece `render_panels()` per preservare la griglia.
        """
        lines: list[str] = []

        lines.append("== Percezioni ==")
        if self.perceptions:
            for p in self.perceptions:
                lines.append(f"[{p.source.value}] {format_perception_line(p)}")
        else:
            lines.append("(nessuna)")

        lines.append("== Trigger/Eventi ==")
        if self.triggers:
            for t in self.triggers:
                who = t.interlocutor if t.interlocutor else "-"
                lines.append(f"{t.kind} <- {who}")
        else:
            lines.append("(nessuno)")

        lines.append("== Audio ==")
        if self.audio_transcriptions:
            for p in self.audio_transcriptions:
                speaker = p.speaker or "?"
                lines.append(f"{p.ts:.3f} {speaker}: {p.text}")
        else:
            lines.append("(nessun transcript)")

        lines.append("== Speaker ==")
        lines.append(
            "utterances="
            f"{self.speaker.total_utterances} clustered="
            f"{self.speaker.clustered_utterances} unknown="
            f"{self.speaker.unknown_utterances} streamer_cluster="
            f"{self.speaker.streamer_cluster_id}"
        )
        if self.speaker.clusters:
            for cluster in self.speaker.clusters:
                lines.append(
                    f"cluster {cluster.cluster_id} {cluster.label} "
                    f"talk={cluster.talk_time_seconds:.1f}s "
                    f"updates={cluster.updates}"
                )
        else:
            lines.append("(nessun cluster)")

        lines.append("== Video ==")
        lines.append(
            "frames="
            f"{self.video.frames_seen} sampled={self.video.sampled} "
            f"dedup_skipped={self.video.dedup_skipped} "
            f"captioned={self.video.captioned} failed={self.video.failed}"
        )
        if self.video_captions:
            for p in self.video_captions:
                lines.append(f"{p.ts:.3f} {p.text}")
        else:
            lines.append("(nessuna caption)")

        lines.append("== Adapter ==")
        if self.adapter:
            for channel, stats in self.adapter.items():
                line = (
                    f"{channel}: produced={stats.produced} "
                    f"dropped={stats.dropped}"
                )
                if stats.failure:
                    line = f"{line} failure={stats.failure}"
                lines.append(line)
        else:
            lines.append("(nessun adapter)")

        lines.append("== Queue ==")
        if self.queue:
            for channel, stats in self.queue.items():
                lines.append(
                    f"{channel}: queued={stats.queued} "
                    f"processed={stats.processed} dropped={stats.dropped} "
                    f"failed={stats.failed} cancelled={stats.cancelled} "
                    f"depth={stats.queue_depth}"
                )
        else:
            lines.append("(nessuna queue)")

        lines.append("== Failure locali ==")
        if self.failures:
            for failure in self.failures:
                lines.append(
                    f"{failure.channel}/{failure.stage}: {failure.message}"
                )
        else:
            lines.append("(nessuna)")

        lines.append("== Finestre aperte ==")
        if self.windows:
            for who in self.windows:
                lines.append(who)
        else:
            lines.append("(nessuna)")

        lines.append("== MINNARONE ==")
        if self.messages:
            lines.extend(self.messages)
        else:
            lines.append("(nessuno)")

        if self.send is not None:
            lines.append("== Send ==")
            s = self.send
            lines.append(
                f"mode={s.mode} promoted={s.promoted} "
                f"kill_switch={s.kill_switch} failures={s.consecutive_failures}"
            )
            lines.append(f"budget={s.minute_remaining}/{s.hour_remaining}")
            if s.last_action is not None:
                lines.append(f"last={s.last_action}/{s.last_reason}")
            else:
                lines.append("last=(none)")

        if self.synthesizer_messages:
            lines.append("== SINTETIZZATORE ==")
            lines.extend(self.synthesizer_messages)

        if self.suggester_messages:
            lines.append("== SUGGERIMENTI ==")
            lines.extend(self.suggester_messages)

        return "\n".join(lines)


def _format_window(window: ConversationWindow) -> str:
    return (
        f"{window.interlocutor} aperta "
        f"da {window.opened_at:.3f}; ultimo={window.last_seen:.3f}"
    )


def _format_schema_metadata(
    label: str,
    metadata: dict[str, object],
    *,
    required_keys: tuple[str, ...],
    optional_keys: tuple[str, ...] = (),
) -> list[str]:
    canonical_keys = (*required_keys, *optional_keys)
    lines = [
        f"{label} "
        + " ".join(
            f"{key}={_canonical_metadata_value(metadata, key)}"
            for key in required_keys
        )
    ]
    optional_parts = [
        f"{key}={_canonical_metadata_value(metadata, key)}"
        for key in optional_keys
        if key in metadata
    ]
    if optional_parts:
        lines[0] = f"{lines[0]} {' '.join(optional_parts)}"

    extra_parts = [
        f"{key}={value}"
        for key, value in metadata.items()
        if key not in canonical_keys
    ]
    if extra_parts:
        lines.append(f"{label}_extra " + " ".join(extra_parts))
    return lines


def _canonical_metadata_value(metadata: dict[str, object], key: str) -> object:
    value = metadata.get(key)
    if value is None:
        return "unknown"
    return value


def snapshot(
    *,
    store=None,
    senser=None,
    reactor=None,
    minnarone_output=None,
    output_streams: dict[CommentatorStyle, object] | None = None,
    perception_queue=None,
    speaker_tagger=None,
    video_perceiver=None,
    adapter=None,
    prompt_recorder=None,
    summarizer=None,
    send_policy=None,
    channel: str | None = None,
    started_at: datetime | None = None,
    now: datetime | None = None,
    recent_perceptions: int = _DEFAULT_RECENT_PERCEPTIONS,
    recent_triggers: int = _DEFAULT_RECENT_TRIGGERS,
    recent_messages: int = _DEFAULT_RECENT_MESSAGES,
) -> DashboardState:
    """Aggrega in sola lettura le sorgenti vive in un `DashboardState` puro.

    Ogni sorgente è opzionale: si passano solo quelle disponibili (lo store, il
    Senser, il Reactor). Si usano ESCLUSIVAMENTE accessor di sola lettura, così
    produrre lo snapshot non muta nulla e non interferisce con il loop:

    - `store.tail(n)`            -> percezioni recenti
    - `senser.window_snapshot()` -> finestre di conversazione aperte
    - `senser.recent_triggers()` -> trigger/eventi recenti
    - `reactor.recent_messages()`-> messaggi instradati di recente
    """
    perceptions: list[Perception] = []
    if store is not None and recent_perceptions > 0:
        perceptions = list(store.tail(recent_perceptions))
    chat_messages = _tail_matching(
        store,
        limit=recent_perceptions,
        source="chat",
        type="msg",
    )
    audio_transcriptions = _tail_matching(
        store,
        limit=recent_perceptions,
        source="audio",
        type="speech",
    )
    video_captions = _tail_matching(
        store,
        limit=recent_perceptions,
        source="video",
        type="caption",
    )

    triggers: list[Trigger] = []
    windows: dict[str, ConversationWindow] = {}
    if senser is not None:
        triggers = list(senser.recent_triggers(recent_triggers))
        # Copia DIFENSIVA: ConversationWindow è mutabile e gli oggetti restituiti
        # da open_windows() sono quelli vivi usati dal Senser per TTL/idle. Lo
        # snapshot è sola-lettura, quindi cloniamo ogni finestra così un consumer
        # non può mutare lo stato di conversazione vivo attraverso lo snapshot.
        window_source = getattr(senser, "window_snapshot", senser.open_windows)
        windows = {who: replace(win) for who, win in window_source().items()}

    messages: list[str] = []
    if minnarone_output is not None:
        output_messages = minnarone_output.recent_messages(recent_messages)
        messages = [message.text for message in output_messages]
    elif reactor is not None:
        messages = list(reactor.recent_messages(recent_messages))

    queue = _queue_diagnostics(perception_queue)
    adapter_diagnostics = _adapter_diagnostics(adapter)
    failures = _queue_failures(queue) + _adapter_failures(adapter_diagnostics)
    speaker = _speaker_diagnostics(speaker_tagger)
    video = _video_diagnostics(video_perceiver)
    latest_prompt = _latest_prompt_observation(prompt_recorder)
    memory_summary = _current_memory_summary(summarizer)
    send = _send_diagnostics(send_policy)
    synthesizer_messages = _per_profile_messages(
        output_streams, CommentatorStyle.MEETING_SYNTHESIZER, recent_messages,
    )
    suggester_messages = _per_profile_messages(
        output_streams, CommentatorStyle.SUGGESTER, recent_messages,
    )

    return DashboardState(
        perceptions=perceptions,
        chat_messages=chat_messages,
        audio_transcriptions=audio_transcriptions,
        video_captions=video_captions,
        triggers=triggers,
        windows=windows,
        messages=messages,
        queue=queue,
        adapter=adapter_diagnostics,
        failures=failures,
        speaker=speaker,
        video=video,
        latest_prompt=latest_prompt,
        memory_summary=memory_summary,
        send=send,
        synthesizer_messages=synthesizer_messages,
        suggester_messages=suggester_messages,
        channel=_safe_status_value(channel),
        started_at=started_at,
        now=now or (datetime.now(UTC) if started_at is not None else None),
    )


def _current_memory_summary(summarizer) -> str:
    if summarizer is None:
        return ""
    summary = getattr(summarizer, "current_summary", "")
    return summary if isinstance(summary, str) else ""


def _per_profile_messages(
    output_streams: dict[CommentatorStyle, object] | None,
    style: CommentatorStyle,
    limit: int,
) -> list[str]:
    """Read recent messages from a per-profile MinnaroneOutputStream."""
    if output_streams is None:
        return []
    stream = output_streams.get(style)
    if stream is None:
        return []
    recent = getattr(stream, "recent_messages", None)
    if recent is None:
        return []
    return [msg.text for msg in recent(limit)]


def _tail_matching(
    store,
    *,
    limit: int,
    source: str,
    type: str,  # noqa: A002 - mirrors Perception field.
) -> list[Perception]:
    if store is None or limit <= 0:
        return []
    tail_matching = getattr(store, "tail_matching", None)
    if tail_matching is None:
        return [
            p for p in store.tail(limit) if p.source.value == source and p.type == type
        ][-limit:]
    return list(tail_matching(limit, source=source, type=type))


def _latest_prompt_observation(prompt_recorder) -> PromptObservation | None:
    if prompt_recorder is None:
        return None
    latest = getattr(prompt_recorder, "latest", None)
    if latest is None:
        return None
    observation = latest()
    if observation is None:
        return None
    observation = sanitize_observation(observation)
    return replace(
        observation,
        response_metadata=dict(observation.response_metadata),
        token_metadata=dict(observation.token_metadata),
        cache_metadata=dict(observation.cache_metadata),
        error=_safe_message(observation.error),
    )


def _queue_diagnostics(perception_queue) -> dict[str, QueueChannelDiagnostics]:
    if perception_queue is None:
        return {}
    stats_method = getattr(perception_queue, "stats", None)
    if stats_method is None:
        return {}
    stats = stats_method()
    channels = getattr(stats, "channels", {})
    return {
        channel: QueueChannelDiagnostics(
            queued=getattr(channel_stats, "queued", 0),
            processed=getattr(channel_stats, "processed", 0),
            dropped=getattr(channel_stats, "dropped", 0),
            failed=getattr(channel_stats, "failed", 0),
            cancelled=getattr(channel_stats, "cancelled", 0),
            cleanup_failures=getattr(channel_stats, "cleanup_failures", 0),
            abandoned=getattr(channel_stats, "abandoned", 0),
            queue_depth=getattr(channel_stats, "queue_depth", 0),
            last_error=_safe_message(getattr(channel_stats, "last_error", None)),
        )
        for channel, channel_stats in channels.items()
    }


def _queue_failures(
    queue: dict[str, QueueChannelDiagnostics],
) -> list[LocalFailure]:
    failures: list[LocalFailure] = []
    for channel, stats in queue.items():
        if stats.failed or stats.cleanup_failures or stats.abandoned:
            failures.append(
                LocalFailure(
                    channel=channel,
                    stage=_stage_from_error(channel, stats.last_error),
                    message=stats.last_error or "local perception failure",
                )
            )
    return failures


def _adapter_diagnostics(adapter) -> dict[str, AdapterChannelDiagnostics]:
    if adapter is None:
        return {}
    stats_method = getattr(adapter, "stats", None)
    if stats_method is None:
        return {}
    stats = stats_method()
    produced = getattr(stats, "produced", {})
    dropped = getattr(stats, "dropped", {})
    failures = getattr(stats, "failures", {})
    channels = set(produced) | set(dropped) | set(failures)
    return {
        channel: AdapterChannelDiagnostics(
            produced=int(produced.get(channel, 0)),
            dropped=int(dropped.get(channel, 0)),
            failure=_safe_message(failures.get(channel)),
        )
        for channel in sorted(channels)
    }


def _adapter_failures(
    adapter: dict[str, AdapterChannelDiagnostics],
) -> list[LocalFailure]:
    failures: list[LocalFailure] = []
    for channel, stats in adapter.items():
        if stats.failure:
            failures.append(
                LocalFailure(
                    channel=channel,
                    stage=_stage_from_error(channel, stats.failure),
                    message=stats.failure,
                )
            )
    return failures


def _speaker_diagnostics(speaker_tagger) -> SpeakerDiagnostics:
    if speaker_tagger is None:
        return SpeakerDiagnostics()
    stats_method = getattr(speaker_tagger, "stats", None)
    if stats_method is None:
        return SpeakerDiagnostics()
    stats = stats_method()
    return SpeakerDiagnostics(
        total_utterances=getattr(stats, "total_utterances", 0),
        clustered_utterances=getattr(stats, "clustered_utterances", 0),
        unknown_utterances=getattr(stats, "unknown_utterances", 0),
        streamer_cluster_id=getattr(stats, "streamer_cluster_id", None),
        clusters=[
            SpeakerClusterDiagnostics(
                cluster_id=cluster.cluster_id,
                label=cluster.label,
                talk_time_seconds=cluster.talk_time_seconds,
                updates=cluster.updates,
            )
            for cluster in getattr(stats, "clusters", ())
        ],
    )


def _video_diagnostics(video_perceiver) -> VideoDiagnostics:
    if video_perceiver is None:
        return VideoDiagnostics()
    stats_method = getattr(video_perceiver, "stats", None)
    if stats_method is None:
        return VideoDiagnostics()
    stats = stats_method()
    return VideoDiagnostics(
        frames_seen=getattr(stats, "frames_seen", 0),
        sampled=getattr(stats, "sampled", 0),
        dedup_skipped=getattr(stats, "dedup_skipped", 0),
        captioned=getattr(stats, "captioned", 0),
        empty_captions=getattr(stats, "empty_captions", 0),
        failed=getattr(stats, "failed", 0),
    )


def _send_diagnostics(send_policy) -> SendDiagnostics | None:
    if send_policy is None:
        return None
    snap_method = getattr(send_policy, "snapshot", None)
    if snap_method is None:
        return None
    snap = snap_method()
    last = getattr(snap, "last_decision", None)
    return SendDiagnostics(
        mode=getattr(getattr(snap, "mode", None), "value", str(getattr(snap, "mode", "off"))),
        promoted=getattr(snap, "promoted", False),
        kill_switch=getattr(snap, "kill_switch", False),
        consecutive_failures=getattr(snap, "consecutive_failures", 0),
        minute_remaining=getattr(snap, "minute_remaining", 0),
        hour_remaining=getattr(snap, "hour_remaining", 0),
        last_action=getattr(last, "action", None) if last is not None else None,
        last_reason=getattr(last, "reason", None) if last is not None else None,
    )
