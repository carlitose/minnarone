"""Lazy, redacted OAuth capability validation for YouTube live sending.

The authorization-code acquisition flow is intentionally outside the runtime.
This module only loads an already-provisioned refresh credential at live
startup, refreshes it, verifies the granted scope and binds it to one approved
stable YouTube channel ID through ``channels.list(mine=true)``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import time
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .youtube_target import YouTubeChannelId

YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"
YOUTUBE_FORCE_SSL_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
YOUTUBE_OAUTH_CLIENT_ID_ENV_VAR = "YOUTUBE_OAUTH_CLIENT_ID"
YOUTUBE_OAUTH_CLIENT_SECRET_ENV_VAR = "YOUTUBE_OAUTH_CLIENT_SECRET"
YOUTUBE_OAUTH_REFRESH_TOKEN_ENV_VAR = "YOUTUBE_OAUTH_REFRESH_TOKEN"

_ACCEPTED_SEND_SCOPES = frozenset({YOUTUBE_SCOPE, YOUTUBE_FORCE_SSL_SCOPE})
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_MINE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels?part=id&mine=true"
_DEFAULT_TIMEOUT_SECONDS = 5.0
_DEFAULT_INTERVAL_SECONDS = 60.0 * 60.0
_MAX_RESPONSE_BYTES = 1024 * 1024
_SAFE_REASON_RE = re.compile(r"^[a-z0-9_]{1,80}$")

logger = logging.getLogger(__name__)


class YouTubeCapabilityError(RuntimeError):
    """A closed, machine-safe capability failure without provider payloads."""

    def __init__(self, reason: str) -> None:
        self.reason = reason if _SAFE_REASON_RE.fullmatch(reason) else "oauth_failed"
        super().__init__(f"YouTube live capability unavailable ({self.reason})")


@dataclass(frozen=True, slots=True)
class YouTubeOAuthClientCredentials:
    """Secret refresh inputs; values never cross the OAuth boundary."""

    client_id: str
    client_secret: str
    refresh_token: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value.strip()
            for value in (self.client_id, self.client_secret, self.refresh_token)
        ):
            raise YouTubeCapabilityError("missing_credentials")


@dataclass(frozen=True, slots=True)
class YouTubeOAuthToken:
    """In-memory access token plus non-secret validation metadata."""

    access_token: str
    scopes: frozenset[str]
    expires_in: int


@dataclass(frozen=True, slots=True)
class YouTubeOAuthHttpResponse:
    status: int
    body: bytes


class YouTubeCredentialStore(Protocol):
    def load(self) -> YouTubeOAuthClientCredentials: ...


class YouTubeOAuthApi(Protocol):
    async def refresh(
        self, credentials: YouTubeOAuthClientCredentials
    ) -> YouTubeOAuthToken: ...

    async def get_my_channel_id(self, access_token: str) -> str: ...


class EnvYouTubeOAuthCredentialStore:
    """Load write credentials lazily from the process environment."""

    def load(self) -> YouTubeOAuthClientCredentials:
        values = (
            os.environ.get(YOUTUBE_OAUTH_CLIENT_ID_ENV_VAR),
            os.environ.get(YOUTUBE_OAUTH_CLIENT_SECRET_ENV_VAR),
            os.environ.get(YOUTUBE_OAUTH_REFRESH_TOKEN_ENV_VAR),
        )
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise YouTubeCapabilityError("missing_credentials")
        client_id, client_secret, refresh_token = values
        assert client_id is not None
        assert client_secret is not None
        assert refresh_token is not None
        return YouTubeOAuthClientCredentials(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
        )


OAuthFetcher = Callable[..., Awaitable[YouTubeOAuthHttpResponse]]


class YouTubeOAuthRestApi:
    """Small OAuth/identity client; it never owns chat insertion."""

    def __init__(
        self,
        *,
        fetch: OAuthFetcher | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        self._fetch = fetch or _fetch_oauth_http
        self._timeout = float(timeout_seconds)

    async def refresh(
        self, credentials: YouTubeOAuthClientCredentials
    ) -> YouTubeOAuthToken:
        response = await self._fetch(
            url=_TOKEN_URL,
            method="POST",
            headers={"Accept": "application/json"},
            form={
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "refresh_token": credentials.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=self._timeout,
        )
        if response.status == 401:
            raise YouTubeCapabilityError("auth_revoked")
        if response.status >= 500:
            raise YouTubeCapabilityError("temporary_failure")
        if response.status != 200:
            try:
                provider_error = _json_object(response.body).get("error")
            except YouTubeCapabilityError:
                provider_error = None
            if provider_error == "invalid_grant":
                raise YouTubeCapabilityError("auth_revoked")
            raise YouTubeCapabilityError("oauth_refresh_rejected")
        payload = _json_object(response.body)

        access_token = payload.get("access_token")
        scope = payload.get("scope")
        expires_in = payload.get("expires_in")
        token_type = payload.get("token_type")
        if (
            not isinstance(access_token, str)
            or not access_token.strip()
            or not isinstance(scope, str)
            or not isinstance(expires_in, int)
            or isinstance(expires_in, bool)
            or not isinstance(token_type, str)
            or token_type.lower() != "bearer"
        ):
            raise YouTubeCapabilityError("malformed_oauth_response")
        return YouTubeOAuthToken(
            access_token=access_token,
            scopes=frozenset(scope.split()),
            expires_in=expires_in,
        )

    async def get_my_channel_id(self, access_token: str) -> str:
        response = await self._fetch(
            url=_MINE_CHANNEL_URL,
            method="GET",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            form=None,
            timeout=self._timeout,
        )
        if response.status == 401:
            raise YouTubeCapabilityError("auth_revoked")
        if response.status == 403:
            raise YouTubeCapabilityError("forbidden")
        if response.status != 200:
            reason = (
                "temporary_failure"
                if response.status >= 500
                else "identity_lookup_failed"
            )
            raise YouTubeCapabilityError(reason)
        payload = _json_object(response.body)
        items = payload.get("items")
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise YouTubeCapabilityError("identity_missing")
        channel_id = items[0].get("id")
        try:
            normalized_channel_id = YouTubeChannelId.parse(channel_id).value
        except ValueError:
            raise YouTubeCapabilityError("identity_malformed") from None
        return normalized_channel_id


class YouTubeLiveCapabilityGuard:
    """Refresh and validate one YouTube write identity for an attended session."""

    def __init__(
        self,
        *,
        approved_channel_id: str,
        credential_store: YouTubeCredentialStore,
        api: YouTubeOAuthApi,
        required_scopes: Collection[str] = _ACCEPTED_SEND_SCOPES,
        interval: float = _DEFAULT_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        try:
            approved_channel_id = YouTubeChannelId.parse(approved_channel_id).value
        except ValueError:
            raise ValueError(
                "approved_channel_id must be a stable YouTube channel ID"
            ) from None
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("interval must be positive and finite")
        scopes = frozenset(required_scopes)
        if not scopes:
            raise ValueError("required_scopes must not be empty")
        self._approved_channel_id = approved_channel_id
        self._credential_store = credential_store
        self._api = api
        self._required_scopes = scopes
        self._interval = float(interval)
        self._clock = clock
        self._sleep = sleep
        self._access_token: str | None = None
        self._expires_at: float | None = None
        self._deadline: float | None = None
        self._disabled = False
        self._validated = False
        self._failure_reason = "capability_not_validated"

    @property
    def send_enabled(self) -> bool:
        return (
            self._validated
            and not self._disabled
            and self._access_token is not None
            and self._expires_at is not None
            and self._clock() < self._expires_at
        )

    def access_token(self) -> str:
        if self._expires_at is not None and self._clock() >= self._expires_at:
            self.disarm("token_expired")
        if not self.send_enabled or self._access_token is None:
            raise YouTubeCapabilityError(self._failure_reason)
        return self._access_token

    def disarm(self, reason: str = "auth_revoked") -> None:
        safe_reason = reason if _SAFE_REASON_RE.fullmatch(reason) else "oauth_failed"
        self._disabled = True
        self._validated = False
        self._access_token = None
        self._expires_at = None
        self._deadline = None
        self._failure_reason = safe_reason

    async def validate_startup(self) -> bool:
        if self._disabled:
            return False
        try:
            validated = await self._refresh_and_validate(anchor=self._clock())
        except YouTubeCapabilityError as exc:
            if self._disabled:
                return False
            self.disarm(exc.reason)
            logger.warning("YouTube live sending disabled: %s", exc)
            return False
        return validated

    async def monitor(
        self,
        *,
        on_send_invalid: Callable[[], Awaitable[None]],
    ) -> None:
        if self._deadline is None or not self.send_enabled:
            raise RuntimeError("validate_startup must succeed before monitor")
        while self.send_enabled and self._deadline is not None:
            deadline = self._deadline
            try:
                await self._sleep(max(0.0, deadline - self._clock()))
                if (
                    not self._disabled
                    and self._expires_at is not None
                    and self._clock() >= self._expires_at
                ):
                    self.disarm("token_expired")
                    logger.warning(
                        "YouTube live sending disabled: %s",
                        YouTubeCapabilityError("token_expired"),
                    )
                    await on_send_invalid()
                    return
                if not self.send_enabled or self._deadline is None:
                    return
                validated = await self._refresh_and_validate(anchor=deadline)
            except YouTubeCapabilityError as exc:
                if self._disabled:
                    return
                reason = exc.reason
            except Exception:
                if self._disabled:
                    return
                reason = "oauth_failed"
            else:
                if not validated:
                    return
                continue
            self.disarm(reason)
            logger.warning(
                "YouTube live sending disabled: %s",
                YouTubeCapabilityError(reason),
            )
            await on_send_invalid()
            return

    async def _refresh_and_validate(self, *, anchor: float) -> bool:
        if self._disabled:
            return False
        credentials = await asyncio.to_thread(self._credential_store.load)
        if self._disabled:
            return False
        token = await self._api.refresh(credentials)
        if self._disabled:
            return False
        if (
            not isinstance(token.access_token, str)
            or not token.access_token.strip()
            or not isinstance(token.expires_in, int)
            or isinstance(token.expires_in, bool)
            or token.expires_in <= 0
        ):
            raise YouTubeCapabilityError("token_expired")
        if not (token.scopes & self._required_scopes):
            raise YouTubeCapabilityError("scope_mismatch")
        margin = min(60.0, max(1.0, token.expires_in * 0.10))
        usable_for = token.expires_in - margin
        if usable_for <= 0:
            raise YouTubeCapabilityError("token_expired")
        channel_id = await self._api.get_my_channel_id(token.access_token)
        if self._disabled:
            return False
        if channel_id != self._approved_channel_id:
            raise YouTubeCapabilityError("identity_mismatch")
        expires_at = anchor + token.expires_in
        if self._clock() >= expires_at:
            raise YouTubeCapabilityError("token_expired")
        self._access_token = token.access_token
        self._expires_at = expires_at
        self._validated = True
        self._failure_reason = "ok"
        self._deadline = anchor + min(self._interval, usable_for)
        return True


def _json_object(body: bytes) -> dict[str, object]:
    if len(body) > _MAX_RESPONSE_BYTES:
        raise YouTubeCapabilityError("response_too_large")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise YouTubeCapabilityError("malformed_oauth_response") from None
    if not isinstance(payload, dict):
        raise YouTubeCapabilityError("malformed_oauth_response")
    return payload


async def _fetch_oauth_http(**request: object) -> YouTubeOAuthHttpResponse:
    return await asyncio.to_thread(_fetch_oauth_http_sync, **request)


def _fetch_oauth_http_sync(
    *,
    url: str,
    method: str,
    headers: dict[str, str],
    form: dict[str, str] | None,
    timeout: float,
) -> YouTubeOAuthHttpResponse:
    body = urlencode(form).encode("ascii") if form is not None else None
    request_headers = dict(headers)
    if body is not None:
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    http_request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(http_request, timeout=timeout) as response:
            return YouTubeOAuthHttpResponse(
                status=response.status,
                body=response.read(_MAX_RESPONSE_BYTES + 1),
            )
    except HTTPError as exc:
        return YouTubeOAuthHttpResponse(
            status=exc.code,
            body=exc.read(_MAX_RESPONSE_BYTES + 1),
        )
    except (TimeoutError, URLError, OSError):
        raise YouTubeCapabilityError("oauth_unreachable") from None
