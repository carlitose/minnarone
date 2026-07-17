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
from minnarone.config import CommentatorStyle, Config, ConfigError, TwitchSendMode
from minnarone.console import ConsoleOutputRouter
from minnarone.os_capture import OsCaptureAdapter
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

    # La sezione os_capture è obbligatoria quando adapter == os_capture (che è
    # il default innocuo dei test): senza di essa la Config verrebbe rifiutata.
    # Default video-only: il perceiver video è LAZY (il captioner VLM si
    # costruisce al primo frame) e la sorgente device è lazy, quindi `build_agent`
    # cabla l'adapter senza aprire hardware né richiedere il backend ASR (che il
    # canale audio esigerebbe eagerly, come su Twitch). I test audio abilitano il
    # canale esplicitamente e iniettano le sorgenti/perceiver.
    os_capture_block = (
        "os_capture:\n  audio: false\n  video: true\n"
        if adapter == "os_capture"
        else ""
    )

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
        {os_capture_block}
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
            os_capture_block=os_capture_block,
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
    cfg = Config.load(
        _write_workspace(tmp_path, extra="commentator:\n  profiles:\n    operator: {}")
    )
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

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="commentator:\n  profiles:\n    operator: {}",
        )
    )
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

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="commentator:\n  profiles:\n    operator: {}",
        )
    )
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


def test_twitch_chat_runtime_rejects_empty_token_after_oauth_prefix(
    tmp_path, monkeypatch
):
    # Footgun: TWITCH_OAUTH_TOKEN=oauth: (prefisso senza valore). Deve fallire
    # al build, non solo alla connessione IRC a runtime.
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:")
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

    with pytest.raises(ConfigError, match="TWITCH_OAUTH_TOKEN"):
        build_agent(cfg, transport=_fake_transport)


def _live_send_twitch_config(tmp_path):
    return Config.load(
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
                  send:
                    mode: live
                    allowed_channels: ["minnarone"]
                """
            ),
        )
    )


def test_twitch_send_live_build_requires_write_token(tmp_path, monkeypatch):
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    monkeypatch.delenv("TWITCH_SEND_OAUTH_TOKEN", raising=False)
    cfg = _live_send_twitch_config(tmp_path)

    with pytest.raises(ConfigError, match="TWITCH_SEND_OAUTH_TOKEN") as excinfo:
        build_agent(cfg, transport=_fake_transport)
    # Il messaggio nomina la variabile, mai un valore di token.
    assert "oauth:" not in str(excinfo.value)


def test_twitch_send_live_build_rejects_whitespace_only_write_token(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    # Un token di soli spazi equivale a un token assente.
    monkeypatch.setenv("TWITCH_SEND_OAUTH_TOKEN", "   ")
    cfg = _live_send_twitch_config(tmp_path)

    with pytest.raises(ConfigError, match="TWITCH_SEND_OAUTH_TOKEN"):
        build_agent(cfg, transport=_fake_transport)


def test_twitch_send_live_build_succeeds_with_write_token(tmp_path, monkeypatch):
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    monkeypatch.setenv("TWITCH_SEND_OAUTH_TOKEN", "oauth:finto-token-scrittura")
    cfg = _live_send_twitch_config(tmp_path)

    agent = build_agent(cfg, transport=_fake_transport)

    assert agent.config.twitch.send.mode is TwitchSendMode.LIVE


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
                  language: it
                  profiles:
                    operator:
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


def test_original_chat_style_reaches_prompt_boundary_without_public_output(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("TWITCH_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)

    from minnarone.fakes import FakeSourceAdapter

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
                commentator:
                  profiles:
                    original_chat: {}
                """
            ),
        )
    )

    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        adapter=FakeSourceAdapter([], channels=set()),
    )

    assert agent.mode is OutputMode.PRIVATE
    assert isinstance(agent.router, ConsoleOutputRouter)
    assert agent.prompt_builder.commentator_style is CommentatorStyle.ORIGINAL_CHAT


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
                  language: it
                  profiles:
                    operator:
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


def test_tui_original_chat_output_goes_to_dashboard_as_re_msg(
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

        payload = {
            "choices": [
                {"message": {"content": "re : boss fight\nmsg : bella giocata"}}
            ]
        }
        return HttpResponse(status=200, body=json.dumps(payload).encode("utf-8"))

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
                commentator:
                  profiles:
                    original_chat: {}
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
            source=Source.CHAT,
            type="msg",
            text="minnarone guarda qui",
            speaker="alice",
        )
    )

    asyncio.run(agent.reactor.run_once())

    captured = capsys.readouterr()
    assert "re : boss fight" not in captured.out
    state = agent.observability_snapshot()
    assert state.messages == ["RE: boss fight\nMSG: bella giocata"]
    panel_text = {panel.title: panel.text for panel in state.render_panels()}
    assert "RE: boss fight" in panel_text["MINNARONE"]
    assert "MSG: bella giocata" in panel_text["MINNARONE"]


