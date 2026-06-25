"""Test dell'app di riferimento (slice 11): assemblaggio da config.

L'issue 11 cabla i moduli SDK insieme a partire da una `Config`. Qui si verifica
che `build_agent` componga il grafo correttamente (offline, con fake LLM
transport e adapter in-memory), lo switch modalità public/private, e che i punti
v2 (disclosure/retention/auto-memory) siano presenti ma inerti.
"""

import asyncio
import json
import textwrap

import pytest

from minnarone.app import (
    Agent,
    PrivateModeNotImplemented,
    PrivateNotImplementedRouter,
    build_agent,
)
from minnarone.config import Config, ConfigError
from minnarone.console import ConsoleOutputRouter
from minnarone.output import OutputMode
from minnarone.perception import Perception, Source
from minnarone.reactor import Reactor
from minnarone.source import RawEvent


def _fake_transport(*, url, headers, body, timeout):
    # Trasporto HTTP fake: nessuna rete. Non dovrebbe nemmeno essere chiamato
    # durante il solo assemblaggio, ma è qui per sicurezza se un test reagisce.
    from minnarone.openrouter import HttpResponse

    payload = b'{"choices":[{"message":{"content":"ciao"}}]}'
    return HttpResponse(status=200, body=payload)


def _write_workspace(
    tmp_path, *, mode="public", announce_ai=False, auto_memory=True, extra=""
):
    """Crea soul/facts su disco e un config YAML; ritorna il path del config."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    soul = tmp_path / "soul.md"
    soul.write_text("Sono Minnarone, 25 anni.", encoding="utf-8")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir(exist_ok=True)
    (facts_dir / "canale.md").write_text("Canale Twitch di test.", encoding="utf-8")

    # Dedent PRIMA della sostituzione, così un `extra` multilinea (le cui righe
    # 2+ non sono indentate) non sballa il calcolo dell'indentazione comune.
    template = textwrap.dedent(
        """
        mode: {mode}
        soul_path: {soul}
        facts_dir: {facts_dir}
        adapter: os_capture
        llm_provider: grok
        agent_name: minnarone
        disclosure:
          announce_ai: {announce_ai}
        retention:
          perceptions_days: 7
        auto_memory: {auto_memory}
        {extra}
        """
    )
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        template.format(
            mode=mode,
            soul=soul,
            facts_dir=facts_dir,
            announce_ai=str(announce_ai).lower(),
            auto_memory=str(auto_memory).lower(),
            extra=extra,
        ),
        encoding="utf-8",
    )
    return cfg


# --- 1. build_agent compone un agente eseguibile ---------------------------


def test_build_agent_wires_all_components(tmp_path):
    cfg = Config.load(_write_workspace(tmp_path))
    agent = build_agent(cfg, transport=_fake_transport)

    assert isinstance(agent, Agent)
    # Reactor presente e cablato (è l'orchestratore del loop senso-reazione).
    assert isinstance(agent.reactor, Reactor)
    # Lo store esiste su disco (cartella di lavoro derivata dal config).
    assert agent.store is not None
    # Senser, summarizer, human, prompt builder, llm tutti cablati.
    assert agent.senser is not None
    assert agent.summarizer is not None
    assert agent.human is not None
    assert agent.prompt_builder is not None
    assert agent.llm is not None


def test_build_agent_passes_announce_ai_into_prompt(tmp_path):
    cfg = Config.load(_write_workspace(tmp_path, announce_ai=True))
    agent = build_agent(cfg, transport=_fake_transport)
    # announce_ai True deve fluire nella stance del prompt: la regola di
    # disclosure consente di dichiararsi AI (byte-invariante per config fissa).
    prefix = agent.prompt_builder.stable_prefix()
    assert "puoi dichiarare apertamente di" in prefix


def test_build_agent_default_hides_ai_disclosure(tmp_path):
    cfg = Config.load(_write_workspace(tmp_path, announce_ai=False))
    agent = build_agent(cfg, transport=_fake_transport)
    prefix = agent.prompt_builder.stable_prefix()
    assert "Non rivelare MAI di essere un'AI" in prefix


def test_build_agent_loads_soul_and_facts_from_config(tmp_path):
    cfg = Config.load(_write_workspace(tmp_path))
    agent = build_agent(cfg, transport=_fake_transport)
    prefix = agent.prompt_builder.stable_prefix()
    assert "Sono Minnarone" in prefix
    assert "Canale Twitch di test." in prefix


# --- 2. config invalido -> errore chiaro -----------------------------------


def test_build_from_missing_config_raises_config_error(tmp_path):
    with pytest.raises(ConfigError):
        Config.load(tmp_path / "nope.yaml")


# --- 3. mode: public -> ConsoleOutputRouter --------------------------------


def test_public_mode_uses_console_router(tmp_path):
    cfg = Config.load(_write_workspace(tmp_path, mode="public"))
    agent = build_agent(cfg, transport=_fake_transport)
    assert isinstance(agent.router, ConsoleOutputRouter)
    assert agent.mode is OutputMode.PUBLIC


# --- 4. mode: private -> accettato, ma output segnala not-implemented -------


def test_private_mode_builds_without_crashing(tmp_path):
    cfg = Config.load(_write_workspace(tmp_path, mode="private"))
    # Costruzione NON deve crashare: la modalità privata è accettata.
    agent = build_agent(cfg, transport=_fake_transport)
    assert agent.mode is OutputMode.PRIVATE
    assert isinstance(agent.router, PrivateNotImplementedRouter)


def test_private_router_signals_not_implemented_on_route(tmp_path):
    import asyncio

    cfg = Config.load(_write_workspace(tmp_path, mode="private"))
    agent = build_agent(cfg, transport=_fake_transport)
    # Usare il percorso privato segnala chiaramente "non implementato in MVP".
    with pytest.raises(PrivateModeNotImplemented):
        asyncio.run(agent.router.route("ciao", OutputMode.PRIVATE))


# --- 5. punti v2 presenti ma inerti ----------------------------------------


def test_v2_points_present_but_inert(tmp_path):
    # Inertness REALE: togglare auto_memory True vs False non cambia ALCUN
    # comportamento osservabile dell'agente assemblato (è un punto v2 non
    # cablato). Si confrontano due agenti identici tranne `auto_memory`.
    cfg_on = Config.load(_write_workspace(tmp_path / "on", auto_memory=True))
    cfg_off = Config.load(_write_workspace(tmp_path / "off", auto_memory=False))
    assert cfg_on.auto_memory is True
    assert cfg_off.auto_memory is False
    assert cfg_on.retention.perceptions_days == 7

    agent_on = build_agent(cfg_on, transport=_fake_transport)
    agent_off = build_agent(cfg_off, transport=_fake_transport)

    # Prompt stabile (soul/facts/stance) byte-identico: auto_memory non incide.
    assert agent_on.prompt_builder.stable_prefix() == (
        agent_off.prompt_builder.stable_prefix()
    )
    # Memoria caricata identica: nessun auto-aggiornamento.
    assert agent_on.memory.load().soul == agent_off.memory.load().soul
    assert agent_on.memory.load().facts == agent_off.memory.load().facts
    # Stessi canali di percezione cablati: nessun ramo dipende da auto_memory.
    assert set(agent_on.perceivers) == set(agent_off.perceivers)


# --- agent_name additivo ----------------------------------------------------


# --- smoke end-to-end dello scenario streamer pubblico ---------------------


def test_streamer_scenario_smoke_end_to_end(tmp_path, monkeypatch):
    """Una menzione in chat → l'agente reagisce sul canale pubblico.

    Esercita il motore senso-reazione assemblato da config, offline: store +
    Senser (menzione) + PromptBuilder + LLM (fake transport) + HumanLikeness +
    OutputRouter. Il loop di percezione è simulato scrivendo direttamente nello
    store (il passo manuale live è la cattura device). Si inietta un router che
    cattura l'output (l'instradamento per modalità è coperto dai test sopra).
    """
    import asyncio

    from minnarone.fakes import FakeOutputRouter

    # Il provider reale risolve l'API key prima della chiamata: nel test la
    # forniamo via env così il fake transport (nessuna rete) viene usato.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    capture = FakeOutputRouter()
    store_path = tmp_path / "perceptions.jsonl"
    cfg = Config.load(_write_workspace(tmp_path, mode="public"))
    agent = build_agent(
        cfg, transport=_fake_transport, store_path=store_path, router=capture
    )
    assert agent.mode is OutputMode.PUBLIC

    # Simula la percezione: un utente nomina l'agente in chat.
    agent.store.append(
        Perception(
            ts=1.0,
            source=Source.CHAT,
            type="msg",
            text="ehi minnarone come va?",
            speaker="utente1",
        )
    )

    asyncio.run(agent.reactor.run_once())

    # L'agente ha instradato esattamente la risposta del (fake) LLM in PUBLIC.
    assert capture.sent == [("ciao", OutputMode.PUBLIC)]


def test_agent_name_defaults_when_omitted(tmp_path):
    # Config minimale senza agent_name: deve avere un default sensato e non
    # rompere l'assemblaggio.
    soul = tmp_path / "soul.md"
    soul.write_text("io", encoding="utf-8")
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text(
        textwrap.dedent(
            f"""
            mode: public
            soul_path: {soul}
            facts_dir: {facts_dir}
            adapter: os_capture
            llm_provider: grok
            """
        ),
        encoding="utf-8",
    )
    cfg = Config.load(cfg_path)
    assert cfg.agent_name  # default non vuoto
    agent = build_agent(cfg, transport=_fake_transport)
    assert agent is not None


# --- Fix 1: il loop del Summarizer parte nel percorso live ------------------


def _prompt_from_body(body: bytes) -> str:
    """Estrae il testo del prompt dal body JSON della richiesta (OpenAI shape)."""
    data = json.loads(body.decode("utf-8"))
    return data["messages"][-1]["content"]


def _recording_transport(prompts: list[str], *, summary: str = "RIASSUNTO-NOTO"):
    """Transport fake che registra i prompt e risponde in modo deterministico.

    Riconosce la chiamata del Summarizer dal suo header ("## EVENTI") e risponde
    con un riassunto noto; per ogni altra chiamata (reazione del Reactor) risponde
    "ciao" e registra il prompt in `prompts`, così il test può asserire che il
    riassunto è fluito nel prompt di reazione.
    """
    from minnarone.openrouter import HttpResponse

    def transport(*, url, headers, body, timeout):
        prompt = _prompt_from_body(body)
        if "## EVENTI" in prompt:
            content = summary
        else:
            prompts.append(prompt)
            content = "ciao"
        payload = json.dumps({"choices": [{"message": {"content": content}}]})
        return HttpResponse(status=200, body=payload.encode("utf-8"))

    return transport


def test_run_starts_summarizer_loop(tmp_path, monkeypatch):
    """`Agent.run()` avvia il loop del Summarizer concorrentemente al resto.

    Senza adapter è il loop di reazione a guidare la durata: lo si avvia come
    task, si attende che il Summarizer abbia agito (`summarize()` invocato — non
    resta inerte come prima del fix), poi si ferma il Reactor per chiudere pulito.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    calls = {"n": 0}

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="summarizer_interval: 0.01\nsenser_interval: 0.01",
        )
    )
    agent = build_agent(
        cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl"
    )

    # Una percezione nello store così `summarize()` fa effettivamente lavoro.
    agent.store.append(
        Perception(ts=1.0, source=Source.CHAT, type="msg", text="ciao a tutti")
    )

    orig = agent.summarizer.summarize

    async def counting_summarize():
        calls["n"] += 1
        return await orig()

    monkeypatch.setattr(agent.summarizer, "summarize", counting_summarize)

    async def drive():
        task = asyncio.create_task(agent.run())
        # Attendi (con timeout) che il loop del Summarizer abbia agito.
        for _ in range(500):
            if calls["n"] >= 1:
                break
            await asyncio.sleep(0.01)
        agent.reactor.stop()
        await asyncio.wait_for(task, timeout=5.0)

    asyncio.run(drive())
    assert calls["n"] >= 1


