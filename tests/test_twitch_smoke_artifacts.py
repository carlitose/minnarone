"""Twitch smoke artifact writer behavior."""

import asyncio
import json

from minnarone.audio import AudioChunk
from minnarone.fakes import FakeSourceAdapter
from minnarone.source import RawEvent
from minnarone.twitch_smoke_artifacts import TwitchSmokeArtifacts, capture_twitch_smoke
from minnarone.video import VideoFrame


def test_smoke_artifacts_write_chat_audio_samples_and_stats(tmp_path):
    artifacts = TwitchSmokeArtifacts(tmp_path / "smoke", max_audio_samples=1)

    assert artifacts.record(
        RawEvent(
            channel="chat",
            payload={"text": "ciao", "speaker": "Viewer"},
            ts=1.0,
        )
    )
    assert artifacts.record(
        RawEvent(
            channel="audio",
            payload=AudioChunk(
                samples=b"pcm-one",
                sample_rate=16_000,
                source_label="stream",
                ts=2.0,
            ),
            ts=2.0,
        )
    )
    assert artifacts.record(
        RawEvent(
            channel="audio",
            payload=AudioChunk(
                samples=b"pcm-two",
                sample_rate=16_000,
                source_label="stream",
                ts=3.0,
            ),
            ts=3.0,
        )
    )
    artifacts.add_failure("audio: ffmpeg exited")
    artifacts.write_stats()

    perception = json.loads(artifacts.perceptions_path.read_text().strip())
    assert perception == {
        "ts": 1.0,
        "source": "chat",
        "type": "msg",
        "text": "ciao",
        "speaker": "Viewer",
    }
    audio_files = sorted((tmp_path / "smoke" / "raw" / "audio").glob("*.pcm"))
    assert [path.name for path in audio_files] == ["audio-0001.pcm"]
    assert audio_files[0].read_bytes() == b"pcm-one"
    stats = json.loads(artifacts.stats_path.read_text())
    assert stats == {
        "chat_events": 1,
        "audio_events": 2,
        "audio_samples_saved": 1,
        "video_events": 0,
        "video_frames_saved": 0,
        "failures": ["audio: ffmpeg exited"],
    }


def test_smoke_artifacts_start_from_fresh_files(tmp_path):
    output = tmp_path / "smoke"
    raw_audio = output / "raw" / "audio"
    raw_audio.mkdir(parents=True)
    (output / "perceptions.jsonl").write_text("stale\n", encoding="utf-8")
    (raw_audio / "audio-9999.pcm").write_bytes(b"stale")

    artifacts = TwitchSmokeArtifacts(output)

    assert artifacts.perceptions_path.read_text(encoding="utf-8") == ""
    assert list(raw_audio.glob("*.pcm")) == []


def test_smoke_artifacts_can_preserve_custom_perceptions_path(tmp_path):
    artifacts = TwitchSmokeArtifacts(
        tmp_path / "smoke",
        perceptions_path=tmp_path / "custom-chat.jsonl",
    )
    artifacts.record(RawEvent(channel="chat", payload={"text": "ciao"}, ts=1.0))

    assert artifacts.perceptions_path == tmp_path / "custom-chat.jsonl"
    assert (tmp_path / "custom-chat.jsonl").exists()
    assert not (tmp_path / "smoke" / "perceptions.jsonl").exists()


def test_smoke_artifacts_write_capped_video_frames(tmp_path):
    artifacts = TwitchSmokeArtifacts(tmp_path / "smoke", max_video_frames=1)

    assert artifacts.record(
        RawEvent(
            channel="video",
            payload=VideoFrame(pixels=b"jpeg-one", source_label="stream", ts=1.0),
            ts=1.0,
        )
    )
    assert artifacts.record(
        RawEvent(
            channel="video",
            payload=VideoFrame(pixels=b"jpeg-two", source_label="stream", ts=2.0),
            ts=2.0,
        )
    )
    artifacts.write_stats()

    video_files = sorted((tmp_path / "smoke" / "raw" / "video").glob("*.jpg"))
    assert [path.name for path in video_files] == ["video-0001.jpg"]
    assert video_files[0].read_bytes() == b"jpeg-one"
    stats = json.loads(artifacts.stats_path.read_text())
    assert stats["video_events"] == 2
    assert stats["video_frames_saved"] == 1


def test_capture_twitch_smoke_bounds_cleanup_and_writes_stats(tmp_path):
    class HangingStopAdapter(FakeSourceAdapter):
        async def stop(self):
            await asyncio.Event().wait()

    stats = asyncio.run(
        capture_twitch_smoke(
            [
                HangingStopAdapter(
                    [RawEvent(channel="chat", payload={"text": "ciao"}, ts=1.0)]
                )
            ],
            output_dir=tmp_path / "smoke",
            duration=0.01,
            stop_timeout=0.01,
        )
    )

    assert any("cleanup timed out" in failure for failure in stats.failures)
    written = json.loads((tmp_path / "smoke" / "stats.json").read_text())
    assert any("cleanup timed out" in failure for failure in written["failures"])
