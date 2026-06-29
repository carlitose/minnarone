"""Test dell'app di riferimento (slice 11): assemblaggio da config.

L'issue 11 cabla i moduli SDK insieme a partire da una `Config`. Qui si verifica
che `build_agent` componga il grafo correttamente (offline, con fake LLM
transport e adapter in-memory), lo switch modalità public/private, e che i punti
v2 (disclosure/retention/auto-memory) siano presenti ma inerti.
"""

import asyncio
import json
import textwrap
from dataclasses import replace
from threading import Event

import pytest

from minnarone.app import (
    Agent,
    PrivateModeNotImplemented,
    PrivateNotImplementedRouter,
    build_agent,
)
from minnarone.audio import AudioChunk
from minnarone.config import Config, ConfigError
from minnarone.console import ConsoleOutputRouter
from minnarone.output import OutputMode
from minnarone.perception import Perception, Source
from minnarone.reactor import Reactor
from minnarone.run_artifacts import create_run_session
from minnarone.source import RawEvent, SourceAdapter
from minnarone.twitch_stream import TwitchStreamAdapter, TwitchStreamRuntimeError
from minnarone.twitch_video import DecodedVideoFrame
from minnarone.video import VideoFrame
from minnarone.vlm import QwenVlCaptionError


def _fake_transport(*, url, headers, body, timeout):
    # Trasporto HTTP fake: nessuna rete. Non dovrebbe nemmeno essere chiamato
    # durante il solo assemblaggio, ma è qui per sicurezza se un test reagisce.
    from minnarone.openrouter import HttpResponse

    payload = b'{"choices":[{"message":{"content":"ciao"}}]}'
    return HttpResponse(status=200, body=payload)