def test_tui_public_shadow_output_marked_in_panel_not_stdout(
    tmp_path, monkeypatch, capsys
):
    """Public+TUI: l'output shadow finisce nel pannello MINNARONE con marcatore
    [SHADOW], NON su stdout; send_policy è esposto.

    Regressione (run di accettazione issue 10): il percorso public+TUI non era
    cablato — l'output usciva su stdout (dietro la TUI) e il pannello mostrava
    testo non marcato. Questo test blocca il ritorno del difetto.
    """
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeSourceAdapter
    from minnarone.output_sink import MinnaroneOutputStream

    def transport(*, url, headers, body, timeout):
        del url, headers, body, timeout
        from minnarone.openrouter import HttpResponse

        payload = {
            "choices": [
                {"message": {"content": "re : boss fight\nmsg : bella giocata"}}
            ]
        }
        return HttpResponse(status=200, body=json.dumps(payload).encode("utf-8"))

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: minnarone
                  chat: true
                  audio: false
                  video: false
                  send:
                    mode: shadow
                """
            ),
            extra=textwrap.dedent(
                """
                commentator:
                  profiles:
                    original_chat: {}
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
    assert agent.send_policy is not None
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="minnarone guarda qui",
            speaker="alice",
        )
    )

    asyncio.run(agent.reactor.run_once())

    captured = capsys.readouterr()
    # Niente eco su stdout: sotto la TUI sfonderebbe lo schermo alternativo.
    assert "[SHADOW]" not in captured.out
    assert "bella giocata" not in captured.out

    state = agent.observability_snapshot()
    panel_text = {panel.title: panel.text for panel in state.render_panels()}
    assert "[SHADOW]" in panel_text["MINNARONE"]
    assert "bella giocata" in panel_text["MINNARONE"]
    assert state.send is not None
    assert state.send.mode == TwitchSendMode.SHADOW.value
    assert state.send.last_action == "shadow"


def test_tui_original_chat_end_conv_output_goes_to_dashboard_as_skipped_re_msg(
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

        payload = {
            "choices": [
                {"message": {"content": "RE: idle\nMSG: #end_conv"}}
            ]
        }
        return HttpResponse(status=200, body=json.dumps(payload).encode("utf-8"))

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
                commentator:
                  profiles:
                    original_chat: {}
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
            source=Source.CHAT,
            type="msg",
            text="minnarone guarda qui",
            speaker="alice",
        )
    )

    asyncio.run(agent.reactor.run_once())

    captured = capsys.readouterr()
    display = "RE: idle\nMSG: #end_conv\n(skip: not sent)"
    assert "[PRIVATE]" not in captured.out
    state = agent.observability_snapshot()
    assert state.messages == [display]
    assert "alice" not in state.windows
    panel_text = {panel.title: panel.text for panel in state.render_panels()}
    assert "RE: idle" in panel_text["MINNARONE"]
    assert "MSG: #end_conv" in panel_text["MINNARONE"]
    assert "(skip: not sent)" in panel_text["MINNARONE"]


def test_console_original_chat_output_prints_re_msg_locally(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.delenv("TWITCH_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeSourceAdapter

    def transport(*, url, headers, body, timeout):
        del url, headers, body, timeout
        from minnarone.openrouter import HttpResponse

        payload = {
            "choices": [
                {"message": {"content": "re : boss fight\nmsg : bella giocata"}}
            ]
        }
        return HttpResponse(status=200, body=json.dumps(payload).encode("utf-8"))

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
                commentator:
                  profiles:
                    original_chat: {}
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=transport,
        store_path=tmp_path / "p.jsonl",
        adapter=FakeSourceAdapter([], channels=set()),
    )
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="minnarone guarda qui",
            speaker="alice",
        )
    )

    asyncio.run(agent.reactor.run_once())

    captured = capsys.readouterr()
    assert "[PRIVATE] RE: boss fight" in captured.out
    assert "MSG: bella giocata" in captured.out


def test_console_original_chat_end_conv_output_prints_skipped_re_msg_locally(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.delenv("TWITCH_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeSourceAdapter

    def transport(*, url, headers, body, timeout):
        del url, headers, body, timeout
        from minnarone.openrouter import HttpResponse

        payload = {
            "choices": [
                {"message": {"content": "RE: idle\nMSG: #end_conv"}}
            ]
        }
        return HttpResponse(status=200, body=json.dumps(payload).encode("utf-8"))

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
                commentator:
                  profiles:
                    original_chat: {}
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=transport,
        store_path=tmp_path / "p.jsonl",
        adapter=FakeSourceAdapter([], channels=set()),
    )
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="minnarone guarda qui",
            speaker="alice",
        )
    )

    asyncio.run(agent.reactor.run_once())

    captured = capsys.readouterr()
    assert "[PRIVATE] RE: idle" in captured.out
    assert "MSG: #end_conv" in captured.out
    assert "(skip: not sent)" in captured.out


