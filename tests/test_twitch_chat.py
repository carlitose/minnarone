"""Twitch chat adapter smoke-slice behavior."""

import asyncio
import json

import pytest

from minnarone.fakes import FakeSourceAdapter
from minnarone.source import RawEvent
from minnarone.twitch_chat import (
    TwitchChatError,
    TwitchChatReader,
    capture_chat_smoke,
    normalize_twitch_oauth_token,
    parse_twitch_chat_event,
)


def test_tagged_privmsg_becomes_chat_raw_event_with_display_name():
    line = (
        "@badge-info=;badges=;display-name=CoolUser;mod=0 "
        ":cooluser!cooluser@cooluser.tmi.twitch.tv PRIVMSG #minnarone :ciao chat"
    )

    event = parse_twitch_chat_event(line, ts=12.5)

    assert event is not None
    assert event.channel == "chat"
    assert event.payload == {"text": "ciao chat", "speaker": "CoolUser"}
    assert event.ts == 12.5


def test_privmsg_falls_back_to_login_when_display_name_is_missing():
    line = (
        "@badge-info=;badges=;mod=0 "
        ":login_name!login_name@login_name.tmi.twitch.tv PRIVMSG #minnarone :ciao"
    )

    event = parse_twitch_chat_event(line, ts=13.0)

    assert event is not None
    assert event.payload == {"text": "ciao", "speaker": "login_name"}


def test_plain_privmsg_without_tags_parses_login_and_text():
    line = ":viewer!viewer@viewer.tmi.twitch.tv PRIVMSG #minnarone :hello there"

    event = parse_twitch_chat_event(line, ts=14.0)

    assert event is not None
    assert event.payload == {"text": "hello there", "speaker": "viewer"}


def test_irc_tag_escapes_are_decoded_for_display_name():
    line = (
        r"@display-name=Cool\sUser "
        ":cooluser!cooluser@cooluser.tmi.twitch.tv PRIVMSG #minnarone :ciao"
    )

    event = parse_twitch_chat_event(line, ts=15.0)

    assert event is not None
    assert event.payload == {"text": "ciao", "speaker": "Cool User"}


def test_malformed_privmsg_without_trailing_text_is_ignored():
    line = ":viewer!viewer@viewer.tmi.twitch.tv PRIVMSG #minnarone"

    assert parse_twitch_chat_event(line, ts=16.0) is None


def test_oauth_token_normalization_accepts_prefixed_and_plain_values():
    assert normalize_twitch_oauth_token("oauth:abc") == "oauth:abc"
    assert normalize_twitch_oauth_token("abc") == "oauth:abc"


def test_reader_rejects_empty_or_invalid_channel_before_connecting():
    with pytest.raises(ValueError, match="invalid Twitch channel"):
        TwitchChatReader(channel="#", username="bot_user", oauth_token="abc")


class _FakeIRCStream:
    def __init__(self, incoming):
        self._incoming = list(incoming)
        self.writes = []
        self.closed = False

    async def readline(self):
        if not self._incoming:
            return ""
        return self._incoming.pop(0)

    async def write(self, line):
        self.writes.append(line)

    async def close(self):
        self.closed = True


def test_reader_authenticates_joins_pongs_emits_chat_events_and_stops():
    stream = _FakeIRCStream(
        [
            "PING :tmi.twitch.tv\r\n",
            (
                "@display-name=Viewer "
                ":viewer!viewer@viewer.tmi.twitch.tv PRIVMSG #minnarone :hello\r\n"
            ),
        ]
    )

    async def connect():
        return stream

    reader = TwitchChatReader(
        channel="Minnarone",
        username="bot_user",
        oauth_token="abc",
        connect=connect,
        clock=lambda: 20.0,
    )

    async def run():
        assert reader.channels() == {"chat"}
        await reader.start()
        events = [event async for event in reader.events()]
        await reader.stop()
        return events

    events = asyncio.run(run())

    assert stream.writes == [
        "CAP REQ :twitch.tv/tags twitch.tv/commands",
        "PASS oauth:abc",
        "NICK bot_user",
        "JOIN #minnarone",
        "PONG :tmi.twitch.tv",
    ]
    assert len(events) == 1
    assert events[0].payload == {"text": "hello", "speaker": "Viewer"}
    assert events[0].ts == 20.0
    assert stream.closed is True