def _write_workspace(
    tmp_path,
    *,
    mode="public",
    adapter="os_capture",
    announce_ai=False,
    auto_memory=True,
    twitch_block="",
    extra="",
):
    """Crea soul/facts su disco e un config YAML; ritorna il path del config."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    soul = tmp_path / "soul.md"
    soul.write_text("Sono Minnarone, 25 anni.", encoding="utf-8")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir(exist_ok=True)
    (facts_dir / "canale.md").write_text("Canale Twitch di test.", encoding="utf-8")

    # Dedent PRIMA della sostituzione, così un `extra` multilinea (le cui righe
    # 2+ non sono indentate) non sballa il calcolo dell'indentazione comune.
    template = textwrap.dedent(
        """
        mode: {mode}
        soul_path: {soul}
        facts_dir: {facts_dir}
        adapter: {adapter}
        llm_provider: grok
        agent_name: minnarone
        {twitch_block}
        disclosure:
          announce_ai: {announce_ai}
        retention:
          perceptions_days: 7
        auto_memory: {auto_memory}
        {extra}
        """
    )
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        template.format(
            mode=mode,
            soul=soul,
            facts_dir=facts_dir,
            adapter=adapter,
            twitch_block=twitch_block,
            announce_ai=str(announce_ai).lower(),
            auto_memory=str(auto_memory).lower(),
            extra=extra,
        ),
        encoding="utf-8",
    )
    return cfg


class _FakeVideoStream:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeVideoStreamOpener:
    def __init__(self, stream: _FakeVideoStream) -> None:
        self._stream = stream
        self.calls = []

    def open(self, *, channel: str, quality: str):
        self.calls.append({"channel": channel, "quality": quality})
        return self._stream


class _FakeVideoFrameDecoder:
    def __init__(self, frames: list[DecodedVideoFrame]) -> None:
        self._frames = list(frames)

    def decode(self, stream):
        yield from self._frames


class _CollectingVideoPerceiver:
    def __init__(self) -> None:
        self.payloads = []

    def perceive_event(self, event: RawEvent) -> None:
        self.payloads.append(event.payload)


class _FakeCaptioner:
    def __init__(self) -> None:
        self.frames: list[VideoFrame] = []

    def caption(self, frame: VideoFrame) -> str:
        self.frames.append(frame)
        return "A game menu is visible on the stream."


class _FailingCaptioner:
    def caption(self, _frame: VideoFrame) -> str:
        raise QwenVlCaptionError("vlm exploded")


# --- 1. build_agent compone un agente eseguibile ---------------------------


def test_build_agent_wires_all_components(tmp_path):
    cfg = Config.load(_write_workspace(tmp_path))
    agent = build_agent(cfg, transport=_fake_transport)

    assert isinstance(agent, Agent)
    # Reactor presente e cablato (è l'orchestratore del loop senso-reazione).
    assert isinstance(agent.reactor, Reactor)
    # Lo store esiste su disco (cartella di lavoro derivata dal config).
    assert agent.store is not None
    # Senser, summarizer, human, prompt builder, llm tutti cablati.
    assert agent.senser is not None
    assert agent.summarizer is not None
    assert agent.human is not None
    assert agent.prompt_builder is not None
    assert agent.llm is not None


def test_build_agent_uses_run_session_store_path_when_no_store_path_is_supplied(
    tmp_path,
):
    cfg = Config.load(_write_workspace(tmp_path))
    session = create_run_session(root=tmp_path / ".local" / "minnarone" / "runs")

    agent = build_agent(cfg, transport=_fake_transport, run_session=session)

    assert agent.run_session == session
    assert agent.store.path == session.perception_log_path


def test_build_agent_respects_explicit_store_path_with_run_session(tmp_path):
    cfg = Config.load(_write_workspace(tmp_path))
    session = create_run_session(root=tmp_path / ".local" / "minnarone" / "runs")
    explicit_store = tmp_path / "custom" / "perceptions.jsonl"

    agent = build_agent(
        cfg,
        transport=_fake_transport,
        run_session=session,
        store_path=explicit_store,
    )

    assert agent.run_session == session
    assert agent.store.path == explicit_store


def test_build_agent_records_prompt_observations_in_run_session(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from minnarone.fakes import FakeOutputRouter
    from minnarone.openrouter import HttpResponse

    prompts: list[str] = []

    def transport(*, url, headers, body, timeout):
        del url, headers, timeout
        prompt = _prompt_from_body(body)
        prompts.append(prompt)
        payload = {
            "choices": [{"message": {"content": "ciao"}}],
            "model": "fake-observed-model",
            "usage": {
                "prompt_tokens": 21,
                "completion_tokens": 3,
                "total_tokens": 24,
                "cost": 0.0007,
                "prompt_tokens_details": {
                    "cached_tokens": 10,
                    "cache_write_tokens": 0,
                },
            },
        }
        return HttpResponse(status=200, body=json.dumps(payload).encode("utf-8"))

    cfg = Config.load(_write_workspace(tmp_path, mode="public"))
    session = create_run_session(root=tmp_path / "runs")
    agent = build_agent(
        cfg,
        transport=transport,
        run_session=session,
        router=FakeOutputRouter(),
    )
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="ehi minnarone, ci sei?",
            speaker="utente1",
        )
    )

    asyncio.run(agent.reactor.run_once())

    state = agent.observability_snapshot()
    assert prompts
    assert state.latest_prompt is not None
    assert state.latest_prompt.prompt == prompts[-1]
    assert state.latest_prompt.model == "fake-observed-model"
    assert state.latest_prompt.context == "reactor:mention"
    assert state.latest_prompt.token_metadata == {
        "prompt_tokens": 21,
        "completion_tokens": 3,
        "total_tokens": 24,
    }
    assert state.latest_prompt.cache_metadata == {
        "cached_tokens": 10,
        "cache_write_tokens": 0,
    }
    assert state.latest_prompt.cost == 0.0007

    [path] = list((session.debug_dir / "prompts").glob("prompt-*.json"))
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["prompt"] == prompts[-1]
    assert session.run_dir in path.parents


def test_build_agent_records_replayable_trigger_and_output_events(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from minnarone.fakes import FakeOutputRouter
    from minnarone.replay import load_replay_state

    cfg = Config.load(_write_workspace(tmp_path, mode="public"))
    session = create_run_session(root=tmp_path / "runs")
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        run_session=session,
        router=FakeOutputRouter(),
    )
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="ehi minnarone, replayami",
            speaker="utente1",
        )
    )

    asyncio.run(agent.reactor.run_once())

    event_log = session.debug_dir / "events.jsonl"
    assert event_log.is_file()
    replay = load_replay_state(session.run_dir)
    panels = {panel.title: panel.text for panel in replay.render_panels()}
    assert "mention <- utente1" in panels["EVENTI"]
    assert panels["MINNARONE"] == "ciao"
    assert "replayed chat=1 audio=0 video=0 events=1 minnarone=1" in (
        replay.render_status_bar()
    )


def test_build_agent_passes_announce_ai_into_prompt(tmp_path):
    cfg = Config.load(_write_workspace(tmp_path, announce_ai=True))
    agent = build_agent(cfg, transport=_fake_transport)
    # announce_ai True deve fluire nella stance del prompt: la regola di
    # disclosure consente di dichiararsi AI (byte-invariante per config fissa).
    prefix = agent.prompt_builder.stable_prefix()
    assert "puoi dichiarare apertamente di" in prefix


def test_observability_snapshot_includes_run_channel_and_uptime(tmp_path):
    from minnarone.fakes import FakeOutputRouter

    cfg = Config.load(_write_workspace(tmp_path, mode="public"))
    session = create_run_session(root=tmp_path / "runs", channel="minnarone")
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        run_session=session,
        router=FakeOutputRouter(),
    )

    state = agent.observability_snapshot()

    assert state.channel == "minnarone"
    assert state.started_at == session.started_at
    status = state.render_status_bar()
    assert "channel=minnarone" in status
    assert "uptime=" in status


def test_build_agent_default_hides_ai_disclosure(tmp_path):
    cfg = Config.load(_write_workspace(tmp_path, announce_ai=False))
    agent = build_agent(cfg, transport=_fake_transport)
    prefix = agent.prompt_builder.stable_prefix()
    assert "Non rivelare MAI di essere un'AI" in prefix


def test_build_agent_loads_soul_and_facts_from_config(tmp_path):
    cfg = Config.load(_write_workspace(tmp_path))
    agent = build_agent(cfg, transport=_fake_transport)
    prefix = agent.prompt_builder.stable_prefix()
    assert "Sono Minnarone" in prefix
    assert "Canale Twitch di test." in prefix


def test_build_agent_constructs_twitch_chat_adapter_from_config(tmp_path, monkeypatch):
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  chat: true
                  audio: false
                  video: false
                """
            ),
        )
    )

    agent = build_agent(cfg, transport=_fake_transport)

    assert agent.adapter is not None
    assert isinstance(agent.adapter, TwitchStreamAdapter)
    assert agent.adapter.channels() == {"chat"}
    assert set(agent.perceivers) == {"chat"}


