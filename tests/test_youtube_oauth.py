"""Fake-only tests for the YouTube OAuth capability lifecycle."""

from __future__ import annotations

import asyncio
import json

import pytest

from minnarone.youtube_oauth import (
    YOUTUBE_FORCE_SSL_SCOPE,
    YouTubeCapabilityError,
    YouTubeLiveCapabilityGuard,
    YouTubeOAuthClientCredentials,
    YouTubeOAuthHttpResponse,
    YouTubeOAuthRestApi,
    YouTubeOAuthToken,
)

APPROVED_CHANNEL_ID = "UCabcdefghijklmnopqrstuv"


def _secret(kind: str) -> str:
    return "-".join(("runtime", "only", kind, "value"))


class MemoryCredentialStore:
    def __init__(self) -> None:
        self.calls = 0

    def load(self) -> YouTubeOAuthClientCredentials:
        self.calls += 1
        return YouTubeOAuthClientCredentials(
            client_id=_secret("client-id"),
            client_secret=_secret("client-secret"),
            refresh_token=_secret("refresh-token"),
        )


class FakeOAuthApi:
    def __init__(
        self,
        *,
        tokens: list[YouTubeOAuthToken | BaseException],
        channels: list[str | BaseException],
    ) -> None:
        self.tokens = list(tokens)
        self.channels = list(channels)
        self.refresh_calls = 0
        self.channel_calls = 0

    async def refresh(self, credentials):
        assert isinstance(credentials, YouTubeOAuthClientCredentials)
        self.refresh_calls += 1
        result = self.tokens.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    async def get_my_channel_id(self, access_token):
        assert access_token == _secret("access-token")
        self.channel_calls += 1
        result = self.channels.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def _token(*, scopes=frozenset({YOUTUBE_FORCE_SSL_SCOPE}), expires_in=3600):
    return YouTubeOAuthToken(
        access_token=_secret("access-token"),
        scopes=scopes,
        expires_in=expires_in,
    )


def test_guard_loads_credentials_only_on_startup_and_binds_stable_identity():
    store = MemoryCredentialStore()
    api = FakeOAuthApi(tokens=[_token()], channels=[APPROVED_CHANNEL_ID])
    guard = YouTubeLiveCapabilityGuard(
        approved_channel_id=APPROVED_CHANNEL_ID,
        credential_store=store,
        api=api,
    )

    assert store.calls == 0
    assert guard.send_enabled is False
    assert asyncio.run(guard.validate_startup()) is True
    assert guard.send_enabled is True
    assert guard.access_token() == _secret("access-token")
    assert store.calls == api.refresh_calls == api.channel_calls == 1


@pytest.mark.parametrize(
    ("token", "channel", "reason"),
    [
        (_token(scopes=frozenset()), APPROVED_CHANNEL_ID, "scope_mismatch"),
        (_token(), "UCzyxwvutsrqponmlkjihgfe", "identity_mismatch"),
        (_token(expires_in=0), APPROVED_CHANNEL_ID, "token_expired"),
        (
            YouTubeCapabilityError("auth_revoked"),
            APPROVED_CHANNEL_ID,
            "auth_revoked",
        ),
    ],
)
def test_scope_identity_expiry_and_revocation_fail_closed_without_secret_logs(
    token, channel, reason, caplog
):
    store = MemoryCredentialStore()
    api = FakeOAuthApi(tokens=[token], channels=[channel])
    guard = YouTubeLiveCapabilityGuard(
        approved_channel_id=APPROVED_CHANNEL_ID,
        credential_store=store,
        api=api,
    )

    assert asyncio.run(guard.validate_startup()) is False
    assert guard.send_enabled is False
    with pytest.raises(YouTubeCapabilityError) as raised:
        guard.access_token()
    assert raised.value.reason == reason
    rendered = caplog.text + str(raised.value)
    for kind in ("access-token", "client-secret", "refresh-token"):
        assert _secret(kind) not in rendered


def test_periodic_revocation_disarms_once_and_stops_monitor():
    store = MemoryCredentialStore()
    api = FakeOAuthApi(
        tokens=[_token(expires_in=20), YouTubeCapabilityError("auth_revoked")],
        channels=[APPROVED_CHANNEL_ID],
    )
    clock = [0.0]

    async def sleep(delay: float) -> None:
        clock[0] += delay

    guard = YouTubeLiveCapabilityGuard(
        approved_channel_id=APPROVED_CHANNEL_ID,
        credential_store=store,
        api=api,
        interval=5.0,
        clock=lambda: clock[0],
        sleep=sleep,
    )
    callbacks = 0

    async def disarm() -> None:
        nonlocal callbacks
        callbacks += 1

    async def run() -> None:
        assert await guard.validate_startup() is True
        await guard.monitor(on_send_invalid=disarm)

    asyncio.run(run())

    assert callbacks == 1
    assert guard.send_enabled is False
    assert api.refresh_calls == 2


