"""Test del modello di snapshot di osservabilità (slice 10).

Il modello `DashboardState` / `snapshot()` è PURO e senza dipendenze: aggrega in
sola lettura percezioni, trigger, finestre di conversazione e messaggi inviati.
Tutti i test sono offline e NON richiedono `textual`.
"""

import asyncio

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
from minnarone.reactor import Reactor
from minnarone.senser import Senser
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