def test_twitch_chat_runtime_requires_clear_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("TWITCH_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  chat: true
                  audio: false
                  video: false
                """
            ),
        )
    )

    with pytest.raises(ConfigError, match="TWITCH_BOT_USERNAME.*TWITCH_OAUTH_TOKEN"):
        build_agent(cfg, transport=_fake_transport)


def test_twitch_chat_runtime_reacts_to_console_without_sending_chat(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")

    class FakeIRCStream:
        def __init__(self):
            self.writes: list[str] = []
            self.closed = False
            self._incoming = [
                (
                    "@display-name=Viewer "
                    ":viewer!viewer@viewer.tmi.twitch.tv "
                    "PRIVMSG #minnarone :ehi minnarone ci sei?\r\n"
                ),
                "",
            ]

        async def readline(self):
            return self._incoming.pop(0)

        async def write(self, line):
            self.writes.append(line)

        async def close(self):
            self.closed = True

    stream = FakeIRCStream()

    async def connect():
        return stream

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  chat: true
                  audio: false
                  video: false
                """
            ),
            extra="summarizer_interval: 0.01\nsenser_interval: 0.01",
        )
    )
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        twitch_chat_connect=connect,
    )

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    tail = agent.store.tail(10)
    assert any(
        p.source is Source.CHAT
        and p.text == "ehi minnarone ci sei?"
        and p.speaker == "Viewer"
        for p in tail
    )
    assert "[PUBLIC] ciao" in capsys.readouterr().out
    assert stream.closed is True
    assert not any(line.startswith("PRIVMSG ") for line in stream.writes)


def test_twitch_runtime_rejects_audio_until_backends_are_cabled(tmp_path, monkeypatch):
    monkeypatch.delenv("TWITCH_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)

    audio_cfg = Config.load(
        _write_workspace(
            tmp_path / "audio",
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  chat: false
                  audio: true
                  video: false
                """
            ),
        )
    )
    with pytest.raises(ConfigError, match="twitch.audio"):
        build_agent(
            audio_cfg,
            transport=_fake_transport,
            asr_model_factory=lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("no local model")
            ),
        )


def test_twitch_audio_runtime_writes_clustered_speaker_speech_perception(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeSourceAdapter

    class PrefixDetector:
        def is_speech(self, frame: bytes, sample_rate: int) -> bool:
            return frame.startswith(b"S")

    class FakeWhisperModel:
        def transcribe(self, audio, **kwargs):
            return iter([type("Segment", (), {"text": " ciao stream "})()]), object()

    constructed = {}

    def model_factory(name: str, *, device: str, compute_type: str):
        constructed.update(
            {"name": name, "device": device, "compute_type": compute_type}
        )
        return FakeWhisperModel()

    speaker_model_path = tmp_path / "speaker.onnx"
    speaker_model_path.write_bytes(b"fake")
    speaker_constructed = {}

    class FakeSpeakerEmbeddingBackend:
        def __init__(self):
            self.calls = []

        def embed(self, segment):
            self.calls.append(segment)
            return (1.0, 0.0)

    speaker_backend = FakeSpeakerEmbeddingBackend()

    def speaker_embedding_factory(config):
        speaker_constructed.update(
            {
                "model_path": config.model_path,
                "provider": config.provider,
                "num_threads": config.num_threads,
                "dimension": config.dimension,
            }
        )
        return speaker_backend

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  chat: false
                  audio: true
                  video: false
                """
            ),
            extra=textwrap.dedent(
                f"""
                vad:
                  padding_ms: 30
                asr:
                  device: cpu
                  compute_type: int8
                  language: it
                speaker_embedding:
                  model_path: {speaker_model_path}
                  provider: cpu
                  num_threads: 2
                  dimension: 2
                speaker_clustering:
                  threshold: 0.8
                  warmup_seconds: 0
                  min_update_seconds: 0
                """
            ),
        )
    )
    frame_bytes = cfg.vad.frame_bytes
    adapter = FakeSourceAdapter(
        [
            RawEvent(
                channel="audio",
                payload=AudioChunk(
                    samples=(b"S" * frame_bytes) + (b"_" * frame_bytes),
                    sample_rate=16_000,
                    source_label="twitch",
                    ts=10.0,
                ),
                ts=10.0,
            )
        ],
        channels={"audio"},
    )

    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        adapter=adapter,
        vad_detector=PrefixDetector(),
        asr_model_factory=model_factory,
        speaker_embedding_factory=speaker_embedding_factory,
    )

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    tail = agent.store.tail(10)
    assert len(tail) == 1
    perception = tail[0]
    assert perception.source is Source.AUDIO
    assert perception.type == "speech"
    assert perception.text == "ciao stream"
    assert perception.speaker == "streamer"
    assert perception.ts == 10.0
    assert constructed == {
        "name": "large-v3-turbo",
        "device": "cpu",
        "compute_type": "int8",
    }
    assert speaker_constructed == {
        "model_path": speaker_model_path,
        "provider": "cpu",
        "num_threads": 2,
        "dimension": 2,
    }
    assert len(speaker_backend.calls) == 1
    diagnostics = agent.observability_snapshot()
    assert diagnostics.audio_transcriptions[0].speaker == "streamer"
    assert diagnostics.speaker.total_utterances == 1
    assert diagnostics.speaker.clustered_utterances == 1