# --- meeting_synthesizer profile: Reactor con Senser periodico (issue 09) ---


def test_meeting_synthesizer_config_is_valid(tmp_path):
    """A config with a single meeting_synthesizer profile loads without error."""
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    meeting_synthesizer:
                      interval_s: 5
                """
            ),
        )
    )
    assert CommentatorStyle.MEETING_SYNTHESIZER in cfg.commentator.profiles
    assert cfg.commentator.profiles[CommentatorStyle.MEETING_SYNTHESIZER].interval_s == 5.0


def test_meeting_synthesizer_build_agent_wires_periodic_senser(tmp_path):
    """build_agent with MEETING_SYNTHESIZER profile creates a periodic Senser."""
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    meeting_synthesizer:
                      interval_s: 42
                """
            ),
        )
    )
    agent = build_agent(cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl")

    assert isinstance(agent, Agent)
    assert agent.senser.trigger_mode == "periodic"
    assert agent.senser._interval_s == 42.0
    assert agent.prompt_builder.commentator_style is CommentatorStyle.MEETING_SYNTHESIZER
    assert isinstance(agent.router, ConsoleOutputRouter)
    assert agent.mode is OutputMode.PRIVATE


def test_meeting_synthesizer_reactor_produces_private_output_at_interval(
    tmp_path, monkeypatch
):
    """End-to-end: the MEETING_SYNTHESIZER Reactor emits [PRIVATE] after interval_s.

    Uses a FakeLLMProvider so no network is needed. The Senser is periodic: it
    emits a synthesis_tick after interval_s seconds. The test advances a fake
    clock to exercise the timer.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeOutputRouter

    prompts: list[str] = []

    def capture_transport(*, url, headers, body, timeout):
        del url, headers, timeout
        from minnarone.openrouter import HttpResponse

        prompt = _prompt_from_body(body)
        # Summarizer calls have "Sei un sintetizzatore", reactor calls don't
        if "Sei un sintetizzatore" not in prompt:
            prompts.append(prompt)
        content = "Riepilogo della riunione: argomenti discussi e decisioni prese."
        payload = json.dumps({"choices": [{"message": {"content": content}}]})
        return HttpResponse(status=200, body=payload.encode("utf-8"))

    router = FakeOutputRouter()
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    meeting_synthesizer:
                      interval_s: 5
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=capture_transport,
        store_path=tmp_path / "p.jsonl",
        router=router,
    )

    # Add some perceptions so the prompt has context
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.AUDIO,
            type="speech",
            text="Discutiamo il budget del Q3",
            speaker="speaker_A",
        )
    )

    # Before the interval elapses: no trigger, no output
    asyncio.run(agent.reactor.run_once())
    assert router.sent == []

    # Advance the clock past the interval by manipulating _last_trigger_at
    agent.senser._last_trigger_at -= 6.0  # 6 > 5 = interval_s

    asyncio.run(agent.reactor.run_once())

    assert len(router.sent) == 1
    message, mode = router.sent[0]
    assert mode is OutputMode.PRIVATE
    assert "Riepilogo" in message

    # The prompt should contain MEETING_SYNTHESIZER-specific content
    assert prompts
    assert "sintesi riunione" in prompts[0]
    assert "synthesis_tick" in prompts[0]


def test_meeting_synthesizer_summary_reaches_prompt(tmp_path, monkeypatch):
    """The Summarizer's current_summary flows into the MEETING_SYNTHESIZER prompt."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    prompts: list[str] = []

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    meeting_synthesizer:
                      interval_s: 5
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=_recording_transport(prompts, summary="SUMMARY-FROM-SUMMARIZER"),
        store_path=tmp_path / "p.jsonl",
    )

    # Pre-seed a perception and a summary
    agent.store.append(
        Perception(
            ts=0.5,
            source=Source.CHAT,
            type="msg",
            text="contesto della sessione",
        )
    )
    asyncio.run(agent.summarizer.summarize())
    assert agent.summarizer.current_summary == "SUMMARY-FROM-SUMMARIZER"

    # Force the periodic senser to fire
    agent.senser._last_trigger_at -= 6.0

    asyncio.run(agent.reactor.run_once())

    assert prompts, "the Reactor never reacted to the synthesis_tick"
    assert any("SUMMARY-FROM-SUMMARIZER" in p for p in prompts)


def test_meeting_synthesizer_check_mode_passes(tmp_path):
    """A config with only meeting_synthesizer profile passes --check (build only)."""
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    meeting_synthesizer:
                      interval_s: 180
                """
            ),
        )
    )
    # --check just builds the agent; no crash = pass
    agent = build_agent(cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl")
    assert isinstance(agent, Agent)
    assert agent.senser.trigger_mode == "periodic"


# --- suggester profile: Reactor con Senser on_perception (issue 10) ---------


def test_suggester_config_is_valid(tmp_path):
    """A config with a single suggester profile loads without error."""
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    suggester: {}
                """
            ),
        )
    )
    assert CommentatorStyle.SUGGESTER in cfg.commentator.profiles


