"""Twitch OAuth validation and live-session guard behavior."""

import asyncio
import json

import pytest

from minnarone.twitch_auth import (
    TwitchLiveTokenGuard,
    TwitchTokenValidationError,
    TwitchValidateResponse,
    validate_twitch_token,
)


@pytest.mark.parametrize("interval", [0.0, -1.0])
def test_live_guard_rejects_nonpositive_validation_interval(interval):
    with pytest.raises(ValueError, match="interval"):
        TwitchLiveTokenGuard(
            username="minnarone_bot",
            read_token="oauth:read-token",
            send_token="oauth:send-token",
            interval=interval,
        )


def test_validate_twitch_token_accepts_matching_login_scopes_and_expiry():
    calls = []

    def transport(*, token, timeout):
        calls.append((token, timeout))
        return TwitchValidateResponse(
            status=200,
            body=json.dumps(
                {
                    "client_id": "client",
                    "login": "minnarone_bot",
                    "scopes": ["chat:read", "chat:edit"],
                    "user_id": "123",
                    "expires_in": 3600,
                }
            ).encode(),
        )

    result = validate_twitch_token(
        "oauth:secret-token",
        expected_login="minnarone_bot",
        required_scopes={"chat:read"},
        transport=transport,
    )

    assert result.login == "minnarone_bot"
    assert result.scopes == frozenset({"chat:read", "chat:edit"})
    assert result.expires_in == 3600
    assert calls == [("secret-token", 5.0)]


def test_live_guard_revalidates_before_short_token_expiry():
    now = 100.0
    sleeps = []
    calls = []

    def clock():
        return now

    async def sleep(seconds):
        nonlocal now
        sleeps.append(seconds)
        if len(sleeps) > 1:
            raise asyncio.CancelledError
        now += seconds

    def transport(*, token, timeout):
        del timeout
        calls.append(token)
        expires_in = 120 if token == "read-token" else 7200
        return TwitchValidateResponse(
            status=200,
            body=json.dumps(
                {
                    "client_id": "client",
                    "login": "minnarone_bot",
                    "scopes": ["chat:read", "chat:edit"],
                    "user_id": "123",
                    "expires_in": expires_in,
                }
            ).encode(),
        )

    guard = TwitchLiveTokenGuard(
        username="minnarone_bot",
        read_token="oauth:read-token",
        send_token="oauth:send-token",
        transport=transport,
        clock=clock,
        sleep=sleep,
    )

    assert asyncio.run(guard.validate_startup()) is True
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(guard.monitor(on_send_invalid=lambda: asyncio.sleep(0)))

    assert sleeps[0] == pytest.approx(108.0)
    assert calls == ["read-token", "send-token", "read-token"]


def test_live_guard_fails_closed_when_read_token_is_inside_safety_margin():
    def transport(*, token, timeout):
        del timeout
        return TwitchValidateResponse(
            status=200,
            body=json.dumps(
                {
                    "client_id": "client",
                    "login": "minnarone_bot",
                    "scopes": ["chat:read"] if token == "read-token" else ["chat:edit"],
                    "user_id": "123",
                    "expires_in": 1,
                }
            ).encode(),
        )

    guard = TwitchLiveTokenGuard(
        username="minnarone_bot",
        read_token="oauth:read-token",
        send_token="oauth:send-token",
        transport=transport,
    )

    with pytest.raises(TwitchTokenValidationError, match="read token.*expiry"):
        asyncio.run(guard.validate_startup())


def test_live_guard_degrades_when_send_token_is_inside_safety_margin():
    def transport(*, token, timeout):
        del timeout
        is_read = token == "read-token"
        return TwitchValidateResponse(
            status=200,
            body=json.dumps(
                {
                    "client_id": "client",
                    "login": "minnarone_bot",
                    "scopes": ["chat:read" if is_read else "chat:edit"],
                    "user_id": "123",
                    "expires_in": 2 if is_read else 1,
                }
            ).encode(),
        )

    guard = TwitchLiveTokenGuard(
        username="minnarone_bot",
        read_token="oauth:read-token",
        send_token="oauth:send-token",
        transport=transport,
    )

    assert asyncio.run(guard.validate_startup()) is False
    assert guard.send_enabled is False


def test_live_guard_schedules_just_outside_safety_margin_without_hammering():
    now = 0.0
    sleeps = []

    def clock():
        return now

    async def sleep(seconds):
        nonlocal now
        sleeps.append(seconds)
        raise asyncio.CancelledError

    def transport(*, token, timeout):
        del timeout
        is_read = token == "read-token"
        return TwitchValidateResponse(
            status=200,
            body=json.dumps(
                {
                    "client_id": "client",
                    "login": "minnarone_bot",
                    "scopes": ["chat:read" if is_read else "chat:edit"],
                    "user_id": "123",
                    "expires_in": 2 if is_read else 7200,
                }
            ).encode(),
        )

    guard = TwitchLiveTokenGuard(
        username="minnarone_bot",
        read_token="oauth:read-token",
        send_token="oauth:send-token",
        transport=transport,
        clock=clock,
        sleep=sleep,
    )

    async def run():
        assert await guard.validate_startup() is True
        with pytest.raises(asyncio.CancelledError):
            await guard.monitor(on_send_invalid=lambda: asyncio.sleep(0))

    asyncio.run(run())

    assert sleeps == [1.0]


