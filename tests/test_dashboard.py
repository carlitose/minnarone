"""Test del modello di snapshot di osservabilità (slice 10).

Il modello `DashboardState` / `snapshot()` è PURO e senza dipendenze: aggrega in
sola lettura percezioni, trigger, finestre di conversazione e messaggi inviati.
Tutti i test sono offline e NON richiedono `textual`.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from minnarone.chat import ChatPerceiver
from minnarone.dashboard import (
    AdapterChannelDiagnostics,
    DashboardState,
    LocalFailure,
    QueueChannelDiagnostics,
    SpeakerClusterDiagnostics,
    SpeakerDiagnostics,
    VideoDiagnostics,
    snapshot,
)
from minnarone.output import OutputMode, OutputRouter
from minnarone.perception import Perception, Source
from minnarone.perception_queue import (
    PerceptionQueueChannelStats,
    PerceptionQueueStats,
)
from minnarone.prompt_observation import PromptObservation, PromptObservationRecorder
from minnarone.reactor import Reactor
from minnarone.senser import ConversationWindow, Senser, Trigger
from minnarone.store import PerceptionStore


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class RecordingRouter(OutputRouter):
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def route(self, message: str, mode: OutputMode) -> None:
        self.sent.append(message)


class StubLLM:
    def __init__(self, message: str) -> None:
        self._message = message

    async def complete(self, prompt):
        from minnarone.llm import LLMResult

        return LLMResult(message=self._message)


def _store(tmp_path):
    return PerceptionStore(tmp_path / "perceptions.jsonl")


def _chat_perception(text, speaker, ts):
    return Perception(
        ts=ts, source=Source.CHAT, type="msg", text=text, speaker=speaker
    )


def _audio_perception(text, speaker, ts):
    return Perception(
        ts=ts, source=Source.AUDIO, type="speech", text=text, speaker=speaker
    )


def _video_perception(text, ts):
    return Perception(ts=ts, source=Source.VIDEO, type="caption", text=text)


def _prompt_observation(prompt: str, index: int) -> PromptObservation:
    started = datetime(2026, 6, 29, 10, 30, index, tzinfo=UTC)
    return PromptObservation(
        prompt=prompt,
        model="fake",
        status="success",
        started_at=started,
        completed_at=started + timedelta(milliseconds=1),
        token_metadata={"prompt_tokens": index},
    )


def _queue_stats(**channels):
    return SimpleNamespace(channels=channels)


# --- Percezioni recenti ----------------------------------------------------


def test_snapshot_reflects_recent_perceptions_from_store(tmp_path):
    store = _store(tmp_path)
    store.append(_chat_perception("ciao", "alice", 1.0))
    store.append(_chat_perception("come va", "bob", 2.0))

    state = snapshot(store=store)

    assert isinstance(state, DashboardState)
    texts = [p.text for p in state.perceptions]
    assert texts == ["ciao", "come va"]
    # La sorgente è etichettata/raggruppabile per source.
    assert all(p.source is Source.CHAT for p in state.perceptions)


def test_snapshot_exposes_latest_prompt_observation():
    recorder = PromptObservationRecorder()
    recorder.record(_prompt_observation("first prompt", 1))
    recorder.record(_prompt_observation("latest prompt", 2))

    state = snapshot(prompt_recorder=recorder)

    assert state.latest_prompt is not None
    assert state.latest_prompt.prompt == "latest prompt"
    assert state.latest_prompt.token_metadata == {"prompt_tokens": 2}

    state.latest_prompt.token_metadata["prompt_tokens"] = 999

    latest = recorder.latest()
    assert latest is not None
    assert latest.token_metadata == {"prompt_tokens": 2}


def test_prompt_view_degrades_unknown_metadata_gracefully():
    started = datetime(2026, 6, 29, 10, 30, tzinfo=UTC)
    state = DashboardState(
        latest_prompt=PromptObservation(
            prompt="## SITUAZIONE\nNessun dato opzionale.",
            model="",
            status="",
            started_at=started,
            completed_at=started,
        )
    )

    rendered = state.render_prompt_view()

    assert "trigger=unknown" in rendered
    assert "status=unknown" in rendered
    assert "model=unknown" in rendered
    assert (
        "tokens prompt_tokens=unknown completion_tokens=unknown total_tokens=unknown"
        in rendered
    )
    assert "cache cached_tokens=unknown cache_write_tokens=unknown" in rendered
    assert "cost=unknown" in rendered
    assert rendered.endswith("## SITUAZIONE\nNessun dato opzionale.")


def test_prompt_view_renders_partial_token_and_cache_metadata_schema():
    started = datetime(2026, 6, 29, 10, 30, tzinfo=UTC)
    state = DashboardState(
        latest_prompt=PromptObservation(
            prompt="prompt",
            model="fake",
            status="success",
            started_at=started,
            completed_at=started,
            token_metadata={
                "prompt_tokens": 8,
                "provider": "fake",
            },
            cache_metadata={
                "cached_tokens": 3,
                "cache_read_tokens": 2,
                "cache_backend": "memory",
            },
        )
    )

    rendered = state.render_prompt_view()

    assert (
        "tokens prompt_tokens=8 completion_tokens=unknown total_tokens=unknown"
        in rendered
    )
    assert "tokens_extra provider=fake" in rendered
    assert (
        "cache cached_tokens=3 cache_write_tokens=unknown cache_read_tokens=2"
        in rendered
    )
    assert "cache_extra cache_backend=memory" in rendered


def test_prompt_view_renders_none_canonical_metadata_as_unknown_and_preserves_zero():
    started = datetime(2026, 6, 29, 10, 30, tzinfo=UTC)
    state = DashboardState(
        latest_prompt=PromptObservation(
            prompt="prompt",
            model="fake",
            status="success",
            started_at=started,
            completed_at=started,
            token_metadata={
                "prompt_tokens": 0,
                "completion_tokens": None,
                "total_tokens": None,
            },
            cache_metadata={
                "cached_tokens": 0,
                "cache_write_tokens": None,
                "cache_read_tokens": None,
            },
        )
    )

    rendered = state.render_prompt_view()

    assert (
        "tokens prompt_tokens=0 completion_tokens=unknown total_tokens=unknown"
        in rendered
    )
    assert (
        "cache cached_tokens=0 cache_write_tokens=unknown cache_read_tokens=unknown"
        in rendered
    )


def test_snapshot_prompt_view_keeps_secrets_redacted():
    started = datetime(2026, 6, 29, 10, 30, tzinfo=UTC)

    class UnsafePromptRecorder:
        def latest(self):
            return PromptObservation(
                prompt=(
                    "## FATTI\n"
                    "OPENROUTER_API_KEY=sk-or-this-secret-must-not-render\n"
                    "Authorization: Bearer raw-token"
                ),
                model="openrouter/sk-or-model-leak",
                status="success",
                started_at=started,
                completed_at=started,
                token_metadata={"access_token": "raw-secret-value"},
            )

    rendered = snapshot(prompt_recorder=UnsafePromptRecorder()).render_prompt_view()

    assert "sk-or-this-secret-must-not-render" not in rendered
    assert "raw-token" not in rendered
    assert "raw-secret-value" not in rendered
    assert "[redacted" in rendered


def test_snapshot_exposes_current_memory_summary():
    class FakeSummarizer:
        current_summary = "Lo streamer sta preparando la prossima run."

    state = snapshot(summarizer=FakeSummarizer())

    assert state.memory_summary == "Lo streamer sta preparando la prossima run."
    assert "prossima run" in state.render_panels()[-1].text


def test_snapshot_health_gracefully_degrades_when_stats_are_missing():
    state = snapshot(
        perception_queue=object(),
        adapter=object(),
        speaker_tagger=object(),
        video_perceiver=object(),
        prompt_recorder=object(),
    )

    assert set(state.source_health) == {
        "chat",
        "audio",
        "video",
        "asr",
        "speaker",
        "vlm",
        "llm",
        "queue",
        "adapter",
    }
    assert all(health.status == "unknown" for health in state.source_health.values())
    assert "queue_depth=0" in state.render_status_bar()


def test_snapshot_marks_missing_video_captions_suspicious_after_active_sources(tmp_path):
    store = _store(tmp_path)
    store.append(_chat_perception("ciao chat", "alice", 1.0))
    store.append(_audio_perception("frase dal microfono", "streamer", 2.0))

    class FakeQueue:
        def stats(self):
            return _queue_stats(
                video=PerceptionQueueChannelStats(queued=3, processed=3)
            )

    class FakeVideoPerceiver:
        def stats(self):
            return VideoDiagnostics(frames_seen=3, sampled=3, captioned=0)

    state = snapshot(
        store=store,
        perception_queue=FakeQueue(),
        video_perceiver=FakeVideoPerceiver(),
        channel="minnarone",
        started_at=datetime(2026, 6, 29, 10, 30, tzinfo=UTC),
        now=datetime(2026, 6, 29, 10, 31, 5, tzinfo=UTC),
    )

    assert state.source_health["chat"].status == "ok"
    assert state.source_health["audio"].status == "ok"
    assert state.source_health["video"].status == "idle"
    assert "suspicious" in state.source_health["video"].detail
    status = state.render_status_bar()
    assert "channel=minnarone" in status
    assert "uptime=01:05" in status
    assert "video=idle" in status
    assert "chat=1 audio=1 video=0" in status


def test_status_bar_exposes_asr_busy_and_vlm_failure():
    state = DashboardState(
        queue={
            "audio": QueueChannelDiagnostics(queue_depth=1),
            "video": QueueChannelDiagnostics(
                failed=1,
                last_error="local Qwen2-VL caption failed: vlm exploded",
            ),
        }
    )

    assert state.source_health["asr"].status == "busy"
    assert state.source_health["vlm"].status == "failed"
    status = state.render_status_bar()
    assert "asr=busy" in status
    assert "vlm=failed" in status
    assert "latest_failure=video/vlm" in status


def test_drops_only_queue_pressure_does_not_render_failed():
    state = DashboardState(
        queue={
            "audio": QueueChannelDiagnostics(dropped=2),
            "video": QueueChannelDiagnostics(dropped=1),
        }
    )

    status = state.render_status_bar()

    assert state.source_health["queue"].status != "failed"
    assert "queue=failed" not in status
    assert "queue failed=0 dropped=3 abandoned=0 cleanup=0" in status


def test_queue_last_error_still_renders_failed():
    state = DashboardState(
        queue={
            "audio": QueueChannelDiagnostics(
                processed=4,
                last_error="audio queue timed out",
            )
        }
    )

    status = state.render_status_bar()

    assert state.source_health["queue"].status == "failed"
    assert state.source_health["queue"].detail == "audio queue timed out"
    assert "queue=failed" in status
    assert "latest_failure=audio/queue: audio queue timed out" in status


def test_technical_event_lines_still_show_dropped_queue_counts():
    state = DashboardState(
        queue={
            "audio": QueueChannelDiagnostics(processed=4, dropped=2),
            "video": QueueChannelDiagnostics(processed=3, dropped=1),
        }
    )

    event_text = {panel.title: panel.text for panel in state.render_panels()}["EVENTI"]

    assert "audio/queue: dropped=2" in event_text
    assert "video/queue: dropped=1" in event_text


def test_productive_audio_video_health_stays_ok_with_queue_drops():
    state = DashboardState(
        audio_transcriptions=[
            _audio_perception("audio produttivo", "streamer", 1.0),
        ],
        video_captions=[
            _video_perception("caption produttiva", 2.0),
        ],
        video=VideoDiagnostics(frames_seen=8, sampled=4, captioned=1),
        queue={
            "audio": QueueChannelDiagnostics(processed=4, dropped=2),
            "video": QueueChannelDiagnostics(processed=3, dropped=1),
        },
    )

    status = state.render_status_bar()

    assert state.source_health["audio"].status == "ok"
    assert state.source_health["video"].status == "ok"
    assert state.source_health["asr"].status == "ok"
    assert state.source_health["vlm"].status == "ok"
    assert state.source_health["queue"].status != "failed"
    assert "audio=ok" in status
    assert "video=ok" in status
    assert "asr=ok" in status
    assert "vlm=ok" in status
    assert "queue=failed" not in status


def test_source_health_failures_do_not_hide_behind_recent_successes():
    state = DashboardState(
        chat_messages=[
            _chat_perception("chat ok", "alice", 1.0),
        ],
        audio_transcriptions=[
            _audio_perception("audio ok", "streamer", 2.0),
        ],
        video_captions=[
            _video_perception("video ok", 3.0),
        ],
        adapter={
            "chat": AdapterChannelDiagnostics(produced=3, failure="irc failed"),
            "audio": AdapterChannelDiagnostics(produced=3, dropped=2),
            "video": AdapterChannelDiagnostics(produced=3, dropped=1),
        },
    )

    assert state.source_health["chat"].status == "failed"
    assert state.source_health["audio"].status == "failed"
    assert state.source_health["video"].status == "failed"


def test_asr_and_vlm_health_do_not_claim_unrelated_queue_failures():
    state = DashboardState(
        queue={
            "audio": QueueChannelDiagnostics(
                failed=1,
                last_error="speaker embedding failed",
            ),
            "video": QueueChannelDiagnostics(
                failed=1,
                last_error="pyav decode failed",
            ),
        }
    )

    assert state.source_health["audio"].status == "failed"
    assert state.source_health["video"].status == "failed"
    assert state.source_health["asr"].status == "idle"
    assert state.source_health["vlm"].status == "unknown"


def test_video_and_vlm_health_visible_as_busy_during_warmup():
    # Frame di schermo accodati/droppati ma nessuna caption ancora (es. warm-up
    # del VLM): video e vlm devono restare VISIBILI come "busy" nell'header,
    # non sparire come "unknown" (che li ometterebbe dalla status bar).
    state = DashboardState(
        queue={
            "video": QueueChannelDiagnostics(queued=20, processed=0, dropped=18),
        },
    )

    assert state.source_health["video"].status == "busy"
    assert state.source_health["vlm"].status == "busy"
    status = state.render_status_bar()
    assert "video=busy" in status
    assert "vlm=busy" in status


def test_status_bar_exposes_loss_counters_and_bounds_dynamic_segments():
    state = DashboardState(
        channel="channel-" + ("x" * 200),
        queue={
            "audio": QueueChannelDiagnostics(
                failed=1,
                dropped=2,
                abandoned=3,
                cleanup_failures=4,
                queue_depth=5,
            )
        },
        adapter={"video": AdapterChannelDiagnostics(dropped=6)},
    )

    status = state.render_status_bar()

    assert "queue_depth=5" in status
    assert "queue failed=1 dropped=2 abandoned=3 cleanup=4" in status
    assert "adapter_dropped=6" in status
    assert len(status) <= 320


def test_dashboard_failure_redaction_handles_base64_like_tokens():
    class FakeQueue:
        def stats(self):
            return _queue_stats(
                audio=PerceptionQueueChannelStats(
                    failed=1,
                    last_error=(
                        "asr failed oauth:abc/def+ghi= "
                        "Authorization: Bearer sk-or-secret/plus+value="
                    ),
                )
            )

    state = snapshot(perception_queue=FakeQueue())

    event_text = {panel.title: panel.text for panel in state.render_panels()}["EVENTI"]
    status = state.render_status_bar()

    combined = f"{event_text}\n{status}"
    assert "abc/def+ghi" not in combined
    assert "sk-or-secret/plus+value" not in combined
    assert "[redacted]" not in combined
    assert "\\[redacted\\]" in combined


def test_dashboard_failure_redaction_covers_twitch_send_write_token():
    """Il token di SCRITTURA (`TWITCH_SEND_OAUTH_TOKEN`) è nominato a parte
    nel pattern di redazione, come il token di lettura."""

    class FakeQueue:
        def stats(self):
            return _queue_stats(
                audio=PerceptionQueueChannelStats(
                    failed=1,
                    last_error=(
                        "irc send failed "
                        "TWITCH_SEND_OAUTH_TOKEN=segretissimo-send "
                        "TWITCH_OAUTH_TOKEN=segreto-lettura"
                    ),
                )
            )

    state = snapshot(perception_queue=FakeQueue())

    event_text = {panel.title: panel.text for panel in state.render_panels()}["EVENTI"]
    status = state.render_status_bar()

    combined = f"{event_text}\n{status}"
    assert "segretissimo-send" not in combined
    assert "segreto-lettura" not in combined
    assert "\\[redacted\\]" in combined


def test_snapshot_perceptions_limited_to_recent_n(tmp_path):
    store = _store(tmp_path)
    for i in range(10):
        store.append(_chat_perception(f"m{i}", "alice", float(i)))

    state = snapshot(store=store, recent_perceptions=3)

    assert [p.text for p in state.perceptions] == ["m7", "m8", "m9"]


# --- Finestre di conversazione --------------------------------------------


def test_snapshot_includes_open_conversation_windows(tmp_path):
    clock = FakeClock(start=100.0)
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone", clock=clock, window_ttl=180.0)
    # Una menzione apre una finestra per alice.
    store.append(_chat_perception("ehi Minnarone", "alice", 100.0))
    senser.tick()

    state = snapshot(store=store, senser=senser)

    assert "alice" in state.windows


def test_snapshot_excludes_expired_conversation_windows(tmp_path):
    clock = FakeClock(start=100.0)
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone", clock=clock, window_ttl=180.0)
    store.append(_chat_perception("ehi Minnarone", "alice", 100.0))
    senser.tick()
    # Oltre il ttl: la finestra deve essere scaduta e NON apparire.
    clock.advance(200.0)

    state = snapshot(store=store, senser=senser)

    assert "alice" not in state.windows


def test_snapshot_does_not_expire_live_senser_windows(tmp_path):
    clock = FakeClock(start=100.0)
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone", clock=clock, window_ttl=10.0)
    store.append(_chat_perception("ehi Minnarone", "alice", 100.0))
    senser.tick()
    clock.advance(20.0)

    state = snapshot(store=store, senser=senser)

    assert state.windows == {}
    assert "alice" in senser._windows


# --- Messaggi inviati ------------------------------------------------------


def test_snapshot_includes_recent_sent_messages(tmp_path):
    from minnarone.memory import MemoryBlocks
    from minnarone.prompt import PromptBuilder

    clock = FakeClock(start=0.0)
    store = _store(tmp_path)
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    router = RecordingRouter()
    blocks = MemoryBlocks(soul="Sono Minnarone.", facts="")
    reactor = Reactor(
        senser=senser,
        prompt_builder=PromptBuilder(blocks),
        llm=StubLLM("Ciao alice!"),
        router=router,
        store=store,
    )
    chat.perceive(text="ehi Minnarone", speaker="alice")
    asyncio.run(reactor.run_once())
    assert router.sent == ["Ciao alice!"]  # sanity: ha davvero instradato

    state = snapshot(store=store, reactor=reactor)

    assert "Ciao alice!" in state.messages


def test_snapshot_exposes_minnarone_output_stream():
    from minnarone.output_sink import MinnaroneOutputStream, TuiPrivateOutputRouter

    stream = MinnaroneOutputStream(clock=lambda: 10.0)
    router = TuiPrivateOutputRouter(stream)
    asyncio.run(router.route("Commento locale", OutputMode.PRIVATE))

    state = snapshot(minnarone_output=stream)

    assert state.messages == ["Commento locale"]
    rendered = state.render_text()
    assert "== MINNARONE ==" in rendered
    assert "[PRIVATE]" not in rendered


# --- Trigger / eventi ------------------------------------------------------


def test_snapshot_includes_recent_triggers(tmp_path):
    clock = FakeClock(start=0.0)
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    store.append(_chat_perception("ehi Minnarone", "alice", 0.0))
    senser.tick()

    state = snapshot(store=store, senser=senser)

    kinds = [t.kind for t in state.triggers]
    assert "mention" in kinds
    assert any(t.interlocutor == "alice" for t in state.triggers)


def test_events_include_senser_triggers_and_redacted_openrouter_failures(tmp_path):
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone")
    store.append(_chat_perception("ehi Minnarone", "alice", 1.0))
    senser.tick()
    recorder = PromptObservationRecorder()
    started = datetime(2026, 6, 29, 10, 30, tzinfo=UTC)
    recorder.record(
        PromptObservation(
            prompt="p",
            model="openrouter/grok",
            status="error",
            started_at=started,
            completed_at=started + timedelta(seconds=1),
            error=(
                "OpenRouter ha risposto con status 401: "
                "Authorization: Bearer sk-or-secret"
            ),
        )
    )

    state = snapshot(store=store, senser=senser, prompt_recorder=recorder)

    event_text = {panel.title: panel.text for panel in state.render_panels()}["EVENTI"]
    assert "mention <- alice" in event_text
    assert "llm/openrouter" in event_text
    assert "OpenRouter ha risposto con status 401" in event_text
    assert "sk-or-secret" not in event_text
    status = state.render_status_bar()
    assert "llm=error" in status
    assert "model=openrouter/grok" in status
    assert "latest_failure=OpenRouter ha risposto con status 401" in status
    assert "sk-or-secret" not in status
    assert state.source_health["llm"].status == "failed"


# --- Sola lettura ----------------------------------------------------------


def test_snapshot_is_read_only_over_store_and_senser(tmp_path):
    clock = FakeClock(start=100.0)
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    store.append(_chat_perception("ehi Minnarone", "alice", 100.0))
    senser.tick()

    before_tail = [p.text for p in store.tail(50)]
    before_position = senser._position
    before_windows = dict(senser.open_windows())

    snapshot(store=store, senser=senser, recent_perceptions=50)
    snapshot(store=store, senser=senser, recent_perceptions=50)

    after_tail = [p.text for p in store.tail(50)]
    assert after_tail == before_tail
    # Il cursore di lettura del Senser non avanza: la dashboard non consuma.
    assert senser._position == before_position
    assert set(senser.open_windows()) == set(before_windows)


def test_snapshot_does_not_emit_new_triggers(tmp_path):
    clock = FakeClock(start=0.0)
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    store.append(_chat_perception("ehi Minnarone", "alice", 0.0))
    senser.tick()
    n_before = len(senser.recent_triggers())

    snapshot(store=store, senser=senser)
    snapshot(store=store, senser=senser)

    # Lo snapshot non chiama tick(): nessun nuovo trigger generato.
    assert len(senser.recent_triggers()) == n_before


# --- Resa testuale (per il view) -------------------------------------------


def test_snapshot_renders_to_text_without_textual(tmp_path):
    store = _store(tmp_path)
    store.append(_chat_perception("ciao", "alice", 1.0))

    state = snapshot(store=store)
    rendered = state.render_text()

    assert isinstance(rendered, str)
    assert "alice" in rendered
    assert "ciao" in rendered


def test_dashboard_state_renders_screenshot_faithful_panels():
    state = DashboardState(
        perceptions=[
            _chat_perception("messaggio live della chat", "alice", 1.0),
            _audio_perception("frase trascritta", "streamer", 2.0),
            _video_perception("boss visibile sullo schermo", 3.0),
        ],
        audio_transcriptions=[
            _audio_perception("frase trascritta", "streamer", 2.0)
        ],
        video_captions=[
            _video_perception("boss visibile sullo schermo", 3.0)
        ],
        triggers=[
            Trigger(
                reason="mention",
                perception=_chat_perception("ehi Minnarone", "alice", 4.0),
                kind="mention",
                interlocutor="alice",
            )
        ],
        windows={
            "alice": ConversationWindow(
                interlocutor="alice", opened_at=1.0, last_seen=4.0
            ),
            "streamer": ConversationWindow(
                interlocutor="streamer", opened_at=2.0, last_seen=5.0
            ),
        },
        messages=["Commento privato di Minnarone"],
        memory_summary="Alice sta chiedendo aiuto durante il boss.",
    )

    panels = state.render_panels()

    assert [panel.title for panel in panels] == [
        "IDLE",
        "FINESTRA CHAT",
        "STREAMER",
        "CHAT",
        "EVENTI",
        "MINNARONE",
        "TRASCRIZIONE",
        "VIDEO",
        "MEMORIA",
    ]
    panel_text = {panel.title: panel.text for panel in panels}
    assert "alice aperta" in panel_text["FINESTRA CHAT"]
    assert "messaggio live della chat" not in panel_text["FINESTRA CHAT"]
    assert "messaggio live della chat" in panel_text["CHAT"]
    assert "streamer aperta" in panel_text["STREAMER"]
    assert "mention <- alice" in panel_text["EVENTI"]
    assert "Commento privato di Minnarone" in panel_text["MINNARONE"]
    assert "streamer: frase trascritta" in panel_text["TRASCRIZIONE"]
    assert "boss visibile sullo schermo" in panel_text["VIDEO"]
    assert "Alice sta chiedendo aiuto" in panel_text["MEMORIA"]


def test_source_panels_are_not_starved_by_other_busy_sources(tmp_path):
    store = _store(tmp_path)
    store.append(_audio_perception("audio ancora rilevante", "streamer", 1.0))
    store.append(_video_perception("video ancora rilevante", 2.0))
    for index in range(300):
        store.append(_chat_perception(f"chat intensa {index}", "alice", 3.0 + index))
    for index in range(300):
        store.append(_audio_perception(f"audio intenso {index}", "streamer", 303.0 + index))

    state = snapshot(store=store, recent_perceptions=20)
    panel_text = {panel.title: panel.text for panel in state.render_panels()}

    assert "audio intenso 299" in panel_text["TRASCRIZIONE"]
    assert "video ancora rilevante" in panel_text["VIDEO"]
    assert "chat intensa 299" in panel_text["CHAT"]


def test_snapshot_exposes_audio_video_and_queue_diagnostics(tmp_path):
    store = _store(tmp_path)
    store.append(_audio_perception("ciao dal microfono", "streamer", 1.0))
    store.append(_video_perception("menu di gioco aperto", 2.0))

    class FakeQueue:
        def stats(self):
            return PerceptionQueueStats(
                channels={
                    "audio": PerceptionQueueChannelStats(
                        queued=3,
                        processed=2,
                        dropped=1,
                        failed=0,
                        queue_depth=0,
                    ),
                    "video": PerceptionQueueChannelStats(
                        queued=4,
                        processed=1,
                        dropped=2,
                        failed=1,
                        queue_depth=1,
                        last_error="vlm setup exploded",
                    ),
                }
            )

    state = snapshot(store=store, perception_queue=FakeQueue())

    assert [(p.speaker, p.text) for p in state.audio_transcriptions] == [
        ("streamer", "ciao dal microfono")
    ]
    assert [(p.ts, p.text) for p in state.video_captions] == [
        (2.0, "menu di gioco aperto")
    ]
    assert state.queue["audio"] == QueueChannelDiagnostics(
        queued=3,
        processed=2,
        dropped=1,
        failed=0,
        cancelled=0,
        cleanup_failures=0,
        abandoned=0,
        queue_depth=0,
        last_error=None,
    )
    assert state.queue["video"].failed == 1
    assert state.failures == [
        LocalFailure(
            channel="video",
            stage="vlm",
            message="vlm setup exploded",
        )
    ]
    rendered = state.render_text()
    assert "== Audio ==" in rendered
    assert "streamer: ciao dal microfono" in rendered
    assert "== Video ==" in rendered
    assert "menu di gioco aperto" in rendered
    assert "audio: queued=3 processed=2 dropped=1 failed=0" in rendered
    assert "video/vlm: vlm setup exploded" in rendered


def test_snapshot_exposes_adapter_and_video_perceiver_diagnostics():
    class FakeAdapter:
        def stats(self):
            from minnarone.twitch_stream import TwitchStreamStats

            return TwitchStreamStats(
                running=True,
                produced={"video": 3},
                dropped={"video": 1},
                failures={"video": "PyAV decode failed"},
            )

    class FakeVideoPerceiver:
        def stats(self):
            from minnarone.video import VideoPerceptionStats

            return VideoPerceptionStats(
                frames_seen=10,
                sampled=4,
                dedup_skipped=2,
                captioned=1,
                empty_captions=1,
                failed=1,
            )

    state = snapshot(adapter=FakeAdapter(), video_perceiver=FakeVideoPerceiver())

    assert state.adapter == {
        "video": AdapterChannelDiagnostics(
            produced=3,
            dropped=1,
            failure="PyAV decode failed",
        )
    }
    assert state.video == VideoDiagnostics(
        frames_seen=10,
        sampled=4,
        dedup_skipped=2,
        captioned=1,
        empty_captions=1,
        failed=1,
    )
    assert state.failures == [
        LocalFailure(channel="video", stage="pyav", message="PyAV decode failed")
    ]
    rendered = state.render_text()
    assert "frames=10 sampled=4 dedup_skipped=2 captioned=1 failed=1" in rendered
    assert "video: produced=3 dropped=1 failure=PyAV decode failed" in rendered


def test_snapshot_sanitizes_failure_messages_before_rendering():
    class UnsafeQueue:
        def stats(self):
            return PerceptionQueueStats(
                channels={
                    "audio": PerceptionQueueChannelStats(
                        failed=1,
                        last_error=(
                            "\x1b[31mASR failed oauth:abcd1234 "
                            "OPENROUTER_API_KEY=sk-secret "
                            "api_key: 'sk-colon-secret' "
                            "embedding=(0.1, 0.2, 0.3, 0.4) "
                            "payload=b'raw-audio-bytes-here'"
                        ),
                    )
                }
            )

    state = snapshot(perception_queue=UnsafeQueue())

    message = state.failures[0].message
    assert "oauth:abcd1234" not in message
    assert "sk-secret" not in message
    assert "sk-colon-secret" not in message
    assert "raw-audio-bytes-here" not in message
    assert "0.1, 0.2" not in message
    assert "\x1b" not in message
    assert "\\[redacted\\]" in message


def test_unknown_queue_failures_do_not_default_to_asr_or_vlm():
    class UnknownQueue:
        def stats(self):
            return PerceptionQueueStats(
                channels={"video": PerceptionQueueChannelStats(failed=1)}
            )

    state = snapshot(perception_queue=UnknownQueue())

    assert state.failures == [
        LocalFailure(
            channel="video",
            stage="unknown",
            message="local perception failure",
        )
    ]


def test_snapshot_exposes_speaker_cluster_diagnostics_without_centroids(tmp_path):
    class FakeSpeakerDiagnostics:
        def stats(self):
            from minnarone.speaker import (
                SpeakerClusterStats,
                SpeakerTaggingStats,
            )

            return SpeakerTaggingStats(
                total_utterances=3,
                clustered_utterances=2,
                unknown_utterances=1,
                streamer_cluster_id=7,
                clusters=(
                    SpeakerClusterStats(
                        cluster_id=7,
                        label="streamer",
                        talk_time_seconds=12.5,
                        updates=4,
                        centroid=(0.1, 0.2, 0.3),
                    ),
                    SpeakerClusterStats(
                        cluster_id=8,
                        label="speaker_2",
                        talk_time_seconds=3.0,
                        updates=1,
                        centroid=(0.9, 0.1, 0.0),
                    ),
                ),
            )

    state = snapshot(speaker_tagger=FakeSpeakerDiagnostics())

    assert state.speaker == SpeakerDiagnostics(
        total_utterances=3,
        clustered_utterances=2,
        unknown_utterances=1,
        streamer_cluster_id=7,
        clusters=[
            SpeakerClusterDiagnostics(
                cluster_id=7,
                label="streamer",
                talk_time_seconds=12.5,
                updates=4,
            ),
            SpeakerClusterDiagnostics(
                cluster_id=8,
                label="speaker_2",
                talk_time_seconds=3.0,
                updates=1,
            ),
        ],
    )
    rendered = state.render_text()
    assert "streamer_cluster=7" in rendered
    assert "cluster 7 streamer talk=12.5s updates=4" in rendered
    assert "0.1" not in rendered


def test_snapshot_windows_are_defensive_copies(tmp_path):
    clock = FakeClock(start=100.0)
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    store.append(_chat_perception("ehi Minnarone", "alice", 100.0))
    senser.tick()

    who = next(iter(senser.open_windows()))
    live_before = senser.open_windows()[who].last_seen

    state = snapshot(store=store, senser=senser)
    # la finestra nello snapshot è un oggetto distinto da quello vivo
    assert state.windows[who] is not senser.open_windows()[who]
    # mutare lo snapshot NON tocca lo stato di conversazione vivo
    state.windows[who].last_seen = 999999.0
    assert senser.open_windows()[who].last_seen == live_before


# --- Send diagnostics (issue 04) ------------------------------------------


def test_snapshot_exposes_send_diagnostics_from_policy():
    """The snapshot wires a policy snapshot into a plain SendDiagnostics."""
    from minnarone.dashboard import SendDiagnostics

    class FakePolicy:
        def snapshot(self):
            from minnarone.config import TwitchSendMode
            from minnarone.public_send import PolicySnapshot, SendDecision

            return PolicySnapshot(
                mode=TwitchSendMode.SHADOW,
                promoted=False,
                kill_switch=False,
                consecutive_failures=0,
                minute_remaining=5,
                hour_remaining=20,
                last_decision=SendDecision(action="shadow", reason="ok"),
            )

    state = snapshot(send_policy=FakePolicy())

    assert state.send is not None
    assert isinstance(state.send, SendDiagnostics)
    assert state.send.mode == "shadow"
    assert state.send.promoted is False
    assert state.send.kill_switch is False
    assert state.send.consecutive_failures == 0
    assert state.send.minute_remaining == 5
    assert state.send.hour_remaining == 20
    assert state.send.last_action == "shadow"
    assert state.send.last_reason == "ok"


def test_snapshot_send_diagnostics_none_when_no_policy():
    """Without a send policy, send diagnostics are None."""
    state = snapshot()
    assert state.send is None


def test_send_health_idle_before_any_decision():
    """Before any decision, send health is idle."""
    from minnarone.dashboard import SendDiagnostics

    state = DashboardState(
        send=SendDiagnostics(mode="shadow", minute_remaining=5, hour_remaining=20),
    )

    assert state.source_health["send"].status == "idle"


def test_send_health_ok_after_successful_shadow_decision():
    from minnarone.dashboard import SendDiagnostics

    state = DashboardState(
        send=SendDiagnostics(
            mode="shadow",
            minute_remaining=4,
            hour_remaining=19,
            last_action="shadow",
            last_reason="ok",
        ),
    )

    assert state.source_health["send"].status == "ok"


def test_send_health_ok_after_successful_send_decision():
    from minnarone.dashboard import SendDiagnostics

    state = DashboardState(
        send=SendDiagnostics(
            mode="live",
            promoted=True,
            minute_remaining=4,
            hour_remaining=19,
            last_action="send",
            last_reason="ok",
        ),
    )

    assert state.source_health["send"].status == "ok"


def test_send_health_failed_with_kill_switch():
    from minnarone.dashboard import SendDiagnostics

    state = DashboardState(
        send=SendDiagnostics(
            mode="live",
            kill_switch=True,
            consecutive_failures=3,
            minute_remaining=5,
            hour_remaining=20,
            last_action="shadow",
            last_reason="kill_switch",
        ),
    )

    assert state.source_health["send"].status == "failed"
    assert "kill_switch" in state.source_health["send"].detail


def test_status_bar_includes_send_budget():
    from minnarone.dashboard import SendDiagnostics

    state = DashboardState(
        send=SendDiagnostics(
            mode="shadow",
            minute_remaining=3,
            hour_remaining=18,
            last_action="shadow",
            last_reason="ok",
        ),
    )

    status = state.render_status_bar()
    assert "send=ok" in status
    assert "budget=3/18" in status


def test_tui_router_captures_shadow_messages_in_minnarone_panel():
    """PUBLIC messages routed through the shadow router appear in the
    MinnaroneOutputStream with [SHADOW] markers for the MINNARONE panel."""
    from minnarone.config import TwitchSendConfig, TwitchSendMode
    from minnarone.output_sink import MinnaroneOutputStream, TuiPrivateOutputRouter
    from minnarone.shadow_router import TwitchPublicOutputRouter

    import io

    config = TwitchSendConfig(
        mode=TwitchSendMode.SHADOW,
        allowed_channels=["#test"],
    )
    clock = FakeClock(start=0.0)
    from minnarone.public_send import PublicSendPolicy

    policy = PublicSendPolicy(config, clock=clock)
    stdout_sink = io.StringIO()
    public_router = TwitchPublicOutputRouter(
        policy=policy, channel="#test", stream=stdout_sink,
    )
    stream = MinnaroneOutputStream(clock=clock)
    router = TuiPrivateOutputRouter(stream, public_router=public_router)

    asyncio.run(router.route("Ciao chat!", OutputMode.PUBLIC))

    messages = [m.text for m in stream.recent_messages()]
    assert messages == ["[SHADOW] Ciao chat!"]


def test_tui_router_captures_sent_messages_in_minnarone_panel():
    """PUBLIC messages that are SENT (not shadow) appear with [SENT] marker."""
    from minnarone.config import TwitchSendConfig, TwitchSendMode
    from minnarone.output_sink import MinnaroneOutputStream, TuiPrivateOutputRouter
    from minnarone.shadow_router import TwitchPublicOutputRouter

    import io

    config = TwitchSendConfig(
        mode=TwitchSendMode.LIVE,
        allowed_channels=["#test"],
    )
    clock = FakeClock(start=0.0)
    from minnarone.public_send import PublicSendPolicy

    policy = PublicSendPolicy(config, clock=clock)
    policy.promote()
    stdout_sink = io.StringIO()

    class FakeSender:
        async def send(self, message: str) -> None:
            pass  # successful send

    public_router = TwitchPublicOutputRouter(
        policy=policy, channel="#test", stream=stdout_sink, sender=FakeSender(),
    )
    stream = MinnaroneOutputStream(clock=clock)
    router = TuiPrivateOutputRouter(stream, public_router=public_router)

    asyncio.run(router.route("Ciao chat!", OutputMode.PUBLIC))

    messages = [m.text for m in stream.recent_messages()]
    assert messages == ["[SENT] Ciao chat!"]


def test_render_text_includes_send_section():
    from minnarone.dashboard import SendDiagnostics

    state = DashboardState(
        send=SendDiagnostics(
            mode="shadow",
            promoted=False,
            kill_switch=False,
            consecutive_failures=0,
            minute_remaining=5,
            hour_remaining=20,
            last_action="shadow",
            last_reason="ok",
        ),
    )

    rendered = state.render_text()
    assert "== Send ==" in rendered
    assert "mode=shadow" in rendered
    assert "promoted=False" in rendered
    assert "kill_switch=False" in rendered
    assert "failures=0" in rendered
    assert "budget=5/20" in rendered
    assert "last=shadow/ok" in rendered


def test_render_text_omits_send_section_when_no_policy():
    state = DashboardState()
    rendered = state.render_text()
    assert "== Send ==" not in rendered


def test_tui_router_does_not_capture_dropped_messages():
    """Dropped PUBLIC messages do NOT appear in MinnaroneOutputStream."""
    from minnarone.config import TwitchSendConfig, TwitchSendMode
    from minnarone.output_sink import MinnaroneOutputStream, TuiPrivateOutputRouter
    from minnarone.shadow_router import TwitchPublicOutputRouter

    import io

    config = TwitchSendConfig(
        mode=TwitchSendMode.SHADOW,
        allowed_channels=["#test"],
        max_per_minute=1,
    )
    clock = FakeClock(start=0.0)
    from minnarone.public_send import PublicSendPolicy

    policy = PublicSendPolicy(config, clock=clock)
    stdout_sink = io.StringIO()
    public_router = TwitchPublicOutputRouter(
        policy=policy, channel="#test", stream=stdout_sink,
    )
    stream = MinnaroneOutputStream(clock=clock)
    router = TuiPrivateOutputRouter(stream, public_router=public_router)

    # First message consumes the minute budget
    asyncio.run(router.route("First", OutputMode.PUBLIC))
    # Second message is dropped (budget exhausted)
    asyncio.run(router.route("Dropped", OutputMode.PUBLIC))

    messages = [m.text for m in stream.recent_messages()]
    assert messages == ["[SHADOW] First"]
    assert "Dropped" not in " ".join(messages)


# --- Per-profile output panels (issue 13) -----------------------------------


def test_dashboard_state_has_per_profile_message_fields():
    """DashboardState has synthesizer_messages and suggester_messages."""
    state = DashboardState(
        synthesizer_messages=["Riassunto della riunione."],
        suggester_messages=["Suggerimento: prova questa strategia."],
    )

    assert state.synthesizer_messages == ["Riassunto della riunione."]
    assert state.suggester_messages == ["Suggerimento: prova questa strategia."]


def test_dashboard_state_per_profile_defaults_empty():
    """Without explicit data, per-profile lists default to empty."""
    state = DashboardState()

    assert state.synthesizer_messages == []
    assert state.suggester_messages == []


def test_render_panels_includes_sintetizzatore_when_active():
    """SINTETIZZATORE panel appears when synthesizer has messages."""
    state = DashboardState(
        synthesizer_messages=["Sintesi del discorso."],
    )

    panels = state.render_panels()
    titles = [p.title for p in panels]

    assert "SINTETIZZATORE" in titles
    panel_text = {p.title: p.text for p in panels}
    assert "Sintesi del discorso." in panel_text["SINTETIZZATORE"]


def test_render_panels_includes_suggerimenti_when_active():
    """SUGGERIMENTI panel appears when suggester has messages."""
    state = DashboardState(
        suggester_messages=["Suggerimento strategico."],
    )

    panels = state.render_panels()
    titles = [p.title for p in panels]

    assert "SUGGERIMENTI" in titles
    panel_text = {p.title: p.text for p in panels}
    assert "Suggerimento strategico." in panel_text["SUGGERIMENTI"]


def test_render_panels_excludes_sintetizzatore_when_inactive():
    """SINTETIZZATORE panel does NOT appear when no synthesizer messages."""
    state = DashboardState()

    panels = state.render_panels()
    titles = [p.title for p in panels]

    assert "SINTETIZZATORE" not in titles


def test_render_panels_excludes_suggerimenti_when_inactive():
    """SUGGERIMENTI panel does NOT appear when no suggester messages."""
    state = DashboardState()

    panels = state.render_panels()
    titles = [p.title for p in panels]

    assert "SUGGERIMENTI" not in titles


def test_render_panels_includes_both_new_panels_when_both_active():
    """Both SINTETIZZATORE and SUGGERIMENTI appear when both have messages."""
    state = DashboardState(
        synthesizer_messages=["Sintesi."],
        suggester_messages=["Suggerimento."],
    )

    panels = state.render_panels()
    titles = [p.title for p in panels]

    assert "SINTETIZZATORE" in titles
    assert "SUGGERIMENTI" in titles
    # The base 9 panels are still present.
    assert "MINNARONE" in titles
    assert "MEMORIA" in titles


def test_render_panels_preserves_base_panels_order_with_new_panels():
    """New panels appear after MEMORIA; base panel order unchanged."""
    state = DashboardState(
        synthesizer_messages=["Sintesi."],
        suggester_messages=["Suggerimento."],
    )

    panels = state.render_panels()
    titles = [p.title for p in panels]

    # The original 9 titles should appear in their original order.
    base_titles = [
        "IDLE", "FINESTRA CHAT", "STREAMER", "CHAT", "EVENTI",
        "MINNARONE", "TRASCRIZIONE", "VIDEO", "MEMORIA",
    ]
    base_in_result = [t for t in titles if t in base_titles]
    assert base_in_result == base_titles
    # New panels come after the base ones.
    assert titles.index("SINTETIZZATORE") > titles.index("MEMORIA")
    assert titles.index("SUGGERIMENTI") > titles.index("SINTETIZZATORE")


def test_snapshot_populates_per_profile_messages_from_output_streams():
    """snapshot() reads per-profile streams into per-profile message fields."""
    from minnarone.output import CommentatorStyle
    from minnarone.output_sink import MinnaroneOutputStream

    syn_stream = MinnaroneOutputStream(clock=lambda: 10.0)
    syn_stream.append("Sintesi riunione.", OutputMode.PRIVATE)

    sug_stream = MinnaroneOutputStream(clock=lambda: 11.0)
    sug_stream.append("Suggerimento tattico.", OutputMode.PRIVATE)

    output_streams = {
        CommentatorStyle.MEETING_SYNTHESIZER: syn_stream,
        CommentatorStyle.SUGGESTER: sug_stream,
    }

    state = snapshot(output_streams=output_streams)

    assert state.synthesizer_messages == ["Sintesi riunione."]
    assert state.suggester_messages == ["Suggerimento tattico."]


def test_snapshot_per_profile_empty_when_no_streams():
    """Without output_streams, per-profile messages are empty."""
    state = snapshot()

    assert state.synthesizer_messages == []
    assert state.suggester_messages == []


def test_snapshot_per_profile_empty_when_stream_has_no_messages():
    """A present but empty stream yields an empty list."""
    from minnarone.output import CommentatorStyle
    from minnarone.output_sink import MinnaroneOutputStream

    syn_stream = MinnaroneOutputStream(clock=lambda: 10.0)
    output_streams = {CommentatorStyle.MEETING_SYNTHESIZER: syn_stream}

    state = snapshot(output_streams=output_streams)

    assert state.synthesizer_messages == []
    assert state.suggester_messages == []


def test_status_bar_includes_active_profile_segments():
    """Status bar shows per-profile health segments when profiles are active."""
    state = DashboardState(
        synthesizer_messages=["Sintesi."],
        suggester_messages=["Suggerimento."],
    )

    status = state.render_status_bar()

    assert "syn=ok" in status
    assert "sug=ok" in status


def test_status_bar_omits_profile_segments_when_inactive():
    """Status bar does NOT show profile segments when no messages."""
    state = DashboardState()

    status = state.render_status_bar()

    assert "syn=" not in status
    assert "sug=" not in status


def test_render_text_includes_per_profile_sections():
    """render_text() includes per-profile sections when messages exist."""
    state = DashboardState(
        synthesizer_messages=["Sintesi."],
        suggester_messages=["Suggerimento."],
    )

    rendered = state.render_text()

    assert "== SINTETIZZATORE ==" in rendered
    assert "Sintesi." in rendered
    assert "== SUGGERIMENTI ==" in rendered
    assert "Suggerimento." in rendered


def test_render_text_omits_per_profile_sections_when_empty():
    """render_text() does NOT include per-profile sections when empty."""
    state = DashboardState()

    rendered = state.render_text()

    assert "== SINTETIZZATORE ==" not in rendered
    assert "== SUGGERIMENTI ==" not in rendered
