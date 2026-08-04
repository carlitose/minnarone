"""Application wiring for attended YouTube live-send capability."""

from __future__ import annotations

import asyncio
import os

import pytest

from minnarone.app import build_agent
from minnarone.cli import main
from minnarone.config import Config
from minnarone.output import OutputMode
from minnarone.send_commands import SendCommandSurface
from minnarone.source import RawEvent
from minnarone.youtube_chat_sender import (
    YouTubeChatInsertResponse,
    YouTubeSendError,
)
from minnarone.youtube_oauth import (
    YOUTUBE_FORCE_SSL_SCOPE,
    YouTubeCapabilityError,
    YouTubeOAuthClientCredentials,
    YouTubeOAuthToken,
)

APPROVED_CHANNEL_ID = "UCabcdefghijklmnopqrstuv"


def _secret(kind: str) -> str:
    return "-".join(("runtime", "only", kind, "value"))


def _workspace(tmp_path, *, send_mode: str = "live") -> Config:
    soul = tmp_path / "soul.md"
    soul.write_text("Sono Minnarone.", encoding="utf-8")
    facts = tmp_path / "facts"
    facts.mkdir()
    (facts / "channel.md").write_text("Canale sintetico.", encoding="utf-8")
    path = tmp_path / "youtube-live.yaml"
    lines = [
        "mode: public",
        f"soul_path: {soul}",
        f"facts_dir: {facts}",
        "adapter: youtube",
        "llm_provider: grok",
        "agent_name: minnarone",
        "youtube:",
        "  video_id: abcDEF123_-",
        "  send:",
        f"    mode: {send_mode}",
    ]
    if send_mode == "live":
        lines.extend(
            (
                "    allowed_video_ids: [abcDEF123_-]",
                f"    approved_channel_id: {APPROVED_CHANNEL_ID}",
                "    max_per_minute: 10",
                "    max_per_hour: 10",
            )
        )
    lines.extend(("commentator:", "  profiles:", "    original_chat: {}"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return Config.load(path)


class CredentialStore:
    def __init__(self) -> None:
        self.calls = 0

    def load(self):
        self.calls += 1
        return YouTubeOAuthClientCredentials(
            client_id=_secret("client-id"),
            client_secret=_secret("client-secret"),
            refresh_token=_secret("refresh-token"),
        )


class OAuthApi:
    def __init__(
        self, *, fail: bool = False, revoke_after_refreshes: int | None = None
    ) -> None:
        self.fail = fail
        self.revoke_after_refreshes = revoke_after_refreshes
        self.refresh_calls = 0

    async def refresh(self, credentials):
        del credentials
        self.refresh_calls += 1
        if self.fail or (
            self.revoke_after_refreshes is not None
            and self.refresh_calls >= self.revoke_after_refreshes
        ):
            raise YouTubeCapabilityError("auth_revoked")
        return YouTubeOAuthToken(
            access_token=_secret("access-token"),
            scopes=frozenset({YOUTUBE_FORCE_SSL_SCOPE}),
            expires_in=3600,
        )

    async def get_my_channel_id(self, access_token):
        assert access_token == _secret("access-token")
        return APPROVED_CHANNEL_ID


class HoldingAdapter:
    def __init__(self) -> None:
        self.release = asyncio.Event()

    def channels(self):
        return {"chat"}

    def stats(self):
        return None

    async def start(self):
        return None

    async def stop(self):
        self.release.set()

    async def events(self):
        await self.release.wait()
        yield RawEvent(channel="unused", payload=None, ts=0.0)


class QueueAdapter:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[RawEvent | None] = asyncio.Queue()

    def channels(self):
        return {"chat"}

    def stats(self):
        return None

    async def start(self):
        return None

    async def stop(self):
        return None

    async def events(self):
        while (event := await self.queue.get()) is not None:
            yield event


class FakeInsert:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, **request):
        del request
        self.calls += 1
        return YouTubeChatInsertResponse(
            status=200,
            body=b'{"id":"synthetic-sent-message"}',
        )


def test_live_build_is_lazy_then_validates_before_manual_promotion(tmp_path):
    store = CredentialStore()
    oauth = OAuthApi()
    insert = FakeInsert()
    adapter = HoldingAdapter()
    agent = build_agent(
        _workspace(tmp_path),
        store_path=tmp_path / "perceptions.jsonl",
        adapter=adapter,
        youtube_credential_store=store,
        youtube_oauth_api=oauth,
        youtube_insert=insert,
        youtube_live_chat_id=lambda: "synthetic-live-chat",
    )

    assert store.calls == 0
    assert agent.sender is not None
    assert agent.token_guard is not None
    assert agent.send_policy.promote() is False

    async def run() -> None:
        task = asyncio.create_task(agent.run())
        while not agent.token_guard.send_enabled:
            await asyncio.sleep(0)
        snapshot = agent.send_policy.snapshot()
        assert snapshot.live_capability is True
        assert snapshot.promoted is False
        assert SendCommandSurface(agent.send_policy).promote().accepted is True
        await agent.router.route("candidate", OutputMode.PUBLIC)
        adapter.release.set()
        await task

    asyncio.run(run())

    assert store.calls == oauth.refresh_calls == 1
    assert insert.calls == 1


def test_revoked_startup_capability_permanently_stays_shadow(tmp_path):
    store = CredentialStore()
    adapter = HoldingAdapter()
    adapter.release.set()
    agent = build_agent(
        _workspace(tmp_path),
        store_path=tmp_path / "perceptions.jsonl",
        adapter=adapter,
        youtube_credential_store=store,
        youtube_oauth_api=OAuthApi(fail=True),
        youtube_insert=FakeInsert(),
        youtube_live_chat_id=lambda: "synthetic-live-chat",
    )

    asyncio.run(agent.run())

    assert agent.token_guard.send_enabled is False
    assert agent.send_policy.promote() is False
    assert agent.send_policy.snapshot().live_capability is False


def test_periodic_revocation_keeps_observing_in_shadow_until_source_stops(tmp_path):
    store = CredentialStore()
    oauth = OAuthApi(revoke_after_refreshes=2)
    insert = FakeInsert()
    adapter = QueueAdapter()
    agent = build_agent(
        _workspace(tmp_path),
        store_path=tmp_path / "perceptions.jsonl",
        adapter=adapter,
        youtube_credential_store=store,
        youtube_oauth_api=oauth,
        youtube_insert=insert,
        youtube_live_chat_id=lambda: "synthetic-live-chat",
        youtube_oauth_validation_interval=0.001,
    )

    async def run() -> None:
        task = asyncio.create_task(agent.run())
        while not agent.token_guard.send_enabled:
            await asyncio.sleep(0)
        assert SendCommandSurface(agent.send_policy).promote().accepted is True
        await agent.router.route("before revocation", OutputMode.PUBLIC)

        while agent.send_policy.snapshot().live_capability:
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert task.done() is False

        await agent.router.route("after revocation", OutputMode.PUBLIC)
        await adapter.queue.put(
            RawEvent(
                channel="chat",
                payload={
                    "text": "still observing",
                    "speaker": "viewer",
                    "author_channel_id": "UCzyxwvutsrqponmlkjihgf",
                },
                ts=1.0,
            )
        )

        async def wait_until_observed() -> None:
            while not agent.store.tail(1):
                await asyncio.sleep(0)

        await asyncio.wait_for(wait_until_observed(), timeout=1.0)
        await adapter.queue.put(None)
        await task

    asyncio.run(asyncio.wait_for(run(), timeout=2.0))

    assert insert.calls == 1
    assert agent.send_policy.snapshot().live_capability is False
    assert [item.text for item in agent.store.tail(1)] == ["still observing"]


def test_unexpected_periodic_oauth_failure_fails_closed_without_stopping_observation(
    tmp_path, caplog
):
    failure_observed = asyncio.Event()

    class UnexpectedOAuthApi(OAuthApi):
        async def refresh(self, credentials):
            del credentials
            self.refresh_calls += 1
            if self.refresh_calls >= 2:
                failure_observed.set()
                raise RuntimeError(_secret("unexpected-monitor"))
            return YouTubeOAuthToken(
                access_token=_secret("access-token"),
                scopes=frozenset({YOUTUBE_FORCE_SSL_SCOPE}),
                expires_in=3600,
            )

    store = CredentialStore()
    oauth = UnexpectedOAuthApi()
    insert = FakeInsert()
    adapter = QueueAdapter()
    agent = build_agent(
        _workspace(tmp_path),
        store_path=tmp_path / "perceptions.jsonl",
        adapter=adapter,
        youtube_credential_store=store,
        youtube_oauth_api=oauth,
        youtube_insert=insert,
        youtube_live_chat_id=lambda: "synthetic-live-chat",
        youtube_oauth_validation_interval=0.001,
    )

    async def run() -> tuple[YouTubeCapabilityError, YouTubeSendError]:
        task = asyncio.create_task(agent.run())
        try:
            while not agent.token_guard.send_enabled:
                await asyncio.sleep(0)
            assert SendCommandSurface(agent.send_policy).promote().accepted is True
            await agent.router.route("before monitor failure", OutputMode.PUBLIC)

            await asyncio.wait_for(failure_observed.wait(), timeout=1.0)
            await asyncio.sleep(0)
            assert agent.token_guard.send_enabled is False
            with pytest.raises(YouTubeCapabilityError) as token_error:
                agent.token_guard.access_token()
            assert token_error.value.reason == "oauth_failed"
            assert await agent.token_guard.validate_startup() is False

            with pytest.raises(YouTubeSendError) as send_error:
                await agent.sender.send("direct sender bypass")
            assert send_error.value.reason == "oauth_failed"
            assert send_error.value.disarms_live is True

            assert agent.send_policy.snapshot().live_capability is False
            assert task.done() is False
            await agent.router.route("after monitor failure", OutputMode.PUBLIC)
            await adapter.queue.put(
                RawEvent(
                    channel="chat",
                    payload={
                        "text": "observation remains active",
                        "speaker": "viewer",
                        "author_channel_id": "UCzyxwvutsrqponmlkjihgf",
                    },
                    ts=2.0,
                )
            )
            while not agent.store.tail(1):
                await asyncio.sleep(0)
            await adapter.queue.put(None)
            await task
            return token_error.value, send_error.value
        finally:
            if not task.done():
                await adapter.queue.put(None)
            await asyncio.gather(task, return_exceptions=True)

    token_error, send_error = asyncio.run(asyncio.wait_for(run(), timeout=2.0))

    assert insert.calls == 1
    assert oauth.refresh_calls == 2
    assert [item.text for item in agent.store.tail(1)] == ["observation remains active"]
    rendered = caplog.text + str(token_error) + str(send_error)
    assert _secret("unexpected-monitor") not in rendered
    assert _secret("access-token") not in rendered


def test_off_and_shadow_never_load_or_construct_write_capability(tmp_path):
    for mode in ("off", "shadow"):
        workspace = tmp_path / mode
        workspace.mkdir()
        store = CredentialStore()
        agent = build_agent(
            _workspace(workspace, send_mode=mode),
            store_path=workspace / "perceptions.jsonl",
            adapter=HoldingAdapter(),
            youtube_credential_store=store,
            youtube_oauth_api=OAuthApi(),
            youtube_insert=FakeInsert(),
        )
        assert store.calls == 0
        assert agent.sender is None
        assert agent.token_guard is None


def test_cli_check_live_does_not_load_oauth_or_open_network(tmp_path, monkeypatch):
    config = _workspace(tmp_path)
    config_path = tmp_path / "youtube-live.yaml"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    for name in (
        "YOUTUBE_OAUTH_CLIENT_ID",
        "YOUTUBE_OAUTH_CLIENT_SECRET",
        "YOUTUBE_OAUTH_REFRESH_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            (
                f"YOUTUBE_OAUTH_CLIENT_ID={_secret('client-id')}",
                f"YOUTUBE_OAUTH_CLIENT_SECRET={_secret('client-secret')}",
                f"YOUTUBE_OAUTH_REFRESH_TOKEN={_secret('refresh-token')}",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "minnarone.youtube_oauth.EnvYouTubeOAuthCredentialStore.load",
        lambda _self: (_ for _ in ()).throw(
            AssertionError("--check must not load write credentials")
        ),
    )
    monkeypatch.setattr(
        "minnarone.youtube_oauth.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("--check must not open OAuth network")
        ),
    )

    assert config.youtube is not None
    assert main([str(config_path), "--check"]) == 0
    for name in (
        "YOUTUBE_OAUTH_CLIENT_ID",
        "YOUTUBE_OAUTH_CLIENT_SECRET",
        "YOUTUBE_OAUTH_REFRESH_TOKEN",
    ):
        assert name not in os.environ
