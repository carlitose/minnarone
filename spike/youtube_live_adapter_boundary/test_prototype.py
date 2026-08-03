"""Causal tests for the disposable YouTube adapter/media boundary spike."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from minnarone.audio import AudioChunk
from minnarone.chat import ChatPerceiver
from minnarone.store import PerceptionStore
from minnarone.video import VideoFrame
from spike.youtube_live_adapter_boundary import prototype
from spike.youtube_live_adapter_boundary.prototype import (
    MediaKind,
    ResolvedMediaSource,
    ValidatedSyntheticMediaOpener,
    YouTubeVideoId,
    build_specific_branch,
    build_typed_media_branch,
)

BUILDERS = (build_specific_branch, build_typed_media_branch)


def _collect(branch):
    async def run():
        await branch.adapter.start()
        return [event async for event in branch.adapter.events()]

    return asyncio.run(run())


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("abcDEF123_-", "abcDEF123_-"),
        ("https://youtu.be/abcDEF123_-?si=synthetic", "abcDEF123_-"),
        ("https://www.youtube.com/watch?v=abcDEF123_-", "abcDEF123_-"),
        ("https://youtube.com/live/abcDEF123_-", "abcDEF123_-"),
    ],
)
def test_target_normalization_accepts_only_explicit_supported_shapes(value, expected):
    assert YouTubeVideoId.parse(value).value == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/watch?v=abcDEF123_-",
        "http://youtube.com/watch?v=abcDEF123_-",
        "https://youtube.com/@channel/live",
        "https://youtube.com:444/live/abcDEF123_-",
        "not a video id",
    ],
)
def test_target_normalization_rejects_ambiguous_or_untrusted_values(value):
    with pytest.raises(ValueError):
        YouTubeVideoId.parse(value)


@pytest.mark.parametrize("builder", BUILDERS, ids=lambda fn: fn.__name__)
def test_both_branches_emit_existing_canonical_raw_event_shapes(builder, tmp_path):
    branch = builder(YouTubeVideoId("abcDEF123_-"))
    events = _collect(branch)
    by_channel = {event.channel: event for event in events}

    assert set(by_channel) == {"chat", "audio", "video"}
    assert isinstance(by_channel["chat"].payload, dict)
    assert by_channel["chat"].payload["text"] == "synthetic hello"
    assert by_channel["chat"].payload["message_id"] == "synthetic-message-1"
    assert isinstance(by_channel["audio"].payload, AudioChunk)
    assert by_channel["audio"].payload.sample_rate == 16_000
    assert isinstance(by_channel["video"].payload, VideoFrame)

    store = PerceptionStore(tmp_path / f"{branch.name}.jsonl")
    perceived = ChatPerceiver(store).perceive_event(by_channel["chat"])
    assert perceived is not None
    assert perceived.text == "synthetic hello"
    assert perceived.speaker == "Synthetic Viewer"


@pytest.mark.parametrize("builder", BUILDERS, ids=lambda fn: fn.__name__)
def test_start_stop_are_idempotent_and_cleanup_is_complete(builder):
    branch = builder(YouTubeVideoId("abcDEF123_-"))

    async def run():
        await branch.adapter.start()
        await branch.adapter.start()
        await asyncio.sleep(0)
        await branch.adapter.stop()
        await branch.adapter.stop()

    asyncio.run(run())

    assert all(reader.starts == 1 for reader in branch.readers.values())
    assert all(reader.stops == 1 for reader in branch.readers.values())
    assert branch.adapter.stats().running is False
    if branch.opener is not None:
        assert branch.opener.opened
        assert all(stream.closed for stream in branch.opener.opened)
        assert all(stream.close_calls == 1 for stream in branch.opener.opened)


@pytest.mark.parametrize("builder", BUILDERS, ids=lambda fn: fn.__name__)
def test_reader_set_can_restart_after_a_completed_stop(builder):
    branch = builder(YouTubeVideoId("abcDEF123_-"))

    async def run_cycle():
        await branch.adapter.start()
        channels = {event.channel async for event in branch.adapter.events()}
        await branch.adapter.stop()
        return channels

    async def run():
        first = await run_cycle()
        second = await run_cycle()
        return first, second

    first, second = asyncio.run(run())

    assert first == second == {"chat", "audio", "video"}
    assert all(reader.starts == 2 for reader in branch.readers.values())
    assert all(reader.stops == 2 for reader in branch.readers.values())
    if branch.opener is not None:
        assert len(branch.opener.opened) == 4
        assert all(stream.closed for stream in branch.opener.opened)


@pytest.mark.parametrize("builder", BUILDERS, ids=lambda fn: fn.__name__)
def test_stop_before_start_is_safe_and_does_not_poison_first_run(builder):
    branch = builder(YouTubeVideoId("abcDEF123_-"))

    async def run():
        await branch.adapter.stop()
        await branch.adapter.stop()
        assert all(reader.starts == 0 for reader in branch.readers.values())
        assert all(reader.stops == 0 for reader in branch.readers.values())
        await branch.adapter.start()
        channels = {event.channel async for event in branch.adapter.events()}
        await branch.adapter.stop()
        return channels

    assert asyncio.run(run()) == {"chat", "audio", "video"}
    assert all(reader.starts == 1 for reader in branch.readers.values())
    assert all(reader.stops == 1 for reader in branch.readers.values())


@pytest.mark.parametrize("builder", BUILDERS, ids=lambda fn: fn.__name__)
def test_video_failure_is_isolated_while_chat_and_audio_continue(builder):
    branch = builder(
        YouTubeVideoId("abcDEF123_-"),
        failing_channel="video",
    )
    events = _collect(branch)

    assert {event.channel for event in events} == {"chat", "audio"}
    assert "failed" in branch.adapter.stats().failures["video"]
    assert branch.readers["chat"].stops == 1
    assert branch.readers["audio"].stops == 1
    expected_video_stops = 0 if branch.opener is not None else 1
    assert branch.readers["video"].stops == expected_video_stops
    if branch.opener is not None:
        assert all(stream.closed for stream in branch.opener.opened)


@pytest.mark.parametrize("builder", BUILDERS, ids=lambda fn: fn.__name__)
def test_chat_failure_is_isolated_while_media_continue(builder):
    branch = builder(YouTubeVideoId("abcDEF123_-"), failing_channel="chat")
    events = _collect(branch)

    assert {event.channel for event in events} == {"audio", "video"}
    assert "chat reader failed" in branch.adapter.stats().failures["chat"]
    assert all(reader.stops == 1 for reader in branch.readers.values())
    if branch.opener is not None:
        assert all(stream.closed for stream in branch.opener.opened)


@pytest.mark.parametrize("builder", BUILDERS, ids=lambda fn: fn.__name__)
def test_empty_audio_channel_finishes_without_failing_productive_siblings(builder):
    branch = builder(YouTubeVideoId("abcDEF123_-"), empty_channel="audio")
    events = _collect(branch)
    stats = branch.adapter.stats()

    assert {event.channel for event in events} == {"chat", "video"}
    assert stats.produced["audio"] == 0
    assert "audio" not in stats.failures
    assert all(reader.stops == 1 for reader in branch.readers.values())


def test_typed_reader_can_retry_after_one_exception_safe_open_failure():
    branch = build_typed_media_branch(
        YouTubeVideoId("abcDEF123_-"),
        fail_once_channel="video",
    )

    async def run():
        await branch.adapter.start()
        first = {event.channel async for event in branch.adapter.events()}
        first_failures = branch.adapter.stats().failures
        await branch.adapter.stop()

        await branch.adapter.start()
        second = {event.channel async for event in branch.adapter.events()}
        second_failures = branch.adapter.stats().failures
        await branch.adapter.stop()
        return first, first_failures, second, second_failures

    first, first_failures, second, second_failures = asyncio.run(run())

    assert first == {"chat", "audio"}
    assert "failed once" in first_failures["video"]
    assert second == {"chat", "audio", "video"}
    assert second_failures == {}
    assert branch.readers["video"].starts == 2
    assert branch.readers["video"].stops == 1
    assert all(stream.closed for stream in branch.opener.opened)


@pytest.mark.parametrize("builder", BUILDERS, ids=lambda fn: fn.__name__)
def test_full_queue_drops_media_to_preserve_chat(builder):
    branch = builder(YouTubeVideoId("abcDEF123_-"), queue_size=1)

    async def run():
        await branch.adapter.start()
        await asyncio.sleep(0)
        await branch.adapter.stop()

    asyncio.run(run())
    stats = branch.adapter.stats()

    assert stats.produced["chat"] == 1
    assert stats.dropped["audio"] + stats.dropped["video"] >= 1
    assert stats.dropped["chat"] == 0


def test_typed_opener_rejects_arbitrary_urls_and_unvalidated_strings():
    with pytest.raises(ValueError, match="not a URL"):
        ResolvedMediaSource(
            provider="youtube-fake",
            resource_id="https://youtube.com/live/abcDEF123_-",
            kind=MediaKind.AUDIO,
            quality="best",
        )

    opener = ValidatedSyntheticMediaOpener({})
    with pytest.raises(TypeError, match="ResolvedMediaSource"):
        opener.open("https://youtube.com/live/abcDEF123_-")  # type: ignore[arg-type]


def test_prototype_imports_no_network_browser_process_or_credentials():
    path = Path(prototype.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )

    assert imported_roots.isdisjoint(
        {
            "boto3",
            "googleapiclient",
            "httpx",
            "keyring",
            "requests",
            "selenium",
            "socket",
            "subprocess",
            "webbrowser",
        }
    )
    source = path.read_text(encoding="utf-8")
    assert "create_subprocess" not in source
    assert "Authorization:" not in source
    assert "oauth" not in source.lower()
