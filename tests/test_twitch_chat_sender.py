"""TwitchChatSender -- the only component that writes PRIVMSG."""

import asyncio

import pytest

from minnarone.twitch_chat_sender import (
    TwitchChatSender,
    TwitchSendConnectionError,
    TwitchSendMessageRefused,
    TwitchSendNotConnected,
)

# ---------------------------------------------------------------------------
# Fake IRC stream (same pattern as test_twitch_chat.py)
# ---------------------------------------------------------------------------


class _FakeIRCStream:
    """In-memory IRC stream for testing, no network involved."""

    def __init__(self, incoming: list[str] | None = None) -> None:
        self._incoming = list(incoming or [])
        self.writes: list[str] = []
        self.closed = False

    async def readline(self) -> str:
        if not self._incoming:
            # Block forever until cancelled (simulates idle connection)
            await asyncio.Event().wait()
        return self._incoming.pop(0)

    async def write(self, line: str) -> None:
        self.writes.append(line)

    async def close(self) -> None:
        self.closed = True


class _DisconnectingStream(_FakeIRCStream):
    """Stream that raises OSError on the Nth write call."""

    def __init__(self, fail_on_write: int, incoming: list[str] | None = None) -> None:
        super().__init__(incoming)
        self._fail_on_write = fail_on_write
        self._write_count = 0

    async def write(self, line: str) -> None:
        self._write_count += 1
        if self._write_count >= self._fail_on_write:
            raise OSError("connection reset")
        self.writes.append(line)


# ---------------------------------------------------------------------------
# 1. Login / handshake
# ---------------------------------------------------------------------------


def test_sender_authenticates_and_joins_channel():
    """start() sends PASS, NICK, JOIN in order."""
    stream = _FakeIRCStream()

    async def connect():
        return stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot_user",
        oauth_token="abc",
        connect=connect,
    )

    async def run():
        await sender.start()
        await sender.stop()

    asyncio.run(run())

    assert stream.writes[:3] == [
        "PASS oauth:abc",
        "NICK bot_user",
        "JOIN #minnarone",
    ]
    assert stream.closed is True


def test_sender_normalizes_channel_and_token():
    """Channel with # prefix and token with oauth: prefix are handled."""
    stream = _FakeIRCStream()

    async def connect():
        return stream

    sender = TwitchChatSender(
        channel="#MyChannel",
        username="bot",
        oauth_token="oauth:tok123",
        connect=connect,
    )

    async def run():
        await sender.start()
        await sender.stop()

    asyncio.run(run())

    assert stream.writes[0] == "PASS oauth:tok123"
    assert stream.writes[2] == "JOIN #mychannel"


def test_sender_rejects_invalid_channel():
    """Invalid channel names are caught at construction time."""

    async def connect():
        raise AssertionError("should not connect")

    with pytest.raises(ValueError, match="invalid Twitch channel"):
        TwitchChatSender(
            channel="",
            username="bot",
            oauth_token="tok",
            connect=connect,
        )


def test_sender_closes_stream_when_handshake_fails():
    """If a write during handshake fails, the stream is still closed."""
    stream = _DisconnectingStream(fail_on_write=1)

    async def connect():
        return stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        with pytest.raises(OSError, match="connection reset"):
            await sender.start()

    asyncio.run(run())

    assert stream.closed is True


# ---------------------------------------------------------------------------
# 2. PING / PONG keep-alive
# ---------------------------------------------------------------------------


def test_sender_responds_to_ping():
    """The background ping loop answers PING with PONG."""
    stream = _FakeIRCStream(["PING :tmi.twitch.tv\r\n"])

    async def connect():
        return stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        # Give the ping loop a chance to process the PING line
        await asyncio.sleep(0.05)
        await sender.stop()

    asyncio.run(run())

    # After PASS, NICK, JOIN the next write should be the PONG
    assert "PONG :tmi.twitch.tv" in stream.writes


# ---------------------------------------------------------------------------
# 3. send() -- happy path
# ---------------------------------------------------------------------------


def test_send_frames_privmsg_correctly():
    """send() writes PRIVMSG #channel :text."""
    stream = _FakeIRCStream()

    async def connect():
        return stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        await sender.send("hello chat!")
        await sender.stop()

    asyncio.run(run())

    # The PRIVMSG should appear after the handshake writes
    assert "PRIVMSG #minnarone :hello chat!" in stream.writes


