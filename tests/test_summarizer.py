"""Test del Summarizer: memoria a breve termine via LLM.

Contratto: legge periodicamente le percezioni dallo store, chiede all'LLM un
riassunto della sessione finora, e lo espone come memoria a breve termine. Deve
tollerare input rumoroso/vuoto ed errori dell'LLM senza rompere il loop.
"""

import asyncio

from minnarone.chat import ChatPerceiver
from minnarone.fakes import FakeLLMProvider
from minnarone.perception import Perception, Source
from minnarone.prompt_observation import ObservedLLMProvider, PromptObservationRecorder
from minnarone.store import PerceptionStore
from minnarone.summarizer import Summarizer


def _build(tmp_path, llm_message="enkk ha battuto il boss."):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    llm = FakeLLMProvider(message=llm_message)
    summarizer = Summarizer(llm=llm, store=store)
    return store, chat, llm, summarizer


def _speech(store, text, speaker="streamer", ts=1.0):
    store.append(
        Perception(ts=ts, source=Source.AUDIO, type="speech", text=text, speaker=speaker)
    )


def _caption(store, text, ts=1.0):
    store.append(Perception(ts=ts, source=Source.VIDEO, type="caption", text=text))


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


def test_summarizer_prompt_observation_has_context_label(tmp_path):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    recorder = PromptObservationRecorder()
    llm = ObservedLLMProvider(
        FakeLLMProvider(message="riassunto"),
        recorder=recorder,
    )
    summarizer = Summarizer(llm=llm, store=store)
    chat.perceive("ho battuto il boss", speaker="enkk", ts=1.0)

    asyncio.run(summarizer.summarize())

    observation = recorder.latest()
    assert observation is not None
    assert observation.context == "summarizer"


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


def test_summarize_prompt_is_rolling_sintetizzatore_shape(tmp_path):
    # Il prompt e' quello incrementale del "sintetizzatore", non piu' il vecchio
    # "## EVENTI" from-scratch.
    store, chat, llm, summarizer = _build(tmp_path)
    chat.perceive("ciao", speaker="tizio", ts=1.0)

    asyncio.run(summarizer.summarize())

    assert "Sei un sintetizzatore" in llm.last_prompt
    assert "Riassunto attuale:" in llm.last_prompt
    assert "Eventi recenti:" in llm.last_prompt
    assert "Aggiorna il riassunto." in llm.last_prompt
    assert "## EVENTI" not in llm.last_prompt


def test_summarize_prompt_first_turn_uses_neutral_placeholder(tmp_path):
    # Primo giro: riassunto precedente vuoto -> placeholder neutro, non riga vuota.
    store, chat, llm, summarizer = _build(tmp_path)
    chat.perceive("ciao", speaker="tizio", ts=1.0)

    asyncio.run(summarizer.summarize())

    prompt = llm.last_prompt
    after = prompt.split("Riassunto attuale:\n", 1)[1]
    first_line = after.splitlines()[0]
    assert first_line.strip() != ""


def test_summarize_prompt_reinjects_previous_summary(tmp_path):
    # Il riassunto precedente viene reiniettato sotto "Riassunto attuale:".
    store, chat, llm, summarizer = _build(tmp_path, llm_message="Prima: enkk gioca.")
    chat.perceive("ciao", speaker="tizio", ts=1.0)
    asyncio.run(summarizer.summarize())  # stabilisce il riassunto precedente

    chat.perceive("come va?", speaker="caio", ts=2.0)
    asyncio.run(summarizer.summarize())

    prompt = llm.last_prompt
    reinjected = prompt.split("Riassunto attuale:\n", 1)[1]
    assert "Prima: enkk gioca." in reinjected.split("Eventi recenti:", 1)[0]


def test_summarize_prompt_groups_events_by_source(tmp_path):
    store, chat, llm, summarizer = _build(tmp_path)
    _speech(store, "adesso sistemo il dedup", speaker="streamer", ts=1.0)
    _caption(store, "editor di codice", ts=2.0)
    chat.perceive("finalmente funziona", speaker="pippo", ts=3.0)

    asyncio.run(summarizer.summarize())

    prompt = llm.last_prompt
    assert "STREAMER ha detto:" in prompt
    assert "SCHERMO:" in prompt
    assert "CHAT:" in prompt
    assert "- adesso sistemo il dedup" in prompt
    assert "- editor di codice" in prompt
    assert "- pippo: finalmente funziona" in prompt


def test_summarize_prompt_omits_empty_groups(tmp_path):
    store, chat, llm, summarizer = _build(tmp_path)
    chat.perceive("solo chat qui", speaker="pippo", ts=1.0)

    asyncio.run(summarizer.summarize())

    prompt = llm.last_prompt
    assert "CHAT:" in prompt
    assert "STREAMER ha detto:" not in prompt
    assert "SCHERMO:" not in prompt


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