def test_run_summary_reaches_reaction_prompt(tmp_path, monkeypatch):
    """End-to-end: il riassunto prodotto dal loop raggiunge il prompt di reazione.

    Si inietta un adapter che emette una menzione in chat e un transport che
    risponde con un riassunto noto alla chiamata del Summarizer. Dopo aver
    girato l'agente, il prompt di reazione (registrato) contiene quel riassunto:
    prova che il loop del Summarizer gira e che `current_summary` fluisce nel
    Reactor attraverso il motore in esecuzione.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    prompts: list[str] = []

    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="summarizer_interval: 0.01\nsenser_interval: 0.01",
        )
    )

    from minnarone.fakes import FakeSourceAdapter

    adapter = FakeSourceAdapter(
        [
            RawEvent(
                channel="chat",
                payload={"text": "ehi minnarone ci sei?", "speaker": "u1"},
                ts=1.0,
            )
        ]
    )
    agent = build_agent(
        cfg,
        transport=_recording_transport(prompts, summary="RIASSUNTO-NOTO"),
        store_path=tmp_path / "p.jsonl",
        adapter=adapter,
    )

    # Genera il riassunto PRIMA di avviare run(), così è già disponibile quando
    # il Reactor reagisce nel tick finale (deterministico, niente race sul loop).
    agent.store.append(
        Perception(ts=0.5, source=Source.CHAT, type="msg", text="contesto sessione")
    )
    asyncio.run(agent.summarizer.summarize())
    assert agent.summarizer.current_summary == "RIASSUNTO-NOTO"

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    assert prompts, "il Reactor non ha mai reagito alla menzione"
    assert any("RIASSUNTO-NOTO" in p for p in prompts)


# --- Fix 2: la pompa di percezione attraversa l'adapter (percorso live) -----


def test_dispatch_routes_chat_event_to_store(tmp_path):
    """Il dispatcher instrada un `RawEvent` di chat al `ChatPerceiver` → store."""
    cfg = Config.load(_write_workspace(tmp_path, mode="public"))
    agent = build_agent(
        cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl"
    )
    agent.dispatch(
        RawEvent(channel="chat", payload={"text": "ciao mondo", "speaker": "u1"}, ts=7.0)
    )
    tail = agent.store.tail(10)
    assert tail[-1].text == "ciao mondo"
    assert tail[-1].speaker == "u1"
    assert tail[-1].source is Source.CHAT


def test_dispatch_skips_unconfigured_channel(tmp_path):
    """Un canale senza perceiver (audio/video AFK) viene saltato, non crasha."""
    cfg = Config.load(_write_workspace(tmp_path, mode="public"))
    agent = build_agent(
        cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl"
    )
    assert "audio" not in agent.perceivers
    assert "video" not in agent.perceivers
    # Nessuna eccezione, nessuna percezione scritta.
    agent.dispatch(RawEvent(channel="audio", payload=object(), ts=1.0))
    assert agent.store.tail(10) == []


def test_run_pumps_chat_perception_end_to_end(tmp_path, monkeypatch):
    """Capstone e2e: adapter → perceiver → store → senser → reactor → output.

    Un `FakeSourceAdapter` emette una menzione in chat; si avvia l'Agent; la
    percezione atterra nello store E il Reactor reagisce (il router cattura il
    messaggio) — tutto concorrente nel motore in esecuzione.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from minnarone.fakes import FakeOutputRouter, FakeSourceAdapter

    capture = FakeOutputRouter()
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="summarizer_interval: 0.01\nsenser_interval: 0.01",
        )
    )
    adapter = FakeSourceAdapter(
        [
            RawEvent(
                channel="chat",
                payload={"text": "ehi minnarone come va?", "speaker": "u1"},
                ts=1.0,
            )
        ]
    )
    agent = build_agent(
        cfg,
        transport=_fake_transport,
        store_path=tmp_path / "p.jsonl",
        router=capture,
        adapter=adapter,
    )

    asyncio.run(asyncio.wait_for(agent.run(), timeout=5.0))

    # La percezione è atterrata nello store (pompa adapter→perceiver→store).
    tail = agent.store.tail(10)
    assert any(p.text == "ehi minnarone come va?" for p in tail)
    # E il Reactor ha reagito instradando la risposta del (fake) LLM in PUBLIC.
    assert ("ciao", OutputMode.PUBLIC) in capture.sent


def test_run_without_adapter_stops_cleanly_on_reactor_stop(tmp_path, monkeypatch):
    """Senza adapter `run()` gira il loop di reazione finché `reactor.stop()`.

    Comportamento live identico a prima del capstone (la cattura device è il
    passo manuale): nessuna sorgente, il loop di reazione guida la durata e si
    ferma pulito su `stop()`, senza task orfani (un timeout = fallimento).
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    cfg = Config.load(
        _write_workspace(
            tmp_path,
            mode="public",
            extra="summarizer_interval: 0.01\nsenser_interval: 0.01",
        )
    )
    agent = build_agent(
        cfg, transport=_fake_transport, store_path=tmp_path / "p.jsonl"
    )
    assert agent.adapter is None

    async def drive():
        task = asyncio.create_task(agent.run())
        await asyncio.sleep(0.05)  # lascia girare qualche tick
        assert not task.done()  # senza stop, il loop NON termina da solo
        agent.reactor.stop()
        await asyncio.wait_for(task, timeout=5.0)

    asyncio.run(drive())