def test_twitch_audio_runtime_builds_real_adapter_without_injected_adapter(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("TWITCH_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)

    class FakeWhisperModel:
        def transcribe(self, audio, **kwargs):
            return iter([]), object()

    class FakeSpeakerEmbeddingBackend:
        def embed(self, segment):
            return (1.0, 0.0)

    class SilentDetector:
        def is_speech(self, frame: bytes, sample_rate: int) -> bool:
            return False

    speaker_model_path = tmp_path / "speaker.onnx"
    speaker_model_path.write_bytes(b"fake")
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  chat: false
                  audio: true
                  video: false
                """
            ),
            extra=textwrap.dedent(
                f"""
                speaker_embedding:
                  model_path: {speaker_model_path}
                  dimension: 2
                speaker_clustering:
                  warmup_seconds: 0
                  min_update_seconds: 0
                """
            ),
        )
    )

    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        vad_detector=SilentDetector(),
        asr_model_factory=lambda *args, **kwargs: FakeWhisperModel(),
        speaker_embedding_factory=lambda config: FakeSpeakerEmbeddingBackend(),
    )

    assert isinstance(agent.adapter, TwitchStreamAdapter)
    assert agent.adapter.channels() == {"audio"}
    assert set(agent.perceivers) == {"chat", "audio"}
    assert agent.perception_queue is not None
    assert set(agent.perception_queue_stats().channels) == {"audio"}


def test_twitch_video_runtime_builds_pyav_adapter_and_bounded_queue(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    stream = _FakeVideoStream()
    opener = _FakeVideoStreamOpener(stream)
    decoder = _FakeVideoFrameDecoder(
        [DecodedVideoFrame(pixels="video-frame", time_seconds=0.0)]
    )
    video_perceiver = _CollectingVideoPerceiver()
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  quality: 720p
                  chat: false
                  audio: false
                  video: true
                  video_fps: 10.0
                """
            ),
            extra="perception_queue_size: 1\n",
        )
    )

    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        video_perceiver=video_perceiver,  # type: ignore[arg-type]
        video_stream_opener=opener,
        video_frame_decoder=decoder,
    )

    assert isinstance(agent.adapter, TwitchStreamAdapter)
    assert agent.adapter.channels() == {"video"}
    assert agent.perception_queue is not None
    assert set(agent.perception_queue_stats().channels) == {"video"}

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    assert opener.calls == [{"channel": "minnarone", "quality": "720p"}]
    assert stream.closed is True
    assert [payload.pixels for payload in video_perceiver.payloads] == ["video-frame"]
    assert agent.perception_queue_stats().channels["video"].processed == 1


def test_twitch_video_runtime_builds_default_qwen_captioner_when_enabled(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    stream = _FakeVideoStream()
    opener = _FakeVideoStreamOpener(stream)
    decoder = _FakeVideoFrameDecoder(
        [DecodedVideoFrame(pixels="video-frame", time_seconds=0.0)]
    )
    captioner = _FakeCaptioner()
    constructed = []
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  quality: best
                  chat: false
                  audio: false
                  video: true
                  video_fps: 1.0
                """
            ),
            extra=textwrap.dedent(
                """
                vlm:
                  model: /models/qwen2-vl
                  device: cpu
                """
            ),
        )
    )

    def captioner_factory(config):
        constructed.append(config)
        return captioner

    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        qwen_captioner_factory=captioner_factory,
        video_stream_opener=opener,
        video_frame_decoder=decoder,
    )

    assert isinstance(agent.adapter, TwitchStreamAdapter)
    assert agent.adapter.channels() == {"video"}
    assert agent.perception_queue is not None
    assert set(agent.perception_queue_stats().channels) == {"video"}

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    tail = agent.store.tail(10)
    assert len(tail) == 1
    assert tail[0].source is Source.VIDEO
    assert tail[0].type == "caption"
    assert tail[0].text == "A game menu is visible on the stream."
    assert tail[0].ts > 0
    assert [frame.pixels for frame in captioner.frames] == ["video-frame"]
    assert constructed == [cfg.vlm]
    assert agent.perception_queue_stats().channels["video"].processed == 1
    diagnostics = agent.observability_snapshot()
    assert diagnostics.video.frames_seen == 1
    assert diagnostics.video.captioned == 1
    assert diagnostics.queue["video"].processed == 1
    assert diagnostics.adapter["video"].produced == 1
    assert diagnostics.video_captions[0].text == "A game menu is visible on the stream."


def test_twitch_video_caption_failures_are_recorded_without_killing_chat(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeSourceAdapter

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  chat: true
                  audio: false
                  video: true
                """
            ),
            extra=textwrap.dedent(
                """
                vlm:
                  model: /models/qwen2-vl
                """
            ),
        )
    )
    adapter = FakeSourceAdapter(
        [
            RawEvent(
                channel="chat",
                payload={"speaker": "Viewer", "text": "ciao chat"},
                ts=1.0,
            ),
            RawEvent(
                channel="video",
                payload=VideoFrame(pixels="frame", source_label="stream", ts=2.0),
                ts=2.0,
            ),
        ],
        channels={"chat", "video"},
    )

    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        adapter=adapter,
        qwen_captioner_factory=lambda _config: _FailingCaptioner(),
    )

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    tail = agent.store.tail(10)
    assert [(p.source, p.type, p.text) for p in tail] == [
        (Source.CHAT, "msg", "ciao chat")
    ]
    stats = agent.perception_queue_stats().channels["video"]
    assert stats.failed == 1
    assert stats.processed == 0
    assert stats.last_error == "vlm exploded"


