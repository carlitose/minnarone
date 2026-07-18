"""Twitch IRC chat sender -- the ONLY component that writes PRIVMSG.

This module owns the write side of the Twitch IRC connection. It authenticates
with a dedicated write-scope token (separate from the read token), joins the
configured channel, handles PING/PONG keep-alive, and frames outbound messages
as ``PRIVMSG #channel :text``.

Design constraints (from the PRD):
- No policy logic: the caller decides *whether* to send; this class executes.
- Never truncate: oversized or protocol-unsafe messages are refused with a typed
  error so the caller can account for the failure.
- Never queue or retry a failed message: a missed turn is better than a stale
  public message.
- The write token value must never appear in logs, errors, or artifacts.
"""

from __future__ import annotations

import asyncio
import logging
import re

from .twitch_chat import ConnectIRC, TwitchIRCStream, normalize_twitch_oauth_token
from .twitch_media import normalize_twitch_channel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# IRC protocol constants
# ---------------------------------------------------------------------------

#: Maximum bytes Twitch allows per IRC message (including CRLF).
_IRC_MAX_LINE_BYTES = 500

#: Characters forbidden inside a chat message body.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")

# ---------------------------------------------------------------------------
# Reconnect backoff defaults
# ---------------------------------------------------------------------------

_BACKOFF_BASE_SECONDS = 1.0
_BACKOFF_MAX_SECONDS = 30.0

# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class TwitchSendError(RuntimeError):
    """Base error for the Twitch chat sender."""


class TwitchSendAuthError(TwitchSendError):
    """The write-token authentication was rejected by Twitch."""


class TwitchSendConnectionError(TwitchSendError):
    """The IRC connection was lost or could not be established."""


class TwitchSendMessageRefused(TwitchSendError):
    """The message violates protocol hygiene (too long or contains control chars)."""


class TwitchSendNotConnected(TwitchSendError):
    """``send()`` was called while the sender is not connected."""


# ---------------------------------------------------------------------------
# TwitchChatSender
# ---------------------------------------------------------------------------


class TwitchChatSender:
    """Write-only Twitch IRC connection that sends PRIVMSG messages.

    Parameters
    ----------
    channel:
        Target Twitch channel (with or without ``#`` prefix).
    username:
        Bot account username for the NICK handshake.
    oauth_token:
        Write-scope OAuth token (with or without ``oauth:`` prefix).
    connect:
        Factory that returns a fresh :class:`TwitchIRCStream`. Injected in
        tests with a fake; defaults to the real asyncio SSL connection.
    """

    def __init__(
        self,
        *,
        channel: str,
        username: str,
        oauth_token: str,
        connect: ConnectIRC,
    ) -> None:
        self._channel = normalize_twitch_channel(channel)
        self._username = username
        self._pass = normalize_twitch_oauth_token(oauth_token)
        self._connect = connect
        self._stream: TwitchIRCStream | None = None
        self._ping_task: asyncio.Task[None] | None = None
        self._connected = False
        self._stopped = True
        # Reconnect state
        self._reconnecting = False
        self._reconnect_task: asyncio.Task[None] | None = None
        self._backoff_seconds = _BACKOFF_BASE_SECONDS

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Open the IRC connection, authenticate, and join the channel."""
        if self._connected:
            return
        self._stopped = False
        await self._do_connect()

    async def _do_connect(self) -> None:
        """Perform the actual connection + handshake sequence."""
        stream = await self._connect()
        try:
            await stream.write(f"PASS {self._pass}")
            await stream.write(f"NICK {self._username}")
            await stream.write(f"JOIN #{self._channel}")
        except BaseException:
            await stream.close()
            raise
        self._stream = stream
        self._connected = True
        self._backoff_seconds = _BACKOFF_BASE_SECONDS
        self._ping_task = asyncio.create_task(self._ping_loop())

    async def stop(self) -> None:
        """Shut down the sender cleanly from any state."""
        self._stopped = True
        self._connected = False
        # Cancel reconnect if in progress
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except (asyncio.CancelledError, Exception):
                pass
            self._reconnect_task = None
        # Cancel ping loop
        if self._ping_task is not None:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except (asyncio.CancelledError, Exception):
                pass
            self._ping_task = None
        # Close stream
        stream = self._stream
        self._stream = None
        if stream is not None:
            await stream.close()

    # -- send ----------------------------------------------------------------

    async def send(self, text: str) -> None:
        """Send a PRIVMSG to the channel.

        Raises
        ------
        TwitchSendNotConnected
            If the sender has not been started or is reconnecting.
        TwitchSendMessageRefused
            If the message is too long or contains control characters.
        TwitchSendConnectionError
            If the write fails due to a broken connection.
        """
        if not self._connected or self._stream is None:
            raise TwitchSendNotConnected("sender is not connected")

        self._validate_message(text)

        line = f"PRIVMSG #{self._channel} :{text}"
        try:
            await self._stream.write(line)
        except (OSError, ConnectionError) as exc:
            self._connected = False
            self._schedule_reconnect()
            raise TwitchSendConnectionError("write failed, connection lost") from exc

    def _validate_message(self, text: str) -> None:
        """Refuse messages that would violate IRC protocol constraints."""
        if _CONTROL_CHAR_RE.search(text):
            raise TwitchSendMessageRefused("message contains control characters")

        # The full IRC line is: PRIVMSG #channel :text\r\n
        overhead = len(f"PRIVMSG #{self._channel} :".encode("utf-8")) + 2  # \r\n
        if len(text.encode("utf-8")) + overhead > _IRC_MAX_LINE_BYTES:
            raise TwitchSendMessageRefused("message exceeds IRC length limit")

    # -- reconnect -----------------------------------------------------------

    def _schedule_reconnect(self) -> None:
        """Start a background reconnection attempt if not already running."""
        if self._stopped or self._reconnecting:
            return
        self._reconnecting = True
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Attempt reconnection with capped exponential backoff."""
        try:
            while not self._stopped:
                delay = self._backoff_seconds
                self._backoff_seconds = min(
                    self._backoff_seconds * 2, _BACKOFF_MAX_SECONDS
                )
                logger.info("twitch sender: reconnecting in %.1fs", delay)
                await asyncio.sleep(delay)
                if self._stopped:
                    break
                try:
                    await self._do_connect()
                    logger.info("twitch sender: reconnected")
                    self._reconnecting = False
                    return
                except (OSError, ConnectionError):
                    logger.warning("twitch sender: reconnect attempt failed, retrying")
                    continue
        except asyncio.CancelledError:
            pass
        finally:
            self._reconnecting = False

    # -- keep-alive ----------------------------------------------------------

    async def _ping_loop(self) -> None:
        """Read from the stream and respond to PING messages."""
        stream = self._stream
        if stream is None:
            return
        try:
            while self._connected and not self._stopped:
                try:
                    line = await stream.readline()
                except (OSError, ConnectionError):
                    if not self._stopped:
                        self._connected = False
                        self._schedule_reconnect()
                    return
                if not line:
                    if not self._stopped:
                        self._connected = False
                        self._schedule_reconnect()
                    return
                if line.startswith("PING "):
                    try:
                        await stream.write(f"PONG {line[5:].strip()}")
                    except (OSError, ConnectionError):
                        if not self._stopped:
                            self._connected = False
                            self._schedule_reconnect()
                        return
        except asyncio.CancelledError:
            pass
