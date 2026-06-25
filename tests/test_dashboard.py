"""Test del modello di snapshot di osservabilità (slice 10).

Il modello `DashboardState` / `snapshot()` è PURO e senza dipendenze: aggrega in
sola lettura percezioni, trigger, finestre di conversazione e messaggi inviati.
Tutti i test sono offline e NON richiedono `textual`.
"""

import asyncio

from minnarone.chat import ChatPerceiver
from minnarone.dashboard import DashboardState, snapshot
from minnarone.output import OutputMode, OutputRouter
from minnarone.perception import Perception, Source
from minnarone.reactor import Reactor
from minnarone.senser import Senser
from minnarone.store import PerceptionStore


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class RecordingRouter(OutputRouter):
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def route(self, message: str, mode: OutputMode) -> None:
        self.sent.append(message)


class StubLLM:
    def __init__(self, message: str) -> None:
        self._message = message

    async def complete(self, prompt):
        from minnarone.llm import LLMResult

        return LLMResult(message=self._message)


def _store(tmp_path):
    return PerceptionStore(tmp_path / "perceptions.jsonl")


def _chat_perception(text, speaker, ts):
    return Perception(
        ts=ts, source=Source.CHAT, type="msg", text=text, speaker=speaker
    )


# --- Percezioni recenti ----------------------------------------------------


def test_snapshot_reflects_recent_perceptions_from_store(tmp_path):
    store = _store(tmp_path)
    store.append(_chat_perception("ciao", "alice", 1.0))
    store.append(_chat_perception("come va", "bob", 2.0))

    state = snapshot(store=store)

    assert isinstance(state, DashboardState)
    texts = [p.text for p in state.perceptions]
    assert texts == ["ciao", "come va"]
    # La sorgente è etichettata/raggruppabile per source.
    assert all(p.source is Source.CHAT for p in state.perceptions)


def test_snapshot_perceptions_limited_to_recent_n(tmp_path):
    store = _store(tmp_path)
    for i in range(10):
        store.append(_chat_perception(f"m{i}", "alice", float(i)))

    state = snapshot(store=store, recent_perceptions=3)

    assert [p.text for p in state.perceptions] == ["m7", "m8", "m9"]


# --- Finestre di conversazione --------------------------------------------


def test_snapshot_includes_open_conversation_windows(tmp_path):
    clock = FakeClock(start=100.0)
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone", clock=clock, window_ttl=180.0)
    # Una menzione apre una finestra per alice.
    store.append(_chat_perception("ehi Minnarone", "alice", 100.0))
    senser.tick()

    state = snapshot(store=store, senser=senser)

    assert "alice" in state.windows


def test_snapshot_excludes_expired_conversation_windows(tmp_path):
    clock = FakeClock(start=100.0)
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone", clock=clock, window_ttl=180.0)
    store.append(_chat_perception("ehi Minnarone", "alice", 100.0))
    senser.tick()
    # Oltre il ttl: la finestra deve essere scaduta e NON apparire.
    clock.advance(200.0)

    state = snapshot(store=store, senser=senser)

    assert "alice" not in state.windows


# --- Messaggi inviati ------------------------------------------------------


def test_snapshot_includes_recent_sent_messages(tmp_path):
    from minnarone.memory import MemoryBlocks
    from minnarone.prompt import PromptBuilder

    clock = FakeClock(start=0.0)
    store = _store(tmp_path)
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    router = RecordingRouter()
    blocks = MemoryBlocks(soul="Sono Minnarone.", facts="")
    reactor = Reactor(
        senser=senser,
        prompt_builder=PromptBuilder(blocks),
        llm=StubLLM("Ciao alice!"),
        router=router,
        store=store,
    )
    chat.perceive(text="ehi Minnarone", speaker="alice")
    asyncio.run(reactor.run_once())
    assert router.sent == ["Ciao alice!"]  # sanity: ha davvero instradato

    state = snapshot(store=store, reactor=reactor)

    assert "Ciao alice!" in state.messages


# --- Trigger / eventi ------------------------------------------------------


def test_snapshot_includes_recent_triggers(tmp_path):
    clock = FakeClock(start=0.0)
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    store.append(_chat_perception("ehi Minnarone", "alice", 0.0))
    senser.tick()

    state = snapshot(store=store, senser=senser)

    kinds = [t.kind for t in state.triggers]
    assert "mention" in kinds
    assert any(t.interlocutor == "alice" for t in state.triggers)


# --- Sola lettura ----------------------------------------------------------


def test_snapshot_is_read_only_over_store_and_senser(tmp_path):
    clock = FakeClock(start=100.0)
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    store.append(_chat_perception("ehi Minnarone", "alice", 100.0))
    senser.tick()

    before_tail = [p.text for p in store.tail(50)]
    before_position = senser._position
    before_windows = dict(senser.open_windows())

    snapshot(store=store, senser=senser, recent_perceptions=50)
    snapshot(store=store, senser=senser, recent_perceptions=50)

    after_tail = [p.text for p in store.tail(50)]
    assert after_tail == before_tail
    # Il cursore di lettura del Senser non avanza: la dashboard non consuma.
    assert senser._position == before_position
    assert set(senser.open_windows()) == set(before_windows)


def test_snapshot_does_not_emit_new_triggers(tmp_path):
    clock = FakeClock(start=0.0)
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    store.append(_chat_perception("ehi Minnarone", "alice", 0.0))
    senser.tick()
    n_before = len(senser.recent_triggers())

    snapshot(store=store, senser=senser)
    snapshot(store=store, senser=senser)

    # Lo snapshot non chiama tick(): nessun nuovo trigger generato.
    assert len(senser.recent_triggers()) == n_before


# --- Resa testuale (per il view) -------------------------------------------


def test_snapshot_renders_to_text_without_textual(tmp_path):
    store = _store(tmp_path)
    store.append(_chat_perception("ciao", "alice", 1.0))

    state = snapshot(store=store)
    rendered = state.render_text()

    assert isinstance(rendered, str)
    assert "alice" in rendered
    assert "ciao" in rendered


def test_snapshot_windows_are_defensive_copies(tmp_path):
    clock = FakeClock(start=100.0)
    store = _store(tmp_path)
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    store.append(_chat_perception("ehi Minnarone", "alice", 100.0))
    senser.tick()

    who = next(iter(senser.open_windows()))
    live_before = senser.open_windows()[who].last_seen

    state = snapshot(store=store, senser=senser)
    # la finestra nello snapshot è un oggetto distinto da quello vivo
    assert state.windows[who] is not senser.open_windows()[who]
    # mutare lo snapshot NON tocca lo stato di conversazione vivo
    state.windows[who].last_seen = 999999.0
    assert senser.open_windows()[who].last_seen == live_before
