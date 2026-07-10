"""Operator handoff coverage for Twitch smoke/config docs."""

import re
import shlex
from pathlib import Path

import pytest

import minnarone.cli as cli
from minnarone.config import Config
from minnarone.memory import FileMemory
from minnarone.output import CommentatorStyle, OutputMode
from minnarone.prompt import PromptBuilder
from minnarone.twitch_smoke import main
from minnarone.twitch_smoke_artifacts import SmokeStats


def test_existing_os_capture_example_remains_valid():
    cfg = Config.load(Path("examples/minnarone.example.yaml"))

    assert cfg.adapter == "os_capture"
    assert cfg.twitch is None


def test_twitch_example_config_loads_future_shape():
    cfg = Config.load(Path("examples/twitch.example.yaml"))

    assert cfg.adapter == "twitch"
    assert cfg.twitch is not None
    assert cfg.twitch.channel == "minnarone"
    assert cfg.twitch.chat is True
    assert cfg.twitch.audio is False
    assert cfg.twitch.video is False
    assert cfg.vad.mode == 2
    assert cfg.vad.frame_ms == 30
    assert cfg.vad.padding_ms == 300
    assert cfg.asr.model == "large-v3-turbo"
    assert cfg.asr.condition_on_previous_text is False
    assert cfg.speaker_embedding.provider == "cpu"
    assert cfg.speaker_embedding.dimension == 192
    assert cfg.speaker_clustering.threshold == 0.45
    assert cfg.speaker_clustering.warmup_seconds == 60.0
    assert cfg.speaker_clustering.min_update_seconds == 1.0
    assert cfg.video.sample_every == 1
    assert cfg.video.dedup_change_threshold == 0.0
    assert cfg.vlm.model is None
    assert cfg.vlm.device == "auto"
    assert cfg.vlm.max_new_tokens == 48
    assert cfg.vlm.language == "en"
    assert len(cfg.commentator.profiles) == 0


def test_twitch_commentator_example_config_loads_console_only_shape():
    cfg = Config.load(Path("examples/twitch-commentator.example.yaml"))

    assert cfg.mode is OutputMode.PRIVATE
    assert cfg.adapter == "twitch"
    assert cfg.twitch is not None
    assert cfg.twitch.chat is True
    assert cfg.twitch.audio is False
    assert cfg.twitch.video is False
    assert len(cfg.commentator.profiles) > 0
    assert cfg.commentator.language == "it"
    assert CommentatorStyle.OPERATOR in cfg.commentator.profiles
    assert cfg.commentator.profiles[CommentatorStyle.OPERATOR].idle_interval == 30.0


def test_teams_commentator_preset_loads_os_capture_private_shape():
    cfg = Config.load(Path("examples/teams-commentator.yaml"))

    assert cfg.mode is OutputMode.PRIVATE
    assert cfg.adapter == "os_capture"
    assert cfg.twitch is None
    assert cfg.os_capture is not None
    assert cfg.os_capture.audio is True
    assert cfg.os_capture.video is True
    assert cfg.os_capture.video_fps == 1.0
    assert cfg.os_capture.monitor == 1
    assert len(cfg.commentator.profiles) > 0
    assert CommentatorStyle.OPERATOR in cfg.commentator.profiles
    assert cfg.commentator.language == "it"
    # Nessun VALORE segreto hardcoded nel preset: non deve dichiarare una chiave
    # (i commenti possono nominare OPENROUTER_API_KEY, che arriva dall'ambiente).
    assert not cfg.llm_params.get("api_key")


def test_original_chat_example_loads_seed_memory_into_prompt():
    cfg = Config.load(Path("examples/twitch-original-chat.example.yaml"))

    assert cfg.mode is OutputMode.PRIVATE
    assert CommentatorStyle.ORIGINAL_CHAT in cfg.commentator.profiles

    blocks = FileMemory(soul_path=cfg.soul_path, facts_dir=cfg.facts_dir).load()
    assert blocks.soul.strip()
    assert blocks.facts.strip()

    active = cfg.commentator.active_styles()
    style = active[0] if active else None
    prefix = PromptBuilder(
        blocks,
        announce_ai=cfg.disclosure.announce_ai,
        commentator_language=cfg.commentator.language,
        commentator_style=style,
    ).stable_prefix()

    assert "[MEMORIA PERMANENTE]" in prefix
    assert prefix.index("CHI SEI:") < prefix.index(blocks.soul)
    assert prefix.index("COSA SAI SU @enkk") < prefix.index(blocks.facts)


