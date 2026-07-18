"""Test del TwitchPublicOutputRouter: shadow + live send (slice 03 + 07).

Il router compone la PublicSendPolicy, un display sink locale e un event
recorder. In shadow mode la decisione della policy determina se il messaggio
appare localmente con il marcatore [SHADOW] o viene scartato silenziosamente
(drop). Con un sender collegato, una decisione `send` invoca il sender reale,
mostra il marcatore [SENT] in locale e registra l'evento. Fallimenti del sender
alimentano l'auto-degrado della policy e saltano il turno.
"""

import asyncio
import io

from minnarone.config import TwitchSendMode
from minnarone.output import OutputMode, OutputRouter
from minnarone.public_send import (
    ACTION_DROP,
    ACTION_SEND,
    ACTION_SHADOW,
    REASON_BUDGET_MINUTE,
    REASON_KILL_SWITCH,
    REASON_OK,
    PolicySnapshot,
    SendDecision,
)
from minnarone.shadow_router import TwitchPublicOutputRouter
from minnarone.twitch_chat_sender import TwitchSendConnectionError, TwitchSendError

# --- Fakes per isolamento del router ----------------------------------------


class StubPolicy:
    """Policy stub: ritorna sempre la stessa decisione prefissata."""

    def __init__(self, decision: SendDecision) -> None:
        self._decision = decision

    def decide(self, message: str, channel: str) -> SendDecision:
        return self._decision


class SpyPolicy:
    """Policy with success/failure tracking and configurable auto-degrade."""

    def __init__(
        self,
        decision: SendDecision,
        *,
        failure_threshold: int = 3,
    ) -> None:
        self._decision = decision
        self._failure_threshold = failure_threshold
        self.success_calls = 0
        self.failure_calls = 0
        self._kill_switch = False
        self._promoted = True

    def decide(self, message: str, channel: str) -> SendDecision:
        if self._kill_switch:
            return SendDecision(ACTION_SHADOW, REASON_KILL_SWITCH)
        return self._decision

    def record_success(self) -> None:
        self.success_calls += 1
        self.failure_calls = 0

    def record_failure(self) -> None:
        self.failure_calls += 1
        if self.failure_calls >= self._failure_threshold:
            self._kill_switch = True
            self._promoted = False

    def snapshot(self) -> PolicySnapshot:
        return PolicySnapshot(
            mode=TwitchSendMode.LIVE,
            promoted=self._promoted,
            kill_switch=self._kill_switch,
            consecutive_failures=self.failure_calls,
            minute_remaining=10,
            hour_remaining=20,
            last_decision=self._decision,
        )


class FakeSender:
    """Sender fake: registra i messaggi inviati, opzionalmente fallisce."""

    def __init__(self, *, fail: TwitchSendError | None = None) -> None:
        self.sent: list[str] = []
        self._fail = fail
        self.started = False
        self.stopped = False

    async def send(self, text: str) -> None:
        if self._fail is not None:
            raise self._fail
        self.sent.append(text)

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


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


def test_echo_false_suppresses_stdout_but_keeps_last_decision():
    # Sotto la TUI il display è del pannello (via wrapper); il router non deve
    # stampare su stdout. `last_decision` resta valorizzato per il wrapper.
    buf = io.StringIO()
    router = TwitchPublicOutputRouter(
        policy=StubPolicy(SendDecision(ACTION_SHADOW, REASON_OK)),
        channel="testchannel",
        stream=buf,
        echo=False,
    )
    asyncio.run(router.route("ciao a tutti", OutputMode.PUBLIC))
    assert buf.getvalue() == ""
    assert router.last_decision == SendDecision(ACTION_SHADOW, REASON_OK)


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

# Import di sezione intenzionali: il file è organizzato per slice, ogni
# sezione dichiara accanto ai test ciò che usa.
import json  # noqa: E402

from minnarone.run_events import RunEventRecorder  # noqa: E402


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

# Import di sezione intenzionali (vedi sezione 5).
from minnarone.app import build_agent  # noqa: E402
from minnarone.config import Config  # noqa: E402
from minnarone.console import ConsoleOutputRouter  # noqa: E402
from minnarone.output import CommentatorStyle  # noqa: E402


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

# Import di sezione intenzionali (vedi sezione 5).
from minnarone.llm import LLMProvider, LLMResult  # noqa: E402
from minnarone.perception import Perception, Source  # noqa: E402
from minnarone.prompt import PromptBuilder  # noqa: E402
from minnarone.reactor import Reactor  # noqa: E402
from minnarone.senser import Senser  # noqa: E402
from minnarone.store import PerceptionStore  # noqa: E402


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
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="ehi minnarone",
            speaker="user1",
        )
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
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="ehi minnarone",
            speaker="user1",
        )
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
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="ehi minnarone",
            speaker="user1",
        )
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


