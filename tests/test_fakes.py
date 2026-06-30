"""Test dei fake: verificano che soddisfino i contratti astratti (comportamento esterno).

Le parti async sono eseguite con `asyncio.run` per non dipendere da plugin pytest.
"""

import asyncio

import pytest

from minnarone.fakes import (
    FakeLLMProvider,
    FakeMemory,
    FakeOutputRouter,
    FakeSourceAdapter,
)
from minnarone.llm import LLMProvider, LLMTimeout
from minnarone.memory import FactsDelta, Memory
from minnarone.output import OutputMode, OutputRouter
from minnarone.source import RawEvent, SourceAdapter


def test_fakes_implement_their_interfaces():
    assert isinstance(FakeSourceAdapter([]), SourceAdapter)
    assert isinstance(FakeLLMProvider(), LLMProvider)
    assert isinstance(FakeMemory(), Memory)
    assert isinstance(FakeOutputRouter(), OutputRouter)


def test_source_adapter_lifecycle_and_replay():
    events = [RawEvent(channel="chat", payload={"text": "ciao"}, ts=1.0)]
    adapter = FakeSourceAdapter(events)

    async def run():
        assert adapter.channels() == {"chat"}
        await adapter.start()
        collected = [e async for e in adapter.events()]
        await adapter.stop()
        return collected

    assert asyncio.run(run()) == events


def test_llm_provider_returns_deterministic_message():
    provider = FakeLLMProvider(message="bella clip")
    result = asyncio.run(provider.complete("un prompt"))
    assert result.message == "bella clip"
    assert provider.last_prompt == "un prompt"


def test_llm_provider_scripted_messages_fail_loudly_when_exhausted():
    provider = FakeLLMProvider(messages=["prima"])

    assert asyncio.run(provider.complete("prompt 1")).message == "prima"
    with pytest.raises(AssertionError, match="fake LLM messages exhausted"):
        asyncio.run(provider.complete("prompt inatteso"))


def test_llm_provider_can_raise_timeout():
    provider = FakeLLMProvider(raise_timeout=True)
    with pytest.raises(LLMTimeout):
        asyncio.run(provider.complete("x"))


def test_memory_update_is_noop():
    mem = FakeMemory(soul="sono minnarone", facts="enkk ha 35 anni")
    blocks = mem.load()
    mem.update(FactsDelta(entity="enkk", text="ama il trap"))
    assert mem.load() == blocks  # update non altera lo stato in MVP


def test_output_router_captures_messages():
    router = FakeOutputRouter()
    asyncio.run(router.route("ciao a tutti", OutputMode.PUBLIC))
    assert router.sent == [("ciao a tutti", OutputMode.PUBLIC)]