@pytest.mark.parametrize(
    ("cwd", "config_path"),
    [
        (Path("examples"), Path("twitch-original-chat.example.yaml")),
        (Path("tests"), Path("../examples/twitch-original-chat.example.yaml")),
    ],
)
def test_original_chat_example_loads_seed_memory_from_non_root_cwd(
    monkeypatch,
    cwd,
    config_path,
):
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(repo_root / cwd)

    cfg = Config.load(config_path)
    blocks = FileMemory(soul_path=cfg.soul_path, facts_dir=cfg.facts_dir).load()

    assert blocks.soul.strip()
    assert blocks.facts.strip()


def test_twitch_example_documents_console_only_runtime():
    text = Path("examples/twitch.example.yaml").read_text(encoding="utf-8")

    assert "console" in text.lower()
    assert "no privmsg sent" in text.lower()


def test_twitch_operator_docs_cover_setup_smoke_artifacts_and_troubleshooting():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "streamlink",
        "ffmpeg",
        "python --version",
        "uv --version",
        "TWITCH_BOT_USERNAME",
        "TWITCH_OAUTH_TOKEN",
        "minnarone-twitch-smoke",
        "--no-chat --audio",
        "--vad-diagnostic",
        "vad_utterances",
        "vad_utterance_durations_ms",
        "--no-chat --video",
        "--audio --video",
        "perceptions.jsonl",
        "raw/audio",
        "raw/video",
        "stats.json",
        "adapter: twitch",
        "OPENROUTER_API_KEY",
        "offline",
        "zero eventi",
    ]
    for phrase in required:
        assert phrase in text


def test_twitch_operator_docs_cover_python_extras_and_model_setup():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "Python Extras Matrix",
        "uv sync --extra asr",
        "uv sync --extra speaker",
        "uv sync --extra audio",
        "uv sync --extra video",
        "uv sync --extra vlm",
        "uv sync --extra tui",
        "webrtcvad-wheels",
        "faster-whisper",
        "sherpa-onnx",
        "Python `streamlink` package",
        "`av`",
        "transformers",
        "torch",
        "torchvision",
        "accelerate",
        "Pillow",
        "Model Setup",
        "large-v3-turbo",
        "CAM++",
        "Qwen2-VL-compatible",
        "vlm.model",
    ]
    for phrase in required:
        assert phrase in text


def test_twitch_operator_docs_cover_apple_silicon_recommendations():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "Apple Silicon",
        "M2 Max",
        "32 GB",
        "device: cpu",
        "compute_type: int8",
        "provider: cpu",
        "num_threads: 2",
        "device: mps",
        "device_map: null",
        "video_fps: 1.0",
        "280 GB",
    ]
    for phrase in required:
        assert phrase in text


def test_twitch_operator_docs_describe_console_runtime_with_optional_audio():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    assert "chat-only" in text
    assert "twitch.audio: true" in text
    assert "console" in text
    assert "twitch.send.mode: off" in text
    assert "does not yet wire" not in text


def test_twitch_operator_docs_cover_manual_local_asr_smoke():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "Local ASR Smoke",
        "faster-whisper",
        "large-v3-turbo",
        "condition_on_previous_text: false",
        "speaker `?`",
        "audio/speech",
        "python - <<'PY'",
        "minnarone.asr",
    ]
    for phrase in required:
        assert phrase in text


def test_twitch_operator_docs_cover_manual_speaker_embedding_smoke():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "Local Speaker Embedding Smoke",
        "sherpa-onnx",
        "uv sync --extra audio",
        "SpeakerEmbeddingConfig",
        "SherpaOnnxSpeakerEmbeddingBackend",
        "speaker_embedding:",
        "speaker_clustering:",
        "warmup_seconds: 60.0",
        "min_update_seconds: 1.0",
        "streamer",
        "altro",
    ]
    for phrase in required:
        assert phrase in text