# --- 10. Live send: sender invocato su decisione send -------------------------


def test_send_decision_with_sender_calls_send_and_displays_sent_marker():
    """A send decision with a sender calls sender.send() and displays [SENT]."""
    sender = FakeSender()
    policy = SpyPolicy(SendDecision(ACTION_SEND, REASON_OK))
    buf = io.StringIO()
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=buf,
        sender=sender,
    )
    asyncio.run(router.route("ciao a tutti", OutputMode.PUBLIC))
    assert sender.sent == ["ciao a tutti"]
    assert "[SENT] ciao a tutti" in buf.getvalue()


def test_send_decision_calls_policy_record_success():
    """A successful send calls policy.record_success()."""
    sender = FakeSender()
    policy = SpyPolicy(SendDecision(ACTION_SEND, REASON_OK))
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=io.StringIO(),
        sender=sender,
    )
    asyncio.run(router.route("ciao", OutputMode.PUBLIC))
    assert policy.success_calls == 1


def test_send_decision_records_send_event():
    """A successful send records a send_decision event with action=send."""
    recorder = FakeEventRecorder()
    sender = FakeSender()
    policy = SpyPolicy(SendDecision(ACTION_SEND, REASON_OK))
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=io.StringIO(),
        event_recorder=recorder,
        sender=sender,
    )
    asyncio.run(router.route("ciao", OutputMode.PUBLIC))
    assert len(recorder.events) == 1
    assert recorder.events[0]["action"] == ACTION_SEND
    assert recorder.events[0]["reason"] == REASON_OK


def test_send_without_sender_falls_back_to_shadow():
    """A send decision without a sender falls back to [SHADOW] display."""
    policy = SpyPolicy(SendDecision(ACTION_SEND, REASON_OK))
    buf = io.StringIO()
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=buf,
    )
    asyncio.run(router.route("ciao", OutputMode.PUBLIC))
    assert "[SHADOW] ciao" in buf.getvalue()
    assert "[SENT]" not in buf.getvalue()


# --- 11. Sender failure: record, display failed, skip turn --------------------


def test_sender_failure_displays_failed_marker():
    """A sender failure displays [FAILED] marker."""
    sender = FakeSender(fail=TwitchSendConnectionError("connection lost"))
    policy = SpyPolicy(SendDecision(ACTION_SEND, REASON_OK))
    buf = io.StringIO()
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=buf,
        sender=sender,
    )
    asyncio.run(router.route("ciao", OutputMode.PUBLIC))
    assert "[FAILED] ciao" in buf.getvalue()
    assert "[SENT]" not in buf.getvalue()
    assert "[SHADOW]" not in buf.getvalue()


def test_sender_failure_calls_policy_record_failure():
    """A sender failure calls policy.record_failure()."""
    sender = FakeSender(fail=TwitchSendConnectionError("connection lost"))
    policy = SpyPolicy(SendDecision(ACTION_SEND, REASON_OK))
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=io.StringIO(),
        sender=sender,
    )
    asyncio.run(router.route("ciao", OutputMode.PUBLIC))
    assert policy.failure_calls == 1
    assert policy.success_calls == 0


def test_sender_failure_records_failed_event():
    """A sender failure records a send_decision event with action=failed."""
    recorder = FakeEventRecorder()
    sender = FakeSender(fail=TwitchSendConnectionError("connection lost"))
    policy = SpyPolicy(SendDecision(ACTION_SEND, REASON_OK))
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=io.StringIO(),
        event_recorder=recorder,
        sender=sender,
    )
    asyncio.run(router.route("ciao", OutputMode.PUBLIC))
    assert len(recorder.events) >= 1
    failed_events = [e for e in recorder.events if e["action"] == "failed"]
    assert len(failed_events) == 1
    assert "connection lost" in failed_events[0]["reason"]
    assert failed_events[0]["channel"] == "testchannel"


def test_sender_failure_does_not_record_success_event():
    """A failed send must NOT record a success (action=send) event."""
    recorder = FakeEventRecorder()
    sender = FakeSender(fail=TwitchSendConnectionError("connection lost"))
    policy = SpyPolicy(SendDecision(ACTION_SEND, REASON_OK))
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=io.StringIO(),
        event_recorder=recorder,
        sender=sender,
    )
    asyncio.run(router.route("ciao", OutputMode.PUBLIC))
    send_events = [e for e in recorder.events if e["action"] == ACTION_SEND]
    assert len(send_events) == 0


