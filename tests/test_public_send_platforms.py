"""Cross-platform characterization for the public-send safety floor."""

from __future__ import annotations

import asyncio
import inspect
import io
import json
import textwrap

import pytest

from minnarone.app import build_agent
from minnarone.config import Config, ConfigError, TwitchSendConfig, YouTubeSendConfig
from minnarone.output import OutputMode
from minnarone.public_router import PublicOutputRouter, PublicSendFailure
from minnarone.public_send import (
    PublicSendConfig,
    PublicSendMode,
    PublicSendPolicy,
    PublicTarget,
)
from minnarone.run_events import RunEventRecorder
from minnarone.send_commands import SendCommandSurface


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _workspace(tmp_path, *, send: str) -> Config:
    soul = tmp_path / "soul.md"
    soul.write_text("Sono Minnarone.", encoding="utf-8")
    facts = tmp_path / "facts"
    facts.mkdir()
    (facts / "channel.md").write_text("Canale sintetico.", encoding="utf-8")
    path = tmp_path / "youtube.yaml"
    send_block = textwrap.indent(send.strip(), "  ")
    path.write_text(
        f"""mode: public
soul_path: {soul}
facts_dir: {facts}
adapter: youtube
llm_provider: grok
youtube:
  video_id: abcDEF123_-
{send_block}
commentator:
  profiles:
    original_chat: {{}}
""",
        encoding="utf-8",
    )
    return Config.load(path)


def _youtube_agent(tmp_path, monkeypatch, *, send: str):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    cfg = _workspace(tmp_path, send=send)
    return build_agent(cfg, store_path=tmp_path / "perceptions.jsonl")


def test_neutral_policy_types_do_not_import_platform_modules():
    import minnarone.public_router as public_router
    import minnarone.public_send as public_send

    source = inspect.getsource(public_send) + inspect.getsource(public_router)
    assert ".config" not in source
    assert "twitch_" not in source.lower()
    assert "youtube_" not in source.lower()


def test_twitch_and_youtube_translate_identifiers_to_typed_targets():
    twitch = TwitchSendConfig(mode="live", allowed_channels=("#Example",))
    youtube = YouTubeSendConfig(
        mode="live",
        allowed_video_ids=("https://youtube.com/watch?v=abcDEF123_-",),
    )

    assert twitch.allowed_targets == (PublicTarget("twitch", "example"),)
    assert youtube.allowed_targets == (PublicTarget("youtube", "abcDEF123_-"),)


def test_neutral_policy_rejects_a_target_from_another_platform():
    allowed = PublicTarget("youtube", "abcDEF123_-")
    policy = PublicSendPolicy(
        PublicSendConfig(
            mode=PublicSendMode.LIVE,
            allowed_targets=(allowed,),
            max_per_minute=10,
            max_per_hour=10,
        ),
        clock=FakeClock(),
        live_capability=True,
    )

    assert policy.promote() is True
    decision = policy.decide("ciao", PublicTarget("twitch", "abcDEF123_-"))

    assert decision.action == "drop"
    assert decision.reason == "channel_not_allowed"


def test_youtube_off_drops_without_display(tmp_path, monkeypatch):
    agent = _youtube_agent(tmp_path, monkeypatch, send="send:\n  mode: 'off'")
    stream = io.StringIO()
    agent.router._stream = stream

    asyncio.run(agent.router.route("ciao", OutputMode.PUBLIC))

    assert isinstance(agent.router, PublicOutputRouter)
    assert agent.router.last_decision.action == "drop"
    assert agent.router.last_decision.reason == "mode_off"
    assert stream.getvalue() == ""
    assert agent.sender is None
    assert agent.token_guard is None


def test_youtube_shadow_displays_and_consumes_product_budget(tmp_path, monkeypatch):
    agent = _youtube_agent(
        tmp_path,
        monkeypatch,
        send="send:\n  mode: shadow\n  max_per_minute: 1",
    )
    stream = io.StringIO()
    agent.router._stream = stream

    asyncio.run(agent.router.route("primo", OutputMode.PUBLIC))
    asyncio.run(agent.router.route("secondo", OutputMode.PUBLIC))

    assert "[SHADOW] primo" in stream.getvalue()
    assert "secondo" not in stream.getvalue()
    assert agent.router.last_decision.reason == "budget_minute"