def test_twitch_video_caption_setup_failure_is_recorded_without_killing_chat(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeSourceAdapter

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  chat: true
                  audio: false
                  video: true
                """
            ),
            extra=textwrap.dedent(
                """
                vlm:
                  model: /models/qwen2-vl
                """
            ),
        )
    )
    adapter = FakeSourceAdapter(
        [
            RawEvent(
                channel="chat",
                payload={"speaker": "Viewer", "text": "ciao chat"},
                ts=1.0,
            ),
            RawEvent(
                channel="video",
                payload=VideoFrame(pixels="frame", source_label="stream", ts=2.0),
                ts=2.0,
            ),
        ],
        channels={"chat", "video"},
    )

    def broken_factory(_config):
        raise QwenVlCaptionError("vlm setup exploded")

    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        adapter=adapter,
        qwen_captioner_factory=broken_factory,
    )

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    tail = agent.store.tail(10)
    assert [(p.source, p.type, p.text) for p in tail] == [
        (Source.CHAT, "msg", "ciao chat")
    ]
    stats = agent.perception_queue_stats().channels["video"]
    assert stats.failed == 1
    assert stats.last_error == "vlm setup exploded"


def test_twitch_chat_runtime_fails_clearly_on_auth_notice(tmp_path, monkeypatch):
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:bad")

    class NoticeIRCStream:
        def __init__(self):
            self.closed = False
            self._incoming = [
                ":tmi.twitch.tv NOTICE * :Login authentication failed\r\n",
                "",
            ]

        async def readline(self):
            return self._incoming.pop(0)

        async def write(self, _line):
            return None

        async def close(self):
            self.closed = True

    stream = NoticeIRCStream()

    async def connect():
        return stream

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  chat: true
                  audio: false
                  video: false
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        twitch_chat_connect=connect,
    )

    with pytest.raises(TwitchStreamRuntimeError, match="Login authentication failed"):
        asyncio.run(agent.run())
    assert stream.closed is True


# --- 2. config invalido -> errore chiaro -----------------------------------


def test_build_from_missing_config_raises_config_error(tmp_path):
    with pytest.raises(ConfigError):
        Config.load(tmp_path / "nope.yaml")


# --- 3. mode: public -> ConsoleOutputRouter --------------------------------


def test_public_mode_uses_console_router(tmp_path):
    cfg = Config.load(_write_workspace(tmp_path, mode="public"))
    agent = build_agent(cfg, transport=_fake_transport)
    assert isinstance(agent.router, ConsoleOutputRouter)
    assert agent.mode is OutputMode.PUBLIC


# --- 4. mode: private -> accettato, ma output segnala not-implemented -------


def test_private_mode_builds_without_crashing(tmp_path):
    cfg = Config.load(_write_workspace(tmp_path, mode="private"))
    # Costruzione NON deve crashare: la modalità privata è accettata.
    agent = build_agent(cfg, transport=_fake_transport)
    assert agent.mode is OutputMode.PRIVATE
    assert isinstance(agent.router, PrivateNotImplementedRouter)


def test_commentator_mode_routes_private_output_to_console_and_changes_prompt(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("TWITCH_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeOutputRouter, FakeSourceAdapter
    from minnarone.openrouter import HttpResponse

    prompts = []

    def capture_transport(*, url, headers, body, timeout):
        del url, headers, timeout
        payload = json.loads(body.decode("utf-8"))
        prompts.append(payload["messages"][0]["content"])
        return HttpResponse(
            status=200,
            body=b'{"choices":[{"message":{"content":"Commento privato per l\'operatore."}}]}',
        )

    router = FakeOutputRouter()
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  chat: true
                  audio: false
                  video: false
                """
            ),
            extra=textwrap.dedent(
                """
                idle_interval: 999
                commentator:
                  enabled: true
                  language: it
                  idle_interval: 0.01
                """
            ),
        )
    )
    adapter = FakeSourceAdapter([], channels=set())
    agent = build_agent(
        cfg,
        transport=capture_transport,
        store_path=tmp_path / "p.jsonl",
        adapter=adapter,
        router=router,
    )
    console_agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p-console.jsonl",
        adapter=FakeSourceAdapter([], channels=set()),
    )
    assert isinstance(console_agent.router, ConsoleOutputRouter)

    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.AUDIO,
            type="speech",
            text="minnarone, sta entrando nel boss finale",
            speaker="streamer",
        )
    )

    asyncio.run(agent.reactor.run_once())

    assert router.sent == [("Commento privato per l'operatore.", OutputMode.PRIVATE)]
    assert "commentatore locale" in prompts[0]
    assert "italiano" in prompts[0].lower()
    assert "NON inviare messaggi pubblici Twitch" in prompts[0]
    assert agent.senser.idle_interval == 0.01


def test_tui_commentator_output_goes_to_dashboard_not_console(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.delenv("TWITCH_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeSourceAdapter
    from minnarone.output_sink import MinnaroneOutputStream

    def transport(*, url, headers, body, timeout):
        del url, headers, body, timeout
        from minnarone.openrouter import HttpResponse

        return HttpResponse(
            status=200,
            body=b'{"choices":[{"message":{"content":"Commento privato."}}]}',
        )

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  chat: true
                  audio: false
                  video: false
                """
            ),
            extra=textwrap.dedent(
                """
                idle_interval: 999
                commentator:
                  enabled: true
                  language: it
                  idle_interval: 0.01
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=transport,
        store_path=tmp_path / "p.jsonl",
        adapter=FakeSourceAdapter([], channels=set()),
        minnarone_output=MinnaroneOutputStream(),
    )
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.AUDIO,
            type="speech",
            text="minnarone, commenta questa giocata",
            speaker="streamer",
        )
    )

    asyncio.run(agent.reactor.run_once())

    captured = capsys.readouterr()
    assert "[PRIVATE]" not in captured.out
    assert "Commento privato." not in captured.out
    assert agent.observability_snapshot().messages == ["Commento privato."]


def test_router_override_keeps_minnarone_output_stream_inactive(tmp_path):
    from minnarone.fakes import FakeOutputRouter
    from minnarone.output_sink import MinnaroneOutputStream

    stream = MinnaroneOutputStream()
    router = FakeOutputRouter()
    cfg = Config.load(_write_workspace(tmp_path, mode="public"))
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        router=router,
        minnarone_output=stream,
    )

    asyncio.run(agent.reactor._route_and_note("ciao"))

    assert agent.minnarone_output is None
    assert stream.recent_messages() == []
    assert agent.observability_snapshot().messages == ["ciao"]