def test_sender_failure_preserves_last_decision_for_bookkeeping():
    """A failed send keeps last_decision as 'send' for reactor bookkeeping.

    The reactor uses last_decision to determine if bookkeeping should run.
    A failed send should be treated as 'sent' for conservative bookkeeping.
    """
    sender = FakeSender(fail=TwitchSendConnectionError("connection lost"))
    policy = SpyPolicy(SendDecision(ACTION_SEND, REASON_OK))
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=io.StringIO(),
        sender=sender,
    )
    asyncio.run(router.route("ciao", OutputMode.PUBLIC))
    assert router.last_decision is not None
    assert router.last_decision.action == ACTION_SEND


# --- 12. Auto-degrade at failure threshold ------------------------------------


def test_auto_degrade_records_transition_event():
    """At failure threshold, auto-degrade records a transition event."""
    recorder = FakeEventRecorder()
    sender = FakeSender(fail=TwitchSendConnectionError("connection lost"))
    policy = SpyPolicy(
        SendDecision(ACTION_SEND, REASON_OK),
        failure_threshold=2,
    )
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=io.StringIO(),
        event_recorder=recorder,
        sender=sender,
    )
    # First failure: below threshold
    asyncio.run(router.route("msg1", OutputMode.PUBLIC))
    degrade_events = [e for e in recorder.events if e["action"] == "auto_degrade"]
    assert len(degrade_events) == 0

    # Second failure: crosses threshold, triggers auto-degrade
    asyncio.run(router.route("msg2", OutputMode.PUBLIC))
    degrade_events = [e for e in recorder.events if e["action"] == "auto_degrade"]
    assert len(degrade_events) == 1
    assert degrade_events[0]["reason"] == "kill_switch"


def test_auto_degrade_flips_subsequent_decisions_to_shadow():
    """After auto-degrade, subsequent decisions are shadow with kill_switch."""
    sender = FakeSender(fail=TwitchSendConnectionError("connection lost"))
    policy = SpyPolicy(
        SendDecision(ACTION_SEND, REASON_OK),
        failure_threshold=2,
    )
    buf = io.StringIO()
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=buf,
        sender=sender,
    )
    # Two failures to trigger auto-degrade
    asyncio.run(router.route("msg1", OutputMode.PUBLIC))
    asyncio.run(router.route("msg2", OutputMode.PUBLIC))

    # Next message: policy is now kill-switched, returns shadow
    asyncio.run(router.route("msg3", OutputMode.PUBLIC))
    assert router.last_decision is not None
    assert router.last_decision.action == ACTION_SHADOW
    assert router.last_decision.reason == REASON_KILL_SWITCH
    # Sender should NOT have been called for the shadow message
    assert sender.sent == []
    assert "[SHADOW] msg3" in buf.getvalue()


# --- 13. Shadow path unchanged with sender present ---------------------------


def test_shadow_decision_with_sender_does_not_call_sender():
    """A shadow decision should never call the sender, even if present."""
    sender = FakeSender()
    policy = SpyPolicy(SendDecision(ACTION_SHADOW, REASON_OK))
    buf = io.StringIO()
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=buf,
        sender=sender,
    )
    asyncio.run(router.route("ciao", OutputMode.PUBLIC))
    assert sender.sent == []
    assert "[SHADOW] ciao" in buf.getvalue()
    assert policy.success_calls == 0
    assert policy.failure_calls == 0


def test_drop_decision_with_sender_does_not_call_sender():
    """A drop decision should never call the sender, even if present."""
    sender = FakeSender()
    policy = SpyPolicy(SendDecision(ACTION_DROP, REASON_BUDGET_MINUTE))
    buf = io.StringIO()
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=buf,
        sender=sender,
    )
    asyncio.run(router.route("ciao", OutputMode.PUBLIC))
    assert sender.sent == []
    assert buf.getvalue() == ""


# --- 14. Bookkeeping: sent message appears in reactor recent -----------------


def test_sent_message_appears_in_recent_messages(tmp_path):
    """A sent message should update the reactor's own-message history."""
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    store.append(
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="ehi minnarone",
            speaker="user1",
        )
    )
    sender = FakeSender()
    policy = SpyPolicy(SendDecision(ACTION_SEND, REASON_OK))
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=io.StringIO(),
        sender=sender,
    )
    reactor = _build_reactor(
        store=store,
        router=router,
        llm_response="RE: greeting\nMSG: ciao a tutti",
    )
    asyncio.run(reactor.run_once())
    assert "ciao a tutti" in reactor.recent_messages()
    assert sender.sent == ["ciao a tutti"]


def test_failed_send_updates_bookkeeping_conservatively(tmp_path):
    """A failed send updates bookkeeping as if sent (conservative per PRD)."""
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    store.append(
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="ehi minnarone",
            speaker="user1",
        )
    )
    sender = FakeSender(fail=TwitchSendConnectionError("connection lost"))
    policy = SpyPolicy(SendDecision(ACTION_SEND, REASON_OK))
    router = TwitchPublicOutputRouter(
        policy=policy,
        channel="testchannel",
        stream=io.StringIO(),
        sender=sender,
    )
    reactor = _build_reactor(
        store=store,
        router=router,
        llm_response="RE: greeting\nMSG: ciao a tutti",
    )
    asyncio.run(reactor.run_once())
    # Conservative bookkeeping: message is remembered even after failure
    assert "ciao a tutti" in reactor.recent_messages()


