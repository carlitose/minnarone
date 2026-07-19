"""Twitch IRC chat ingestion.

Questo modulo contiene il bordo Twitch-specifico: normalizza righe IRC in
`RawEvent(channel="chat")` senza far trapelare dettagli IRC nel core.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .chat import ChatPerceiver
from .source import RawEvent, SourceAdapter
from .store import PerceptionStore

_TWITCH_CHANNEL_RE = re.compile(r"^[a-z0-9_]{1,25}$")
_IRC_CLOSE_TIMEOUT_SECONDS = 5.0
_FATAL_NOTICE_FRAGMENTS = (
    "authentication failed",
    "improperly formatted auth",
    "error logging in",
    "invalid nick",
)


class TwitchChatError(RuntimeError):
    """Errore runtime del reader IRC Twitch."""


class TwitchIRCStream(Protocol):
    """Stream IRC minimale, fakeabile nei test e adattabile a asyncio live."""

    async def readline(self) -> str: ...

    async def write(self, line: str) -> None: ...

    async def close(self) -> None: ...


ConnectIRC = Callable[[], Awaitable[TwitchIRCStream]]


@dataclass(frozen=True, slots=True)
class _IRCMessage:
    tags: dict[str, str]
    prefix: str | None
    command: str
    params: tuple[str, ...]
    trailing: str | None


def normalize_twitch_oauth_token(token: str) -> str:
    """Restituisce il valore `PASS` IRC, accettando token con o senza prefisso."""
    value = token.strip()
    if value.startswith("oauth:"):
        return value
    return f"oauth:{value}"


def parse_twitch_chat_event(line: str, *, ts: float) -> RawEvent | None:
    """Converte una riga IRC `PRIVMSG` Twitch in un evento chat normalizzato."""
    message = _parse_irc_message(line)
    if (
        message is None
        or message.command.upper() != "PRIVMSG"
        or not message.params
        or message.trailing is None
    ):
        return None
    speaker = _speaker_from_tags(message.tags) or _speaker_from_prefix(message.prefix)
    if speaker is None:
        return None
    return RawEvent(
        channel="chat",
        payload={"text": message.trailing, "speaker": speaker},
        ts=ts,
    )


class TwitchChatReader(SourceAdapter):
    """Reader IRC Twitch read-only che emette `RawEvent(channel="chat")`."""

    def __init__(
        self,
        *,
        channel: str,
        username: str,
        oauth_token: str,
        connect: ConnectIRC | None = None,
        clock: Callable[[], float] = time.time,
        close_timeout: float = _IRC_CLOSE_TIMEOUT_SECONDS,
    ) -> None:
        self._channel = _normalize_channel(channel)
        self._username = username
        self._pass = normalize_twitch_oauth_token(oauth_token)
        self._connect = connect or _connect_twitch_irc
        self._clock = clock
        self._close_timeout = close_timeout
        self._stream: TwitchIRCStream | None = None
        self._running = False

    def channels(self) -> set[str]:
        return {"chat"}

    async def start(self) -> None:
        if self._stream is not None:
            return
        stream = await self._connect()
        try:
            await stream.write("CAP REQ :twitch.tv/tags twitch.tv/commands")
            await stream.write(f"PASS {self._pass}")
            await stream.write(f"NICK {self._username}")
            await stream.write(f"JOIN #{self._channel}")
        except BaseException:
            await stream.close()
            raise
        self._stream = stream
        self._running = True

    async def stop(self) -> None:
        self._running = False
        stream = self._stream
        self._stream = None
        if stream is not None:
            await asyncio.wait_for(stream.close(), timeout=self._close_timeout)

    async def events(self) -> AsyncIterator[RawEvent]:
        if self._stream is None:
            await self.start()
        stream = self._stream
        if stream is None:
            return
        while self._running:
            line = await stream.readline()
            if not line:
                return
            if line.startswith("PING "):
                await stream.write(f"PONG {line[5:].strip()}")
                continue
            fatal_notice = _fatal_notice_message(line)
            if fatal_notice is not None:
                raise TwitchChatError(f"Twitch IRC notice: {fatal_notice}")
            event = parse_twitch_chat_event(line, ts=self._clock())
            if event is not None:
                yield event


async def capture_chat_smoke(
    adapter: SourceAdapter,
    *,
    output_path: str | Path,
    duration: float | None = None,
) -> int:
    """Scrive eventi chat dall'adapter nel perception JSONL e ritorna il conteggio."""
    store = PerceptionStore(output_path)
    perceiver = ChatPerceiver(store)
    count = 0
    try:
        if duration is None:
            await adapter.start()
            async for event in adapter.events():
                if perceiver.perceive_event(event) is not None:
                    count += 1
        else:
            deadline = asyncio.timeout(duration)
            try:
                async with deadline:
                    await adapter.start()
                    async for event in adapter.events():
                        if perceiver.perceive_event(event) is not None:
                            count += 1
            except TimeoutError:
                if deadline.expired():
                    return count
                raise
    except TimeoutError:
        raise
    finally:
        await asyncio.wait_for(adapter.stop(), timeout=_IRC_CLOSE_TIMEOUT_SECONDS)
    return count


