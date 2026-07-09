"""Test del Senser: tick legge percezioni recenti -> Trigger su menzione del nome."""

from minnarone.chat import ChatPerceiver
from minnarone.senser import Senser, Trigger
from minnarone.store import PerceptionStore


def _setup(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    return store, ChatPerceiver(store), Senser(store, agent_name="Minnarone")


def test_mention_produces_trigger(tmp_path):
    store, chat, senser = _setup(tmp_path)
    chat.perceive("ehi minnarone come va", speaker="enkk", ts=1.0)
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].perception.text == "ehi minnarone come va"


def test_no_mention_produces_no_trigger(tmp_path):
    store, chat, senser = _setup(tmp_path)
    chat.perceive("ciao a tutti", speaker="enkk", ts=1.0)
    assert senser.tick() == []


def test_tick_is_idempotent_does_not_refire_seen_perceptions(tmp_path):
    store, chat, senser = _setup(tmp_path)
    chat.perceive("minnarone!", speaker="enkk", ts=1.0)
    assert len(senser.tick()) == 1
    # secondo tick senza nuove percezioni: nessun nuovo trigger
    assert senser.tick() == []


def test_two_mentions_with_same_ts_both_fire(tmp_path):
    # Bug di idempotenza: due percezioni con lo stesso ts non devono "mangiarsi".
    store, chat, senser = _setup(tmp_path)
    chat.perceive("ehi minnarone uno", speaker="enkk", ts=1.0)
    triggers = senser.tick()
    assert len(triggers) == 1
    chat.perceive("ehi minnarone due", speaker="ada", ts=1.0)
    triggers2 = senser.tick()
    assert [t.perception.text for t in triggers2] == ["ehi minnarone due"]


def test_substring_does_not_trigger_but_word_does(tmp_path):
    store, chat, senser = _setup(tmp_path)
    chat.perceive("seguite minnaroneitalia sui social", speaker="enkk", ts=1.0)
    chat.perceive("ciao minnarone", speaker="ada", ts=2.0)
    triggers = senser.tick()
    assert [t.perception.text for t in triggers] == ["ciao minnarone"]


# --- Periodic trigger mode -------------------------------------------------


def test_synthesis_tick_trigger_constructs():
    """synthesis_tick is a valid trigger kind with no perception."""
    t = Trigger(reason="synthesis_tick", perception=None, kind="synthesis_tick")
    assert t.kind == "synthesis_tick"
    assert t.perception is None


def test_senser_default_trigger_mode_is_reactive(tmp_path):
    """Senser defaults to reactive mode (existing behavior unchanged)."""
    store = PerceptionStore(tmp_path / "p.jsonl")
    senser = Senser(store, agent_name="Minnarone")
    assert senser.trigger_mode == "reactive"


def test_senser_accepts_reactive_trigger_mode(tmp_path):
    """Explicit reactive mode behaves the same as default."""
    store = PerceptionStore(tmp_path / "p.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone", trigger_mode="reactive")
    chat.perceive("ehi minnarone", speaker="enkk", ts=1.0)
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].kind == "mention"


class FakeClock:
    """Orologio deterministico per i test periodici."""

    def __init__(self, start: float = 0.0):
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


def _make_periodic(tmp_path, clock, interval_s=60.0):
    """Helper: crea un Senser periodico con clock e intervallo dati."""
    store = PerceptionStore(tmp_path / "p.jsonl")
    senser = Senser(
        store,
        agent_name="Minnarone",
        clock=clock,
        trigger_mode="periodic",
        interval_s=interval_s,
    )
    return store, senser


def test_periodic_emits_synthesis_tick_after_interval(tmp_path):
    """Periodic senser emits synthesis_tick when interval_s elapses."""
    clock = FakeClock(0.0)
    _, senser = _make_periodic(tmp_path, clock)
    # Before interval: no trigger
    assert senser.tick() == []
    # Advance to exactly the interval
    clock.advance(60.0)
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].kind == "synthesis_tick"
    assert triggers[0].perception is None


def test_periodic_no_trigger_before_interval(tmp_path):
    """Periodic senser returns empty if interval has not elapsed."""
    clock = FakeClock(0.0)
    _, senser = _make_periodic(tmp_path, clock)
    clock.advance(30.0)  # half the interval
    assert senser.tick() == []


