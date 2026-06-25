"""Test del Summarizer: memoria a breve termine via LLM.

Contratto: legge periodicamente le percezioni dallo store, chiede all'LLM un
riassunto della sessione finora, e lo espone come memoria a breve termine. Deve
tollerare input rumoroso/vuoto ed errori dell'LLM senza rompere il loop.
"""

import asyncio

from minnarone.chat import ChatPerceiver
from minnarone.fakes import FakeLLMProvider
from minnarone.store import PerceptionStore
from minnarone.summarizer import Summarizer


def _build(tmp_path, llm_message="enkk ha battuto il boss."):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    llm = FakeLLMProvider(message=llm_message)
    summarizer = Summarizer(llm=llm, store=store)
    return store, chat, llm, summarizer


def test_summarize_reads_store_calls_llm_returns_text(tmp_path):
    store, chat, llm, summarizer = _build(tmp_path)
    chat.perceive("ho appena battuto il boss", speaker="enkk", ts=1.0)

    summary = asyncio.run(summarizer.summarize())

    assert summary == "enkk ha battuto il boss."


def test_latest_summary_readable_after_summarize(tmp_path):
    store, chat, llm, summarizer = _build(tmp_path)
    assert summarizer.current_summary == ""
    chat.perceive("ho battuto il boss", speaker="enkk", ts=1.0)

    asyncio.run(summarizer.summarize())

    assert summarizer.current_summary == "enkk ha battuto il boss."


def test_summarization_prompt_includes_perception_content(tmp_path):
    store, chat, llm, summarizer = _build(tmp_path)
    chat.perceive("ho battuto il boss del livello 5", speaker="enkk", ts=1.0)

    asyncio.run(summarizer.summarize())

    assert llm.last_prompt is not None
    assert "ho battuto il boss del livello 5" in llm.last_prompt
    assert "enkk" in llm.last_prompt


def test_empty_store_safe_no_llm_call(tmp_path):
    store, chat, llm, summarizer = _build(tmp_path)

    summary = asyncio.run(summarizer.summarize())

    # nessuna percezione: riassunto neutro, nessuna chiamata LLM sprecata
    assert summary == ""
    assert summarizer.current_summary == ""
    assert llm.last_prompt is None


def test_noisy_transcription_does_not_crash(tmp_path):
    store, chat, llm, summarizer = _build(tmp_path)
    # trascrizioni imperfette: testo vuoto, rumore, caratteri strani
    chat.perceive("", speaker=None, ts=1.0)
    chat.perceive("...ehm... [inint] %%%", speaker="enkk", ts=2.0)
    chat.perceive("ok ok", speaker="enkk", ts=3.0)

    summary = asyncio.run(summarizer.summarize())

    assert summary == "enkk ha battuto il boss."


def test_llm_error_during_loop_keeps_previous_summary(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    chat.perceive("ho battuto il boss", speaker="enkk", ts=1.0)

    # primo giro: LLM funziona, stabilisce un riassunto
    ok_llm = FakeLLMProvider(message="riassunto valido")
    summarizer = Summarizer(llm=ok_llm, store=store)
    asyncio.run(summarizer.summarize())
    assert summarizer.current_summary == "riassunto valido"

    # ora l'LLM va in timeout: il loop periodico non deve propagare l'errore
    summarizer._llm = FakeLLMProvider(raise_timeout=True)  # type: ignore[attr-defined]

    async def drive():
        task = asyncio.create_task(summarizer.run(interval=0.001))
        await asyncio.sleep(0.03)
        summarizer.stop()
        await task

    # non deve sollevare
    asyncio.run(drive())

    # il riassunto precedente è conservato
    assert summarizer.current_summary == "riassunto valido"


def test_run_loop_updates_summary_then_stops(tmp_path):
    store, chat, llm, summarizer = _build(tmp_path)
    chat.perceive("ho battuto il boss", speaker="enkk", ts=1.0)

    async def drive():
        task = asyncio.create_task(summarizer.run(interval=0.001))
        await asyncio.sleep(0.03)
        summarizer.stop()
        await task

    asyncio.run(drive())

    assert summarizer.current_summary == "enkk ha battuto il boss."