def test_reader_closes_stream_when_handshake_write_fails():
    class BrokenWriteStream(_FakeIRCStream):
        async def write(self, line):
            raise OSError("write failed")

    stream = BrokenWriteStream([])

    async def connect():
        return stream

    reader = TwitchChatReader(
        channel="minnarone",
        username="bot_user",
        oauth_token="abc",
        connect=connect,
    )

    async def run():
        with pytest.raises(OSError, match="write failed"):
            await reader.start()

    asyncio.run(run())

    assert stream.closed is True


def test_reader_raises_clear_error_on_auth_notice():
    stream = _FakeIRCStream(
        [
            ":tmi.twitch.tv NOTICE * :Improperly formatted auth\r\n",
        ]
    )

    async def connect():
        return stream

    reader = TwitchChatReader(
        channel="minnarone",
        username="bot_user",
        oauth_token="bad",
        connect=connect,
    )

    async def run():
        await reader.start()
        with pytest.raises(TwitchChatError, match="Improperly formatted auth"):
            async for _event in reader.events():
                pass
        await reader.stop()

    asyncio.run(run())

    assert stream.closed is True


def test_smoke_workflow_writes_chat_perceptions_without_openrouter(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    output = tmp_path / "perceptions.jsonl"
    adapter = FakeSourceAdapter(
        [
            RawEvent(
                channel="chat",
                payload={"text": "ciao", "speaker": "Viewer"},
                ts=30.0,
            )
        ]
    )

    count = asyncio.run(capture_chat_smoke(adapter, output_path=output))

    assert count == 1
    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "ts": 30.0,
        "source": "chat",
        "type": "msg",
        "text": "ciao",
        "speaker": "Viewer",
    }


def test_chat_smoke_preserves_custom_output_file_name(tmp_path):
    output = tmp_path / "custom-chat.jsonl"
    adapter = FakeSourceAdapter(
        [RawEvent(channel="chat", payload={"text": "ciao"}, ts=30.0)]
    )

    count = asyncio.run(capture_chat_smoke(adapter, output_path=output))

    assert count == 1
    assert output.exists()
    assert not (tmp_path / "perceptions.jsonl").exists()


def test_smoke_duration_bounds_adapter_start_and_still_stops(tmp_path):
    class HangingStartAdapter(FakeSourceAdapter):
        def __init__(self):
            super().__init__([])
            self.stopped = False

        async def start(self):
            await asyncio.sleep(60)

        async def stop(self):
            self.stopped = True

    adapter = HangingStartAdapter()

    count = asyncio.run(
        capture_chat_smoke(
            adapter,
            output_path=tmp_path / "perceptions.jsonl",
            duration=0.01,
        )
    )

    assert count == 0
    assert adapter.stopped is True


def test_smoke_reraises_operational_timeout_from_adapter(tmp_path):
    class OperationalTimeoutAdapter(FakeSourceAdapter):
        async def start(self):
            raise TimeoutError("socket read timed out")

        async def stop(self):
            pass

    with pytest.raises(TimeoutError, match="socket read timed out"):
        asyncio.run(
            capture_chat_smoke(
                OperationalTimeoutAdapter([]),
                output_path=tmp_path / "perceptions.jsonl",
                duration=1.0,
            )
        )


def test_chat_smoke_bounds_adapter_stop(tmp_path):
    class HangingStopAdapter(FakeSourceAdapter):
        async def stop(self):
            await asyncio.Event().wait()

    with pytest.raises(TimeoutError):
        asyncio.run(
            capture_chat_smoke(
                HangingStopAdapter(
                    [RawEvent(channel="chat", payload={"text": "ciao"}, ts=1.0)]
                ),
                output_path=tmp_path / "perceptions.jsonl",
                duration=1.0,
            )
        )