def test_suggester_build_agent_wires_on_perception_senser(tmp_path):
    """build_agent with SUGGESTER profile creates an on_perception Senser."""
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    suggester: {}
                """
            ),
        )
    )
    agent = build_agent(cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl")

    assert isinstance(agent, Agent)
    assert agent.senser.trigger_mode == "on_perception"
    assert agent.prompt_builder.commentator_style is CommentatorStyle.SUGGESTER
    assert isinstance(agent.router, ConsoleOutputRouter)
    assert agent.mode is OutputMode.PRIVATE


def test_suggester_speech_perception_produces_private_output(
    tmp_path, monkeypatch
):
    """End-to-end: a speech perception triggers a suggestion as [PRIVATE] output.

    Uses a FakeOutputRouter so no network is needed. The Senser is on_perception:
    it emits a suggestion_eval for each speech perception added to the store.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeOutputRouter

    prompts: list[str] = []

    def capture_transport(*, url, headers, body, timeout):
        del url, headers, timeout
        from minnarone.openrouter import HttpResponse

        prompt = _prompt_from_body(body)
        if "Sei un sintetizzatore" not in prompt:
            prompts.append(prompt)
        content = "Dovresti chiedere qual e' il budget previsto per il Q3."
        payload = json.dumps({"choices": [{"message": {"content": content}}]})
        return HttpResponse(status=200, body=payload.encode("utf-8"))

    router = FakeOutputRouter()
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    suggester: {}
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=capture_transport,
        store_path=tmp_path / "p.jsonl",
        router=router,
    )

    # Add a speech perception
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.AUDIO,
            type="speech",
            text="Discutiamo il budget del Q3",
            speaker="speaker_A",
        )
    )

    asyncio.run(agent.reactor.run_once())

    assert len(router.sent) == 1
    message, mode = router.sent[0]
    assert mode is OutputMode.PRIVATE
    assert "budget" in message

    # The prompt should contain SUGGESTER-specific content
    assert prompts
    assert "suggestion_eval" in prompts[0]


def test_suggester_nothing_response_produces_no_output(tmp_path, monkeypatch):
    """End-to-end: #nothing response from LLM produces NO output."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeOutputRouter

    def nothing_transport(*, url, headers, body, timeout):
        del url, headers, timeout
        from minnarone.openrouter import HttpResponse

        prompt = _prompt_from_body(body)
        if "Sei un sintetizzatore" in prompt:
            content = "summary"
        else:
            content = "#nothing"
        payload = json.dumps({"choices": [{"message": {"content": content}}]})
        return HttpResponse(status=200, body=payload.encode("utf-8"))

    router = FakeOutputRouter()
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    suggester: {}
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=nothing_transport,
        store_path=tmp_path / "p.jsonl",
        router=router,
    )

    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.AUDIO,
            type="speech",
            text="Parliamo del meteo",
            speaker="speaker_B",
        )
    )

    asyncio.run(agent.reactor.run_once())

    assert router.sent == []


def test_suggester_non_speech_perceptions_do_not_trigger(tmp_path, monkeypatch):
    """Non-speech perceptions (CHAT, VIDEO) do not trigger suggestion evaluation."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeOutputRouter

    llm_calls: list[str] = []

    def tracking_transport(*, url, headers, body, timeout):
        del url, headers, timeout
        from minnarone.openrouter import HttpResponse

        prompt = _prompt_from_body(body)
        if "Sei un sintetizzatore" not in prompt:
            llm_calls.append(prompt)
        payload = json.dumps(
            {"choices": [{"message": {"content": "suggestion"}}]}
        )
        return HttpResponse(status=200, body=payload.encode("utf-8"))

    router = FakeOutputRouter()
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    suggester: {}
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=tracking_transport,
        store_path=tmp_path / "p.jsonl",
        router=router,
    )

    # Add CHAT and VIDEO perceptions (not AUDIO/speech)
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="Ciao a tutti!",
            speaker="user_chat",
        )
    )
    agent.store.append(
        Perception(
            ts=2.0,
            source=Source.VIDEO,
            type="caption",
            text="A slide showing Q3 results",
        )
    )

    asyncio.run(agent.reactor.run_once())

    # No LLM calls should have been made (no speech = no trigger)
    assert llm_calls == []
    assert router.sent == []