def test_twitch_operator_docs_cover_manual_speaker_clustering_smoke():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "Local Speaker Clustering Smoke",
        "OnlineSpeakerClusterer",
        "SpeakerClusteringConfig",
        "threshold=0.45",
        "warmup_seconds=2.0",
        "min_update_seconds=1.0",
        "too short -> ?",
        "streamer_cluster_id",
        "{streamer, altro, ?}",
        "label becomes `streamer`",
    ]
    for phrase in required:
        assert phrase in text


def test_twitch_operator_docs_cover_manual_pyav_video_frame_validation():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "PyAV Video Frame Runtime Validation",
        "uv sync --extra video",
        "uv run --extra video python",
        "Python `streamlink` package",
        "twitch.video: true",
        "top-level `video:` block",
        "dedup_change_threshold",
        "Streamlink + PyAV",
        "TwitchPyAvVideoReader",
        "VideoFrame",
        "not captioning",
    ]
    for phrase in required:
        assert phrase in text


def test_twitch_operator_docs_cover_manual_qwen_vl_caption_smoke():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "Local Qwen2-VL Caption Smoke",
        "uv sync --extra video --extra vlm",
        "transformers",
        "torch",
        "torchvision",
        "Pillow",
        "Qwen2VlCaptioner",
        "QwenVlConfig",
        "vlm.model",
        "concise English",
        "video/caption",
        "bounded perception queue",
        "fake captioners",
    ]
    for phrase in required:
        assert phrase in text


def test_twitch_operator_docs_cover_local_commentator_mode():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "Local Commentator Mode",
        "commentator.profiles",
        "mode: private",
        "[PRIVATE]",
        "TUI/dashboard",
        "no PRIVMSG is",
        "no public chat write/send",
        "Italian comments",
        "idle_interval",
        "examples/twitch-commentator.example.yaml",
        "no commentator profiles",
    ]
    for phrase in required:
        assert phrase in text


def test_twitch_operator_docs_cover_original_chat_seed_memory():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    required = [
        "Original-Chat Dry-Run Seed Memory",
        "examples/twitch-original-chat.example.yaml",
        "examples/original-chat-memory/soul.md",
        "examples/original-chat-memory/facts",
        "`soul`",
        "`facts`",
        "identity, persona, and style",
        "stable facts about channels or interlocutors",
        "manually authored for now",
        "no auto-memory",
        "[MEMORIA PERMANENTE]",
    ]
    for phrase in required:
        assert phrase in normalized


def test_twitch_operator_docs_cover_local_perception_observability():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "Local Perception Observability",
        "Agent.observability_snapshot()",
        "audio transcriptions with speaker labels",
        "video captions",
        "bounded media queue counters",
        "stage-categorized local failures",
        "speaker cluster diagnostics",
        "talk time",
        "streamer cluster id",
        "raw audio bytes",
        "raw frame payloads",
        "Twitch OAuth",
        "OpenRouter keys",
        "`vad`",
        "`asr`",
        "`embedding`",
        "`clustering`",
        "`pyav`",
        "`dedup`",
        "`vlm`",
    ]
    for phrase in required:
        assert phrase in text


def test_twitch_operator_docs_cover_live_tui_replay_and_acceptance_workflow():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "Live Observability TUI",
        "uv sync --extra audio --extra video --extra vlm --extra tui",
        "python -m minnarone path/to/twitch-commentator.local.yaml --tui",
        "python -m minnarone --replay .local/minnarone/runs/run-",
        "python -m minnarone --replay .local/minnarone/runs/run-YYYYMMDDTHHMMSSZ-aaaaaaaa/perceptions.jsonl",
        "IDLE",
        "FINESTRA CHAT",
        "STREAMER",
        "CHAT",
        "EVENTI",
        "MINNARONE",
        "TRASCRIZIONE",
        "VIDEO",
        "MEMORIA",
        "PROMPT tab",
        "exact redacted prompt",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cached_tokens",
        "cache_write_tokens",
        "cache_read_tokens",
        "cost=unknown",
        "best effort",
        "source health labels",
        "`ok`",
        "`idle`",
        "`busy`",
        "`failed`",
        "`unknown`",
        "counts chat=",
        "queue_depth=",
        "failed",
        "latest 20",
        "latest 50",
        "200 KB",
        ".local/minnarone/runs/run-",
        "debug/prompts",
        "debug/events.jsonl",
        "gitignored",
        "disk safety",
        "read-only",
        "twitch.send.mode: shadow",
        "Manual Live Acceptance Checklist",
    ]
    for phrase in required:
        assert phrase in text


