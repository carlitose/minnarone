"""Read-only YouTube Live chat ingestion.

The external contract comes from the ticket-01 platform report and the
ticket-03 API-key smoke: ``videos.list`` resolves the ephemeral
``activeLiveChatId`` for one explicit video, then ``liveChatMessages.list``
uses ``nextPageToken`` and never polls before ``pollingIntervalMillis``.

This module has no OAuth, write credential, sender, or insert operation.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .source import RawEvent, SourceAdapter
from .youtube_target import YouTubeVideoId

_VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"
_MESSAGES_ENDPOINT = "https://www.googleapis.com/youtube/v3/liveChat/messages"
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_SAFE_REASON_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


class YouTubeChatOutcome(str, Enum):
    """Closed lifecycle/result vocabulary exposed without response payloads."""

    IDLE = "idle"
    ACTIVE = "active"
    NO_MESSAGES = "no_messages"
    VIDEO_ABSENT = "video_absent"
    LIVE_NOT_STARTED = "live_not_started"
    LIVE_ENDED = "live_ended"
    CHAT_DISABLED = "chat_disabled"
    AUTH_FAILED = "auth_failed"
    QUOTA_EXHAUSTED = "quota_exhausted"
    RATE_LIMITED = "rate_limited"
    TEMPORARY_FAILURE = "temporary_failure"
    STOPPED = "stopped"


class YouTubeApiError(RuntimeError):
    """Sanitized external failure: status and documented reason token only."""

    def __init__(self, *, status: int | None, reason: str) -> None:
        safe_reason = reason if _SAFE_REASON_RE.fullmatch(reason) else "apiError"
        self.status = status
        self.reason = safe_reason
        status_text = "network" if status is None else str(status)
        super().__init__(
            f"YouTube API read failed (status={status_text}, reason={safe_reason})"
        )


class YouTubeLiveChatError(RuntimeError):
    """Fatal read outcome; never contains the API key or request URL."""

    def __init__(self, outcome: YouTubeChatOutcome, reason: str) -> None:
        self.outcome = outcome
        self.reason = reason
        super().__init__(f"YouTube live chat stopped: {outcome.value} ({reason})")


class YouTubeApi(Protocol):
    """Fakeable read-only YouTube Data API boundary."""

    async def get_video(
        self, *, video_id: str, api_key: str
    ) -> Mapping[str, object]: ...

    async def list_messages(
        self,
        *,
        live_chat_id: str,
        api_key: str,
        page_token: str | None,
        max_results: int,
    ) -> Mapping[str, object]: ...


JsonFetcher = Callable[[str, dict[str, object], float], Awaitable[Mapping[str, object]]]


class YouTubeRestTransport:
    """Minimal stdlib REST transport containing only YouTube list methods."""

    def __init__(
        self,
        *,
        fetch_json: JsonFetcher | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be > 0")
        self._fetch_json = fetch_json or _fetch_json
        self._timeout_seconds = float(timeout_seconds)

    async def get_video(self, *, video_id: str, api_key: str) -> Mapping[str, object]:
        return await self._fetch_json(
            _VIDEOS_ENDPOINT,
            {
                "part": "liveStreamingDetails",
                "id": video_id,
                "key": api_key,
            },
            self._timeout_seconds,
        )

    async def list_messages(
        self,
        *,
        live_chat_id: str,
        api_key: str,
        page_token: str | None,
        max_results: int,
    ) -> Mapping[str, object]:
        params: dict[str, object] = {
            "part": "id,snippet,authorDetails",
            "liveChatId": live_chat_id,
            "maxResults": max_results,
            "key": api_key,
        }
        if page_token is not None:
            params["pageToken"] = page_token
        return await self._fetch_json(
            _MESSAGES_ENDPOINT,
            params,
            self._timeout_seconds,
        )


@dataclass(frozen=True, slots=True)
class YouTubeChatStats:
    running: bool
    outcome: str
    produced: dict[str, int]
    dropped: dict[str, int]
    failures: dict[str, str]
    pages: int
    messages: int
    duplicates: int
    unsupported_events: int
    empty_polls: int
    retries: int


class YouTubeLiveChatReader(SourceAdapter):
    """Paced, replay-safe REST reader for one explicit YouTube live video."""

    def __init__(
        self,
        *,
        video_id: str,
        api_key: str,
        api: YouTubeApi | None = None,
        max_results: int = 500,
        max_retries: int = 3,
        retry_base_seconds: float = 1.0,
        retry_max_seconds: float = 30.0,
        dedup_capacity: int = 4096,
        request_timeout_seconds: float = 10.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        jitter: Callable[[float], float] | None = None,
        clock: Callable[[], float] = time.time,
        live_chat_id_observer: Callable[[str | None], None] | None = None,
    ) -> None:
        self._video_id = YouTubeVideoId.parse(video_id).value
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("YouTube API key must be non-empty")
        if (
            isinstance(max_results, bool)
            or not isinstance(max_results, int)
            or not 200 <= max_results <= 2000
        ):
            raise ValueError("max_results must be an integer from 200 to 2000")
        if isinstance(max_retries, bool) or not isinstance(max_retries, int):
            raise ValueError("max_retries must be an integer >= 0")
        if max_retries < 0:
            raise ValueError("max_retries must be an integer >= 0")
        if (
            isinstance(retry_base_seconds, bool)
            or not isinstance(retry_base_seconds, (int, float))
            or isinstance(retry_max_seconds, bool)
            or not isinstance(retry_max_seconds, (int, float))
            or not isfinite(retry_base_seconds)
            or not isfinite(retry_max_seconds)
            or retry_base_seconds <= 0
            or retry_max_seconds < retry_base_seconds
        ):
            raise ValueError("retry bounds must be finite, positive, and ordered")
        if (
            isinstance(request_timeout_seconds, bool)
            or not isinstance(request_timeout_seconds, (int, float))
            or not isfinite(request_timeout_seconds)
            or request_timeout_seconds <= 0
        ):
            raise ValueError("request timeout must be finite and > 0")
        if (
            isinstance(dedup_capacity, bool)
            or not isinstance(dedup_capacity, int)
            or dedup_capacity < 1
        ):
            raise ValueError("dedup_capacity must be an integer >= 1")

        self._api_key = api_key
        self._api = api or YouTubeRestTransport(timeout_seconds=request_timeout_seconds)
        self._max_results = max_results
        self._max_retries = max_retries
        self._retry_base = float(retry_base_seconds)
        self._retry_max = float(retry_max_seconds)
        self._dedup_capacity = dedup_capacity
        self._sleep = sleep
        self._jitter = jitter or _default_jitter
        self._clock = clock
        self._live_chat_id_observer = live_chat_id_observer
        self._seen: OrderedDict[tuple[str, str], None] = OrderedDict()
        self._stop_event = asyncio.Event()
        self._running = False
        self._iterating = False
        self._outcome = YouTubeChatOutcome.IDLE
        self._pages = 0
        self._messages = 0
        self._duplicates = 0
        self._unsupported_events = 0
        self._empty_polls = 0
        self._retries = 0
        self._failure: str | None = None

    @property
    def outcome(self) -> YouTubeChatOutcome:
        return self._outcome

    def channels(self) -> set[str]:
        return {"chat"}

    def stats(self) -> YouTubeChatStats:
        return YouTubeChatStats(
            running=self._running,
            outcome=self._outcome.value,
            produced={"chat": self._messages},
            dropped={"chat": 0},
            failures={"chat": self._failure} if self._failure is not None else {},
            pages=self._pages,
            messages=self._messages,
            duplicates=self._duplicates,
            unsupported_events=self._unsupported_events,
            empty_polls=self._empty_polls,
            retries=self._retries,
        )

    async def start(self) -> None:
        """Arm the reader without opening the network (keeps ``--check`` lazy)."""

        if self._running:
            return
        self._stop_event.clear()
        self._running = True
        self._outcome = YouTubeChatOutcome.IDLE
        self._failure = None

    async def stop(self) -> None:
        """Interrupt pacing immediately; safe before start and after completion."""

        if not self._running:
            return
        self._running = False
        self._outcome = YouTubeChatOutcome.STOPPED
        self._stop_event.set()
        self._publish_live_chat_id(None)

    async def events(self) -> AsyncIterator[RawEvent]:
        if self._iterating:
            raise RuntimeError("YouTubeLiveChatReader supports one event consumer")
        if not self._running:
            await self.start()
        self._iterating = True
        try:
            live_chat_id = await self._discover_chat()
            if live_chat_id is None:
                return
            page_token: str | None = None
            next_wait = 0.0
            not_found_retries = 0
            cursor_rediscoveries = 0
            while self._running:
                if next_wait and not await self._wait(next_wait):
                    return
                try:
                    page = await self._request_messages(
                        live_chat_id=live_chat_id,
                        page_token=page_token,
                        pacing_floor=next_wait,
                    )
                except YouTubeApiError as exc:
                    if exc.reason in {"invalidPageToken", "pageTokenExpired"}:
                        if cursor_rediscoveries >= self._max_retries:
                            self._fail(
                                YouTubeChatOutcome.TEMPORARY_FAILURE,
                                exc.reason,
                            )
                        cursor_rediscoveries += 1
                        replacement = await self._discover_chat()
                        if replacement is None:
                            return
                        live_chat_id = replacement
                        page_token = None
                        next_wait = 0.0
                        continue
                    if exc.reason == "liveChatNotFound":
                        if not_found_retries >= self._max_retries:
                            self._fail(
                                YouTubeChatOutcome.CHAT_DISABLED,
                                "liveChatNotFound",
                            )
                        not_found_retries += 1
                        replacement = await self._discover_chat()
                        if replacement is None:
                            return
                        live_chat_id = replacement
                        page_token = None
                        next_wait = 0.0
                        continue
                    outcome = _classify_api_error(exc)
                    if outcome is YouTubeChatOutcome.CHAT_DISABLED:
                        self._outcome = outcome
                        return
                    if outcome is YouTubeChatOutcome.LIVE_ENDED:
                        await self._refresh_terminal_lifecycle(outcome)
                        return
                    self._fail(outcome, exc.reason)

                self._pages += 1
                not_found_retries = 0
                page_token = _optional_string(page.get("nextPageToken"))
                try:
                    next_wait = _poll_seconds(page.get("pollingIntervalMillis"))
                except YouTubeLiveChatError as exc:
                    self._fail(exc.outcome, exc.reason)
                emitted = 0
                for item in _mapping_items(page.get("items")):
                    event = self._normalize_message(item, live_chat_id=live_chat_id)
                    if event is not None:
                        emitted += 1
                        yield event
                if emitted == 0:
                    self._empty_polls += 1
                    self._outcome = YouTubeChatOutcome.NO_MESSAGES
                else:
                    self._outcome = YouTubeChatOutcome.ACTIVE
                if page_token is None:
                    self._fail(
                        YouTubeChatOutcome.TEMPORARY_FAILURE,
                        "missing_next_page_token",
                    )
        finally:
            self._running = False
            self._iterating = False
            self._stop_event.set()
            self._publish_live_chat_id(None)

    async def _discover_chat(self) -> str | None:
        try:
            response = await self._request_with_retry(
                lambda: self._api.get_video(
                    video_id=self._video_id, api_key=self._api_key
                ),
                pacing_floor=0.0,
            )
        except YouTubeApiError as exc:
            self._fail(_classify_api_error(exc), exc.reason)

        items = _mapping_items(response.get("items"))
        if not items:
            self._publish_live_chat_id(None)
            self._outcome = YouTubeChatOutcome.VIDEO_ABSENT
            return None
        details = items[0].get("liveStreamingDetails")
        if not isinstance(details, Mapping):
            self._publish_live_chat_id(None)
            self._outcome = YouTubeChatOutcome.LIVE_NOT_STARTED
            return None
        if _optional_string(details.get("actualEndTime")) is not None:
            self._publish_live_chat_id(None)
            self._outcome = YouTubeChatOutcome.LIVE_ENDED
            return None
        chat_id = _optional_string(details.get("activeLiveChatId"))
        if chat_id is not None:
            self._publish_live_chat_id(chat_id)
            return chat_id
        self._publish_live_chat_id(None)
        if _optional_string(details.get("actualStartTime")) is None:
            self._outcome = YouTubeChatOutcome.LIVE_NOT_STARTED
        else:
            self._outcome = YouTubeChatOutcome.CHAT_DISABLED
        return None

    def _publish_live_chat_id(self, live_chat_id: str | None) -> None:
        if self._live_chat_id_observer is not None:
            self._live_chat_id_observer(live_chat_id)

    async def _refresh_terminal_lifecycle(self, fallback: YouTubeChatOutcome) -> None:
        self._outcome = fallback
        try:
            await self._discover_chat()
        except YouTubeLiveChatError:
            self._outcome = fallback

    async def _request_messages(
        self,
        *,
        live_chat_id: str,
        page_token: str | None,
        pacing_floor: float,
    ) -> Mapping[str, object]:
        return await self._request_with_retry(
            lambda: self._api.list_messages(
                live_chat_id=live_chat_id,
                api_key=self._api_key,
                page_token=page_token,
                max_results=self._max_results,
            ),
            pacing_floor=pacing_floor,
        )

    async def _request_with_retry(
        self,
        request: Callable[[], Awaitable[Mapping[str, object]]],
        *,
        pacing_floor: float,
    ) -> Mapping[str, object]:
        retries = 0
        while self._running:
            try:
                return await request()
            except YouTubeApiError as exc:
                outcome = _classify_api_error(exc)
                retryable = outcome in {
                    YouTubeChatOutcome.RATE_LIMITED,
                    YouTubeChatOutcome.TEMPORARY_FAILURE,
                }
                if not retryable or retries >= self._max_retries:
                    raise
                delay = min(self._retry_base * (2**retries), self._retry_max)
                jitter = self._jitter(delay)
                if (
                    isinstance(jitter, bool)
                    or not isinstance(jitter, (int, float))
                    or not isfinite(jitter)
                    or jitter < 0
                ):
                    raise YouTubeLiveChatError(
                        YouTubeChatOutcome.TEMPORARY_FAILURE,
                        "invalid_retry_jitter",
                    ) from None
                delay = min(delay + float(jitter), self._retry_max)
                delay = max(delay, pacing_floor)
                retries += 1
                self._retries += 1
                if not await self._wait(delay):
                    raise YouTubeLiveChatError(
                        YouTubeChatOutcome.STOPPED, "operator_stop"
                    ) from None
        raise YouTubeLiveChatError(YouTubeChatOutcome.STOPPED, "operator_stop")

    async def _wait(self, delay: float) -> bool:
        if delay <= 0:
            return self._running
        if self._sleep is not None:
            await self._sleep(delay)
            return self._running
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
        except TimeoutError:
            return self._running
        return False

    def _normalize_message(
        self, item: Mapping[str, object], *, live_chat_id: str
    ) -> RawEvent | None:
        snippet = item.get("snippet")
        if not isinstance(snippet, Mapping):
            self._unsupported_events += 1
            return None
        if snippet.get("type") != "textMessageEvent":
            self._unsupported_events += 1
            return None
        message_id = _optional_string(item.get("id"))
        details = snippet.get("textMessageDetails")
        author = item.get("authorDetails")
        if not isinstance(details, Mapping) or not isinstance(author, Mapping):
            self._unsupported_events += 1
            return None
        text = _optional_string(details.get("messageText"))
        speaker = _optional_string(author.get("displayName"))
        author_id = _optional_string(author.get("channelId")) or _optional_string(
            snippet.get("authorChannelId")
        )
        if message_id is None or text is None or speaker is None or author_id is None:
            self._unsupported_events += 1
            return None

        key = (live_chat_id, message_id)
        if key in self._seen:
            self._duplicates += 1
            return None
        self._seen[key] = None
        if len(self._seen) > self._dedup_capacity:
            self._seen.popitem(last=False)

        self._messages += 1
        return RawEvent(
            channel="chat",
            payload={
                "text": text,
                "speaker": speaker,
                "message_id": message_id,
                "author_channel_id": author_id,
                "live_chat_id": live_chat_id,
            },
            ts=_published_at_epoch(snippet.get("publishedAt"), fallback=self._clock),
        )

    def _fail(self, outcome: YouTubeChatOutcome, reason: str) -> None:
        self._outcome = outcome
        self._failure = outcome.value
        raise YouTubeLiveChatError(outcome, reason)


async def _fetch_json(
    endpoint: str, params: dict[str, object], timeout: float
) -> Mapping[str, object]:
    return await asyncio.to_thread(_fetch_json_sync, endpoint, params, timeout)


def _fetch_json_sync(
    endpoint: str, params: dict[str, object], timeout: float
) -> Mapping[str, object]:
    request = Request(
        f"{endpoint}?{urlencode(params)}",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        try:
            raw_error = exc.read(_MAX_RESPONSE_BYTES + 1)
        except OSError:
            raw_error = b""
        raise YouTubeApiError(
            status=exc.code,
            reason=_extract_error_reason(raw_error),
        ) from None
    except (URLError, TimeoutError, OSError):
        raise YouTubeApiError(status=None, reason="networkError") from None
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise YouTubeApiError(status=None, reason="responseTooLarge")
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise YouTubeApiError(status=None, reason="invalidResponse") from None
    if not isinstance(data, Mapping):
        raise YouTubeApiError(status=None, reason="invalidResponse")
    return data


def _extract_error_reason(raw: bytes) -> str:
    try:
        data = json.loads(raw[:_MAX_RESPONSE_BYTES])
        error = data.get("error") if isinstance(data, Mapping) else None
        errors = error.get("errors") if isinstance(error, Mapping) else None
        if isinstance(errors, list) and errors and isinstance(errors[0], Mapping):
            reason = errors[0].get("reason")
            if isinstance(reason, str) and _SAFE_REASON_RE.fullmatch(reason):
                return reason
        status = error.get("status") if isinstance(error, Mapping) else None
        if isinstance(status, str) and _SAFE_REASON_RE.fullmatch(status):
            return status
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    return "apiError"


def _default_jitter(delay: float) -> float:
    """Add up to 25% full-positive jitter while preserving the configured cap."""

    return random.uniform(0.0, delay * 0.25)


def _classify_api_error(error: YouTubeApiError) -> YouTubeChatOutcome:
    reason = error.reason
    if reason == "liveChatEnded":
        return YouTubeChatOutcome.LIVE_ENDED
    if reason in {"liveChatDisabled", "liveChatNotFound"}:
        return YouTubeChatOutcome.CHAT_DISABLED
    if reason in {"quotaExceeded", "dailyLimitExceeded", "dailyLimitExceededUnreg"}:
        return YouTubeChatOutcome.QUOTA_EXHAUSTED
    if reason in {
        "keyInvalid",
        "accessNotConfigured",
        "ipRefererBlocked",
        "forbidden",
        "insufficientPermissions",
    }:
        return YouTubeChatOutcome.AUTH_FAILED
    if reason == "rateLimitExceeded" or error.status == 429:
        return YouTubeChatOutcome.RATE_LIMITED
    if error.status is None or error.status >= 500:
        return YouTubeChatOutcome.TEMPORARY_FAILURE
    return YouTubeChatOutcome.AUTH_FAILED


def _mapping_items(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value


def _poll_seconds(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or value < 0
    ):
        raise YouTubeLiveChatError(
            YouTubeChatOutcome.TEMPORARY_FAILURE, "invalid_polling_interval"
        )
    return float(value) / 1000.0


def _published_at_epoch(value: object, *, fallback: Callable[[], float]) -> float:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return fallback()