def test_suggester_facts_injected_in_prompt(tmp_path, monkeypatch):
    """Interlocutor facts from facts_dir are injected in the SUGGESTER prompt."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    # Create a facts file for "alice"
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir(exist_ok=True)
    (facts_dir / "alice.md").write_text(
        "Alice lavora nel reparto marketing. Budget annuale: 500k.",
        encoding="utf-8",
    )

    prompts: list[str] = []

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    suggester: {}
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=_recording_transport(prompts),
        store_path=tmp_path / "p.jsonl",
    )

    # Add a speech perception from "alice"
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.AUDIO,
            type="speech",
            text="Dobbiamo rivedere il budget di marketing",
            speaker="alice",
        )
    )

    asyncio.run(agent.reactor.run_once())

    assert prompts, "the Reactor never reacted to the suggestion_eval"
    # The facts for alice should appear in the prompt
    assert any("alice" in p.lower() for p in prompts)
    assert any("marketing" in p.lower() for p in prompts)


def test_suggester_check_mode_passes(tmp_path):
    """A config with only suggester profile passes --check (build only)."""
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    suggester: {}
                """
            ),
        )
    )
    # --check just builds the agent; no crash = pass
    agent = build_agent(cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl")
    assert isinstance(agent, Agent)
    assert agent.senser.trigger_mode == "on_perception"


# --- multi-reactor parallel wiring (issue 11) --------------------------------


def test_multi_profile_build_agent_creates_three_reactors(tmp_path):
    """Config with operator + meeting_synthesizer + suggester produces 3 Reactors."""
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    operator:
                      idle_interval: 30
                    meeting_synthesizer:
                      interval_s: 60
                    suggester: {}
                """
            ),
        )
    )
    agent = build_agent(cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl")

    assert len(agent.reactors) == 3
    # Backward compat: agent.reactor is the first reactor
    assert agent.reactor is agent.reactors[0]


def test_multi_profile_each_reactor_has_correct_trigger_mode_and_style(tmp_path):
    """Each Reactor in a multi-profile config has the correct trigger_mode and style."""
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    operator:
                      idle_interval: 30
                    meeting_synthesizer:
                      interval_s: 60
                    suggester: {}
                """
            ),
        )
    )
    agent = build_agent(cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl")

    # Collect trigger_modes and styles by reactor index
    trigger_modes = [r._senser.trigger_mode for r in agent.reactors]
    styles = [r._prompt_builder.commentator_style for r in agent.reactors]

    assert "reactive" in trigger_modes
    assert "periodic" in trigger_modes
    assert "on_perception" in trigger_modes

    assert CommentatorStyle.OPERATOR in styles
    assert CommentatorStyle.MEETING_SYNTHESIZER in styles
    assert CommentatorStyle.SUGGESTER in styles


def test_multi_profile_all_reactors_share_store_summarizer_llm(tmp_path):
    """All Reactors share the same store, summarizer (via summary_provider), and LLM."""
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    operator:
                      idle_interval: 30
                    meeting_synthesizer:
                      interval_s: 60
                    suggester: {}
                """
            ),
        )
    )
    agent = build_agent(cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl")

    stores = {id(r._store) for r in agent.reactors}
    llms = {id(r._llm) for r in agent.reactors}

    # All share the same store instance
    assert len(stores) == 1
    # All share the same LLM instance
    assert len(llms) == 1
    # Store is the agent's store
    assert id(agent.store) in stores


def test_multi_profile_each_reactor_has_own_senser_prompt_router(tmp_path):
    """Each Reactor has its own Senser, PromptBuilder, and Router."""
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    operator:
                      idle_interval: 30
                    meeting_synthesizer:
                      interval_s: 60
                    suggester: {}
                """
            ),
        )
    )
    agent = build_agent(cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl")

    sensers = [id(r._senser) for r in agent.reactors]
    builders = [id(r._prompt_builder) for r in agent.reactors]

    # Each has its own Senser and PromptBuilder
    assert len(set(sensers)) == 3
    assert len(set(builders)) == 3


def test_multi_profile_concurrent_run_produces_output_from_all(
    tmp_path, monkeypatch
):
    """All 3 Reactors produce output when their respective triggers fire."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeOutputRouter

    def multi_transport(*, url, headers, body, timeout):
        del url, headers, timeout
        from minnarone.openrouter import HttpResponse

        prompt = _prompt_from_body(body)
        if "Sei un sintetizzatore" in prompt:
            content = "summary"
        elif "commentatore locale" in prompt:
            content = "Commento dall'operatore."
        elif "sintesi riunione" in prompt:
            content = "Sintesi della riunione."
        elif "suggestion_eval" in prompt:
            content = "Suggerimento per l'utente."
        else:
            content = "risposta generica"
        payload = json.dumps({"choices": [{"message": {"content": content}}]})
        return HttpResponse(status=200, body=payload.encode("utf-8"))

    router = FakeOutputRouter()
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    operator:
                      idle_interval: 999
                    meeting_synthesizer:
                      interval_s: 5
                    suggester: {}
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=multi_transport,
        store_path=tmp_path / "p.jsonl",
        router=router,
    )

    # Add perceptions that trigger operator (mention) and suggester (speech)
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="ehi minnarone come va?",
            speaker="utente1",
        )
    )
    agent.store.append(
        Perception(
            ts=2.0,
            source=Source.AUDIO,
            type="speech",
            text="Parliamo del budget Q3",
            speaker="speaker_A",
        )
    )

    # Run each reactor once: operator triggers on mention, suggester on speech
    for reactor in agent.reactors:
        if reactor._senser.trigger_mode == "reactive":
            asyncio.run(reactor.run_once())
        elif reactor._senser.trigger_mode == "on_perception":
            asyncio.run(reactor.run_once())

    # Force meeting_synthesizer to fire by advancing its clock
    for reactor in agent.reactors:
        if reactor._senser.trigger_mode == "periodic":
            reactor._senser._last_trigger_at -= 6.0  # past interval_s=5
            asyncio.run(reactor.run_once())

    messages = [msg for msg, _mode in router.sent]
    assert "Commento dall'operatore." in messages
    assert "Sintesi della riunione." in messages
    assert "Suggerimento per l'utente." in messages


# --- per-profile TUI output routing (issue 12) --------------------------------


def test_multi_profile_tui_creates_per_profile_output_streams(tmp_path):
    """TUI path creates one MinnaroneOutputStream per active profile."""
    from minnarone.output_sink import MinnaroneOutputStream

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    operator:
                      idle_interval: 30
                    meeting_synthesizer:
                      interval_s: 60
                    suggester: {}
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        minnarone_output=MinnaroneOutputStream(),
    )

    assert len(agent.output_streams) == 3
    assert CommentatorStyle.OPERATOR in agent.output_streams
    assert CommentatorStyle.MEETING_SYNTHESIZER in agent.output_streams
    assert CommentatorStyle.SUGGESTER in agent.output_streams
    for stream in agent.output_streams.values():
        assert isinstance(stream, MinnaroneOutputStream)


def test_multi_profile_tui_reactors_have_distinct_routers(tmp_path):
    """Each Reactor in a TUI multi-profile config has its own router."""
    from minnarone.output_sink import MinnaroneOutputStream, TuiPrivateOutputRouter

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    operator:
                      idle_interval: 30
                    meeting_synthesizer:
                      interval_s: 60
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        minnarone_output=MinnaroneOutputStream(),
    )

    assert len(agent.reactors) == 2
    router_a = agent.reactors[0]._router
    router_b = agent.reactors[1]._router
    assert isinstance(router_a, TuiPrivateOutputRouter)
    assert isinstance(router_b, TuiPrivateOutputRouter)
    assert router_a is not router_b
    assert router_a.stream is not router_b.stream


def test_multi_profile_tui_messages_do_not_mix(tmp_path, monkeypatch):
    """Messages routed by one profile appear only in its own stream."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from minnarone.output_sink import MinnaroneOutputStream

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    operator:
                      idle_interval: 30
                    meeting_synthesizer:
                      interval_s: 60
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        minnarone_output=MinnaroneOutputStream(),
    )

    op_reactor = next(
        r for r in agent.reactors
        if r._prompt_builder.commentator_style is CommentatorStyle.OPERATOR
    )
    # Verifica che esista un reactor MEETING_SYNTHESIZER (StopIteration se assente).
    next(
        r for r in agent.reactors
        if r._prompt_builder.commentator_style is CommentatorStyle.MEETING_SYNTHESIZER
    )

    agent.store.append(
        Perception(ts=1.0, source=Source.CHAT, type="msg",
                   text="ehi minnarone ci sei?", speaker="u1")
    )

    asyncio.run(op_reactor.run_once())

    op_stream = agent.output_streams[CommentatorStyle.OPERATOR]
    ms_stream = agent.output_streams[CommentatorStyle.MEETING_SYNTHESIZER]

    op_msgs = [m.text for m in op_stream.recent_messages()]
    ms_msgs = [m.text for m in ms_stream.recent_messages()]

    assert len(op_msgs) > 0
    assert len(ms_msgs) == 0