async def run_twitch_chat_smoke(
    *,
    channel: str,
    username: str,
    oauth_token: str,
    output_path: str | Path,
    duration: float,
) -> int:
    """Esegue il manual smoke live Twitch chat-only per una durata fissata."""
    reader = TwitchChatReader(
        channel=channel,
        username=username,
        oauth_token=oauth_token,
    )
    return await capture_chat_smoke(
        reader,
        output_path=output_path,
        duration=duration,
    )


def _parse_irc_message(line: str) -> _IRCMessage | None:
    rest = line.rstrip("\r\n")
    tags: dict[str, str] = {}
    if rest.startswith("@"):
        raw_tags, separator, rest = rest.partition(" ")
        if not separator:
            return None
        tags = _parse_irc_tags(raw_tags[1:])

    prefix: str | None = None
    if rest.startswith(":"):
        raw_prefix, separator, rest = rest[1:].partition(" ")
        if not separator:
            return None
        prefix = raw_prefix

    before_trailing, separator, trailing = rest.partition(" :")
    parts = tuple(before_trailing.split())
    if not parts:
        return None
    return _IRCMessage(
        tags=tags,
        prefix=prefix,
        command=parts[0],
        params=parts[1:],
        trailing=trailing if separator else None,
    )


def _parse_irc_tags(raw_tags: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for part in raw_tags.split(";"):
        key, _, value = part.partition("=")
        if key:
            tags[key] = _unescape_irc_tag_value(value)
    return tags


def _fatal_notice_message(line: str) -> str | None:
    message = _parse_irc_message(line)
    if (
        message is None
        or message.command.upper() != "NOTICE"
        or message.trailing is None
    ):
        return None
    text = message.trailing.strip()
    lowered = text.lower()
    if any(fragment in lowered for fragment in _FATAL_NOTICE_FRAGMENTS):
        return text
    return None


def _speaker_from_tags(tags: dict[str, str]) -> str | None:
    return tags.get("display-name") or None


def _unescape_irc_tag_value(value: str) -> str:
    replacements = {
        "s": " ",
        ":": ";",
        "r": "\r",
        "n": "\n",
        "\\": "\\",
    }
    decoded: list[str] = []
    i = 0
    while i < len(value):
        char = value[i]
        if char != "\\" or i == len(value) - 1:
            decoded.append(char)
            i += 1
            continue
        i += 1
        decoded.append(replacements.get(value[i], value[i]))
        i += 1
    return "".join(decoded)


def _speaker_from_prefix(prefix: str | None) -> str | None:
    if prefix is None:
        return None
    login, _, _host = prefix.partition("!")
    return login or None


def _normalize_channel(channel: str) -> str:
    normalized = channel.strip().lstrip("#").lower()
    if not _TWITCH_CHANNEL_RE.fullmatch(normalized):
        raise ValueError("invalid Twitch channel")
    return normalized


class _AsyncioIRCStream:
    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self._reader = reader
        self._writer = writer

    async def readline(self) -> str:
        return (await self._reader.readline()).decode("utf-8", errors="replace")

    async def write(self, line: str) -> None:
        self._writer.write(f"{line}\r\n".encode("utf-8"))
        await self._writer.drain()

    async def close(self) -> None:
        self._writer.close()
        await self._writer.wait_closed()


async def _connect_twitch_irc() -> TwitchIRCStream:
    reader, writer = await asyncio.open_connection(
        "irc.chat.twitch.tv",
        6697,
        ssl=True,
    )
    return _AsyncioIRCStream(reader, writer)
