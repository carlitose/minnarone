"""YouTube chat plus operator-managed Chrome media via OS capture."""

from __future__ import annotations

import asyncio
import json
import textwrap

import pytest

from minnarone.app import _LazyAudioPerceiver, build_agent
from minnarone.audio import AudioChunk
from minnarone.cli import main
from minnarone.config import Config, ConfigError
from minnarone.merge import MergingSourceAdapter
from minnarone.openrouter import HttpResponse
from minnarone.source import RawEvent
from minnarone.video import VideoFrame
from minnarone.youtube_chat import YouTubeApiError


class _RepeatingYouTubeApi:
    """One synthetic chat event followed by a terminal page on every run."""

    def __init__(self) -> None:
        self.video_calls = 0
        self.chat_calls = 0

    async def get_video(self, *, video_id: str, api_key: str):
        del video_id, api_key
        self.video_calls += 1
        return {
            "items": [
                {
                    "liveStreamingDetails": {
                        "actualStartTime": "2026-08-03T10:00:00Z",
                        "activeLiveChatId": "synthetic-chat",
                    }
                }
            ]
        }

    async def list_messages(self, **kwargs):
        del kwargs
        self.chat_calls += 1
        if self.chat_calls % 2 == 0:
            raise YouTubeApiError(status=403, reason="liveChatEnded")
        message_number = (self.chat_calls + 1) // 2
        return {
            "nextPageToken": f"next-{message_number}",
            "pollingIntervalMillis": 0,
            "items": [
                {
                    "id": f"synthetic-message-{message_number}",
                    "snippet": {
                        "type": "textMessageEvent",
                        "publishedAt": "2026-08-03T10:01:00Z",
                        "authorChannelId": "synthetic-author",
                        "textMessageDetails": {"messageText": f"chat-{message_number}"},
                    },
                    "authorDetails": {
                        "channelId": "synthetic-author",
                        "displayName": "Synthetic Viewer",
                    },
                }
            ],
        }


class _FailingYouTubeApi:
    async def get_video(self, *, video_id: str, api_key: str):
        del video_id, api_key
        raise YouTubeApiError(status=500, reason="backendError")

    async def list_messages(self, **kwargs):  # pragma: no cover - discovery fails
        del kwargs
        raise AssertionError("chat listing must not run")


class _CollectingPerceiver:
    def __init__(self) -> None:
        self.payloads: list[object] = []

    def perceive_event(self, event: RawEvent) -> None:
        self.payloads.append(event.payload)


def _raise_video_failure() -> VideoFrame:
    raise RuntimeError("synthetic video failure")


async def _failing_video_source():
    # Evaluate the failing source before the first item is yielded.
    yield _raise_video_failure()


def _transport(*, url, headers, body, timeout):
    del url, headers, body, timeout
    payload = {"choices": [{"message": {"content": "unused"}}]}
    return HttpResponse(status=200, body=json.dumps(payload).encode())


def _workspace(tmp_path, *, audio: bool = True, video: bool = True):
    soul = tmp_path / "soul.md"
    soul.write_text("Sono Minnarone.", encoding="utf-8")
    facts = tmp_path / "facts"
    facts.mkdir()
    config = tmp_path / "youtube-full-shadow.yaml"
    config.write_text(
        textwrap.dedent(
            f"""
            mode: public
            soul_path: {soul}
            facts_dir: {facts}
            adapter: youtube
            llm_provider: grok
            youtube:
              video_id: abcDEF123_-
              max_retries: 0
            os_capture:
              audio: {str(audio).lower()}
              video: {str(video).lower()}
            commentator:
              profiles: {{}}
            """
        ),
        encoding="utf-8",
    )
    return config


def _audio(label: str = "system", ts: float = 1.0) -> AudioChunk:
    return AudioChunk(
        samples=b"\x00\x00" * 160,
        sample_rate=16_000,
        source_label=label,
        ts=ts,
    )


def _video(ts: float = 2.0) -> VideoFrame:
    return VideoFrame(pixels="synthetic-frame", source_label="screen", ts=ts)


def test_config_accepts_youtube_with_the_single_top_level_os_capture_block(tmp_path):
    cfg = Config.load(_workspace(tmp_path))

    assert cfg.youtube is not None
    assert cfg.os_capture is not None
    assert cfg.os_capture.audio is True
    assert cfg.os_capture.video is True


def test_youtube_media_settings_stay_out_of_the_youtube_section(tmp_path):
    path = _workspace(tmp_path)
    text = path.read_text(encoding="utf-8").replace(
        "video_id: abcDEF123_-", "video_id: abcDEF123_-\n  monitor: 1"
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ConfigError, match="unknown youtube fields.*monitor"):
        Config.load(path)