def test_youtube_live_is_armed_but_cannot_promote_without_sender_capability(
    tmp_path, monkeypatch
):
    agent = _youtube_agent(
        tmp_path,
        monkeypatch,
        send=(
            "send:\n"
            "  mode: live\n"
            "  allowed_video_ids: [abcDEF123_-]\n"
            "  max_per_minute: 10\n"
            "  max_per_hour: 10"
        ),
    )

    before = agent.send_policy.snapshot()
    accepted = agent.send_policy.promote()
    decision = agent.send_policy.decide("ciao", PublicTarget("youtube", "abcDEF123_-"))

    assert before.mode is PublicSendMode.LIVE
    assert before.promoted is False
    assert accepted is False
    assert decision.action == "shadow"
    assert decision.reason == "not_promoted"
    assert agent.sender is None
    assert agent.token_guard is None

    result = SendCommandSurface(agent.send_policy).promote()
    assert result.accepted is False
    assert "capability" in result.reason


def test_youtube_shadow_records_stable_target_and_reason_in_run_events(tmp_path):
    target = PublicTarget("youtube", "abcDEF123_-")
    policy = PublicSendPolicy(
        PublicSendConfig(mode=PublicSendMode.SHADOW),
        clock=FakeClock(),
        live_capability=False,
    )
    recorder = RunEventRecorder(tmp_path)
    router = PublicOutputRouter(
        policy=policy,
        target=target,
        stream=io.StringIO(),
        event_recorder=recorder,
    )

    asyncio.run(router.route("ciao", OutputMode.PUBLIC))

    event = json.loads((tmp_path / "events.jsonl").read_text().splitlines()[0])
    assert event["send_decision"] == {
        "message": "ciao",
        "action": "shadow",
        "reason": "ok",
        "channel": "abcDEF123_-",
    }


def test_youtube_live_requires_the_explicit_video_id_in_the_allow_list(tmp_path):
    with pytest.raises(ConfigError, match="youtube.send.allowed_video_ids"):
        _workspace(
            tmp_path,
            send="send:\n  mode: live\n  allowed_video_ids: [zzzZZZ999_-]",
        )


class _UnexpectedSender:
    async def send(self, message: str) -> None:
        del message
        raise RuntimeError("programming bug")


class _ExpectedFailureSender:
    def __init__(self) -> None:
        self.calls = 0

    async def send(self, message: str) -> None:
        del message
        self.calls += 1
        raise PublicSendFailure("bounded failure")


def _sending_policy() -> PublicSendPolicy:
    target = PublicTarget("youtube", "abcDEF123_-")
    policy = PublicSendPolicy(
        PublicSendConfig(
            mode=PublicSendMode.LIVE,
            allowed_targets=(target,),
            max_per_minute=10,
            max_per_hour=10,
        ),
        clock=FakeClock(),
        live_capability=True,
    )
    assert policy.promote() is True
    return policy


def test_public_router_does_not_misclassify_generic_exceptions_as_send_failures():
    router = PublicOutputRouter(
        policy=_sending_policy(),
        target=PublicTarget("youtube", "abcDEF123_-"),
        sender=_UnexpectedSender(),
        stream=io.StringIO(),
    )

    with pytest.raises(RuntimeError, match="programming bug"):
        asyncio.run(router.route("ciao", OutputMode.PUBLIC))

    assert router._policy.snapshot().consecutive_failures == 0


def test_public_router_skips_a_failed_turn_without_retry_or_stale_queue():
    sender = _ExpectedFailureSender()
    router = PublicOutputRouter(
        policy=_sending_policy(),
        target=PublicTarget("youtube", "abcDEF123_-"),
        sender=sender,
        stream=io.StringIO(),
    )

    asyncio.run(router.route("ciao", OutputMode.PUBLIC))

    assert sender.calls == 1
    assert router._policy.snapshot().consecutive_failures == 1


def test_ticket_06_has_no_youtube_insert_or_write_token_surface():
    import minnarone.app as app
    import minnarone.config as config
    import minnarone.public_router as public_router
    import minnarone.public_send as public_send

    source = "\n".join(
        inspect.getsource(module)
        for module in (app, config, public_router, public_send)
    )
    assert "liveChatMessages.insert" not in source
    assert "YOUTUBE_OAUTH" not in source
    assert "YOUTUBE_WRITE" not in source
