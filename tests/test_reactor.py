"""Test del Reactor: wiring end-to-end Senser -> PromptBuilder -> LLM -> Output.

Verifica lo scheletro che cammina: una menzione transita per lo store e produce
un messaggio sul canale pubblico; senza menzione, nessun output.
"""

import asyncio

import pytest

from minnarone.chat import ChatPerceiver
from minnarone.console import ConsoleOutputRouter  # noqa: F401 (import sanity)
from minnarone.fakes import FakeLLMProvider, FakeMemory, FakeOutputRouter
from minnarone.output import CommentatorStyle, OutputMode
from minnarone.perception import Perception, Source
from minnarone.prompt import PromptBuilder
from minnarone.reactor import Reactor
from minnarone.senser import Senser
from minnarone.store import PerceptionStore


def _build(tmp_path, llm_message="ciao enkk!"):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone")
    builder = PromptBuilder(FakeMemory(soul="Sono Minnarone.", facts="").load())
    llm = FakeLLMProvider(message=llm_message)
    router = FakeOutputRouter()
    reactor = Reactor(
        senser=senser,
        prompt_builder=builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PUBLIC,
    )
    return store, chat, llm, router, reactor


def test_mention_produces_public_output_end_to_end(tmp_path):
    store, chat, llm, router, reactor = _build(tmp_path)
    chat.perceive("ehi minnarone!", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == [("ciao enkk!", OutputMode.PUBLIC)]


def test_no_mention_produces_no_output(tmp_path):
    store, chat, llm, router, reactor = _build(tmp_path)
    chat.perceive("ciao a tutti", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == []


def test_reaction_reads_from_store_not_passed_directly(tmp_path):
    # La percezione viene scritta nello store; il reactor non la riceve mai
    # direttamente. La prova: il prompt inviato all'LLM contiene il testo letto
    # dallo store.
    store, chat, llm, router, reactor = _build(tmp_path)
    chat.perceive("minnarone dimmi qualcosa", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert llm.last_prompt is not None
    assert "minnarone dimmi qualcosa" in llm.last_prompt


def test_llm_timeout_skips_turn_no_output(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone")
    builder = PromptBuilder(FakeMemory().load())
    llm = FakeLLMProvider(raise_timeout=True)
    router = FakeOutputRouter()
    reactor = Reactor(
        senser=senser, prompt_builder=builder, llm=llm, router=router,
        store=store, mode=OutputMode.PUBLIC,
    )
    chat.perceive("minnarone!", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == []


def test_llm_timeout_once_then_recovers_next_tick(tmp_path):
    # EC03/latenza: un timeout su un tick salta il turno (nessun messaggio
    # stale), ma il loop prosegue e il tick successivo produce di nuovo output.
    class FlakyLLM:
        def __init__(self):
            self.calls = 0
            self.last_prompt = None

        async def complete(self, prompt):
            from minnarone.llm import LLMResult, LLMTimeout

            self.last_prompt = prompt
            self.calls += 1
            if self.calls == 1:
                raise LLMTimeout("latenza anomala simulata")
            return LLMResult(message="risposta tardiva!")

    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone")
    builder = PromptBuilder(FakeMemory().load())
    llm = FlakyLLM()
    router = FakeOutputRouter()
    reactor = Reactor(
        senser=senser, prompt_builder=builder, llm=llm, router=router,
        store=store, mode=OutputMode.PUBLIC,
    )

    # primo trigger -> timeout -> turno saltato, nessun output
    chat.perceive("minnarone ci sei?", speaker="enkk", ts=1.0)
    asyncio.run(reactor.run_once())
    assert router.sent == []
    assert llm.calls == 1

    # tick successivo con un nuovo trigger -> l'LLM risponde -> output instradato
    chat.perceive("minnarone rispondi", speaker="enkk", ts=2.0)
    asyncio.run(reactor.run_once())
    assert router.sent == [("risposta tardiva!", OutputMode.PUBLIC)]
    assert llm.calls == 2


def test_generic_llm_error_skips_turn(tmp_path):
    # Anche un LLMError generico (non solo il timeout) salta il turno.
    class ErroringLLM:
        last_prompt = None

        async def complete(self, prompt):
            from minnarone.llm import LLMError

            self.last_prompt = prompt
            raise LLMError("guasto generico")

    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone")
    builder = PromptBuilder(FakeMemory().load())
    router = FakeOutputRouter()
    reactor = Reactor(
        senser=senser, prompt_builder=builder, llm=ErroringLLM(), router=router,
        store=store, mode=OutputMode.PUBLIC,
    )
    chat.perceive("minnarone!", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == []


def test_run_event_recorder_failure_does_not_block_reaction(tmp_path):
    class FailingEventRecorder:
        def record_trigger(self, trigger):
            del trigger
            raise OSError("disk full")

        def record_minnarone_output(self, message, mode):
            del message, mode
            raise OSError("disk full")

    store, chat, llm, router, reactor = _build(tmp_path)
    reactor = Reactor(
        senser=reactor._senser,
        prompt_builder=reactor._prompt_builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PUBLIC,
        event_recorder=FailingEventRecorder(),
    )
    chat.perceive("minnarone, reagisci", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == [("ciao enkk!", OutputMode.PUBLIC)]
    assert reactor.recent_messages() == ["ciao enkk!"]


def test_summary_from_provider_appears_in_reaction_prompt(tmp_path):
    # Un Reactor con un summary_provider deve iniettare il riassunto corrente
    # nella sezione dinamica del prompt di reazione.
    store, chat, llm, router, reactor = _build(tmp_path)
    reactor = Reactor(
        senser=reactor._senser,
        prompt_builder=reactor._prompt_builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PUBLIC,
        summary_provider=lambda: "RIASSUNTO X",
    )
    chat.perceive("minnarone ci sei?", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert llm.last_prompt is not None
    assert "RIASSUNTO X" in llm.last_prompt


def test_summarizer_object_wired_as_summary_provider(tmp_path):
    # Anche un Summarizer (oggetto con current_summary) può essere collegato.
    from minnarone.summarizer import Summarizer

    store, chat, llm, router, reactor = _build(tmp_path)
    summarizer = Summarizer(llm=FakeLLMProvider(message="ignorato"), store=store)
    summarizer._summary = "RIASSUNTO Y"  # come se summarize() fosse già girato
    reactor = Reactor(
        senser=reactor._senser,
        prompt_builder=reactor._prompt_builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PUBLIC,
        summary_provider=lambda: summarizer.current_summary,
    )
    chat.perceive("minnarone ci sei?", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert llm.last_prompt is not None
    assert "RIASSUNTO Y" in llm.last_prompt


def test_no_summary_provider_omits_summary_section(tmp_path):
    # Senza summary_provider il comportamento è invariato: nessuna sezione
    # RIASSUNTO nel prompt.
    store, chat, llm, router, reactor = _build(tmp_path)
    chat.perceive("minnarone ci sei?", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert llm.last_prompt is not None
    assert "RIASSUNTO" not in llm.last_prompt


def test_continuation_wired_end_to_end_via_reactor(tmp_path):
    # Il Reactor deve chiamare note_agent_message dopo un route riuscito, così
    # la continuazione (UC03) funziona nel sistema assemblato: dopo una
    # menzione->risposta, un messaggio dell'interlocutore poco dopo innesca una
    # continuation al tick successivo. Clock deterministico.
    class FakeClock:
        def __init__(self, start=0.0):
            self.t = start

        def __call__(self):
            return self.t

        def advance(self, dt):
            self.t += dt

    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    builder = PromptBuilder(FakeMemory(soul="Sono Minnarone.", facts="").load())
    llm = FakeLLMProvider(message="rispondo!")
    router = FakeOutputRouter()
    reactor = Reactor(
        senser=senser, prompt_builder=builder, llm=llm, router=router,
        store=store, mode=OutputMode.PUBLIC,
    )

    # 1. menzione -> reazione (apre la finestra di enkk e nota il messaggio agente)
    chat.perceive("minnarone ciao", speaker="enkk", ts=clock())
    asyncio.run(reactor.run_once())
    assert len(router.sent) == 1

    # 2. enkk risponde poco dopo, senza rinominare l'agente
    clock.advance(3.0)
    chat.perceive("ah davvero?", speaker="enkk", ts=clock())
    asyncio.run(reactor.run_once())

    # la continuazione ha prodotto una seconda reazione
    assert len(router.sent) == 2


def test_run_loop_reacts_only_when_trigger_fires_then_stops(tmp_path):
    store, chat, llm, router, reactor = _build(tmp_path)
    chat.perceive("ciao a tutti", speaker="enkk", ts=1.0)
    chat.perceive("minnarone ci sei?", speaker="enkk", ts=2.0)

    async def drive():
        task = asyncio.create_task(reactor.run(interval=0.001))
        # lascia girare qualche tick
        await asyncio.sleep(0.05)
        reactor.stop()
        await task

    asyncio.run(drive())

    # un solo messaggio (la menzione), il "ciao a tutti" non innesca nulla
    assert router.sent == [("ciao enkk!", OutputMode.PUBLIC)]


# --- Integrazione HumanLikeness (slice 08) ---------------------------------


def test_human_likeness_routes_after_injected_delay(tmp_path):
    # Con HumanLikeness il messaggio normale è instradato DOPO il typing delay,
    # applicato via uno sleep asincrono iniettato (deterministico, non reale).
    from minnarone.human import HumanLikeness

    store, chat, llm, router, _reactor = _build(tmp_path, llm_message="ehi ciao a tutti")
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    human = HumanLikeness(typing_speed=10.0, min_delay=0.5, max_delay=100.0)
    reactor = Reactor(
        senser=_reactor._senser,
        prompt_builder=_reactor._prompt_builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PUBLIC,
        human=human,
        sleep=fake_sleep,
    )
    chat.perceive("minnarone ci sei?", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    # instradato col testo (ripulito) e dopo aver atteso un delay > 0
    assert router.sent == [("ehi ciao a tutti", OutputMode.PUBLIC)]
    assert len(slept) == 1 and slept[0] > 0


def test_human_likeness_drops_near_duplicate(tmp_path):
    # Un secondo messaggio quasi-identico al primo viene scartato (non inviato).
    from minnarone.human import HumanLikeness

    store, chat, llm, router, _reactor = _build(tmp_path, llm_message="ciao a tutti come va")

    async def fake_sleep(seconds: float) -> None:
        pass

    human = HumanLikeness(dedup_threshold=0.9, min_delay=0.0, max_delay=100.0)
    reactor = Reactor(
        senser=_reactor._senser,
        prompt_builder=_reactor._prompt_builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PUBLIC,
        human=human,
        sleep=fake_sleep,
    )

    # primo turno: instradato
    chat.perceive("minnarone ci sei?", speaker="enkk", ts=1.0)
    asyncio.run(reactor.run_once())
    assert len(router.sent) == 1

    # secondo turno: l'LLM produce lo stesso testo -> scartato dal dedup
    chat.perceive("minnarone ancora?", speaker="enkk", ts=2.0)
    asyncio.run(reactor.run_once())
    assert len(router.sent) == 1  # nessun nuovo invio


def test_human_likeness_end_conv_closes_window_and_suppresses_sentinel(tmp_path):
    # `#end_conv`: la finestra dell'interlocutore viene chiusa via il Senser e
    # il sentinella non esce come messaggio letterale (esce solo il testo utile).
    from minnarone.human import END_CONV_SENTINEL, HumanLikeness

    store, chat, llm, router, _reactor = _build(
        tmp_path, llm_message=f"ok ci vediamo {END_CONV_SENTINEL}"
    )

    async def fake_sleep(seconds: float) -> None:
        pass

    human = HumanLikeness(min_delay=0.0, max_delay=100.0)
    senser = _reactor._senser
    reactor = Reactor(
        senser=senser,
        prompt_builder=_reactor._prompt_builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PUBLIC,
        human=human,
        sleep=fake_sleep,
    )
    chat.perceive("minnarone ci sei?", speaker="enkk", ts=1.0)
    # la menzione apre la finestra di enkk
    asyncio.run(reactor.run_once())

    # il testo ripulito è uscito senza il sentinella
    assert router.sent == [("ok ci vediamo", OutputMode.PUBLIC)]
    assert END_CONV_SENTINEL not in router.sent[0][0]
    # e la finestra di enkk è stata chiusa
    assert "enkk" not in senser.open_windows()


def test_reactor_unchanged_without_human_likeness(tmp_path):
    # Controprova: senza HumanLikeness il comportamento è invariato (slice 01).
    store, chat, llm, router, reactor = _build(tmp_path)
    chat.perceive("ehi minnarone!", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == [("ciao enkk!", OutputMode.PUBLIC)]


def test_reactor_passes_defensive_recent_self_messages_to_prompt_builder(tmp_path):
    class MutatingPromptBuilder:
        def __init__(self):
            self.snapshots: list[list[str]] = []

        def build(self, *, recent, trigger, summary=None, self_messages):
            del recent, trigger, summary
            self.snapshots.append(list(self_messages))
            try:
                self_messages.append("mutation from prompt builder")
            except AttributeError:
                pass
            return "prompt"

    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone")
    builder = MutatingPromptBuilder()
    llm = FakeLLMProvider(message="first reply")
    router = FakeOutputRouter()
    reactor = Reactor(
        senser=senser,
        prompt_builder=builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PUBLIC,
    )

    chat.perceive("minnarone prima", speaker="enkk", ts=1.0)
    asyncio.run(reactor.run_once())

    llm._message = "second reply"
    chat.perceive("minnarone seconda", speaker="enkk", ts=2.0)
    asyncio.run(reactor.run_once())

    assert builder.snapshots == [[], ["first reply"]]
    assert reactor.recent_messages() == ["first reply", "second reply"]


def test_original_chat_reactor_reads_recent_context_by_source(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone")
    builder = PromptBuilder(
        FakeMemory(soul="Sono Minnarone.", facts="").load(),
        commentator_style=CommentatorStyle.ORIGINAL_CHAT,
    )
    llm = FakeLLMProvider(message="ok")
    router = FakeOutputRouter()
    reactor = Reactor(
        senser=senser,
        prompt_builder=builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PUBLIC,
        recent_window=2,
    )
    store.append(
        Perception(
            ts=1.0,
            source=Source.AUDIO,
            type="speech",
            text="audio ancora rilevante",
            speaker="streamer",
        )
    )
    store.append(
        Perception(
            ts=2.0,
            source=Source.VIDEO,
            type="caption",
            text="video ancora rilevante",
        )
    )
    chat.perceive("chat non trigger", speaker="bob", ts=3.0)
    chat.perceive("minnarone guarda qui", speaker="alice", ts=4.0)

    asyncio.run(reactor.run_once())

    assert llm.last_prompt is not None
    assert "[PARLATO RECENTE]" in llm.last_prompt
    assert "audio ancora rilevante" in llm.last_prompt
    assert "[SCHERMO RECENTE]" in llm.last_prompt
    assert "video ancora rilevante" in llm.last_prompt
    chat_recent = llm.last_prompt.split("[CHAT RECENTE]", maxsplit=1)[1].split(
        "[PARLATO RECENTE]", maxsplit=1
    )[0]
    assert "bob: chat non trigger" in chat_recent
    assert "alice: minnarone guarda qui" not in chat_recent
    assert llm.last_prompt.count("minnarone guarda qui") == 1


def test_original_chat_reactor_routes_normalized_display_text(tmp_path):
    from minnarone.human import HumanLikeness

    class SpySenser(Senser):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.agent_message_notes: list[float] = []

        def note_agent_message(self, ts: float) -> None:
            self.agent_message_notes.append(ts)
            super().note_agent_message(ts)

    class RecordingEventRecorder:
        def __init__(self):
            self.outputs: list[tuple[str, OutputMode]] = []

        def record_trigger(self, trigger):
            del trigger

        def record_minnarone_output(self, message, mode):
            self.outputs.append((message, mode))

    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = SpySenser(store, agent_name="Minnarone")
    builder = PromptBuilder(
        FakeMemory(soul="Sono Minnarone.", facts="").load(),
        commentator_style=CommentatorStyle.ORIGINAL_CHAT,
    )
    llm = FakeLLMProvider(message="re : boss fight\nmsg : bella giocata")
    router = FakeOutputRouter()
    recorder = RecordingEventRecorder()
    reactor = Reactor(
        senser=senser,
        prompt_builder=builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PRIVATE,
        human=HumanLikeness(min_delay=0.0, max_delay=100.0),
        event_recorder=recorder,
    )
    chat.perceive("minnarone guarda qui", speaker="alice", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == [
        ("RE: boss fight\nMSG: bella giocata", OutputMode.PRIVATE)
    ]
    assert recorder.outputs == [
        ("RE: boss fight\nMSG: bella giocata", OutputMode.PRIVATE)
    ]
    assert reactor.recent_messages() == ["bella giocata"]
    assert len(senser.agent_message_notes) == 1


def test_operator_commentary_reactor_leaves_re_msg_text_unnormalized(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone")
    builder = PromptBuilder(
        FakeMemory(soul="Sono Minnarone.", facts="").load(),
        commentator_style=CommentatorStyle.OPERATOR,
    )
    llm = FakeLLMProvider(message="re : boss fight\nmsg : bella giocata")
    router = FakeOutputRouter()
    reactor = Reactor(
        senser=senser,
        prompt_builder=builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PRIVATE,
    )
    chat.perceive("minnarone guarda qui", speaker="alice", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == [
        ("re : boss fight\nmsg : bella giocata", OutputMode.PRIVATE)
    ]


def test_original_chat_end_conv_stays_visible_and_closes_window(tmp_path):
    from minnarone.human import HumanLikeness

    class SpySenser(Senser):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.agent_message_notes: list[float] = []

        def note_agent_message(self, ts: float) -> None:
            self.agent_message_notes.append(ts)
            super().note_agent_message(ts)

    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = SpySenser(store, agent_name="Minnarone")
    builder = PromptBuilder(
        FakeMemory(soul="Sono Minnarone.", facts="").load(),
        commentator_style=CommentatorStyle.ORIGINAL_CHAT,
    )
    llm = FakeLLMProvider(message="RE: idle\nMSG: #end_conv")
    router = FakeOutputRouter()
    reactor = Reactor(
        senser=senser,
        prompt_builder=builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PRIVATE,
        human=HumanLikeness(min_delay=0.0, max_delay=100.0),
    )
    chat.perceive("minnarone ci sei?", speaker="alice", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == [
        ("RE: idle\nMSG: #end_conv\n(skip: not sent)", OutputMode.PRIVATE)
    ]
    assert "alice" not in senser.open_windows()
    assert reactor.recent_messages() == []
    assert senser.agent_message_notes == []


def test_original_chat_end_conv_closes_window_before_router_failure(tmp_path):
    calls: list[str] = []

    class TrackingSenser(Senser):
        def close_window(self, interlocutor: str) -> bool:
            calls.append(f"close_window:{interlocutor}")
            return super().close_window(interlocutor)

    class FailingRouter(FakeOutputRouter):
        async def route(self, message: str, mode: OutputMode) -> None:
            del mode
            calls.append(f"route:{message}")
            raise RuntimeError("router unavailable")

    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = TrackingSenser(store, agent_name="Minnarone")
    builder = PromptBuilder(
        FakeMemory(soul="Sono Minnarone.", facts="").load(),
        commentator_style=CommentatorStyle.ORIGINAL_CHAT,
    )
    llm = FakeLLMProvider(message="RE: idle\nMSG: #end_conv")
    router = FailingRouter()
    reactor = Reactor(
        senser=senser,
        prompt_builder=builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PRIVATE,
    )
    chat.perceive("minnarone ci sei?", speaker="alice", ts=1.0)

    with pytest.raises(RuntimeError, match="router unavailable"):
        asyncio.run(reactor.run_once())

    assert calls == [
        "close_window:alice",
        "route:RE: idle\nMSG: #end_conv\n(skip: not sent)",
    ]
    assert "alice" not in senser.open_windows()
    assert router.sent == []
    assert reactor.recent_messages() == []


def test_original_chat_end_conv_close_window_failure_prevents_display(tmp_path):
    calls: list[str] = []

    class FailingSenser(Senser):
        def close_window(self, interlocutor: str) -> bool:
            calls.append(f"close_window:{interlocutor}")
            raise RuntimeError("close_window failed")

    class TrackingRouter(FakeOutputRouter):
        async def route(self, message: str, mode: OutputMode) -> None:
            calls.append(f"route:{message}")
            await super().route(message, mode)

    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = FailingSenser(store, agent_name="Minnarone")
    builder = PromptBuilder(
        FakeMemory(soul="Sono Minnarone.", facts="").load(),
        commentator_style=CommentatorStyle.ORIGINAL_CHAT,
    )
    llm = FakeLLMProvider(message="RE: idle\nMSG: #end_conv")
    router = TrackingRouter()
    reactor = Reactor(
        senser=senser,
        prompt_builder=builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PRIVATE,
    )
    chat.perceive("minnarone ci sei?", speaker="alice", ts=1.0)

    with pytest.raises(RuntimeError, match="close_window failed"):
        asyncio.run(reactor.run_once())

    assert calls == ["close_window:alice"]
    assert router.sent == []
    assert reactor.recent_messages() == []


def test_original_chat_idle_end_conv_stays_visible_without_interlocutor(tmp_path):
    class FakeClock:
        def __init__(self, start=0.0):
            self.t = start

        def __call__(self):
            return self.t

        def advance(self, dt):
            self.t += dt

    class StrictSenser(Senser):
        def close_window(self, interlocutor: str) -> bool:
            if interlocutor is None:
                raise AssertionError("idle end-conversation has no interlocutor")
            return super().close_window(interlocutor)

    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    senser = StrictSenser(
        store,
        agent_name="Minnarone",
        clock=clock,
        idle_interval=10.0,
    )
    builder = PromptBuilder(
        FakeMemory(soul="Sono Minnarone.", facts="").load(),
        commentator_style=CommentatorStyle.ORIGINAL_CHAT,
    )
    llm = FakeLLMProvider(message="RE: idle\nMSG: #end_conv")
    router = FakeOutputRouter()
    reactor = Reactor(
        senser=senser,
        prompt_builder=builder,
        llm=llm,
        router=router,
        store=store,
        mode=OutputMode.PRIVATE,
    )

    clock.advance(11.0)
    asyncio.run(reactor.run_once())

    assert router.sent == [
        ("RE: idle\nMSG: #end_conv\n(skip: not sent)", OutputMode.PRIVATE)
    ]
    assert senser.open_windows() == {}
    assert reactor.recent_messages() == []


# --- #nothing sentinel (issue 08) -------------------------------------------


def test_nothing_sentinel_suppresses_routing(tmp_path):
    """LLM response of exactly '#nothing' produces zero routed messages."""
    store, chat, llm, router, reactor = _build(tmp_path, llm_message="#nothing")
    chat.perceive("minnarone ci sei?", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == []
    assert reactor.recent_messages() == []


def test_nothing_sentinel_tolerates_whitespace(tmp_path):
    """'  #nothing  ' (with whitespace) still suppresses routing."""
    store, chat, llm, router, reactor = _build(
        tmp_path, llm_message="  #nothing  "
    )
    chat.perceive("minnarone ci sei?", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == []
    assert reactor.recent_messages() == []


def test_nothing_sentinel_tolerates_preceding_text(tmp_path):
    """'No suggestion needed. #nothing' still suppresses routing."""
    store, chat, llm, router, reactor = _build(
        tmp_path, llm_message="No suggestion needed. #nothing"
    )
    chat.perceive("minnarone ci sei?", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == []
    assert reactor.recent_messages() == []


def test_normal_response_routes_despite_nothing_sentinel_feature(tmp_path):
    """A response without #nothing routes normally (no false positive)."""
    store, chat, llm, router, reactor = _build(
        tmp_path, llm_message="Here is my suggestion: do X"
    )
    chat.perceive("minnarone ci sei?", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == [("Here is my suggestion: do X", OutputMode.PUBLIC)]
    assert reactor.recent_messages() == ["Here is my suggestion: do X"]


def test_nothing_with_end_conv_suppresses_routing(tmp_path):
    """'#nothing and also #end_conv' suppresses routing (nothing wins)."""
    store, chat, llm, router, reactor = _build(
        tmp_path, llm_message="#nothing and also #end_conv"
    )
    chat.perceive("minnarone ci sei?", speaker="enkk", ts=1.0)

    asyncio.run(reactor.run_once())

    assert router.sent == []
    assert reactor.recent_messages() == []
