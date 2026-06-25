"""Operator handoff coverage for Twitch smoke/config docs."""

import re
import shlex
from pathlib import Path

from minnarone.config import Config
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
    assert cfg.twitch.audio is True
    assert cfg.twitch.video is True


def test_twitch_operator_docs_cover_setup_smoke_artifacts_and_troubleshooting():
    text = Path("docs/twitch-operator.md").read_text(encoding="utf-8")

    required = [
        "streamlink",
        "ffmpeg",
        "TWITCH_BOT_USERNAME",
        "TWITCH_OAUTH_TOKEN",
        "minnarone-twitch-smoke",
        "--no-chat --audio",
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
        (False, False, True),
        (True, True, True),
    ]


def _documented_smoke_commands(text: str) -> list[list[str]]:
    commands = []
    for block in re.findall(r"```bash\n(.*?)\n```", text, flags=re.DOTALL):
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