def test_no_tui_output_streams_empty(tmp_path):
    """Without TUI (no minnarone_output), output_streams is empty."""
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="commentator:\n  profiles:\n    operator: {}",
        )
    )
    agent = build_agent(cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl")

    assert agent.output_streams == {}


def test_minnarone_output_points_to_first_stream(tmp_path):
    """agent.minnarone_output is the first profile's stream (backward compat)."""
    from minnarone.output_sink import MinnaroneOutputStream

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                commentator:
                  language: it
                  profiles:
                    operator: {}
                    meeting_synthesizer:
                      interval_s: 60
                """
            ),
        )
    )
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        minnarone_output=MinnaroneOutputStream(),
    )

    assert agent.minnarone_output is not None
    first_stream = next(iter(agent.output_streams.values()))
    assert agent.minnarone_output is first_stream


def test_zero_profile_config_no_reactors(tmp_path):
    """Zero-profile config works: no Reactors, only pump + summarizer."""
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
        )
    )
    agent = build_agent(cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl")

    assert agent.reactors == []


def test_zero_profile_run_completes_without_error(tmp_path, monkeypatch):
    """Agent.run() with zero Reactors completes without errors (pump + summarizer only)."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeSourceAdapter

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="summarizer_interval: 0.01",
        )
    )
    adapter = FakeSourceAdapter(
        [
            RawEvent(
                channel="chat",
                payload={"text": "ciao mondo", "speaker": "u1"},
                ts=1.0,
            )
        ]
    )
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        adapter=adapter,
    )

    # run() should complete without error even with no reactors
    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    # Perception was pumped into the store
    tail = agent.store.tail(10)
    assert any(p.text == "ciao mondo" for p in tail)


