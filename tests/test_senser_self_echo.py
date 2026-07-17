"""Test del filtro self-echo nel Senser (issue 06).

Le percezioni chat inviate dal bot stesso (eco IRC) devono:
- restare nel PerceptionStore (log fidelity)
- NON produrre trigger (menzione, continuazione, idle)
- NON apparire come chat di terzi nel prompt (filtrate in selezione recente)

Il filtro è basato sul `bot_identity` (send-account username, lowercased).
Se assente (non-Twitch adapter), il filtro è un no-op.
"""

from minnarone.chat import ChatPerceiver
from minnarone.senser import Senser
from minnarone.store import PerceptionStore


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# --- Cycle 1: construction ---------------------------------------------------


def test_senser_accepts_bot_identity_parameter(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    senser = Senser(store, agent_name="Minnarone", bot_identity="minnabot")
    assert senser is not None


# --- Cycle 2: self chat perception does not trigger ---------------------------


def test_self_chat_perception_produces_no_trigger(tmp_path):
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(
        store, agent_name="Minnarone", bot_identity="minnabot", clock=clock
    )
    # The bot's own message echoed back by IRC - contains a mention of itself
    chat.perceive("ciao a tutti sono minnarone", speaker="minnabot", ts=1.0)
    triggers = senser.tick()
    assert triggers == []


# --- Cycle 3: self mention (even fuzzy) does not trigger ----------------------


def test_self_mention_of_agent_name_produces_no_trigger(tmp_path):
    """A self message mentioning the agent's name must not trigger (fuzzy incl.)."""
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(
        store, agent_name="Minnarone", bot_identity="minnabot", clock=clock
    )
    # The bot mentions its own name in the echoed message
    chat.perceive("ehi minnarone ci sono", speaker="minnabot", ts=1.0)
    assert senser.tick() == []
    # Also test fuzzy match (storpiato)
    chat.perceive("minarone test", speaker="minnabot", ts=2.0)
    assert senser.tick() == []


# --- Cycle 4: case-insensitive speaker matching ------------------------------


def test_self_echo_filter_is_case_insensitive(tmp_path):
    """Twitch normalizes usernames; the filter must be case-insensitive."""
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    # bot_identity uppercase, speaker lowercase (and vice versa)
    senser = Senser(
        store, agent_name="Minnarone", bot_identity="MinnaBot", clock=clock
    )
    chat.perceive("ciao", speaker="minnabot", ts=1.0)
    assert senser.tick() == []
    chat.perceive("ciao", speaker="MINNABOT", ts=2.0)
    assert senser.tick() == []
    chat.perceive("ciao", speaker="MinnaBot", ts=3.0)
    assert senser.tick() == []


# --- Cycle 5: third-party messages still trigger normally ---------------------


def test_third_party_mention_still_triggers_with_bot_identity_set(tmp_path):
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(
        store, agent_name="Minnarone", bot_identity="minnabot", clock=clock
    )
    chat.perceive("ehi minnarone!", speaker="enkk", ts=1.0)
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].kind == "mention"
    assert triggers[0].interlocutor == "enkk"


# --- Cycle 6: no bot_identity = no-op filter ---------------------------------


def test_no_bot_identity_allows_all_speakers(tmp_path):
    """Without bot_identity, even a speaker named like a bot triggers normally."""
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone", clock=clock)  # no bot_identity
    chat.perceive("ehi minnarone", speaker="minnabot", ts=1.0)
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].kind == "mention"


# --- Cycle 7: self perceptions remain in store --------------------------------


def test_self_perception_remains_in_store(tmp_path):
    """Self perceptions stay in perceptions.jsonl unmodified (log fidelity)."""
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(
        store, agent_name="Minnarone", bot_identity="minnabot", clock=clock
    )
    chat.perceive("messaggio del bot", speaker="minnabot", ts=1.0)
    assert senser.tick() == []  # no trigger
    # But the perception is still in the store
    stored = store.tail(10)
    assert len(stored) == 1
    assert stored[0].speaker == "minnabot"
    assert stored[0].text == "messaggio del bot"


# --- Cycle 8: self perception does not open a window --------------------------


def test_self_perception_does_not_open_conversation_window(tmp_path):
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(
        store, agent_name="Minnarone", bot_identity="minnabot", clock=clock
    )
    # Self message mentioning agent name - would normally open a window
    chat.perceive("ehi minnarone", speaker="minnabot", ts=1.0)
    senser.tick()
    assert senser.open_windows() == {}


