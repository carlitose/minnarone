"""Test del Reactor: wiring end-to-end Senser -> PromptBuilder -> LLM -> Output.

Verifica lo scheletro che cammina: una menzione transita per lo store e produce
un messaggio sul canale pubblico; senza menzione, nessun output.
"""

import asyncio

from minnarone.chat import ChatPerceiver
from minnarone.console import ConsoleOutputRouter  # noqa: F401 (import sanity)
from minnarone.fakes import FakeLLMProvider, FakeMemory, FakeOutputRouter
from minnarone.output import OutputMode
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