def test_periodic_emits_one_not_catchup_after_double_interval(tmp_path):
    """Advancing by 2*interval produces one trigger, not two (cadence not catchup)."""
    clock = FakeClock(0.0)
    _, senser = _make_periodic(tmp_path, clock)
    clock.advance(120.0)  # 2x the 60s interval
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].kind == "synthesis_tick"


def test_periodic_resets_timer_after_trigger(tmp_path):
    """After emitting a trigger, the timer resets; next trigger needs full interval."""
    clock = FakeClock(0.0)
    _, senser = _make_periodic(tmp_path, clock)
    clock.advance(60.0)
    assert len(senser.tick()) == 1
    # 30s later: not yet
    clock.advance(30.0)
    assert senser.tick() == []
    # 30s more (60s total since last trigger): fires again
    clock.advance(30.0)
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].kind == "synthesis_tick"


def test_periodic_ignores_mentions(tmp_path):
    """Periodic senser does not emit mention triggers even with mentions in store."""
    clock = FakeClock(0.0)
    store, senser = _make_periodic(tmp_path, clock)
    chat = ChatPerceiver(store)
    chat.perceive("ehi minnarone come va", speaker="enkk", ts=1.0)
    # Not enough time for periodic trigger, but there IS a mention
    clock.advance(10.0)
    assert senser.tick() == []
    # Even at full interval, only synthesis_tick, no mention
    clock.advance(50.0)
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].kind == "synthesis_tick"


def test_periodic_ignores_continuation(tmp_path):
    """Periodic senser does not emit continuation triggers."""
    clock = FakeClock(0.0)
    store, senser = _make_periodic(tmp_path, clock)
    chat = ChatPerceiver(store)
    # Set up a scenario that would trigger continuation in reactive mode
    senser.note_agent_message(0.0)
    chat.perceive("ehi minnarone", speaker="enkk", ts=1.0)
    chat.perceive("si grazie", speaker="enkk", ts=5.0)
    clock.advance(10.0)
    assert senser.tick() == []


def test_periodic_ignores_idle(tmp_path):
    """Periodic senser does not emit idle_comment triggers."""
    clock = FakeClock(0.0)
    store, senser = _make_periodic(tmp_path, clock, interval_s=300.0)
    # Advance past the default idle interval (150s) but before periodic interval
    clock.advance(200.0)
    triggers = senser.tick()
    # In reactive mode this would be an idle_comment; in periodic, nothing
    assert triggers == []


def test_periodic_requires_interval_s(tmp_path):
    """Periodic mode without interval_s raises ValueError."""
    import pytest

    store = PerceptionStore(tmp_path / "p.jsonl")
    with pytest.raises(ValueError, match="interval_s"):
        Senser(store, agent_name="Minnarone", trigger_mode="periodic")


def test_invalid_trigger_mode_raises(tmp_path):
    """Unknown trigger_mode raises ValueError."""
    import pytest

    store = PerceptionStore(tmp_path / "p.jsonl")
    with pytest.raises(ValueError, match="trigger_mode"):
        Senser(store, agent_name="Minnarone", trigger_mode="bogus")


# --- on_perception trigger mode -----------------------------------------------

from minnarone.perception import Perception, Source


def _make_on_perception(tmp_path, clock=None, bot_identity=None):
    """Helper: crea un Senser in on_perception mode."""
    if clock is None:
        clock = FakeClock(0.0)
    store = PerceptionStore(tmp_path / "p.jsonl")
    senser = Senser(
        store,
        agent_name="Minnarone",
        clock=clock,
        trigger_mode="on_perception",
        bot_identity=bot_identity,
    )
    return store, senser, clock


def test_suggestion_eval_trigger_constructs():
    """suggestion_eval is a valid trigger kind carrying perception and interlocutor."""
    p = Perception(ts=1.0, source=Source.AUDIO, type="speech", text="hello", speaker="alice")
    t = Trigger(reason="suggestion_eval", perception=p, kind="suggestion_eval", interlocutor="alice")
    assert t.kind == "suggestion_eval"
    assert t.perception is p
    assert t.interlocutor == "alice"


def test_on_perception_speech_produces_suggestion_eval(tmp_path):
    """Speech perception in on_perception mode emits suggestion_eval trigger."""
    store, senser, clock = _make_on_perception(tmp_path)
    p = Perception(ts=1.0, source=Source.AUDIO, type="speech", text="let's discuss the agenda", speaker="alice")
    store.append(p)
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].kind == "suggestion_eval"
    assert triggers[0].perception is not None
    assert triggers[0].perception.text == "let's discuss the agenda"
    assert triggers[0].interlocutor == "alice"