def test_documented_live_tui_and_replay_commands_match_cli_contract():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")
    commands = [
        argv
        for argv in _documented_minnarone_commands(text)
        if "--tui" in argv or "--replay" in argv
    ]

    assert ["path/to/twitch-commentator.local.yaml", "--tui"] in commands
    assert [
        "--replay",
        ".local/minnarone/runs/run-YYYYMMDDTHHMMSSZ-aaaaaaaa",
    ] in commands
    assert [
        "--replay",
        ".local/minnarone/runs/run-YYYYMMDDTHHMMSSZ-aaaaaaaa/perceptions.jsonl",
    ] in commands

    for argv in commands:
        parsed = cli._parse_args(argv)
        if "--tui" in argv:
            assert parsed.config == "path/to/twitch-commentator.local.yaml"
            assert parsed.tui is True
            assert parsed.replay is None
        if "--replay" in argv:
            assert parsed.config is None
            assert parsed.tui is False
            assert parsed.replay is not None


def test_twitch_operator_docs_cover_full_commentator_run_workflow():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "Full Commentator Run Workflow",
        "uv sync --extra audio --extra video --extra vlm --extra tui",
        "examples/twitch-commentator.example.yaml",
        "OPENROUTER_API_KEY",
        "TWITCH_BOT_USERNAME",
        "TWITCH_OAUTH_TOKEN",
        "mode: private",
        "commentator:",
        "uv run python -m minnarone",
        "--check",
        "[PRIVATE]",
        "No public Twitch messages are sent",
        "PRIVMSG output is",
        "Live Observability TUI",
        "--tui",
        "Replay TUI",
    ]
    for phrase in required:
        assert phrase in text


def test_twitch_operator_docs_do_not_show_direct_secret_exports():
    text = (
        Path("docs/twitch-operator.md").read_text(encoding="utf-8")
        + "\n"
        + Path("README.md").read_text(encoding="utf-8")
    )

    forbidden = [
        "export OPENROUTER_API_KEY=",
        "export TWITCH_OAUTH_TOKEN=",
        "export TWITCH_BOT_USERNAME=",
        "export TWITCH_SEND_OAUTH_TOKEN=",
    ]
    for phrase in forbidden:
        assert phrase not in text
    assert 'read -r -s -p "OPENROUTER_API_KEY: "' in text
    assert 'read -r -s -p "TWITCH_OAUTH_TOKEN: "' in text
    assert 'read -r -s -p "TWITCH_SEND_OAUTH_TOKEN: "' in text


def test_readme_private_commentator_wording_is_not_contradictory():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "private+commentator = console locale" in text
    assert "private solo = whisper v2" in text
    assert "commentatore locale su console" in text
    # The README accurately states that private mode never sends PRIVMSG.
    assert "nessun messaggio PRIVMSG" in text


def test_twitch_operator_docs_cover_public_chat_send_section():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "Public Chat Send",
        "Single-Writer Invariant",
        "TwitchChatSender",
        "Dedicated Bot Account",
        "chat:edit",
        "Write Token",
        "TWITCH_SEND_OAUTH_TOKEN",
        "Allow-List Workflow",
        "allowed_channels",
        "Shadow Rehearsal Workflow",
        "twitch.send.mode: shadow",
        "Live Enablement Checklist",
        "kill-switch",
        "attended-only",
        "Budget and Rate Guidance",
        "max_per_minute",
        "max_per_hour",
        "failure_threshold",
        "Send Safety Summary",
        "mode: shadow",
        "mode: live",
    ]
    for phrase in required:
        assert phrase in text


def test_twitch_operator_docs_single_writer_invariant_searchable():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    assert "Only `TwitchChatSender` may write `PRIVMSG`" in text