def test_private_router_signals_not_implemented_on_route(tmp_path):
    import asyncio

    cfg = Config.load(_write_workspace(tmp_path, mode="private"))
    agent = build_agent(cfg, transport=_fake_transport)
    # Usare il percorso privato segnala chiaramente "non implementato in MVP".
    with pytest.raises(PrivateModeNotImplemented):
        asyncio.run(agent.router.route("ciao", OutputMode.PRIVATE))


# --- 5. punti v2 presenti ma inerti ----------------------------------------


def test_v2_points_present_but_inert(tmp_path):
    # Inertness REALE: togglare auto_memory True vs False non cambia ALCUN
    # comportamento osservabile dell'agente assemblato (è un punto v2 non
    # cablato). Si confrontano due agenti identici tranne `auto_memory`.
    cfg_on = Config.load(_write_workspace(tmp_path / "on", auto_memory=True))
    cfg_off = Config.load(_write_workspace(tmp_path / "off", auto_memory=False))
    assert cfg_on.auto_memory is True
    assert cfg_off.auto_memory is False
    assert cfg_on.retention.perceptions_days == 7

    agent_on = build_agent(cfg_on, transport=_fake_transport)
    agent_off = build_agent(cfg_off, transport=_fake_transport)

    # Prompt stabile (soul/facts/stance) byte-identico: auto_memory non incide.
    assert agent_on.prompt_builder.stable_prefix() == (
        agent_off.prompt_builder.stable_prefix()
    )
    # Memoria caricata identica: nessun auto-aggiornamento.
    assert agent_on.memory.load().soul == agent_off.memory.load().soul
    assert agent_on.memory.load().facts == agent_off.memory.load().facts
    # Stessi canali di percezione cablati: nessun ramo dipende da auto_memory.
    assert set(agent_on.perceivers) == set(agent_off.perceivers)


# --- agent_name additivo ----------------------------------------------------


# --- smoke end-to-end dello scenario streamer pubblico ---------------------


def test_streamer_scenario_smoke_end_to_end(tmp_path, monkeypatch):
    """Una menzione in chat → l'agente reagisce sul canale pubblico.

    Esercita il motore senso-reazione assemblato da config, offline: store +
    Senser (menzione) + PromptBuilder + LLM (fake transport) + HumanLikeness +
    OutputRouter. Il loop di percezione è simulato scrivendo direttamente nello
    store (il passo manuale live è la cattura device). Si inietta un router che
    cattura l'output (l'instradamento per modalità è coperto dai test sopra).
    """
    import asyncio

    from minnarone.fakes import FakeOutputRouter

    # Il provider reale risolve l'API key prima della chiamata: nel test la
    # forniamo via env così il fake transport (nessuna rete) viene usato.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    capture = FakeOutputRouter()
    store_path = tmp_path / "perceptions.jsonl"
    cfg = Config.load(_write_workspace(tmp_path, mode="public"))
    agent = build_agent(
        cfg, transport=_fake_transport, store_path=store_path, router=capture
    )
    assert agent.mode is OutputMode.PUBLIC

    # Simula la percezione: un utente nomina l'agente in chat.
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="ehi minnarone come va?",
            speaker="utente1",
        )
    )

    asyncio.run(agent.reactor.run_once())

    # L'agente ha instradato esattamente la risposta del (fake) LLM in PUBLIC.
    assert capture.sent == [("ciao", OutputMode.PUBLIC)]


def test_agent_name_defaults_when_omitted(tmp_path):
    # Config minimale senza agent_name: deve avere un default sensato e non
    # rompere l'assemblaggio.
    soul = tmp_path / "soul.md"
    soul.write_text("io", encoding="utf-8")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text(
        textwrap.dedent(
            f"""
            mode: public
            soul_path: {soul}
            facts_dir: {facts_dir}
            adapter: os_capture
            llm_provider: grok
            """
        ),
        encoding="utf-8",
    )
    cfg = Config.load(cfg_path)
    assert cfg.agent_name  # default non vuoto
    agent = build_agent(cfg, transport=_fake_transport)
    assert agent is not None


# --- Fix 1: il loop del Summarizer parte nel percorso live ------------------


def _prompt_from_body(body: bytes) -> str:
    """Estrae il testo del prompt dal body JSON della richiesta (OpenAI shape)."""
    data = json.loads(body.decode("utf-8"))
    return data["messages"][-1]["content"]


def _recording_transport(prompts: list[str], *, summary: str = "RIASSUNTO-NOTO"):
    """Transport fake che registra i prompt e risponde in modo deterministico.

    Riconosce la chiamata del Summarizer dal suo header ("## EVENTI") e risponde
    con un riassunto noto; per ogni altra chiamata (reazione del Reactor) risponde
    "ciao" e registra il prompt in `prompts`, così il test può asserire che il
    riassunto è fluito nel prompt di reazione.
    """
    from minnarone.openrouter import HttpResponse

    def transport(*, url, headers, body, timeout):
        prompt = _prompt_from_body(body)
        if "## EVENTI" in prompt:
            content = summary
        else:
            prompts.append(prompt)
            content = "ciao"
        payload = json.dumps({"choices": [{"message": {"content": content}}]})
        return HttpResponse(status=200, body=payload.encode("utf-8"))

    return transport