def test_external_disarm_while_monitor_sleeps_prevents_another_refresh():
    store = MemoryCredentialStore()
    api = FakeOAuthApi(
        tokens=[_token(expires_in=20)],
        channels=[APPROVED_CHANNEL_ID],
    )
    clock = [0.0]
    callbacks = 0

    async def run() -> None:
        nonlocal callbacks
        sleeping = asyncio.Event()
        release = asyncio.Event()

        async def sleep(delay: float) -> None:
            clock[0] += delay
            sleeping.set()
            await release.wait()

        async def on_send_invalid() -> None:
            nonlocal callbacks
            callbacks += 1

        guard = YouTubeLiveCapabilityGuard(
            approved_channel_id=APPROVED_CHANNEL_ID,
            credential_store=store,
            api=api,
            interval=5.0,
            clock=lambda: clock[0],
            sleep=sleep,
        )
        assert await guard.validate_startup() is True
        monitor = asyncio.create_task(guard.monitor(on_send_invalid=on_send_invalid))
        await sleeping.wait()
        guard.disarm("auth_revoked")
        release.set()
        await monitor

        assert guard.send_enabled is False
        with pytest.raises(YouTubeCapabilityError, match="auth_revoked"):
            guard.access_token()

    asyncio.run(run())

    assert callbacks == 0
    assert store.calls == api.refresh_calls == api.channel_calls == 1


def test_external_disarm_during_refresh_cannot_restore_capability():
    store = MemoryCredentialStore()
    callbacks = 0

    async def run() -> tuple[YouTubeLiveCapabilityGuard, FakeOAuthApi]:
        nonlocal callbacks
        refreshing = asyncio.Event()
        release = asyncio.Event()

        class BlockingRefreshApi(FakeOAuthApi):
            async def refresh(self, credentials):
                if self.refresh_calls == 1:
                    refreshing.set()
                    await release.wait()
                return await super().refresh(credentials)

        api = BlockingRefreshApi(
            tokens=[_token(expires_in=20), _token(expires_in=20)],
            channels=[APPROVED_CHANNEL_ID],
        )
        clock = [0.0]

        async def sleep(delay: float) -> None:
            clock[0] += delay

        async def on_send_invalid() -> None:
            nonlocal callbacks
            callbacks += 1

        guard = YouTubeLiveCapabilityGuard(
            approved_channel_id=APPROVED_CHANNEL_ID,
            credential_store=store,
            api=api,
            interval=5.0,
            clock=lambda: clock[0],
            sleep=sleep,
        )
        assert await guard.validate_startup() is True
        monitor = asyncio.create_task(guard.monitor(on_send_invalid=on_send_invalid))
        await refreshing.wait()
        guard.disarm("auth_revoked")
        release.set()
        await monitor
        return guard, api

    guard, api = asyncio.run(run())

    assert guard.send_enabled is False
    with pytest.raises(YouTubeCapabilityError, match="auth_revoked"):
        guard.access_token()
    assert callbacks == 0
    assert store.calls == api.refresh_calls == 2
    assert api.channel_calls == 1


def test_access_during_blocked_refresh_disarms_an_expired_token():
    store = MemoryCredentialStore()
    callbacks = 0

    async def run() -> tuple[YouTubeLiveCapabilityGuard, FakeOAuthApi]:
        nonlocal callbacks
        refreshing = asyncio.Event()
        release = asyncio.Event()

        class BlockingRefreshApi(FakeOAuthApi):
            async def refresh(self, credentials):
                if self.refresh_calls == 1:
                    refreshing.set()
                    await release.wait()
                return await super().refresh(credentials)

        api = BlockingRefreshApi(
            tokens=[_token(expires_in=20), _token(expires_in=20)],
            channels=[APPROVED_CHANNEL_ID],
        )
        clock = [0.0]

        async def sleep(delay: float) -> None:
            clock[0] += delay

        async def on_send_invalid() -> None:
            nonlocal callbacks
            callbacks += 1

        guard = YouTubeLiveCapabilityGuard(
            approved_channel_id=APPROVED_CHANNEL_ID,
            credential_store=store,
            api=api,
            interval=5.0,
            clock=lambda: clock[0],
            sleep=sleep,
        )
        assert await guard.validate_startup() is True
        monitor = asyncio.create_task(guard.monitor(on_send_invalid=on_send_invalid))
        await refreshing.wait()
        clock[0] = 20.0
        with pytest.raises(YouTubeCapabilityError) as raised:
            guard.access_token()
        assert raised.value.reason == "token_expired"
        release.set()
        await monitor
        return guard, api

    guard, api = asyncio.run(run())

    assert guard.send_enabled is False
    with pytest.raises(YouTubeCapabilityError) as raised:
        guard.access_token()
    assert raised.value.reason == "token_expired"
    assert callbacks == 0
    assert store.calls == api.refresh_calls == 2
    assert api.channel_calls == 1