def test_build_composes_chat_audio_and_video_as_single_channel_readers(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    audio = _CollectingPerceiver()
    video = _CollectingPerceiver()

    agent = build_agent(
        Config.load(_workspace(tmp_path)),
        transport=_transport,
        youtube_api=_RepeatingYouTubeApi(),
        audio_perceiver=audio,  # type: ignore[arg-type]
        video_perceiver=video,  # type: ignore[arg-type]
        os_capture_audio_source=[_audio()],
        os_capture_video_source=[_video()],
    )

    assert isinstance(agent.adapter, MergingSourceAdapter)
    assert agent.adapter.ordered_channels() == ["chat", "audio", "video"]
    assert agent.adapter.channels() == {"chat", "audio", "video"}
    assert agent.adapter._priority == frozenset({"chat"})  # noqa: SLF001
    assert not any(
        isinstance(reader, MergingSourceAdapter)
        for reader in agent.adapter._readers.values()  # noqa: SLF001
    )


def test_synthetic_full_shadow_reuses_media_perceivers_and_bounded_work_queue(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    audio = _CollectingPerceiver()
    video = _CollectingPerceiver()
    agent = build_agent(
        Config.load(_workspace(tmp_path)),
        transport=_transport,
        store_path=tmp_path / "perceptions.jsonl",
        youtube_api=_RepeatingYouTubeApi(),
        audio_perceiver=audio,  # type: ignore[arg-type]
        video_perceiver=video,  # type: ignore[arg-type]
        os_capture_audio_source=[_audio()],
        os_capture_video_source=[_video()],
    )

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    assert [item.source_label for item in audio.payloads] == ["system"]
    assert [item.sample_rate for item in audio.payloads] == [16_000]
    assert [item.source_label for item in video.payloads] == ["screen"]
    assert agent.store.tail(1)[0].text == "chat-1"
    assert agent.perception_queue is not None
    queue_stats = agent.perception_queue_stats().channels
    assert queue_stats["audio"].processed == 1
    assert queue_stats["video"].processed == 1


def test_chat_failure_is_isolated_from_productive_local_media(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    audio = _CollectingPerceiver()
    agent = build_agent(
        Config.load(_workspace(tmp_path, video=False)),
        transport=_transport,
        youtube_api=_FailingYouTubeApi(),
        audio_perceiver=audio,  # type: ignore[arg-type]
        os_capture_audio_source=[_audio()],
    )

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    assert len(audio.payloads) == 1
    assert isinstance(agent.adapter, MergingSourceAdapter)
    assert "chat" in agent.adapter.stats().failures
    assert agent.adapter.stats().produced["audio"] == 1


def test_media_failure_is_isolated_from_healthy_chat(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    video = _CollectingPerceiver()
    agent = build_agent(
        Config.load(_workspace(tmp_path, audio=False)),
        transport=_transport,
        store_path=tmp_path / "perceptions.jsonl",
        youtube_api=_RepeatingYouTubeApi(),
        video_perceiver=video,  # type: ignore[arg-type]
        os_capture_video_source=_failing_video_source(),
    )

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    assert agent.store.tail(1)[0].text == "chat-1"
    assert isinstance(agent.adapter, MergingSourceAdapter)
    assert "synthetic video failure" in agent.adapter.stats().failures["video"]
    assert agent.adapter.stats().produced["chat"] == 1


def test_missing_audio_backend_fails_that_work_item_without_losing_chat(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    setup_attempts = 0

    def unavailable_audio_backend(*_args, **_kwargs):
        nonlocal setup_attempts
        setup_attempts += 1
        raise ConfigError("os_capture.audio backend unavailable")

    monkeypatch.setattr(
        "minnarone.app._build_default_audio_perceiver",
        unavailable_audio_backend,
    )
    agent = build_agent(
        Config.load(_workspace(tmp_path, video=False)),
        transport=_transport,
        store_path=tmp_path / "perceptions.jsonl",
        youtube_api=_RepeatingYouTubeApi(),
        os_capture_audio_source=[_audio(ts=1.0), _audio(ts=2.0)],
    )

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    assert agent.store.tail(1)[0].text == "chat-1"
    audio_stats = agent.perception_queue_stats().channels["audio"]
    assert audio_stats.failed == 2
    assert audio_stats.last_error == "os_capture.audio backend unavailable"
    assert setup_attempts == 1


def test_lazy_audio_backend_failure_uses_fresh_bounded_exceptions() -> None:
    setup_attempts = 0

    def unavailable_audio_backend():
        nonlocal setup_attempts
        setup_attempts += 1
        raise ConfigError("os_capture.audio backend unavailable")

    perceiver = _LazyAudioPerceiver(unavailable_audio_backend)
    failures: list[ConfigError] = []
    event = RawEvent(channel="audio", payload=_audio(), ts=1.0)

    for _ in range(5):
        with pytest.raises(ConfigError) as captured:
            perceiver.perceive_event(event)
        failures.append(captured.value)

    def traceback_depth(error: BaseException) -> int:
        depth = 0
        traceback = error.__traceback__
        while traceback is not None:
            depth += 1
            traceback = traceback.tb_next
        return depth

    assert setup_attempts == 1
    assert len({id(error) for error in failures}) == len(failures)
    assert max(map(traceback_depth, failures)) <= 3
    assert all(error.__cause__ is None for error in failures)


def test_priority_chat_evicts_media_and_exposes_drop_counters(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    audio = _CollectingPerceiver()
    agent = build_agent(
        Config.load(_workspace(tmp_path, video=False)),
        transport=_transport,
        youtube_api=_RepeatingYouTubeApi(),
        audio_perceiver=audio,  # type: ignore[arg-type]
        os_capture_audio_source=[_audio()],
    )
    assert isinstance(agent.adapter, MergingSourceAdapter)

    async def overflow() -> None:
        for index in range(100):
            await agent.adapter._enqueue(  # noqa: SLF001
                RawEvent(channel="audio", payload=index, ts=float(index))
            )
        await agent.adapter._enqueue(  # noqa: SLF001
            RawEvent(channel="chat", payload="priority", ts=101.0)
        )

    asyncio.run(overflow())

    stats = agent.adapter.stats()
    assert stats.produced["chat"] == 1
    assert stats.dropped["audio"] == 1
    assert agent.adapter._buffer[-1].channel == "chat"  # noqa: SLF001


def test_composed_adapter_restarts_cleanly_with_reiterable_fake_media(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    audio = _CollectingPerceiver()
    agent = build_agent(
        Config.load(_workspace(tmp_path, video=False)),
        transport=_transport,
        youtube_api=_RepeatingYouTubeApi(),
        audio_perceiver=audio,  # type: ignore[arg-type]
        os_capture_audio_source=[_audio()],
    )
    assert isinstance(agent.adapter, MergingSourceAdapter)

    async def drain_twice() -> list[list[str]]:
        runs: list[list[str]] = []
        for _ in range(2):
            await agent.adapter.start()
            runs.append([event.channel async for event in agent.adapter.events()])
            await agent.adapter.stop()
        return runs

    runs = asyncio.run(asyncio.wait_for(drain_twice(), timeout=5.0))

    assert [set(run) for run in runs] == [{"audio", "chat"}, {"audio", "chat"}]


def test_lazy_device_source_is_recreated_on_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    opens = 0

    def fake_device_source(**kwargs):
        del kwargs

        async def source():
            nonlocal opens
            opens += 1
            yield _audio(ts=float(opens))

        return source()

    monkeypatch.setattr("minnarone.app.make_device_capture_source", fake_device_source)
    audio = _CollectingPerceiver()
    agent = build_agent(
        Config.load(_workspace(tmp_path, video=False)),
        transport=_transport,
        youtube_api=_RepeatingYouTubeApi(),
        audio_perceiver=audio,  # type: ignore[arg-type]
    )
    assert isinstance(agent.adapter, MergingSourceAdapter)

    async def drain_twice() -> None:
        for _ in range(2):
            await agent.adapter.start()
            async for _event in agent.adapter.events():
                pass
            await agent.adapter.stop()

    asyncio.run(asyncio.wait_for(drain_twice(), timeout=5.0))

    assert opens == 2


def test_cli_check_with_youtube_screen_capture_opens_no_api_or_device(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    config = _workspace(tmp_path)
    monkeypatch.setattr(
        "minnarone.youtube_chat.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("--check must not call YouTube")
        ),
    )
    monkeypatch.setattr(
        "minnarone.app.make_device_screen_capture_source",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("--check must not open mss")
        ),
    )
    monkeypatch.setattr(
        "minnarone.app.make_device_capture_source",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("--check must not open soundcard")
        ),
    )
    monkeypatch.setattr(
        "minnarone.app._build_default_audio_perceiver",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("--check must not open local models")
        ),
    )

    assert main([str(config), "--check"]) == 0
    assert "ok: agent" in capsys.readouterr().out
