"""YouTube Live read-only chat edge: target, discovery, pacing and lifecycle."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping

import pytest

from minnarone.youtube_chat import (
    YouTubeApiError,
    YouTubeChatOutcome,
    YouTubeLiveChatError,
    YouTubeLiveChatReader,
    YouTubeRestTransport,
)
from minnarone.youtube_target import YouTubeVideoId


class FakeYouTubeApi:
    def __init__(
        self,
        *,
        videos: list[Mapping[str, object] | BaseException],
        chats: list[Mapping[str, object] | BaseException],
    ) -> None:
        self._videos = list(videos)
        self._chats = list(chats)
        self.video_calls: list[str] = []
        self.chat_calls: list[dict[str, object]] = []

    async def get_video(self, *, video_id: str, api_key: str):
        assert api_key == "synthetic-read-key"
        self.video_calls.append(video_id)
        result = self._videos.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    async def list_messages(
        self,
        *,
        live_chat_id: str,
        api_key: str,
        page_token: str | None,
        max_results: int,
    ):
        assert api_key == "synthetic-read-key"
        self.chat_calls.append(
            {
                "live_chat_id": live_chat_id,
                "page_token": page_token,
                "max_results": max_results,
            }
        )
        result = self._chats.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def _video(*, chat_id: str | None = "live-chat-1", ended: bool = False):
    details: dict[str, object] = {
        "scheduledStartTime": "2026-08-03T10:00:00Z",
        "actualStartTime": "2026-08-03T10:01:00Z",
    }
    if chat_id is not None:
        details["activeLiveChatId"] = chat_id
    if ended:
        details["actualEndTime"] = "2026-08-03T11:00:00Z"
        details.pop("activeLiveChatId", None)
    return {"items": [{"id": "abcDEF123_-", "liveStreamingDetails": details}]}


def _text_message(
    message_id: str,
    *,
    text: str = "minnarone ciao",
    speaker: str = "Synthetic Viewer",
):
    return {
        "id": message_id,
        "snippet": {
            "type": "textMessageEvent",
            "publishedAt": "2026-08-03T10:02:03Z",
            "authorChannelId": "synthetic-author-id",
            "textMessageDetails": {"messageText": text},
        },
        "authorDetails": {
            "channelId": "synthetic-author-id",
            "displayName": speaker,
            "profileImageUrl": "https://example.invalid/not-propagated.jpg",
        },
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("abcDEF123_-", "abcDEF123_-"),
        ("https://youtu.be/abcDEF123_-?si=synthetic", "abcDEF123_-"),
        ("https://www.youtube.com/watch?v=abcDEF123_-", "abcDEF123_-"),
        ("https://youtube.com/live/abcDEF123_-", "abcDEF123_-"),
    ],
)
def test_target_accepts_only_explicit_video_ids_and_supported_urls(value, expected):
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
def test_target_rejects_ambiguous_or_untrusted_values(value):
    with pytest.raises(ValueError):
        YouTubeVideoId.parse(value)


def test_reader_discovers_chat_pages_deduplicates_and_preserves_minimal_identity():
    api = FakeYouTubeApi(
        videos=[_video(), _video(ended=True)],
        chats=[
            {
                "nextPageToken": "page-2",
                "pollingIntervalMillis": 1250,
                "items": [
                    _text_message("m-1"),
                    _text_message("m-1"),
                    {"id": "poll", "snippet": {"type": "pollEvent"}},
                ],
            },
            {
                "nextPageToken": "page-3",
                "pollingIntervalMillis": 2000,
                "items": [_text_message("m-2", text="secondo messaggio")],
            },
            YouTubeApiError(status=403, reason="liveChatEnded"),
        ],
    )
    sleeps: list[float] = []
    observed_live_chat_ids: list[str | None] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    reader = YouTubeLiveChatReader(
        video_id="abcDEF123_-",
        api_key="synthetic-read-key",
        api=api,
        sleep=fake_sleep,
        live_chat_id_observer=observed_live_chat_ids.append,
    )

    async def collect():
        return [event async for event in reader.events()]

    events = asyncio.run(collect())

    assert [event.payload["message_id"] for event in events] == ["m-1", "m-2"]
    assert events[0].channel == "chat"
    assert events[0].payload == {
        "text": "minnarone ciao",
        "speaker": "Synthetic Viewer",
        "message_id": "m-1",
        "author_channel_id": "synthetic-author-id",
        "live_chat_id": "live-chat-1",
    }
    assert api.video_calls == ["abcDEF123_-", "abcDEF123_-"]
    assert [call["page_token"] for call in api.chat_calls] == [
        None,
        "page-2",
        "page-3",
    ]
    assert sleeps == [1.25, 2.0]
    assert reader.outcome is YouTubeChatOutcome.LIVE_ENDED
    assert reader.stats().duplicates == 1
    assert reader.stats().unsupported_events == 1
    assert reader.stats().produced == {"chat": 2}
    assert reader.stats().failures == {}
    assert "live-chat-1" in observed_live_chat_ids
    assert observed_live_chat_ids[-1] is None


def test_empty_chat_and_disabled_chat_are_not_generic_failures():
    api = FakeYouTubeApi(
        videos=[_video()],
        chats=[
            {
                "nextPageToken": "next",
                "pollingIntervalMillis": 1750,
                "items": [],
            },
            YouTubeApiError(status=403, reason="liveChatDisabled"),
        ],
    )

    async def no_wait(_delay: float) -> None:
        return None

    reader = YouTubeLiveChatReader(
        video_id="abcDEF123_-",
        api_key="synthetic-read-key",
        api=api,
        sleep=no_wait,
    )

    assert asyncio.run(_collect(reader)) == []
    assert reader.outcome is YouTubeChatOutcome.CHAT_DISABLED
    assert reader.stats().empty_polls == 1


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("keyInvalid", YouTubeChatOutcome.AUTH_FAILED),
        ("quotaExceeded", YouTubeChatOutcome.QUOTA_EXHAUSTED),
    ],
)
def test_auth_and_quota_fail_closed_with_distinct_outcomes(reason, expected):
    api = FakeYouTubeApi(
        videos=[_video()],
        chats=[YouTubeApiError(status=403, reason=reason)],
    )
    reader = YouTubeLiveChatReader(
        video_id="abcDEF123_-",
        api_key="synthetic-read-key",
        api=api,
    )

    with pytest.raises(YouTubeLiveChatError) as raised:
        asyncio.run(_collect(reader))

    assert raised.value.outcome is expected
    assert reader.outcome is expected
    assert reader.stats().failures == {"chat": expected.value}


def test_not_found_chat_is_re_resolved_only_from_the_configured_video():
    api = FakeYouTubeApi(
        videos=[
            _video(chat_id="old-chat"),
            _video(chat_id="new-chat"),
            _video(ended=True),
        ],
        chats=[
            YouTubeApiError(status=404, reason="liveChatNotFound"),
            {
                "nextPageToken": "next",
                "pollingIntervalMillis": 0,
                "items": [_text_message("m-new")],
            },
            YouTubeApiError(status=403, reason="liveChatEnded"),
        ],
    )
    reader = YouTubeLiveChatReader(
        video_id="abcDEF123_-",
        api_key="synthetic-read-key",
        api=api,
    )

    events = asyncio.run(_collect(reader))

    assert events[0].payload["live_chat_id"] == "new-chat"
    assert api.video_calls == ["abcDEF123_-", "abcDEF123_-", "abcDEF123_-"]
    assert [call["live_chat_id"] for call in api.chat_calls] == [
        "old-chat",
        "new-chat",
        "new-chat",
    ]


def test_expired_page_token_rediscovers_and_deduplicates_replayed_history():
    api = FakeYouTubeApi(
        videos=[_video(), _video(), _video(ended=True)],
        chats=[
            {
                "nextPageToken": "expired-token",
                "pollingIntervalMillis": 0,
                "items": [_text_message("m-1")],
            },
            YouTubeApiError(status=400, reason="invalidPageToken"),
            {
                "nextPageToken": "fresh-token",
                "pollingIntervalMillis": 0,
                "items": [
                    _text_message("m-1"),
                    _text_message("m-2", text="nuovo"),
                ],
            },
            YouTubeApiError(status=403, reason="liveChatEnded"),
        ],
    )
    reader = YouTubeLiveChatReader(
        video_id="abcDEF123_-",
        api_key="synthetic-read-key",
        api=api,
    )

    events = asyncio.run(_collect(reader))

    assert [event.payload["message_id"] for event in events] == ["m-1", "m-2"]
    assert [call["page_token"] for call in api.chat_calls] == [
        None,
        "expired-token",
        None,
        "fresh-token",
    ]
    assert api.video_calls == ["abcDEF123_-", "abcDEF123_-", "abcDEF123_-"]
    assert reader.stats().duplicates == 1
    assert reader.outcome is YouTubeChatOutcome.LIVE_ENDED


def test_temporary_failures_retry_with_bounded_backoff_then_fail_closed():
    api = FakeYouTubeApi(
        videos=[_video()],
        chats=[
            YouTubeApiError(status=503, reason="backendError"),
            YouTubeApiError(status=503, reason="backendError"),
            YouTubeApiError(status=503, reason="backendError"),
        ],
    )
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    reader = YouTubeLiveChatReader(
        video_id="abcDEF123_-",
        api_key="synthetic-read-key",
        api=api,
        sleep=fake_sleep,
        max_retries=2,
        retry_base_seconds=1.0,
        retry_max_seconds=8.0,
        jitter=lambda _delay: 0.0,
    )

    with pytest.raises(YouTubeLiveChatError) as raised:
        asyncio.run(_collect(reader))

    assert raised.value.outcome is YouTubeChatOutcome.TEMPORARY_FAILURE
    assert sleeps == [1.0, 2.0]
    assert len(api.chat_calls) == 3


def test_retry_adds_injected_bounded_jitter_without_breaking_fatal_outcome():
    api = FakeYouTubeApi(
        videos=[_video()],
        chats=[
            YouTubeApiError(status=503, reason="backendError"),
            YouTubeApiError(status=403, reason="quotaExceeded"),
        ],
    )
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    reader = YouTubeLiveChatReader(
        video_id="abcDEF123_-",
        api_key="synthetic-read-key",
        api=api,
        sleep=fake_sleep,
        max_retries=2,
        retry_base_seconds=1.0,
        retry_max_seconds=8.0,
        jitter=lambda delay: delay * 0.25,
    )

    with pytest.raises(YouTubeLiveChatError) as raised:
        asyncio.run(_collect(reader))

    assert sleeps == [1.25]
    assert raised.value.outcome is YouTubeChatOutcome.QUOTA_EXHAUSTED


def test_non_finite_server_pacing_and_injected_jitter_fail_closed():
    pacing_api = FakeYouTubeApi(
        videos=[_video()],
        chats=[
            {
                "nextPageToken": "next",
                "pollingIntervalMillis": float("inf"),
                "items": [],
            }
        ],
    )
    pacing_reader = YouTubeLiveChatReader(
        video_id="abcDEF123_-",
        api_key="synthetic-read-key",
        api=pacing_api,
    )

    with pytest.raises(YouTubeLiveChatError) as pacing_error:
        asyncio.run(_collect(pacing_reader))
    assert pacing_error.value.outcome is YouTubeChatOutcome.TEMPORARY_FAILURE

    jitter_api = FakeYouTubeApi(
        videos=[_video()],
        chats=[YouTubeApiError(status=503, reason="backendError")],
    )
    jitter_reader = YouTubeLiveChatReader(
        video_id="abcDEF123_-",
        api_key="synthetic-read-key",
        api=jitter_api,
        jitter=lambda _delay: float("nan"),
    )

    with pytest.raises(YouTubeLiveChatError) as jitter_error:
        asyncio.run(_collect(jitter_reader))
    assert jitter_error.value.outcome is YouTubeChatOutcome.TEMPORARY_FAILURE


def test_stop_interrupts_long_server_pacing_wait_and_cleanup_is_bounded():
    api = FakeYouTubeApi(
        videos=[_video()],
        chats=[
            {
                "nextPageToken": "next",
                "pollingIntervalMillis": 60_000,
                "items": [],
            }
        ],
    )
    reader = YouTubeLiveChatReader(
        video_id="abcDEF123_-",
        api_key="synthetic-read-key",
        api=api,
    )

    async def run() -> None:
        task = asyncio.create_task(_collect(reader))
        while reader.stats().empty_polls == 0:
            await asyncio.sleep(0)
        await reader.stop()
        assert await asyncio.wait_for(task, timeout=0.1) == []

    asyncio.run(run())
    assert reader.outcome is YouTubeChatOutcome.STOPPED
    assert len(api.chat_calls) == 1


def test_rest_transport_uses_only_read_list_endpoints_and_fixed_parts():
    calls: list[tuple[str, dict[str, object], float]] = []

    async def fetch_json(
        endpoint: str, params: dict[str, object], timeout: float
    ) -> Mapping[str, object]:
        calls.append((endpoint, params, timeout))
        return {"items": []}

    transport = YouTubeRestTransport(fetch_json=fetch_json, timeout_seconds=3.0)

    async def run() -> None:
        await transport.get_video(video_id="abcDEF123_-", api_key="synthetic-key")
        await transport.list_messages(
            live_chat_id="synthetic-chat",
            api_key="synthetic-key",
            page_token="next",
            max_results=500,
        )

    asyncio.run(run())

    assert calls[0][0].endswith("/videos")
    assert calls[1][0].endswith("/liveChat/messages")
    assert calls[0][1] == {
        "part": "liveStreamingDetails",
        "id": "abcDEF123_-",
        "key": "synthetic-key",
    }
    assert calls[1][1] == {
        "part": "id,snippet,authorDetails",
        "liveChatId": "synthetic-chat",
        "maxResults": 500,
        "pageToken": "next",
        "key": "synthetic-key",
    }
    assert all("insert" not in endpoint.lower() for endpoint, _, _ in calls)


@pytest.mark.parametrize("timeout", [float("nan"), float("inf")])
def test_rest_transport_rejects_non_finite_timeout(timeout):
    with pytest.raises(ValueError, match="timeout_seconds"):
        YouTubeRestTransport(timeout_seconds=timeout)


@pytest.mark.parametrize(
    "overrides",
    [
        {"retry_base_seconds": float("nan")},
        {"retry_max_seconds": float("inf")},
        {"request_timeout_seconds": float("inf")},
    ],
)
def test_reader_rejects_non_finite_retry_and_request_bounds(overrides):
    with pytest.raises(ValueError, match="finite|bounds|timeout"):
        YouTubeLiveChatReader(
            video_id="abcDEF123_-",
            api_key="synthetic-read-key",
            **overrides,
        )


async def _collect(reader: YouTubeLiveChatReader):
    return [event async for event in reader.events()]