def test_twitch_operator_docs_no_live_mode_in_example_yaml():
    """Example configs must show shadow at most; live appears only in docs."""
    for name in [
        "examples/twitch.example.yaml",
        "examples/twitch-commentator.example.yaml",
        "examples/twitch-original-chat.example.yaml",
    ]:
        text = Path(name).read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.lstrip("# ").strip()
            # Skip doc prose/comments that mention live as a concept
            if stripped.startswith("mode:") and "live" in stripped:
                assert False, f"{name} contains 'mode: live' as a config value"


def test_twitch_operator_docs_no_real_tokens():
    import re

    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    # No string that looks like a real oauth token (30+ hex chars after prefix)
    assert not re.search(r"oauth:[a-z0-9]{30,}", text)


def test_twitch_operator_docs_troubleshoot_model_capture_diarization_video_vlm():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "Missing ASR model",
        "Empty ASR output",
        "vad_utterances",
        "Speaker over-segmentation",
        "Speaker under-segmentation",
        "speaker_embedding.model_path",
        "No PyAV frames",
        "Repeated or stale video captions",
        "dedup_skipped",
        "VLM setup failure",
        "VLM timeout",
        "vlm.max_new_tokens",
        "queue `failed`, `dropped`, and `abandoned` counters",
        "Public Twitch output",
    ]
    for phrase in required:
        assert phrase in text


def test_documented_smoke_commands_match_cli_contract(monkeypatch):
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")
    commands = _documented_smoke_commands(text)
    calls = []

    async def fake_smoke(**kwargs):
        calls.append(kwargs)
        return SmokeStats(
            chat_events=2 if kwargs["enable_chat"] else 0,
            audio_events=1 if kwargs["enable_audio"] else 0,
            audio_samples_saved=1 if kwargs["enable_audio"] else 0,
            vad_utterances=1 if kwargs["enable_vad_diagnostic"] else 0,
            vad_utterance_durations_ms=(
                [300.0] if kwargs["enable_vad_diagnostic"] else []
            ),
            video_events=1 if kwargs["enable_video"] else 0,
            video_frames_saved=1 if kwargs["enable_video"] else 0,
        )

    monkeypatch.setattr("minnarone.twitch_smoke.run_twitch_smoke", fake_smoke)

    for argv in commands:
        if "--no-chat" in argv:
            monkeypatch.delenv("TWITCH_BOT_USERNAME", raising=False)
            monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)
        else:
            monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
            monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
        assert main(argv) == 0

    assert [
        (call["enable_chat"], call["enable_audio"], call["enable_video"])
        for call in calls
    ] == [
        (True, False, False),
        (False, True, False),
        (False, True, False),
        (False, True, False),
        (False, False, True),
        (True, True, True),
    ]
    assert [call["enable_vad_diagnostic"] for call in calls] == [
        False,
        False,
        True,
        False,
        False,
        False,
    ]


def _documented_smoke_commands(text: str) -> list[list[str]]:
    commands = []
    for block in re.findall(
        r"^[ \t]*```bash\n(.*?)\n[ \t]*```",
        text,
        flags=re.DOTALL | re.MULTILINE,
    ):
        if "minnarone-twitch-smoke" not in block:
            continue
        command = " ".join(
            line.strip().removesuffix("\\").strip()
            for line in block.splitlines()
            if line.strip()
        )
        parts = shlex.split(command)
        assert parts[0] == "minnarone-twitch-smoke"
        commands.append(parts[1:])
    return commands


def _documented_minnarone_commands(text: str) -> list[list[str]]:
    commands = []
    for block in re.findall(
        r"^[ \t]*```bash\n(.*?)\n[ \t]*```",
        text,
        flags=re.DOTALL | re.MULTILINE,
    ):
        if "python -m minnarone" not in block:
            continue
        command = " ".join(
            line.strip().removesuffix("\\").strip()
            for line in block.splitlines()
            if line.strip()
        )
        parts = shlex.split(command)
        if parts[:2] == ["uv", "run"]:
            parts = parts[2:]
        assert parts[:3] == ["python", "-m", "minnarone"]
        commands.append(parts[3:])
    return commands
