"""Test del TwitchPublicOutputRouter: tracer bullet shadow (slice 03).

Il router compone la PublicSendPolicy, un display sink locale e un event
recorder. In shadow mode la decisione della policy determina se il messaggio
appare localmente con il marcatore [SHADOW] o viene scartato silenziosamente
(drop). Nessun invio reale: questa slice costruisce solo il percorso shadow.
"""

import asyncio
import io

from minnarone.output import OutputMode, OutputRouter
from minnarone.public_send import (
    ACTION_DROP,
    ACTION_SHADOW,
    REASON_BUDGET_MINUTE,
    REASON_OK,
    SendDecision,
)
from minnarone.shadow_router import TwitchPublicOutputRouter


# --- Fakes per isolamento del router ----------------------------------------


class StubPolicy:
    """Policy stub: ritorna sempre la stessa decisione prefissata."""

    def __init__(self, decision: SendDecision) -> None:
        self._decision = decision

    def decide(self, message: str, channel: str) -> SendDecision:
        return self._decision


def _make_router(
    decision: SendDecision,
    *,
    stream: io.StringIO | None = None,
) -> tuple[TwitchPublicOutputRouter, io.StringIO]:
    buf = stream or io.StringIO()
    router = TwitchPublicOutputRouter(
        policy=StubPolicy(decision),
        channel="testchannel",
        stream=buf,
    )
    return router, buf


# --- 1. Identita e shadow display -------------------------------------------


def test_is_an_output_router():
    router, _ = _make_router(SendDecision(ACTION_SHADOW, REASON_OK))
    assert isinstance(router, OutputRouter)


def test_shadow_decision_displays_message_with_shadow_marker():
    router, buf = _make_router(SendDecision(ACTION_SHADOW, REASON_OK))
    asyncio.run(router.route("ciao a tutti", OutputMode.PUBLIC))
    assert "[SHADOW] ciao a tutti" in buf.getvalue()


# --- 2. Drop non mostra nulla -----------------------------------------------


def test_drop_decision_does_not_display():
    router, buf = _make_router(SendDecision(ACTION_DROP, REASON_BUDGET_MINUTE))
    asyncio.run(router.route("messaggio scartato", OutputMode.PUBLIC))
    assert buf.getvalue() == ""


# --- 3. last_decision espone la decisione della policy ----------------------


def test_last_decision_is_none_before_any_routing():
    router, _ = _make_router(SendDecision(ACTION_SHADOW, REASON_OK))
    assert router.last_decision is None


def test_last_decision_reflects_shadow():
    router, _ = _make_router(SendDecision(ACTION_SHADOW, REASON_OK))
    asyncio.run(router.route("ciao", OutputMode.PUBLIC))
    assert router.last_decision is not None
    assert router.last_decision.action == ACTION_SHADOW
    assert router.last_decision.reason == REASON_OK


def test_last_decision_reflects_drop():
    router, _ = _make_router(SendDecision(ACTION_DROP, REASON_BUDGET_MINUTE))
    asyncio.run(router.route("ciao", OutputMode.PUBLIC))
    assert router.last_decision is not None
    assert router.last_decision.action == ACTION_DROP
    assert router.last_decision.reason == REASON_BUDGET_MINUTE


def test_last_decision_is_none_for_private_mode():
    router, _ = _make_router(SendDecision(ACTION_SHADOW, REASON_OK))
    asyncio.run(router.route("privato", OutputMode.PRIVATE))
    assert router.last_decision is None


# --- 4. Registrazione eventi di invio --------------------------------------