def test_external_disarm_during_identity_lookup_cannot_restore_capability():
    store = MemoryCredentialStore()
    callbacks = 0

    async def run() -> tuple[YouTubeLiveCapabilityGuard, FakeOAuthApi]:
        nonlocal callbacks
        resolving_identity = asyncio.Event()
        release = asyncio.Event()

        class BlockingIdentityApi(FakeOAuthApi):
            async def get_my_channel_id(self, access_token):
                if self.channel_calls == 1:
                    resolving_identity.set()
                    await release.wait()
                return await super().get_my_channel_id(access_token)

        api = BlockingIdentityApi(
            tokens=[_token(expires_in=20), _token(expires_in=20)],
            channels=[APPROVED_CHANNEL_ID, APPROVED_CHANNEL_ID],
        )
        clock = [0.0]

        async def sleep(delay: float) -> None:
            clock[0] += delay

        async def on_send_invalid() -> None:
            nonlocal callbacks
            callbacks += 1

        guard = YouTubeLiveCapabilityGuard(
            approved_channel_id=APPROVED_CHANNEL_ID,
            credential_store=store,
            api=api,
            interval=5.0,
            clock=lambda: clock[0],
            sleep=sleep,
        )
        assert await guard.validate_startup() is True
        monitor = asyncio.create_task(guard.monitor(on_send_invalid=on_send_invalid))
        await resolving_identity.wait()
        guard.disarm("auth_revoked")
        release.set()
        await monitor
        return guard, api

    guard, api = asyncio.run(run())

    assert guard.send_enabled is False
    with pytest.raises(YouTubeCapabilityError, match="auth_revoked"):
        guard.access_token()
    assert callbacks == 0
    assert store.calls == api.refresh_calls == api.channel_calls == 2


def test_rest_api_uses_refresh_and_mine_identity_contracts_with_fake_http():
    calls: list[dict[str, object]] = []

    async def fetch(**request):
        calls.append(request)
        if request["url"].endswith("/token"):
            return YouTubeOAuthHttpResponse(
                status=200,
                body=json.dumps(
                    {
                        "access_token": _secret("access-token"),
                        "expires_in": 3600,
                        "scope": YOUTUBE_FORCE_SSL_SCOPE,
                        "token_type": "Bearer",
                    }
                ).encode(),
            )
        return YouTubeOAuthHttpResponse(
            status=200,
            body=json.dumps({"items": [{"id": APPROVED_CHANNEL_ID}]}).encode(),
        )

    api = YouTubeOAuthRestApi(fetch=fetch)
    credentials = MemoryCredentialStore().load()

    async def run():
        token = await api.refresh(credentials)
        channel_id = await api.get_my_channel_id(token.access_token)
        return token, channel_id

    token, channel_id = asyncio.run(run())

    assert token.scopes == frozenset({YOUTUBE_FORCE_SSL_SCOPE})
    assert channel_id == APPROVED_CHANNEL_ID
    assert calls[0]["url"] == "https://oauth2.googleapis.com/token"
    assert calls[0]["method"] == "POST"
    assert calls[0]["form"]["grant_type"] == "refresh_token"
    assert calls[1]["url"].endswith("/youtube/v3/channels?part=id&mine=true")
    assert calls[1]["headers"]["Authorization"] == f"Bearer {_secret('access-token')}"


@pytest.mark.parametrize(
    ("status", "body", "reason"),
    [
        (401, b"not-json", "auth_revoked"),
        (503, b"not-json", "temporary_failure"),
    ],
)
def test_refresh_status_is_classified_without_exposing_untrusted_body(
    status, body, reason
):
    async def fetch(**request):
        del request
        return YouTubeOAuthHttpResponse(status=status, body=body)

    api = YouTubeOAuthRestApi(fetch=fetch)

    with pytest.raises(YouTubeCapabilityError) as raised:
        asyncio.run(api.refresh(MemoryCredentialStore().load()))

    assert raised.value.reason == reason
    assert "not-json" not in str(raised.value)
