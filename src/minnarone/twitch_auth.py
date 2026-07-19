"""Twitch OAuth validation boundary for attended live chat sessions."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass

TWITCH_VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
_VALIDATE_TIMEOUT_SECONDS = 5.0
_HOURLY_VALIDATION_SECONDS = 60.0 * 60.0
_EXPIRY_SAFETY_RATIO = 0.10
_MIN_EXPIRY_SAFETY_SECONDS = 1.0
_MAX_EXPIRY_SAFETY_SECONDS = 60.0
_READ_SCOPES = frozenset({"chat:read"})
_SEND_SCOPES = frozenset({"chat:edit"})

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TwitchValidateResponse:
    """Raw response returned by the injectable token-validation transport."""

    status: int
    body: bytes


@dataclass(frozen=True, slots=True)
class ValidatedTwitchToken:
    """Validated, non-secret Twitch token metadata."""

    login: str
    scopes: frozenset[str]
    expires_in: int


class TwitchTokenValidationError(RuntimeError):
    """A Twitch token is invalid, expired, mismatched, or lacks required scopes."""


TokenValidationTransport = Callable[..., TwitchValidateResponse]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


_opener = urllib.request.build_opener(_NoRedirect())


def _urllib_validate_transport(*, token: str, timeout: float) -> TwitchValidateResponse:
    request = urllib.request.Request(TWITCH_VALIDATE_URL, method="GET")
    request.add_header("Authorization", f"OAuth {token}")
    try:
        with _opener.open(request, timeout=timeout) as response:
            return TwitchValidateResponse(status=response.status, body=response.read())
    except urllib.error.HTTPError as exc:
        return TwitchValidateResponse(status=exc.code, body=exc.read())
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        raise TwitchTokenValidationError(
            "Twitch token validation is unreachable"
        ) from exc


def validate_twitch_token(
    token: str,
    *,
    expected_login: str,
    required_scopes: Collection[str],
    transport: TokenValidationTransport | None = None,
    timeout: float = _VALIDATE_TIMEOUT_SECONDS,
) -> ValidatedTwitchToken:
    """Validate one user token without leaking its value in errors or results."""
    raw_token = token.strip()
    if raw_token.startswith("oauth:"):
        raw_token = raw_token[len("oauth:") :]
    if not raw_token:
        raise TwitchTokenValidationError("Twitch token is empty")

    response = (transport or _urllib_validate_transport)(
        token=raw_token,
        timeout=timeout,
    )
    if response.status == 401:
        raise TwitchTokenValidationError(
            "Twitch token is invalid or revoked (HTTP 401)"
        )
    if response.status != 200:
        raise TwitchTokenValidationError(
            f"Twitch token validation failed (HTTP {response.status})"
        )
    try:
        payload = json.loads(response.body.decode("utf-8"))
        client_id = payload["client_id"]
        login = payload["login"]
        scopes = payload["scopes"]
        user_id = payload["user_id"]
        expires_in = payload["expires_in"]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise TwitchTokenValidationError(
            "malformed Twitch token validation response"
        ) from exc

    if (
        not isinstance(client_id, str)
        or not client_id.strip()
        or not isinstance(user_id, str)
        or not user_id.strip()
    ):
        raise TwitchTokenValidationError("malformed Twitch token identity metadata")
    if not isinstance(login, str) or login.lower() != expected_login.strip().lower():
        raise TwitchTokenValidationError(
            "Twitch token account does not match TWITCH_BOT_USERNAME"
        )
    if not isinstance(scopes, list) or not all(
        isinstance(scope, str) for scope in scopes
    ):
        raise TwitchTokenValidationError("malformed Twitch token scopes")
    missing = sorted(set(required_scopes) - set(scopes))
    if missing:
        raise TwitchTokenValidationError("missing Twitch scopes: " + ", ".join(missing))
    if (
        not isinstance(expires_in, int)
        or isinstance(expires_in, bool)
        or expires_in <= 0
    ):
        raise TwitchTokenValidationError(
            "Twitch token expired or expires_in is invalid"
        )
    return ValidatedTwitchToken(
        login=login.lower(),
        scopes=frozenset(scopes),
        expires_in=expires_in,
    )


class TwitchLiveTokenGuard:
    """Validate live-session read/write tokens at startup and hourly."""

    def __init__(
        self,
        *,
        username: str,
        read_token: str,
        send_token: str,
        transport: TokenValidationTransport | None = None,
        interval: float = _HOURLY_VALIDATION_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("interval must be positive and finite")
        self._username = username
        self._read_token = read_token
        self._send_token = send_token
        self._transport = transport
        self._interval = interval
        self._clock = clock
        self._sleep = sleep
        self._send_disabled = False
        self._read_deadline: float | None = None
        self._send_deadline: float | None = None

    @property
    def send_enabled(self) -> bool:
        return not self._send_disabled

    def _validate(
        self, token: str, required_scopes: Collection[str]
    ) -> ValidatedTwitchToken:
        return validate_twitch_token(
            token,
            expected_login=self._username,
            required_scopes=required_scopes,
            transport=self._transport,
        )

    async def _validate_read(self) -> ValidatedTwitchToken:
        try:
            token = await asyncio.to_thread(
                self._validate, self._read_token, _READ_SCOPES
            )
            self._ensure_outside_expiry_margin(token)
            return token
        except TwitchTokenValidationError as exc:
            raise TwitchTokenValidationError(f"Twitch read token: {exc}") from exc

    async def _validate_send(self) -> ValidatedTwitchToken:
        try:
            token = await asyncio.to_thread(
                self._validate, self._send_token, _SEND_SCOPES
            )
            self._ensure_outside_expiry_margin(token)
            return token
        except TwitchTokenValidationError as exc:
            raise TwitchTokenValidationError(f"Twitch send token: {exc}") from exc

    @staticmethod
    def _expiry_safety_margin(token: ValidatedTwitchToken) -> float:
        return min(
            _MAX_EXPIRY_SAFETY_SECONDS,
            max(_MIN_EXPIRY_SAFETY_SECONDS, token.expires_in * _EXPIRY_SAFETY_RATIO),
        )

    def _ensure_outside_expiry_margin(self, token: ValidatedTwitchToken) -> None:
        if token.expires_in <= self._expiry_safety_margin(token):
            raise TwitchTokenValidationError(
                "Twitch token is already inside the expiry safety margin"
            )

    def _next_deadline(self, token: ValidatedTwitchToken, *, anchor: float) -> float:
        before_expiry = token.expires_in - self._expiry_safety_margin(token)
        delay = min(self._interval, before_expiry)
        return anchor + delay

    async def validate_startup(self) -> bool:
        """Stop on invalid read token; return False and disarm send on send failure."""
        read_started_at = self._clock()
        read = await self._validate_read()
        self._read_deadline = self._next_deadline(read, anchor=read_started_at)
        send_started_at = self._clock()
        try:
            send = await self._validate_send()
        except TwitchTokenValidationError as exc:
            self._send_disabled = True
            self._send_deadline = None
            logger.warning("Twitch sending disabled: %s", exc)
            return False
        self._send_deadline = self._next_deadline(send, anchor=send_started_at)
        return True

    async def monitor(
        self,
        *,
        on_send_invalid: Callable[[], Awaitable[None]],
    ) -> None:
        """Revalidate hourly; read failure stops the run, send failure disarms it."""
        if self._read_deadline is None:
            raise RuntimeError("validate_startup must run before monitor")
        while True:
            deadlines = [self._read_deadline]
            if not self._send_disabled and self._send_deadline is not None:
                deadlines.append(self._send_deadline)
            next_deadline = min(deadlines)
            await self._sleep(max(0.0, next_deadline - self._clock()))
            now = self._clock()

            if self._read_deadline <= now:
                previous_read_deadline = self._read_deadline
                read = await self._validate_read()
                self._read_deadline = self._next_deadline(
                    read, anchor=previous_read_deadline
                )

            if (
                not self._send_disabled
                and self._send_deadline is not None
                and self._send_deadline <= now
            ):
                try:
                    previous_send_deadline = self._send_deadline
                    send = await self._validate_send()
                except TwitchTokenValidationError as exc:
                    self._send_disabled = True
                    self._send_deadline = None
                    logger.warning("Twitch sending disabled: %s", exc)
                    await on_send_invalid()
                else:
                    self._send_deadline = self._next_deadline(
                        send, anchor=previous_send_deadline
                    )