class FakeEventRecorder:
    """Cattura le chiamate a record_send_decision per le asserzioni."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def record_send_decision(
        self,
        *,
        message: str,
        action: str,
        reason: str,
        channel: str,
    ) -> None:
        self.events.append(
            {
                "message": message,
                "action": action,
                "reason": reason,
                "channel": channel,
            }
        )


def test_shadow_records_send_event():
    recorder = FakeEventRecorder()
    router = TwitchPublicOutputRouter(
        policy=StubPolicy(SendDecision(ACTION_SHADOW, REASON_OK)),
        channel="testchannel",
        stream=io.StringIO(),
        event_recorder=recorder,
    )
    asyncio.run(router.route("ciao a tutti", OutputMode.PUBLIC))
    assert len(recorder.events) == 1
    event = recorder.events[0]
    assert event["action"] == ACTION_SHADOW
    assert event["reason"] == REASON_OK
    assert event["channel"] == "testchannel"
    assert event["message"] == "ciao a tutti"


def test_drop_records_send_event():
    recorder = FakeEventRecorder()
    router = TwitchPublicOutputRouter(
        policy=StubPolicy(SendDecision(ACTION_DROP, REASON_BUDGET_MINUTE)),
        channel="testchannel",
        stream=io.StringIO(),
        event_recorder=recorder,
    )
    asyncio.run(router.route("scartato", OutputMode.PUBLIC))
    assert len(recorder.events) == 1
    assert recorder.events[0]["action"] == ACTION_DROP


def test_private_mode_does_not_record_send_event():
    recorder = FakeEventRecorder()
    router = TwitchPublicOutputRouter(
        policy=StubPolicy(SendDecision(ACTION_SHADOW, REASON_OK)),
        channel="testchannel",
        stream=io.StringIO(),
        event_recorder=recorder,
    )
    asyncio.run(router.route("privato", OutputMode.PRIVATE))
    assert len(recorder.events) == 0


# --- 5. RunEventRecorder.record_send_decision --------------------------------

import json

from minnarone.run_events import RunEventRecorder


def test_run_event_recorder_records_send_decision(tmp_path):
    recorder = RunEventRecorder(tmp_path)
    recorder.record_send_decision(
        message="ciao a tutti",
        action="shadow",
        reason="ok",
        channel="testchannel",
    )
    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["kind"] == "send_decision"
    assert event["send_decision"]["action"] == "shadow"
    assert event["send_decision"]["reason"] == "ok"
    assert event["send_decision"]["channel"] == "testchannel"
    assert event["send_decision"]["message"] == "ciao a tutti"


# --- 6. App wiring: selezione del router dalla config -----------------------

from minnarone.app import build_agent
from minnarone.config import Config, TwitchConfig, TwitchSendConfig, TwitchSendMode
from minnarone.console import ConsoleOutputRouter
from minnarone.output import CommentatorStyle


def _fake_transport(*, url, headers, body, timeout):
    from minnarone.openrouter import HttpResponse

    payload = b'{"choices":[{"message":{"content":"ciao"}}]}'
    return HttpResponse(status=200, body=payload)


def _write_workspace(tmp_path, *, send_mode="off"):
    """Workspace minimo per build_agent con adapter twitch + mode public."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    soul = tmp_path / "soul.md"
    soul.write_text("Sono Minnarone, 25 anni.", encoding="utf-8")
    facts = tmp_path / "facts"
    facts.mkdir(exist_ok=True)
    (facts / "canale.md").write_text("Canale test.", encoding="utf-8")

    send_block = f"""\
  send:
    mode: '{send_mode}'
    allowed_channels: [testchannel]
"""
    cfg_text = f"""\
mode: public
soul_path: {soul}
facts_dir: {facts}
adapter: twitch
llm_provider: grok
twitch:
  channel: testchannel
  chat: true
  audio: false
  video: false
{send_block}
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(cfg_text, encoding="utf-8")
    return cfg_path


def test_send_mode_off_uses_console_router(tmp_path, monkeypatch):
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:fake")
    cfg = Config.load(_write_workspace(tmp_path, send_mode="off"))
    agent = build_agent(cfg, transport=_fake_transport)
    assert isinstance(agent.router, ConsoleOutputRouter)


def test_send_mode_shadow_uses_twitch_public_router(tmp_path, monkeypatch):
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:fake")
    cfg = Config.load(_write_workspace(tmp_path, send_mode="shadow"))
    agent = build_agent(cfg, transport=_fake_transport)
    assert isinstance(agent.router, TwitchPublicOutputRouter)


# --- 7. Public Twitch usa il contratto original_chat -------------------------


def test_public_twitch_uses_original_chat_prompt_style(tmp_path, monkeypatch):
    """Twitch + mode: public -> prompt builder usa original_chat style."""
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:fake")
    cfg = Config.load(_write_workspace(tmp_path, send_mode="shadow"))
    agent = build_agent(cfg, transport=_fake_transport)
    assert agent.prompt_builder.commentator_style is CommentatorStyle.ORIGINAL_CHAT


def test_public_twitch_send_off_also_uses_original_chat_prompt_style(
    tmp_path, monkeypatch
):
    """Even with send: off, public Twitch uses original_chat for the persona."""
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:fake")
    cfg = Config.load(_write_workspace(tmp_path, send_mode="off"))
    agent = build_agent(cfg, transport=_fake_transport)
    assert agent.prompt_builder.commentator_style is CommentatorStyle.ORIGINAL_CHAT


# --- 8. Reactor bookkeeping: shadow nota, drop no ---------------------------

from minnarone.fakes import FakeOutputRouter
from minnarone.llm import LLMProvider, LLMResult
from minnarone.perception import Perception, Source
from minnarone.prompt import PromptBuilder
from minnarone.reactor import Reactor
from minnarone.senser import Senser
from minnarone.store import PerceptionStore


class _FakeLLM(LLMProvider):
    """LLM che ritorna un messaggio fisso, formato original_chat."""

    def __init__(self, response: str) -> None:
        self._response = response

    async def complete(self, prompt: str) -> LLMResult:
        return LLMResult(message=self._response)


def _shadow_router_for_reactor(
    *,
    decision: SendDecision,
) -> TwitchPublicOutputRouter:
    return TwitchPublicOutputRouter(
        policy=StubPolicy(decision),
        channel="testchannel",
        stream=io.StringIO(),
    )


def _build_reactor(
    *,
    store: PerceptionStore,
    router: OutputRouter,
    llm_response: str = "RE: test\nMSG: ciao a tutti",
) -> Reactor:
    """Build a minimal reactor with original_chat prompt style."""
    from minnarone.memory import MemoryBlocks

    blocks = MemoryBlocks(soul="Test soul", facts=["test fact"])
    prompt_builder = PromptBuilder(
        blocks,
        commentator_style=CommentatorStyle.ORIGINAL_CHAT,
    )
    senser = Senser(store, agent_name="minnarone")
    return Reactor(
        senser=senser,
        prompt_builder=prompt_builder,
        llm=_FakeLLM(llm_response),
        router=router,
        store=store,
        mode=OutputMode.PUBLIC,
    )


def test_shadow_message_appears_in_recent_messages(tmp_path):
    """A shadow decision should update the reactor's own-message history."""
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    store.append(
        Perception(ts=1.0, source=Source.CHAT, type="msg", text="ehi minnarone", speaker="user1")
    )
    router = _shadow_router_for_reactor(
        decision=SendDecision(ACTION_SHADOW, REASON_OK),
    )
    reactor = _build_reactor(
        store=store,
        router=router,
        llm_response="RE: greeting\nMSG: ciao a tutti",
    )
    asyncio.run(reactor.run_once())
    assert "ciao a tutti" in reactor.recent_messages()