def test_live_guard_uses_absolute_hourly_deadline_after_early_wakeup():
    now = 0.0
    sleeps = []
    calls = []

    def clock():
        return now

    async def sleep(seconds):
        nonlocal now
        sleeps.append(seconds)
        if len(sleeps) == 1:
            now += seconds / 2
        elif len(sleeps) == 2:
            now += seconds
        else:
            raise asyncio.CancelledError

    def transport(*, token, timeout):
        del timeout
        calls.append(token)
        return TwitchValidateResponse(
            status=200,
            body=json.dumps(
                {
                    "client_id": "client",
                    "login": "minnarone_bot",
                    "scopes": ["chat:read", "chat:edit"],
                    "user_id": "123",
                    "expires_in": 7200,
                }
            ).encode(),
        )

    guard = TwitchLiveTokenGuard(
        username="minnarone_bot",
        read_token="oauth:read-token",
        send_token="oauth:send-token",
        transport=transport,
        clock=clock,
        sleep=sleep,
    )

    async def run():
        assert await guard.validate_startup() is True
        with pytest.raises(asyncio.CancelledError):
            await guard.monitor(on_send_invalid=lambda: asyncio.sleep(0))

    asyncio.run(run())

    assert sleeps[:2] == pytest.approx([3600.0, 1800.0])
    assert calls == ["read-token", "send-token", "read-token", "send-token"]


def test_live_guard_hourly_deadline_does_not_drift_with_transport_latency():
    now = 0.0
    sleeps = []
    calls = []

    def clock():
        return now

    async def sleep(seconds):
        nonlocal now
        sleeps.append(seconds)
        if len(sleeps) > 2:
            raise asyncio.CancelledError
        now += seconds

    def transport(*, token, timeout):
        nonlocal now
        del timeout
        calls.append(token)
        now += 600.0
        return TwitchValidateResponse(
            status=200,
            body=json.dumps(
                {
                    "client_id": "client",
                    "login": "minnarone_bot",
                    "scopes": ["chat:read", "chat:edit"],
                    "user_id": "123",
                    "expires_in": 7200,
                }
            ).encode(),
        )

    guard = TwitchLiveTokenGuard(
        username="minnarone_bot",
        read_token="oauth:read-token",
        send_token="oauth:send-token",
        transport=transport,
        clock=clock,
        sleep=sleep,
    )

    async def run():
        assert await guard.validate_startup() is True
        with pytest.raises(asyncio.CancelledError):
            await guard.monitor(on_send_invalid=lambda: asyncio.sleep(0))

    asyncio.run(run())

    assert sleeps == pytest.approx([2400.0, 0.0, 2400.0])
    assert calls == ["read-token", "send-token", "read-token", "send-token"]


def test_live_guard_uses_role_specific_chat_scopes():
    def transport(*, token, timeout):
        del timeout
        scope = "chat:read" if token == "read-token" else "chat:edit"
        return TwitchValidateResponse(
            status=200,
            body=json.dumps(
                {
                    "client_id": "client",
                    "login": "minnarone_bot",
                    "scopes": [scope],
                    "user_id": "123",
                    "expires_in": 3600,
                }
            ).encode(),
        )

    guard = TwitchLiveTokenGuard(
        username="minnarone_bot",
        read_token="oauth:read-token",
        send_token="oauth:send-token",
        transport=transport,
    )

    assert asyncio.run(guard.validate_startup()) is True


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [("client_id", 123), ("user_id", ["123"])],
)
def test_validate_twitch_token_rejects_malformed_identity_metadata_without_secret(
    field, invalid_value
):
    payload = {
        "client_id": "client",
        "login": "minnarone_bot",
        "scopes": ["chat:read"],
        "user_id": "123",
        "expires_in": 3600,
    }
    payload[field] = invalid_value

    def transport(*, token, timeout):
        del token, timeout
        return TwitchValidateResponse(status=200, body=json.dumps(payload).encode())

    with pytest.raises(TwitchTokenValidationError, match="malformed") as caught:
        validate_twitch_token(
            "oauth:never-print-me",
            expected_login="minnarone_bot",
            required_scopes={"chat:read"},
            transport=transport,
        )

    assert "never-print-me" not in str(caught.value)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "client_id": "client",
                "login": "another_bot",
                "scopes": ["chat:read", "chat:edit"],
                "user_id": "123",
                "expires_in": 3600,
            },
            "TWITCH_BOT_USERNAME",
        ),
        (
            {
                "client_id": "client",
                "login": "minnarone_bot",
                "scopes": ["chat:read"],
                "user_id": "123",
                "expires_in": 3600,
            },
            "chat:edit",
        ),
        (
            {
                "client_id": "client",
                "login": "minnarone_bot",
                "scopes": ["chat:read", "chat:edit"],
                "user_id": "123",
                "expires_in": 0,
            },
            "expired",
        ),
    ],
)
def test_validate_twitch_token_rejects_account_scope_or_expiry_without_secret(
    payload, message
):
    def transport(*, token, timeout):
        del token, timeout
        return TwitchValidateResponse(status=200, body=json.dumps(payload).encode())

    with pytest.raises(TwitchTokenValidationError, match=message) as caught:
        validate_twitch_token(
            "oauth:never-print-me",
            expected_login="minnarone_bot",
            required_scopes={"chat:read", "chat:edit"},
            transport=transport,
        )

    assert "never-print-me" not in str(caught.value)