def test_multi_profile_graceful_shutdown_cancels_all(tmp_path, monkeypatch):
    """If one Reactor task fails, all others should be cancelled."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeSourceAdapter

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            extra=textwrap.dedent(
                """
                senser_interval: 0.01
                summarizer_interval: 0.01
                commentator:
                  language: it
                  profiles:
                    operator:
                      idle_interval: 999
                    suggester: {}
                """
            ),
        )
    )
    adapter = FakeSourceAdapter([], channels=set())
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        adapter=adapter,
    )

    # run() should complete cleanly (adapter finishes immediately)
    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))


def test_router_override_keeps_minnarone_output_stream_inactive(tmp_path):
    from minnarone.fakes import FakeOutputRouter
    from minnarone.output_sink import MinnaroneOutputStream

    stream = MinnaroneOutputStream()
    router = FakeOutputRouter()
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="commentator:\n  profiles:\n    operator: {}",
        )
    )
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
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="commentator:\n  profiles:\n    operator: {}",
        )
    )
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
            os_capture:
              audio: false
              video: true
            """
        ),
        encoding="utf-8",
    )
    cfg = Config.load(cfg_path)
    assert cfg.agent_name  # default non vuoto
    agent = build_agent(cfg, transport=_fake_transport)
    assert agent is not None


def test_os_capture_config_builds_lazy_video_adapter_without_opening_device(tmp_path):
    # os_capture è cablato: build_agent costruisce un OsCaptureAdapter con
    # sorgenti device LAZY. Al build (come al --check) NON si apre alcun device:
    # il canale video è lazy (captioner VLM + sorgente schermo differiti), quindi
    # l'agente si compone senza hardware né backend ML installato.
    cfg = Config.load(_write_workspace(tmp_path))
    assert cfg.adapter == "os_capture"
    assert cfg.os_capture is not None
    agent = build_agent(cfg, transport=_fake_transport)
    assert isinstance(agent.adapter, OsCaptureAdapter)
    assert agent.adapter.channels() == {"video"}
    # La queue bounded è cablata per il canale video model-backed (ADR
    # backpressure): stesso trattamento di Twitch.
    assert agent.perception_queue is not None
    assert set(agent.perception_queue_stats().channels) == {"video"}


class _CollectingAudioPerceiver:
    """Perceiver audio fake: registra i payload instradati dalla pompa."""

    def __init__(self) -> None:
        self.payloads = []

    def perceive_event(self, event: RawEvent) -> None:
        self.payloads.append(event.payload)
        return None


def test_os_capture_runtime_feeds_store_from_injected_audio_and_video_sources(
    tmp_path,
):
    # Tracer bullet SENZA hardware: si iniettano sorgenti device fake (liste
    # in-memory di AudioChunk/VideoFrame) e perceiver che scrivono nello store.
    # `run()` deve pompare audio+video nello store passando dalla queue bounded.
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            extra=textwrap.dedent(
                """
                os_capture:
                  audio: true
                  video: true
                """
            ),
        )
    )

    audio_source = [
        AudioChunk(
            samples=b"hello",
            sample_rate=16_000,
            source_label="system",
            ts=1.0,
        )
    ]
    video_source = [VideoFrame(pixels="frame", source_label="screen", ts=2.0)]

    audio_perceiver = _CollectingAudioPerceiver()
    video_perceiver = _CollectingVideoPerceiver()

    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        audio_perceiver=audio_perceiver,  # type: ignore[arg-type]
        video_perceiver=video_perceiver,  # type: ignore[arg-type]
        os_capture_audio_source=audio_source,
        os_capture_video_source=video_source,
    )

    assert isinstance(agent.adapter, OsCaptureAdapter)
    assert agent.adapter.channels() == {"audio", "video"}
    assert set(agent.perceivers) >= {"audio", "video"}
    # Audio e video passano dalla queue bounded (policy ADR invariata).
    assert agent.perception_queue is not None
    assert set(agent.perception_queue_stats().channels) == {"audio", "video"}

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    assert [chunk.samples for chunk in audio_perceiver.payloads] == [b"hello"]
    assert [frame.pixels for frame in video_perceiver.payloads] == ["frame"]
    assert agent.perception_queue_stats().channels["audio"].processed == 1
    assert agent.perception_queue_stats().channels["video"].processed == 1