def test_dropped_message_does_not_appear_in_recent_messages(tmp_path):
    """A drop decision should NOT update the reactor's own-message history."""
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    store.append(
        Perception(ts=1.0, source=Source.CHAT, type="msg", text="ehi minnarone", speaker="user1")
    )
    router = _shadow_router_for_reactor(
        decision=SendDecision(ACTION_DROP, REASON_BUDGET_MINUTE),
    )
    reactor = _build_reactor(
        store=store,
        router=router,
        llm_response="RE: greeting\nMSG: ciao a tutti",
    )
    asyncio.run(reactor.run_once())
    assert reactor.recent_messages() == []


# --- 9. #end_conv in public mode: chiude finestra senza shadow ---------------


def test_end_conv_public_does_not_shadow(tmp_path):
    """#end_conv should close the window without generating a shadow message."""
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    store.append(
        Perception(ts=1.0, source=Source.CHAT, type="msg", text="ehi minnarone", speaker="user1")
    )
    buf = io.StringIO()
    router = TwitchPublicOutputRouter(
        policy=StubPolicy(SendDecision(ACTION_SHADOW, REASON_OK)),
        channel="testchannel",
        stream=buf,
    )
    reactor = _build_reactor(
        store=store,
        router=router,
        llm_response="RE: fine\nMSG: #end_conv",
    )
    asyncio.run(reactor.run_once())
    # No shadow message should appear (end_conv skips the router)
    assert buf.getvalue() == ""
    # No self-message history update
    assert reactor.recent_messages() == []
    # The router should not have been called (no last_decision)
    assert router.last_decision is None
