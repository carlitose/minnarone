"""Single-attempt YouTube Live chat sender.

This is the only component that owns the ``liveChatMessages.insert`` request.
Policy decides whether a candidate may send; this class performs exactly one
HTTP attempt and never queues or retries a stale candidate.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .public_router import PublicSendFailure
from .youtube_oauth import YouTubeCapabilityError

YOUTUBE_LIVE_CHAT_MESSAGES_INSERT_URL = (
    "https://www.googleapis.com/youtube/v3/liveChat/messages?part=snippet"
)
_DEFAULT_TIMEOUT_SECONDS = 10.0
_MAX_RESPONSE_BYTES = 1024 * 1024
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")
_SAFE_REASONS = frozenset(
    {
        "auth_revoked",
        "capability_not_validated",
        "forbidden",
        "identity_malformed",
        "identity_mismatch",
        "live_chat_disabled",
        "live_chat_ended",
        "live_chat_not_found",
        "malformed_response",
        "message_text_invalid",
        "missing_credentials",
        "oauth_failed",
        "oauth_refresh_rejected",
        "oauth_unreachable",
        "provider_rejected",
        "quota_exhausted",
        "rate_limited",
        "scope_mismatch",
        "temporary_failure",
        "token_expired",
    }
)


@dataclass(frozen=True, slots=True)
class YouTubeChatInsertResponse:
    status: int
    body: bytes


InsertTransport = Callable[..., Awaitable[YouTubeChatInsertResponse]]


class YouTubeSendError(PublicSendFailure):
    """Typed, sanitized insert failure consumed by the public router."""

    def __init__(self, reason: str, *, disarms_live: bool = False) -> None:
        self.reason = reason if reason in _SAFE_REASONS else "provider_rejected"
        self.disarms_live = disarms_live
        super().__init__(f"YouTube live chat send failed (reason={self.reason})")


class YouTubeLiveChatIdState:
    """Minimal in-memory handoff from the reader to the sender."""

    def __init__(self) -> None:
        self._value: str | None = None

    def update(self, value: str | None) -> None:
        self._value = value if isinstance(value, str) and value else None

    def current(self) -> str | None:
        return self._value


class YouTubeLiveChatSender:
    """Build and execute one official ``liveChatMessages.insert`` call."""

    def __init__(
        self,
        *,
        live_chat_id: Callable[[], str | None],
        access_token: Callable[[], str],
        insert: InsertTransport | None = None,
        on_disarm: Callable[[str], None] | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        self._live_chat_id = live_chat_id
        self._access_token = access_token
        self._insert = insert or _insert_http
        self._on_disarm = on_disarm
        self._timeout = float(timeout_seconds)

    async def start(self) -> None:
        """No connection is opened; insertion remains per-candidate and lazy."""

    async def stop(self) -> None:
        """No queue or background task exists to drain."""

    async def send(self, message: str) -> str:
        if not isinstance(message, str) or not message:
            raise YouTubeSendError("message_text_invalid")
        live_chat_id = self._live_chat_id()
        if not isinstance(live_chat_id, str) or not live_chat_id:
            raise YouTubeSendError("live_chat_not_found")
        try:
            access_token = self._access_token()
        except YouTubeCapabilityError as exc:
            self._raise(exc.reason, disarms_live=True)
        if not isinstance(access_token, str) or not access_token:
            self._raise("auth_revoked", disarms_live=True)

        body = json.dumps(
            {
                "snippet": {
                    "liveChatId": live_chat_id,
                    "type": "textMessageEvent",
                    "textMessageDetails": {"messageText": message},
                }
            },
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            response = await self._insert(
                url=YOUTUBE_LIVE_CHAT_MESSAGES_INSERT_URL,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                body=body,
                timeout=self._timeout,
            )
        except YouTubeSendError:
            raise
        except (TimeoutError, URLError, OSError, ConnectionError):
            raise YouTubeSendError("temporary_failure") from None

        if response.status not in {200, 201}:
            reason = _classify_insert_failure(response)
            self._raise(reason, disarms_live=reason in {"auth_revoked", "forbidden"})
        payload = _json_object(response.body)
        message_id = payload.get("id")
        if not isinstance(message_id, str) or not _SAFE_ID_RE.fullmatch(message_id):
            raise YouTubeSendError("malformed_response")
        return message_id

    def _raise(self, reason: str, *, disarms_live: bool) -> None:
        if disarms_live and self._on_disarm is not None:
            self._on_disarm(reason)
        raise YouTubeSendError(reason, disarms_live=disarms_live) from None


def _json_object(body: bytes) -> Mapping[str, object]:
    if len(body) > _MAX_RESPONSE_BYTES:
        raise YouTubeSendError("malformed_response")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise YouTubeSendError("malformed_response") from None
    if not isinstance(payload, dict):
        raise YouTubeSendError("malformed_response")
    return payload


def _classify_insert_failure(response: YouTubeChatInsertResponse) -> str:
    if response.status == 401:
        return "auth_revoked"
    provider_reason: str | None = None
    try:
        payload = _json_object(response.body)
        error = payload.get("error")
        if isinstance(error, Mapping):
            errors = error.get("errors")
            if isinstance(errors, list) and errors and isinstance(errors[0], Mapping):
                value = errors[0].get("reason")
                if isinstance(value, str):
                    provider_reason = value
    except YouTubeSendError:
        provider_reason = None
    reasons = {
        "forbidden": "forbidden",
        "liveChatDisabled": "live_chat_disabled",
        "liveChatEnded": "live_chat_ended",
        "messageTextInvalid": "message_text_invalid",
        "liveChatNotFound": "live_chat_not_found",
        "rateLimitExceeded": "rate_limited",
        "quotaExceeded": "quota_exhausted",
    }
    if provider_reason in reasons:
        return reasons[provider_reason]
    if response.status == 429:
        return "rate_limited"
    if response.status >= 500:
        return "temporary_failure"
    return "provider_rejected"


async def _insert_http(**request: object) -> YouTubeChatInsertResponse:
    return await asyncio.to_thread(_insert_http_sync, **request)


def _insert_http_sync(
    *,
    url: str,
    headers: dict[str, str],
    body: bytes,
    timeout: float,
) -> YouTubeChatInsertResponse:
    http_request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(http_request, timeout=timeout) as response:
            return YouTubeChatInsertResponse(
                status=response.status,
                body=response.read(_MAX_RESPONSE_BYTES + 1),
            )
    except HTTPError as exc:
        return YouTubeChatInsertResponse(
            status=exc.code,
            body=exc.read(_MAX_RESPONSE_BYTES + 1),
        )
    except (TimeoutError, URLError, OSError):
        raise YouTubeSendError("temporary_failure") from None