# --- Cycle 9: self perception does not trigger continuation -------------------


def test_self_perception_does_not_trigger_continuation(tmp_path):
    """Even with an open window, the bot's own echo must not continue."""
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(
        store, agent_name="Minnarone", bot_identity="minnabot", clock=clock
    )
    # Open a window via third-party mention
    chat.perceive("minnarone ciao", speaker="enkk", ts=1.0)
    assert senser.tick()[0].kind == "mention"
    # Agent responds
    clock.advance(2.0)
    senser.note_agent_message(clock())
    # Now the bot's own echoed message arrives (within continuation window)
    clock.advance(1.0)
    chat.perceive("risposta del bot", speaker="minnabot", ts=clock())
    triggers = senser.tick()
    assert all(t.kind != "continuation" for t in triggers)


# --- Cycle 10: self perceptions filtered from recent prompt context -----------


def test_self_perception_excluded_from_reactor_recent_for_prompt(tmp_path):
    """Self chat perceptions must not appear as third-party chat in the prompt."""
    import asyncio

    from minnarone.llm import LLMResult
    from minnarone.output import OutputMode
    from minnarone.reactor import Reactor

    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(
        store, agent_name="Minnarone", bot_identity="minnabot", clock=clock
    )

    # Record a few perceptions: one from bot, one from third party
    chat.perceive("bot risposta", speaker="minnabot", ts=1.0)
    chat.perceive("ciao a tutti", speaker="enkk", ts=2.0)
    chat.perceive("ehi minnarone", speaker="ada", ts=3.0)

    # Capture what recent perceptions the prompt builder receives
    captured_recent = []

    class SpyPromptBuilder:
        commentator_style = None

        def build(self, *, recent, trigger, summary=None, self_messages=(), now=None):
            captured_recent.extend(recent)
            return "prompt"

        def stable_prefix(self):
            return ""

    class FakeLLM:
        async def complete(self, prompt):
            return LLMResult(message="test reply")

    class FakeRouter:
        async def route(self, msg, mode):
            pass

    reactor = Reactor(
        senser=senser,
        prompt_builder=SpyPromptBuilder(),
        llm=FakeLLM(),
        router=FakeRouter(),
        store=store,
        mode=OutputMode.PUBLIC,
        recent_window=15,
        bot_identity="minnabot",
    )

    asyncio.run(reactor.run_once())

    # The "ada" mention triggers, so recent perceptions are fetched.
    # The bot's own message must NOT appear in the recent context.
    speakers_in_recent = [p.speaker for p in captured_recent]
    assert "minnabot" not in speakers_in_recent
    assert "enkk" in speakers_in_recent


# --- Cycle 11: Reactor without bot_identity does not filter -------------------


def test_reactor_without_bot_identity_includes_all_perceptions(tmp_path):
    """Without bot_identity, all speakers appear in the prompt recent context."""
    import asyncio

    from minnarone.llm import LLMResult
    from minnarone.output import OutputMode
    from minnarone.reactor import Reactor

    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    # No bot_identity on either Senser or Reactor
    senser = Senser(store, agent_name="Minnarone", clock=clock)

    chat.perceive("ciao", speaker="minnabot", ts=1.0)
    chat.perceive("ehi minnarone", speaker="enkk", ts=2.0)

    captured_recent = []

    class SpyPromptBuilder:
        commentator_style = None

        def build(self, *, recent, trigger, summary=None, self_messages=(), now=None):
            captured_recent.extend(recent)
            return "prompt"

        def stable_prefix(self):
            return ""

    class FakeLLM:
        async def complete(self, prompt):
            return LLMResult(message="test reply")

    class FakeRouter:
        async def route(self, msg, mode):
            pass

    reactor = Reactor(
        senser=senser,
        prompt_builder=SpyPromptBuilder(),
        llm=FakeLLM(),
        router=FakeRouter(),
        store=store,
        mode=OutputMode.PUBLIC,
        recent_window=15,
    )

    asyncio.run(reactor.run_once())

    speakers_in_recent = [p.speaker for p in captured_recent]
    # Without bot_identity, both speakers appear
    assert "minnabot" in speakers_in_recent
    assert "enkk" in speakers_in_recent