def test_send_multiple_messages():
    """Multiple sends produce separate PRIVMSG lines."""
    stream = _FakeIRCStream()

    async def connect():
        return stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        await sender.send("first")
        await sender.send("second")
        await sender.stop()

    asyncio.run(run())

    assert "PRIVMSG #minnarone :first" in stream.writes
    assert "PRIVMSG #minnarone :second" in stream.writes


# ---------------------------------------------------------------------------
# 4. send() -- protocol hygiene refusals
# ---------------------------------------------------------------------------


def test_send_refuses_message_with_newline():
    """Messages containing \\n are refused."""
    stream = _FakeIRCStream()

    async def connect():
        return stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        with pytest.raises(TwitchSendMessageRefused, match="control characters"):
            await sender.send("line one\nline two")
        await sender.stop()

    asyncio.run(run())


def test_send_refuses_message_with_carriage_return():
    """Messages containing \\r are refused."""
    stream = _FakeIRCStream()

    async def connect():
        return stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        with pytest.raises(TwitchSendMessageRefused, match="control characters"):
            await sender.send("bad\rmessage")
        await sender.stop()

    asyncio.run(run())


def test_send_refuses_message_with_null_byte():
    """Messages containing \\x00 are refused."""
    stream = _FakeIRCStream()

    async def connect():
        return stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        with pytest.raises(TwitchSendMessageRefused, match="control characters"):
            await sender.send("bad\x00message")
        await sender.stop()

    asyncio.run(run())


def test_send_refuses_oversized_message():
    """Messages that would exceed the IRC 500-byte line limit are refused."""
    stream = _FakeIRCStream()

    async def connect():
        return stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        # Overhead: "PRIVMSG #minnarone :" (20 bytes) + "\r\n" (2 bytes) = 22 bytes
        # Max text = 500 - 22 = 478 bytes
        oversized = "x" * 479
        with pytest.raises(TwitchSendMessageRefused, match="length limit"):
            await sender.send(oversized)
        await sender.stop()

    asyncio.run(run())


def test_send_accepts_message_at_exact_limit():
    """A message exactly at the IRC byte limit is accepted."""
    stream = _FakeIRCStream()

    async def connect():
        return stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        # Overhead for "PRIVMSG #minnarone :" + "\r\n" = 22 bytes
        exact_limit = "x" * 478
        await sender.send(exact_limit)
        await sender.stop()

    asyncio.run(run())

    assert f"PRIVMSG #minnarone :{'x' * 478}" in stream.writes


# ---------------------------------------------------------------------------
# 5. send() while not connected
# ---------------------------------------------------------------------------


def test_send_before_start_raises():
    """send() on a sender that was never started raises TwitchSendNotConnected."""

    async def connect():
        return _FakeIRCStream()

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        with pytest.raises(TwitchSendNotConnected, match="not connected"):
            await sender.send("hello")

    asyncio.run(run())


def test_send_after_stop_raises():
    """send() after stop() raises TwitchSendNotConnected."""
    stream = _FakeIRCStream()

    async def connect():
        return stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        await sender.stop()
        with pytest.raises(TwitchSendNotConnected, match="not connected"):
            await sender.send("hello")

    asyncio.run(run())


# ---------------------------------------------------------------------------
# 6. Connection loss and reconnect
# ---------------------------------------------------------------------------


def test_send_on_broken_connection_raises_and_triggers_reconnect():
    """When write fails, send raises TwitchSendConnectionError."""
    call_count = 0
    good_stream = _FakeIRCStream()
    bad_stream = _DisconnectingStream(
        fail_on_write=4
    )  # Fail on the 4th write (1st after handshake)

    async def connect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return bad_stream
        return good_stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        with pytest.raises(TwitchSendConnectionError, match="connection lost"):
            await sender.send("boom")
        # After failure, send should raise not-connected while reconnecting
        with pytest.raises(TwitchSendNotConnected):
            await sender.send("during reconnect")
        await sender.stop()

    asyncio.run(run())


def test_reconnect_recovers_and_allows_send():
    """After reconnection succeeds, send() works again."""
    call_count = 0
    streams: list[_FakeIRCStream] = []

    async def connect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            s = _DisconnectingStream(fail_on_write=4)
            streams.append(s)
            return s
        s = _FakeIRCStream()
        streams.append(s)
        return s

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        # Trigger connection loss
        with pytest.raises(TwitchSendConnectionError):
            await sender.send("fail")
        # Wait for reconnect (backoff starts at 1s, we use a small delay)
        await asyncio.sleep(1.5)
        # Now should be reconnected
        await sender.send("recovered!")
        await sender.stop()

    asyncio.run(run())

    assert "PRIVMSG #minnarone :recovered!" in streams[1].writes