def test_live_guard_send_token_failure_degrades_startup_to_shadow():
    def transport(*, token, timeout):
        del timeout
        if token == "send-token":
            return TwitchValidateResponse(status=401, body=b'{"message":"invalid"}')
        return TwitchValidateResponse(
            status=200,
            body=json.dumps(
                {
                    "client_id": "client",
                    "login": "minnarone_bot",
                    "scopes": ["chat:read", "chat:edit"],
                    "user_id": "123",
                    "expires_in": 3600,
                }
            ).encode(),
        )

    guard = TwitchLiveTokenGuard(
        username="minnarone_bot",
        read_token="oauth:read-token",
        send_token="oauth:send-token",
        transport=transport,
    )

    assert asyncio.run(guard.validate_startup()) is False


def test_live_guard_read_token_failure_stops_startup():
    def transport(*, token, timeout):
        del token, timeout
        return TwitchValidateResponse(status=401, body=b'{"message":"invalid"}')

    guard = TwitchLiveTokenGuard(
        username="minnarone_bot",
        read_token="oauth:read-token",
        send_token="oauth:send-token",
        transport=transport,
    )

    try:
        asyncio.run(guard.validate_startup())
    except TwitchTokenValidationError as exc:
        assert "read token" in str(exc)
        assert "read-token" not in str(exc)
    else:  # pragma: no cover - assertion helper
        raise AssertionError("read-token validation must stop startup")


def test_hourly_send_token_failure_invokes_shadow_fallback_once():
    callback_calls = []
    sleep_calls = 0
    send_calls = 0
    now = 0.0

    def clock():
        return now

    async def sleep(seconds):
        nonlocal now, sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise asyncio.CancelledError
        now += seconds

    def transport(*, token, timeout):
        nonlocal send_calls
        del timeout
        if token == "send-token":
            send_calls += 1
        status = 401 if token == "send-token" and send_calls > 1 else 200
        return TwitchValidateResponse(
            status=status,
            body=json.dumps(
                {
                    "client_id": "client",
                    "login": "minnarone_bot",
                    "scopes": ["chat:read", "chat:edit"],
                    "user_id": "123",
                    "expires_in": 3600,
                }
            ).encode(),
        )

    async def on_send_invalid():
        callback_calls.append("shadow")

    guard = TwitchLiveTokenGuard(
        username="minnarone_bot",
        read_token="oauth:read-token",
        send_token="oauth:send-token",
        transport=transport,
        clock=clock,
        sleep=sleep,
    )

    async def run():
        assert await guard.validate_startup() is True
        try:
            await guard.monitor(on_send_invalid=on_send_invalid)
        except asyncio.CancelledError:
            pass

    asyncio.run(run())

    assert callback_calls == ["shadow"]
    assert guard.send_enabled is False


def test_hourly_read_token_failure_stops_the_guard():
    now = 0.0
    read_calls = 0

    def clock():
        return now

    async def sleep(seconds):
        nonlocal now
        now += seconds

    def transport(*, token, timeout):
        nonlocal read_calls
        del timeout
        if token == "read-token":
            read_calls += 1
        if token == "read-token" and read_calls > 1:
            return TwitchValidateResponse(status=401, body=b'{"message":"invalid"}')
        return TwitchValidateResponse(
            status=200,
            body=json.dumps(
                {
                    "client_id": "client",
                    "login": "minnarone_bot",
                    "scopes": ["chat:read", "chat:edit"],
                    "user_id": "123",
                    "expires_in": 3600,
                }
            ).encode(),
        )

    guard = TwitchLiveTokenGuard(
        username="minnarone_bot",
        read_token="oauth:read-token",
        send_token="oauth:send-token",
        transport=transport,
        clock=clock,
        sleep=sleep,
    )

    async def run():
        assert await guard.validate_startup() is True
        await guard.monitor(on_send_invalid=lambda: asyncio.sleep(0))

    with pytest.raises(TwitchTokenValidationError, match="Twitch read token"):
        asyncio.run(run())