def test_run_starts_summarizer_loop(tmp_path, monkeypatch):
    """`Agent.run()` avvia il loop del Summarizer concorrentemente al resto.

    Senza adapter è il loop di reazione a guidare la durata: lo si avvia come
    task, si attende che il Summarizer abbia agito (`summarize()` invocato — non
    resta inerte come prima del fix), poi si ferma il Reactor per chiudere pulito.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    calls = {"n": 0}

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="summarizer_interval: 0.01\nsenser_interval: 0.01",
        )
    )
    agent = build_agent(
        cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl"
    )

    # Una percezione nello store così `summarize()` fa effettivamente lavoro.
    agent.store.append(
        Perception(ts=1.0, source=Source.CHAT, type="msg", text="ciao a tutti")
    )

    orig = agent.summarizer.summarize

    async def counting_summarize():
        calls["n"] += 1
        return await orig()

    monkeypatch.setattr(agent.summarizer, "summarize", counting_summarize)

    async def drive():
        task = asyncio.create_task(agent.run())
        # Attendi (con timeout) che il loop del Summarizer abbia agito.
        for _ in range(500):
            if calls["n"] >= 1:
                break
            await asyncio.sleep(0.01)
        agent.reactor.stop()
        await asyncio.wait_for(task, timeout=5.0)

    asyncio.run(drive())
    assert calls["n"] >= 1


def test_run_summary_reaches_reaction_prompt(tmp_path, monkeypatch):
    """End-to-end: il riassunto prodotto dal loop raggiunge il prompt di reazione.

    Si inietta un adapter che emette una menzione in chat e un transport che
    risponde con un riassunto noto alla chiamata del Summarizer. Dopo aver
    girato l'agente, il prompt di reazione (registrato) contiene quel riassunto:
    prova che il loop del Summarizer gira e che `current_summary` fluisce nel
    Reactor attraverso il motore in esecuzione.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    prompts: list[str] = []

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="summarizer_interval: 0.01\nsenser_interval: 0.01",
        )
    )

    from minnarone.fakes import FakeSourceAdapter

    adapter = FakeSourceAdapter(
        [
            RawEvent(
                channel="chat",
                payload={"text": "ehi minnarone ci sei?", "speaker": "u1"},
                ts=1.0,
            )
        ]
    )
    agent = build_agent(
        cfg,
        transport=_recording_transport(prompts, summary="RIASSUNTO-NOTO"),
        store_path=tmp_path / "p.jsonl",
        adapter=adapter,
    )

    # Genera il riassunto PRIMA di avviare run(), così è già disponibile quando
    # il Reactor reagisce nel tick finale (deterministico, niente race sul loop).
    agent.store.append(
        Perception(ts=0.5, source=Source.CHAT, type="msg", text="contesto sessione")
    )
    asyncio.run(agent.summarizer.summarize())
    assert agent.summarizer.current_summary == "RIASSUNTO-NOTO"

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    assert prompts, "il Reactor non ha mai reagito alla menzione"
    assert any("RIASSUNTO-NOTO" in p for p in prompts)


# --- Fix 2: la pompa di percezione attraversa l'adapter (percorso live) -----


def test_dispatch_routes_chat_event_to_store(tmp_path):
    """Il dispatcher instrada un `RawEvent` di chat al `ChatPerceiver` → store."""
    cfg = Config.load(_write_workspace(tmp_path, mode="public"))
    agent = build_agent(
        cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl"
    )
    agent.dispatch(
        RawEvent(channel="chat", payload={"text": "ciao mondo", "speaker": "u1"}, ts=7.0)
    )
    tail = agent.store.tail(10)
    assert tail[-1].text == "ciao mondo"
    assert tail[-1].speaker == "u1"
    assert tail[-1].source is Source.CHAT


def test_dispatch_skips_unconfigured_channel(tmp_path):
    """Un canale senza perceiver (audio/video AFK) viene saltato, non crasha."""
    cfg = Config.load(_write_workspace(tmp_path, mode="public"))
    agent = build_agent(
        cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl"
    )
    assert "audio" not in agent.perceivers
    assert "video" not in agent.perceivers
    # Nessuna eccezione, nessuna percezione scritta.
    agent.dispatch(RawEvent(channel="audio", payload=object(), ts=1.0))
    assert agent.store.tail(10) == []


