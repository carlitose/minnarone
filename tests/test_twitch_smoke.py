"""Manual Twitch chat smoke entrypoint behavior."""

import asyncio

from minnarone.fakes import FakeSourceAdapter
from minnarone.source import RawEvent
from minnarone.twitch_smoke import chat_main, main, run_twitch_smoke
from minnarone.twitch_smoke_artifacts import SmokeStats


def test_twitch_chat_smoke_requires_manual_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("TWITCH_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)

    code = main(
        [
            "--channel",
            "minnarone",
            "--duration",
            "1",
            "--output",
            str(tmp_path / "perceptions.jsonl"),
        ]
    )

    assert code != 0
    err = capsys.readouterr().err
    assert "TWITCH_BOT_USERNAME" in err
    assert "TWITCH_OAUTH_TOKEN" in err


def test_twitch_chat_smoke_requires_channel(tmp_path, capsys):
    code = main(
        [
            "--duration",
            "1",
            "--output",
            str(tmp_path / "perceptions.jsonl"),
        ]
    )

    assert code != 0
    err = capsys.readouterr().err
    assert "--channel" in err


def test_twitch_chat_smoke_requires_positive_duration(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")

    code = main(
        [
            "--channel",
            "minnarone",
            "--duration",
            "0",
            "--output",
            str(tmp_path / "perceptions.jsonl"),
        ]
    )

    assert code != 0
    assert "--duration" in capsys.readouterr().err


def test_twitch_chat_smoke_rejects_nonfinite_duration(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")

    code = main(
        [
            "--channel",
            "minnarone",
            "--duration",
            "inf",
            "--output",
            str(tmp_path / "perceptions.jsonl"),
        ]
    )

    assert code != 0
    assert "--duration" in capsys.readouterr().err


def test_twitch_chat_smoke_command_runs_with_twitch_env_only(
    tmp_path, monkeypatch, capsys
):
    calls = []

    async def fake_smoke(**kwargs):
        calls.append(kwargs)
        return SmokeStats(chat_events=2)

    output = tmp_path / "smoke"
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    monkeypatch.setattr("minnarone.twitch_smoke.run_twitch_smoke", fake_smoke)

    code = main(
        [
            "--channel",
            "minnarone",
            "--duration",
            "3.5",
            "--output",
            str(output),
        ]
    )

    assert code == 0
    assert calls == [
        {
            "channel": "minnarone",
            "username": "bot_user",
            "oauth_token": "oauth:token",
            "output_dir": str(output),
            "duration": 3.5,
            "enable_chat": True,
            "enable_audio": False,
            "quality": "audio_only",
            "audio_chunk_seconds": 1.0,
            "max_audio_samples": 3,
        }
    ]
    assert "2" in capsys.readouterr().out


def test_legacy_chat_smoke_command_uses_jsonl_output_file(
    tmp_path, monkeypatch, capsys
):
    calls = []

    async def fake_chat_smoke(**kwargs):
        calls.append(kwargs)
        return 1

    output = tmp_path / "custom-chat.jsonl"
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    monkeypatch.setattr(
        "minnarone.twitch_smoke.run_twitch_chat_smoke",
        fake_chat_smoke,
    )

    code = chat_main(
        [
            "--channel",
            "minnarone",
            "--duration",
            "3.5",
            "--output",
            str(output),
        ]
    )

    assert code == 0
    assert calls == [
        {
            "channel": "minnarone",
            "username": "bot_user",
            "oauth_token": "oauth:token",
            "output_path": str(output),
            "duration": 3.5,
        }
    ]
    assert "custom-chat.jsonl" in capsys.readouterr().out


def test_twitch_chat_smoke_zero_events_is_failure(tmp_path, monkeypatch, capsys):
    async def fake_smoke(**kwargs):
        return SmokeStats()

    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    monkeypatch.setattr("minnarone.twitch_smoke.run_twitch_smoke", fake_smoke)

    code = main(
        [
            "--channel",
            "minnarone",
            "--duration",
            "1",
            "--output",
            str(tmp_path / "perceptions.jsonl"),
        ]
    )

    assert code != 0
    assert "nessun evento" in capsys.readouterr().err


def test_twitch_chat_smoke_invalid_channel_is_clear_error(
    tmp_path, monkeypatch, capsys
):
    async def fake_smoke(**kwargs):
        raise ValueError("channel Twitch non valido")

    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    monkeypatch.setattr("minnarone.twitch_smoke.run_twitch_smoke", fake_smoke)

    code = main(
        [
            "--channel",
            "#",
            "--duration",
            "1",
            "--output",
            str(tmp_path / "perceptions.jsonl"),
        ]
    )

    assert code != 0
    assert "channel Twitch non valido" in capsys.readouterr().err


def test_twitch_chat_smoke_operational_errors_are_clear(
    tmp_path, monkeypatch, capsys
):
    async def fake_smoke(**kwargs):
        raise OSError("network unreachable")

    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    monkeypatch.setattr("minnarone.twitch_smoke.run_twitch_smoke", fake_smoke)

    code = main(
        [
            "--channel",
            "minnarone",
            "--duration",
            "1",
            "--output",
            str(tmp_path / "perceptions.jsonl"),
        ]
    )

    assert code == 1
    err = capsys.readouterr().err
    assert "errore di connessione" in err
    assert "network unreachable" in err


def test_twitch_smoke_audio_only_does_not_require_chat_credentials(
    tmp_path, monkeypatch
):
    calls = []

    async def fake_smoke(**kwargs):
        calls.append(kwargs)
        return SmokeStats(audio_events=1, audio_samples_saved=1)

    monkeypatch.delenv("TWITCH_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TWITCH_OAUTH_TOKEN", raising=False)
    monkeypatch.setattr("minnarone.twitch_smoke.run_twitch_smoke", fake_smoke)

    code = main(
        [
            "--channel",
            "minnarone",
            "--duration",
            "1",
            "--output",
            str(tmp_path / "smoke"),
            "--no-chat",
            "--audio",
            "--audio-chunk-seconds",
            "0.25",
        ]
    )

    assert code == 0
    assert calls[0]["enable_chat"] is False
    assert calls[0]["enable_audio"] is True
    assert calls[0]["audio_chunk_seconds"] == 0.25


def test_twitch_smoke_fails_when_requested_audio_has_no_events(
    tmp_path, monkeypatch, capsys
):
    async def fake_smoke(**kwargs):
        return SmokeStats(chat_events=1, audio_events=0)

    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    monkeypatch.setattr("minnarone.twitch_smoke.run_twitch_smoke", fake_smoke)

    code = main(
        [
            "--channel",
            "minnarone",
            "--duration",
            "1",
            "--output",
            str(tmp_path / "smoke"),
            "--audio",
        ]
    )

    assert code == 1
    assert "audio: nessun evento" in capsys.readouterr().err


def test_twitch_smoke_fails_when_stats_contains_failures(
    tmp_path, monkeypatch, capsys
):
    async def fake_smoke(**kwargs):
        return SmokeStats(chat_events=1, audio_events=1, failures=["audio: boom"])

    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    monkeypatch.setattr("minnarone.twitch_smoke.run_twitch_smoke", fake_smoke)

    code = main(
        [
            "--channel",
            "minnarone",
            "--duration",
            "1",
            "--output",
            str(tmp_path / "smoke"),
            "--audio",
        ]
    )

    assert code == 1
    assert "audio: boom" in capsys.readouterr().err


def test_twitch_smoke_rejects_invalid_audio_chunk_duration(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")

    code = main(
        [
            "--channel",
            "minnarone",
            "--duration",
            "1",
            "--output",
            str(tmp_path / "smoke"),
            "--audio",
            "--audio-chunk-seconds",
            "nan",
        ]
    )

    assert code != 0
    assert "--audio-chunk-seconds" in capsys.readouterr().err


def test_run_twitch_smoke_disabling_audio_skips_audio_process_runner(tmp_path):
    class ExplodingRunner:
        async def start(self, argv):
            raise AssertionError("audio process should not start")

    chat = FakeSourceAdapter(
        [RawEvent(channel="chat", payload={"text": "ciao"}, ts=1.0)]
    )

    stats = asyncio.run(
        run_twitch_smoke(
            channel="minnarone",
            username="bot_user",
            oauth_token="oauth:token",
            output_dir=tmp_path / "smoke",
            duration=1.0,
            enable_audio=False,
            chat_adapter=chat,
            audio_process_runner=ExplodingRunner(),
        )
    )

    assert stats.chat_events == 1
    assert stats.audio_events == 0
