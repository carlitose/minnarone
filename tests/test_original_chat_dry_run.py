"""Fake/offline original-chat dry-run acceptance."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from minnarone.audio import STREAMER
from minnarone.chat import ChatPerceiver
from minnarone.fakes import FakeLLMProvider, FakeMemory
from minnarone.output import CommentatorStyle, OutputMode, OutputRouter
from minnarone.output_sink import MinnaroneOutputStream, TuiPrivateOutputRouter
from minnarone.perception import Perception, Source
from minnarone.prompt import PromptBuilder
from minnarone.prompt_observation import ObservedLLMProvider, PromptObservationRecorder
from minnarone.reactor import Reactor
from minnarone.senser import Senser
from minnarone.store import PerceptionStore

FAKE_SUMMARY = "La chat ride della parata e lo streamer e' al boss finale."


class FailingPublicRouter(OutputRouter):
    """Public route guard: original-chat dry-run must stay local/private."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, OutputMode]] = []

    async def route(self, message: str, mode: OutputMode) -> None:
        self.sent.append((message, mode))
        raise AssertionError(f"public output path used: {message!r}")


@dataclass(frozen=True, slots=True)
class OriginalChatDryRun:
    store: PerceptionStore
    chat: ChatPerceiver
    senser: Senser
    builder: PromptBuilder
    provider: FakeLLMProvider
    recorder: PromptObservationRecorder
    stream: MinnaroneOutputStream
    public_router: FailingPublicRouter
    reactor: Reactor


def _build_original_chat_dry_run(tmp_path, *, llm_messages: list[str], clock=None):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser_kwargs = {} if clock is None else {"clock": clock}
    senser = Senser(store, agent_name="minnarone", **senser_kwargs)
    builder = PromptBuilder(
        FakeMemory(
            soul="Sono Minnarone nel canale di enkk.",
            facts="@enkk sta facendo una boss run offline di test.",
        ).load(),
        commentator_style=CommentatorStyle.ORIGINAL_CHAT,
    )
    provider = FakeLLMProvider(messages=llm_messages, model="fake-original-chat")
    recorder = PromptObservationRecorder()
    stream = MinnaroneOutputStream()
    public_router = FailingPublicRouter()
    reactor = Reactor(
        senser=senser,
        prompt_builder=builder,
        llm=ObservedLLMProvider(provider, recorder=recorder),
        router=TuiPrivateOutputRouter(stream, public_router=public_router),
        store=store,
        mode=OutputMode.PRIVATE,
        summary_provider=lambda: FAKE_SUMMARY,
    )
    return OriginalChatDryRun(
        store=store,
        chat=chat,
        senser=senser,
        builder=builder,
        provider=provider,
        recorder=recorder,
        stream=stream,
        public_router=public_router,
        reactor=reactor,
    )


def _seed_fake_multimodal_context(runtime: OriginalChatDryRun) -> None:
    runtime.chat.perceive("chat sta spammando KEKW", speaker="bob", ts=1.0)
    runtime.store.append(
        Perception(
            ts=2.0,
            source=Source.AUDIO,
            type="speech",
            text="ho appena parato il colpo del boss",
            speaker=STREAMER,
        )
    )
    runtime.store.append(
        Perception(
            ts=2.5,
            source=Source.VIDEO,
            type="caption",
            text="boss staggered with low health bar on screen",
        )
    )


def _stream_texts(runtime: OriginalChatDryRun) -> list[tuple[str, OutputMode]]:
    return [
        (message.text, message.mode) for message in runtime.stream.recent_messages()
    ]