def test_run_pumps_chat_perception_end_to_end(tmp_path, monkeypatch):
    """Capstone e2e: adapter → perceiver → store → senser → reactor → output.

    Un `FakeSourceAdapter` emette una menzione in chat; si avvia l'Agent; la
    percezione atterra nello store E il Reactor reagisce (il router cattura il
    messaggio) — tutto concorrente nel motore in esecuzione.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeOutputRouter, FakeSourceAdapter

    capture = FakeOutputRouter()
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="summarizer_interval: 0.01\nsenser_interval: 0.01",
        )
    )
    adapter = FakeSourceAdapter(
        [
            RawEvent(
                channel="chat",
                payload={"text": "ehi minnarone come va?", "speaker": "u1"},
                ts=1.0,
            )
        ]
    )
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        router=capture,
        adapter=adapter,
    )

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    # La percezione è atterrata nello store (pompa adapter→perceiver→store).
    tail = agent.store.tail(10)
    assert any(p.text == "ehi minnarone come va?" for p in tail)
    # E il Reactor ha reagito instradando la risposta del (fake) LLM in PUBLIC.
    assert ("ciao", OutputMode.PUBLIC) in capture.sent


def test_run_queues_slow_media_without_dropping_chat(tmp_path, monkeypatch):
    """Slow model-backed media work is bounded while chat stays direct."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class YieldingAdapter(SourceAdapter):
        def __init__(self, events: list[RawEvent]) -> None:
            self._events = events
            self.stopped = False

        def channels(self) -> set[str]:
            return {event.channel for event in self._events}

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            self.stopped = True

        async def events(self):
            for event in self._events:
                yield event
                await asyncio.sleep(0)

    class SlowAudioProcessor:
        def __init__(self) -> None:
            self.started = Event()
            self.release = Event()
            self.seen: list[str] = []

        async def perceive_event(self, event: RawEvent) -> None:
            self.seen.append(str(event.payload))
            self.started.set()
            while not self.release.is_set():
                await asyncio.sleep(0.001)

    audio = SlowAudioProcessor()
    adapter = YieldingAdapter(
        [
            RawEvent(channel="audio", payload="a1", ts=1.0),
            RawEvent(channel="audio", payload="a2", ts=2.0),
            RawEvent(channel="audio", payload="a3", ts=3.0),
            RawEvent(
                channel="chat",
                payload={"text": "ciao chat", "speaker": "viewer"},
                ts=4.0,
            ),
        ]
    )
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra=(
                "summarizer_interval: 0.01\n"
                "senser_interval: 0.01\n"
                "perception_queue_size: 1\n"
                "perception_shutdown_timeout: 1.0\n"
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        adapter=adapter,
        audio_perceiver=audio,
    )

    async def drive() -> None:
        task = asyncio.create_task(agent.run())
        assert await asyncio.to_thread(audio.started.wait, timeout=1.0)
        for _ in range(200):
            if any(p.text == "ciao chat" for p in agent.store.tail(10)):
                break
            await asyncio.sleep(0.01)

        assert any(p.text == "ciao chat" for p in agent.store.tail(10))
        stats = agent.perception_queue_stats().channels["audio"]
        assert stats.queued == 2
        assert stats.dropped == 1
        assert stats.processed == 0

        audio.release.set()
        await asyncio.wait_for(task, timeout=5.0)

    asyncio.run(drive())

    stats = agent.perception_queue_stats().channels["audio"]
    assert audio.seen == ["a1", "a2"]
    assert stats.processed == 2
    assert stats.dropped == 1
    assert adapter.stopped is True


def test_run_without_adapter_stops_cleanly_on_reactor_stop(tmp_path, monkeypatch):
    """Senza adapter `run()` gira il loop di reazione finché `reactor.stop()`.

    Comportamento live identico a prima del capstone (la cattura device è il
    passo manuale): nessuna sorgente, il loop di reazione guida la durata e si
    ferma pulito su `stop()`, senza task orfani (un timeout = fallimento).
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="summarizer_interval: 0.01\nsenser_interval: 0.01",
        )
    )
    agent = build_agent(
        cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl"
    )
    assert agent.adapter is None

    async def drive():
        task = asyncio.create_task(agent.run())
        await asyncio.sleep(0.05)  # lascia girare qualche tick
        assert not task.done()  # senza stop, il loop NON termina da solo
        agent.reactor.stop()
        await asyncio.wait_for(task, timeout=5.0)

    asyncio.run(drive())


def test_run_surfaces_adapter_cleanup_failure_on_cancellation(tmp_path, monkeypatch):
    """TUI cancellation must not hide production cleanup failures."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class FailingStopAdapter(SourceAdapter):
        def __init__(self) -> None:
            self.started = Event()

        def channels(self) -> set[str]:
            return {"chat"}

        async def start(self) -> None:
            self.started.set()

        async def stop(self) -> None:
            raise RuntimeError("adapter stop exploded")

        async def events(self):
            while True:
                await asyncio.sleep(0.01)
                if self.started.is_set() and not self.started.is_set():
                    yield RawEvent(channel="chat", payload={})

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="summarizer_interval: 0.01\nsenser_interval: 0.01",
        )
    )
    adapter = FailingStopAdapter()
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        adapter=adapter,
    )

    async def drive():
        task = asyncio.create_task(agent.run())
        assert await asyncio.to_thread(adapter.started.wait, timeout=1.0)
        task.cancel()
        with pytest.raises(RuntimeError, match="adapter stop exploded"):
            await asyncio.wait_for(task, timeout=5.0)

    asyncio.run(drive())


def test_run_surfaces_cancelled_child_cleanup_failure(tmp_path, monkeypatch):
    """Failures from gathered child tasks must not be swallowed."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class HangingAdapter(SourceAdapter):
        def __init__(self) -> None:
            self.started = Event()

        def channels(self) -> set[str]:
            return {"chat"}

        async def start(self) -> None:
            self.started.set()

        async def stop(self) -> None:
            return None

        async def events(self):
            while True:
                await asyncio.sleep(0.01)
                if self.started.is_set() and not self.started.is_set():
                    yield RawEvent(channel="chat", payload={})

    class FailingSummarizer:
        async def run(self, *, interval: float) -> None:
            del interval
            try:
                while True:
                    await asyncio.sleep(0.01)
            except asyncio.CancelledError as exc:
                raise RuntimeError("summarizer cleanup exploded") from exc

        def stop(self) -> None:
            return None

        @property
        def current_summary(self) -> str:
            return ""

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="summarizer_interval: 0.01\nsenser_interval: 0.01",
        )
    )
    adapter = HangingAdapter()
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        adapter=adapter,
    )
    agent = replace(agent, summarizer=FailingSummarizer())

    async def drive():
        task = asyncio.create_task(agent.run())
        assert await asyncio.to_thread(adapter.started.wait, timeout=1.0)
        task.cancel()
        with pytest.raises(RuntimeError, match="summarizer cleanup exploded"):
            await asyncio.wait_for(task, timeout=5.0)

    asyncio.run(drive())