# --- 15. App wiring: live sessions start shadowed ----------------------------


def test_live_config_starts_shadowed(tmp_path, monkeypatch):
    """Live config + immediate trigger produces shadow, not send."""
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:fake")
    monkeypatch.setenv("TWITCH_SEND_OAUTH_TOKEN", "oauth:fake-write")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    cfg = Config.load(_write_workspace(tmp_path, send_mode="live"))
    agent = build_agent(cfg, transport=_fake_transport)
    assert isinstance(agent.router, TwitchPublicOutputRouter)
    # Feed a mention so the reactor triggers
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="ehi minnarone ci sei?",
            speaker="user1",
        )
    )
    asyncio.run(agent.reactor.run_once())
    # Decision should be shadow (not promoted yet), never send
    assert agent.router.last_decision is not None
    assert agent.router.last_decision.action == ACTION_SHADOW


def test_live_config_wires_sender_into_router(tmp_path, monkeypatch):
    """Live config should construct a sender and wire it into the router."""
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:fake")
    monkeypatch.setenv("TWITCH_SEND_OAUTH_TOKEN", "oauth:fake-write")
    cfg = Config.load(_write_workspace(tmp_path, send_mode="live"))

    async def fake_connect():
        from tests.test_twitch_chat_sender import _FakeIRCStream

        return _FakeIRCStream()

    agent = build_agent(
        cfg,
        transport=_fake_transport,
        twitch_send_connect=fake_connect,
    )
    assert isinstance(agent.router, TwitchPublicOutputRouter)
    assert agent.router._sender is not None
    assert agent.sender is not None


def test_shadow_config_does_not_construct_sender(tmp_path, monkeypatch):
    """Shadow config should not construct a sender."""
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:fake")
    cfg = Config.load(_write_workspace(tmp_path, send_mode="shadow"))
    agent = build_agent(cfg, transport=_fake_transport)
    assert isinstance(agent.router, TwitchPublicOutputRouter)
    assert agent.router._sender is None
    assert agent.sender is None


def test_off_config_does_not_construct_sender(tmp_path, monkeypatch):
    """Off config should not construct a sender."""
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:fake")
    cfg = Config.load(_write_workspace(tmp_path, send_mode="off"))
    agent = build_agent(cfg, transport=_fake_transport)
    assert isinstance(agent.router, ConsoleOutputRouter)
    assert agent.sender is None


# --- 16. Sender lifecycle: agent starts and stops cleanly ---------------------


def test_agent_starts_and_stops_cleanly_with_sender(tmp_path, monkeypatch):
    """Agent starts and stops cleanly with a fake sender in the task group."""
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:fake")
    monkeypatch.setenv("TWITCH_SEND_OAUTH_TOKEN", "oauth:fake-write")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from dataclasses import replace

    from minnarone.fakes import FakeSourceAdapter

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            send_mode="live",
        )
    )
    sender = FakeSender()
    adapter = FakeSourceAdapter([], channels=set())
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        adapter=adapter,
    )
    # Replace the real sender with a fake one for lifecycle testing
    agent = replace(agent, sender=sender, adapter=None, perception_queue=None)

    async def drive():
        task = asyncio.create_task(agent.run())
        await asyncio.sleep(0.05)
        agent.reactor.stop()
        await asyncio.wait_for(task, timeout=5.0)

    asyncio.run(drive())
    assert sender.started is True
    assert sender.stopped is True


def test_agent_surfaces_sender_stop_failure(tmp_path, monkeypatch):
    """Sender stop failure is surfaced, not swallowed."""
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:fake")
    monkeypatch.setenv("TWITCH_SEND_OAUTH_TOKEN", "oauth:fake-write")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from dataclasses import replace

    import pytest

    class FailingStopSender(FakeSender):
        async def stop(self) -> None:
            raise RuntimeError("sender stop exploded")

    cfg = Config.load(
        _write_workspace(tmp_path, send_mode="live"),
    )
    sender = FailingStopSender()
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
    )
    agent = replace(agent, sender=sender, adapter=None, perception_queue=None)

    async def drive():
        task = asyncio.create_task(agent.run())
        await asyncio.sleep(0.05)
        agent.reactor.stop()
        with pytest.raises(RuntimeError, match="sender stop exploded"):
            await asyncio.wait_for(task, timeout=5.0)

    asyncio.run(drive())