def test_on_perception_chat_produces_no_trigger(tmp_path):
    """Chat perception in on_perception mode produces no trigger."""
    store, senser, clock = _make_on_perception(tmp_path)
    p = Perception(ts=1.0, source=Source.CHAT, type="msg", text="ehi minnarone come va", speaker="enkk")
    store.append(p)
    triggers = senser.tick()
    assert triggers == []


def test_on_perception_video_produces_no_trigger(tmp_path):
    """Video perception in on_perception mode produces no trigger."""
    store, senser, clock = _make_on_perception(tmp_path)
    p = Perception(ts=1.0, source=Source.VIDEO, type="caption", text="something on screen", speaker=None)
    store.append(p)
    triggers = senser.tick()
    assert triggers == []


def test_on_perception_event_produces_no_trigger(tmp_path):
    """Event perception in on_perception mode produces no trigger."""
    store, senser, clock = _make_on_perception(tmp_path)
    p = Perception(ts=1.0, source=Source.EVENT, type="join", text="user joined", speaker="bob")
    store.append(p)
    triggers = senser.tick()
    assert triggers == []


def test_on_perception_self_echo_filtered(tmp_path):
    """Self-echo perceptions (bot's own speech) are filtered out in on_perception mode."""
    store, senser, clock = _make_on_perception(tmp_path, bot_identity="Minnarone")
    # Audio perception from the bot itself (self-echo)
    p = Perception(ts=1.0, source=Source.AUDIO, type="speech", text="I think we should...", speaker="Minnarone")
    store.append(p)
    triggers = senser.tick()
    assert triggers == []


def test_on_perception_no_mention_triggers(tmp_path):
    """on_perception mode does not emit mention triggers even with agent name in text."""
    store, senser, clock = _make_on_perception(tmp_path)
    # Chat perception mentioning the agent name: no trigger in this mode
    p = Perception(ts=1.0, source=Source.CHAT, type="msg", text="ehi minnarone", speaker="enkk")
    store.append(p)
    triggers = senser.tick()
    assert triggers == []


def test_on_perception_no_continuation_triggers(tmp_path):
    """on_perception mode does not emit continuation triggers."""
    store, senser, clock = _make_on_perception(tmp_path)
    senser.note_agent_message(0.0)
    # Chat that would trigger continuation in reactive mode
    p = Perception(ts=5.0, source=Source.CHAT, type="msg", text="si grazie", speaker="enkk")
    store.append(p)
    triggers = senser.tick()
    assert triggers == []


def test_on_perception_no_idle_triggers(tmp_path):
    """on_perception mode does not emit idle_comment triggers."""
    store, senser, clock = _make_on_perception(tmp_path)
    clock.advance(200.0)  # well past the default idle interval (150s)
    triggers = senser.tick()
    assert triggers == []


def test_on_perception_multiple_speech_one_trigger_each(tmp_path):
    """Multiple speech perceptions produce one trigger each."""
    store, senser, clock = _make_on_perception(tmp_path)
    p1 = Perception(ts=1.0, source=Source.AUDIO, type="speech", text="first point", speaker="alice")
    p2 = Perception(ts=2.0, source=Source.AUDIO, type="speech", text="second point", speaker="bob")
    store.append(p1)
    store.append(p2)
    triggers = senser.tick()
    assert len(triggers) == 2
    assert triggers[0].kind == "suggestion_eval"
    assert triggers[0].perception.text == "first point"
    assert triggers[0].interlocutor == "alice"
    assert triggers[1].kind == "suggestion_eval"
    assert triggers[1].perception.text == "second point"
    assert triggers[1].interlocutor == "bob"


def test_on_perception_interlocutor_matches_speaker(tmp_path):
    """Trigger interlocutor matches the perception speaker."""
    store, senser, clock = _make_on_perception(tmp_path)
    p = Perception(ts=1.0, source=Source.AUDIO, type="speech", text="my idea is", speaker="carol")
    store.append(p)
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].interlocutor == "carol"
    assert triggers[0].interlocutor == p.speaker


def test_on_perception_idempotent(tmp_path):
    """Already-consumed perceptions don't re-fire on subsequent ticks."""
    store, senser, clock = _make_on_perception(tmp_path)
    p = Perception(ts=1.0, source=Source.AUDIO, type="speech", text="hello", speaker="alice")
    store.append(p)
    assert len(senser.tick()) == 1
    # Second tick: no new perceptions, no triggers
    assert senser.tick() == []
