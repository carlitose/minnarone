"""Manual Twitch chat smoke entrypoint behavior."""

from minnarone.twitch_smoke import main


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
        return 2

    output = tmp_path / "perceptions.jsonl"
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    monkeypatch.setattr("minnarone.twitch_smoke.run_twitch_chat_smoke", fake_smoke)

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
            "output_path": str(output),
            "duration": 3.5,
        }
    ]
    assert "2" in capsys.readouterr().out


def test_twitch_chat_smoke_zero_events_is_failure(tmp_path, monkeypatch, capsys):
    async def fake_smoke(**kwargs):
        return 0

    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    monkeypatch.setattr("minnarone.twitch_smoke.run_twitch_chat_smoke", fake_smoke)

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
    assert "nessuna percezione" in capsys.readouterr().err


def test_twitch_chat_smoke_invalid_channel_is_clear_error(
    tmp_path, monkeypatch, capsys
):
    async def fake_smoke(**kwargs):
        raise ValueError("channel Twitch non valido")

    monkeypatch.setenv("TWITCH_BOT_USERNAME", "bot_user")
    monkeypatch.setenv("TWITCH_OAUTH_TOKEN", "oauth:token")
    monkeypatch.setattr("minnarone.twitch_smoke.run_twitch_chat_smoke", fake_smoke)

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
    monkeypatch.setattr("minnarone.twitch_smoke.run_twitch_chat_smoke", fake_smoke)

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