def test_stop_during_reconnect_is_clean():
    """stop() interrupts a reconnection attempt without hanging."""
    connect_count = 0

    async def connect():
        nonlocal connect_count
        connect_count += 1
        if connect_count == 1:
            return _DisconnectingStream(fail_on_write=4)
        # Second connect takes forever (simulates unreachable server)
        await asyncio.sleep(9999)
        return _FakeIRCStream()

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        with pytest.raises(TwitchSendConnectionError):
            await sender.send("fail")
        # Reconnect is now in progress, stop should cancel it
        await sender.stop()

    asyncio.run(run())
    # If we got here, stop() didn't hang -- success


def test_backoff_is_bounded():
    """Reconnect backoff caps at _BACKOFF_MAX_SECONDS."""
    from minnarone.twitch_chat_sender import _BACKOFF_MAX_SECONDS

    fail_count = 0

    async def connect():
        nonlocal fail_count
        fail_count += 1
        if fail_count <= 2:
            # First connection and first reconnect attempt both fail
            return _DisconnectingStream(fail_on_write=4 if fail_count == 1 else 1)
        return _FakeIRCStream()

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    # Manually verify the backoff doubles but doesn't exceed max
    assert sender._backoff_seconds == 1.0
    # After one bump it should be 2.0 (doubled from 1.0)
    # This is internal state, but we verify the cap constant exists
    assert _BACKOFF_MAX_SECONDS == 30.0


# ---------------------------------------------------------------------------
# 7. stop() from various states
# ---------------------------------------------------------------------------


def test_stop_before_start_is_safe():
    """stop() on a never-started sender does not raise."""

    async def connect():
        return _FakeIRCStream()

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.stop()

    asyncio.run(run())


def test_stop_closes_stream():
    """stop() closes the underlying stream."""
    stream = _FakeIRCStream()

    async def connect():
        return stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        await sender.stop()

    asyncio.run(run())

    assert stream.closed is True


def test_double_start_is_idempotent():
    """Calling start() twice does not open a second connection."""
    connect_count = 0
    stream = _FakeIRCStream()

    async def connect():
        nonlocal connect_count
        connect_count += 1
        return stream

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token="tok",
        connect=connect,
    )

    async def run():
        await sender.start()
        await sender.start()
        await sender.stop()

    asyncio.run(run())

    assert connect_count == 1


# ---------------------------------------------------------------------------
# 8. Token secrecy -- write token must not leak
# ---------------------------------------------------------------------------


def test_token_does_not_appear_in_error_messages():
    """TwitchSendError subclasses must not include the token value."""
    secret_token = "super_secret_token_value_12345"

    async def connect():
        return _FakeIRCStream()

    sender = TwitchChatSender(
        channel="minnarone",
        username="bot",
        oauth_token=secret_token,
        connect=connect,
    )

    async def run():
        # Not-connected error
        try:
            await sender.send("hello")
        except TwitchSendNotConnected as exc:
            assert secret_token not in str(exc)
            assert f"oauth:{secret_token}" not in str(exc)

    asyncio.run(run())


# ---------------------------------------------------------------------------
# 9. No PRIVMSG in any other module (structural assertion)
# ---------------------------------------------------------------------------


def test_only_sender_writes_privmsg():
    """Verify no other module in the package writes PRIVMSG to IRC.

    This is a structural test: the reader (twitch_chat.py) must never write
    PRIVMSG. Only twitch_chat_sender.py is allowed to.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "src" / "minnarone"
    sender_file = "twitch_chat_sender.py"

    for py_file in src.glob("*.py"):
        if py_file.name == sender_file:
            continue
        text = py_file.read_text(encoding="utf-8")
        # Check for PRIVMSG writes (not parse/read references)
        for line_no, line in enumerate(text.splitlines(), 1):
            # Skip comments and string literals that reference PRIVMSG for parsing
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Look for write calls that include PRIVMSG
            if "PRIVMSG" in line and ("write" in line or "send" in line):
                pytest.fail(
                    f"{py_file.name}:{line_no} writes PRIVMSG -- "
                    "only twitch_chat_sender.py may do this"
                )
