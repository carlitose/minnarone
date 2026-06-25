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