def test_os_capture_build_does_not_open_device_when_source_not_injected(tmp_path):
    # Con il canale video abilitato ma nessuna sorgente iniettata, il runtime usa
    # la sorgente device LAZY: build (e --check) NON devono aprire mss/soundcard.
    # `make_device_screen_capture_source` solleva NotImplementedError SOLO se
    # iterata; qui non deve essere invocata al build.
    cfg = Config.load(_write_workspace(tmp_path))
    # Nessuna eccezione: il device è differito, non aperto in costruzione.
    agent = build_agent(cfg, transport=_fake_transport)
    assert isinstance(agent.adapter, OsCaptureAdapter)


def test_os_capture_enabled_audio_without_perceiver_raises_config_error(tmp_path):
    # Coerenza speculare a Twitch: canale abilitato ma perceiver/backend non
    # costruibile → ConfigError chiaro (l'ASR locale non è installato nei test).
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            extra=textwrap.dedent(
                """
                os_capture:
                  audio: true
                  video: false
                """
            ),
        )
    )
    with pytest.raises(ConfigError, match="os_capture.audio"):
        build_agent(
            cfg,
            transport=_fake_transport,
            os_capture_audio_source=[],
        )


# --- Fix 1: il loop del Summarizer parte nel percorso live ------------------


def _prompt_from_body(body: bytes) -> str:
    """Estrae il testo del prompt dal body JSON della richiesta (OpenAI shape)."""
    data = json.loads(body.decode("utf-8"))
    return data["messages"][-1]["content"]


def _recording_transport(prompts: list[str], *, summary: str = "RIASSUNTO-NOTO"):
    """Transport fake che registra i prompt e risponde in modo deterministico.

    Riconosce la chiamata del Summarizer dal suo header ("Sei un sintetizzatore") e risponde
    con un riassunto noto; per ogni altra chiamata (reazione del Reactor) risponde
    "ciao" e registra il prompt in `prompts`, così il test può asserire che il
    riassunto è fluito nel prompt di reazione.
    """
    from minnarone.openrouter import HttpResponse

    def transport(*, url, headers, body, timeout):
        prompt = _prompt_from_body(body)
        if "Sei un sintetizzatore" in prompt:
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
    # Percorso "reactor drives": nessun adapter live (né device os_capture), così
    # è il loop di reazione a guidare la durata (questo test verifica proprio quel
    # ramo di run()). Si annulla l'adapter/queue device cablati di default.
    agent = replace(
        build_agent(cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl"),
        adapter=None,
        perception_queue=None,
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
        agent.summarizer.stop()
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
            mode="private",
            extra=(
                "summarizer_interval: 0.01\nsenser_interval: 0.01\n"
                "commentator:\n  profiles:\n    operator: {}"
            ),
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
    """Un canale senza perceiver configurato viene saltato, non crasha.

    La config di default os_capture cabla il canale "video" (perceiver lazy) ma
    NON "audio": un evento su "audio" (o su un canale ignoto) viene ignorato in
    silenzio, senza crash né percezioni scritte.
    """
    cfg = Config.load(_write_workspace(tmp_path, mode="public"))
    agent = build_agent(
        cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl"
    )
    assert "audio" not in agent.perceivers
    # Nessuna eccezione, nessuna percezione scritta per un canale non cablato.
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
            extra=(
                "summarizer_interval: 0.01\nsenser_interval: 0.01\n"
                "commentator:\n  profiles:\n    operator: {}"
            ),
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
    agent = replace(
        build_agent(
            cfg,
            transport=_fake_transport,
            store_path=tmp_path / "p.jsonl",
            router=capture,
            adapter=adapter,
        ),
        perception_queue=None,
    )

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    tail = agent.store.tail(10)
    assert any(p.text == "ehi minnarone come va?" for p in tail)
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
            extra=(
                "summarizer_interval: 0.01\nsenser_interval: 0.01\n"
                "commentator:\n  profiles:\n    operator: {}"
            ),
        )
    )
    agent = replace(
        build_agent(cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl"),
        adapter=None,
        perception_queue=None,
    )
    assert agent.adapter is None

    async def drive():
        task = asyncio.create_task(agent.run())
        await asyncio.sleep(0.05)
        assert not task.done()
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


def test_original_chat_prompt_uses_channel_from_twitch_config(
    tmp_path, monkeypatch
):
    # FU-01: il canale nel prompt deve seguire twitch.channel della config,
    # non il default cablato "enkk".
    monkeypatch.delenv("TWITCH_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)

    from minnarone.fakes import FakeSourceAdapter

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="private",
            adapter="twitch",
            twitch_block=textwrap.dedent(
                """
                twitch:
                  channel: multiplayerit
                  chat: true
                  audio: false
                  video: false
                """
            ),
            extra=textwrap.dedent(
                """
                commentator:
                  profiles:
                    original_chat: {}
                """
            ),
        )
    )

    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        adapter=FakeSourceAdapter([], channels=set()),
    )

    prefix = agent.prompt_builder.stable_prefix()
    assert "multiplayerit" in prefix
    assert "enkk" not in prefix