def test_fake_original_chat_dry_run_routes_re_msg_locally_and_observes_prompt(
    tmp_path,
):
    runtime = _build_original_chat_dry_run(
        tmp_path,
        llm_messages=["re : parata clutch\nmsg : bella parata"],
        clock=lambda: 100.0,  # clock costante: timestamp relativi deterministici
    )
    _seed_fake_multimodal_context(runtime)
    runtime.chat.perceive(
        "minnarone guarda questa parata",
        speaker="alice",
        ts=3.0,
    )

    asyncio.run(runtime.reactor.run_once())

    assert _stream_texts(runtime) == [
        ("RE: parata clutch\nMSG: bella parata", OutputMode.PRIVATE)
    ]
    assert runtime.public_router.sent == []

    observations = runtime.recorder.observations()
    assert len(observations) == 1
    prompt = observations[0].prompt
    assert observations[0].context == "reactor:mention"
    assert runtime.provider.prompts == [prompt]
    assert "[FORMATO RISPOSTA]" in prompt
    assert "[CHAT RECENTE]" in prompt
    # recent-context original-chat: righe con prefisso `-<N>s` e speaker tra < >
    # (divergenza B). now=100 => bob@1.0 -> -99s, streamer@2.0 -> -98s.
    assert "-99s <bob>: chat sta spammando KEKW" in prompt
    assert "[PARLATO RECENTE]" in prompt
    assert "-98s <streamer>: ho appena parato il colpo del boss" in prompt
    assert "[SCHERMO RECENTE]" in prompt
    assert "s <anon>: boss staggered with low health bar on screen" in prompt
    # la SITUAZIONE (trigger) NON è timestamped: resta la resa piatta.
    assert "alice: minnarone guarda questa parata" in prompt

    stable_prefix = runtime.builder.stable_prefix()
    assert prompt.startswith(stable_prefix)
    assert FAKE_SUMMARY not in stable_prefix
    assert prompt.index(FAKE_SUMMARY) > len(stable_prefix)
    assert prompt.index("[MEMORIA]") < prompt.index("[CONVERSAZIONE RECENTE]")


def test_fake_original_chat_dry_run_second_end_conv_is_visible_and_closes_window(
    tmp_path,
):
    runtime = _build_original_chat_dry_run(
        tmp_path,
        llm_messages=[
            "RE: parata clutch\nMSG: bella parata",
            "RE: scambio finito\nMSG: #end_conv",
        ],
    )
    _seed_fake_multimodal_context(runtime)
    runtime.chat.perceive(
        "minnarone guarda questa parata",
        speaker="alice",
        ts=3.0,
    )
    asyncio.run(runtime.reactor.run_once())

    runtime.chat.perceive("minnarone ci sei ancora?", speaker="alice", ts=4.0)
    asyncio.run(runtime.reactor.run_once())

    assert _stream_texts(runtime) == [
        ("RE: parata clutch\nMSG: bella parata", OutputMode.PRIVATE),
        (
            "RE: scambio finito\nMSG: #end_conv\n(skip: not sent)",
            OutputMode.PRIVATE,
        ),
    ]
    assert runtime.public_router.sent == []
    assert "alice" not in runtime.senser.open_windows()

    observations = runtime.recorder.observations()
    assert [observation.prompt for observation in observations] == (
        runtime.provider.prompts
    )
    assert [observation.context for observation in observations] == [
        "reactor:mention",
        "reactor:mention",
    ]

    stable_prefix = runtime.builder.stable_prefix()
    second_prompt = observations[1].prompt
    assert "bella parata" not in stable_prefix
    assert "[I TUOI ULTIMI MESSAGGI]" in second_prompt
    # Formato divergenza C: `tu: "<msg>" (rispondevi a: <reason RE:>)`. Il
    # prefisso `-<N>s` dipende dal clock reale del dry-run, quindi si asserisce
    # sulla parte deterministica (testo + reason).
    assert 'tu: "bella parata" (rispondevi a: parata clutch)' in second_prompt
    assert second_prompt.index('tu: "bella parata"') > len(stable_prefix)
    assert second_prompt.index("[I TUOI ULTIMI MESSAGGI]") < second_prompt.index(
        "[CONVERSAZIONE RECENTE]"
    )
