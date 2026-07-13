## Parent PRD

[twitch-public-chat-output.md](../../prds/twitch-public-chat-output.md)

## What to build

`TwitchChatSender`: the one and only component allowed to write a `PRIVMSG`.
It owns a dedicated write-capable IRC connection — separate from the chat
perception reader, so the read path stays byte-for-byte untouched — with
interface `start()`, `stop()`, `send(text)`. It logs in with the write-scope
token from the new env var, joins the configured channel, answers PING,
frames messages as `PRIVMSG #channel :text`, reconnects with bounded backoff
after connection loss, raises typed errors on failure, and refuses (never
truncates) messages that exceed the IRC length limit or contain
newlines/control characters (PRD protocol-hygiene decision).

This slice is pure transport: no policy, no router wiring, no app changes.
It reuses the existing IRC stream abstraction of the chat reader and is
tested exclusively against a fake stream.

## Step-by-step implementation plan

1. Define the interface and typed errors.
   - What: sender class with `start`/`stop`/`send`; typed exceptions for
     auth failure, connection loss, refusal (oversize/control chars), and
     send-while-stopped.
   - Why now: the error vocabulary is what slice 07 maps to policy failure
     accounting.
   - Affects: new sender module.
   - Verify: interface unit tests with a fake stream.
   - Pitfall: `send` on a dead connection must raise, not silently queue —
     stale public messages are worse than silence (EC03 philosophy).

2. Implement login and channel join over the stream abstraction.
   - What: connect via the same stream-opening pattern as the reader, PASS
     with the write token (normalizing the `oauth:` prefix like the reader
     does), NICK with the bot account, JOIN the channel, handle PING/PONG.
   - Why now: the connection lifecycle precedes sending.
   - Affects: sender module.
   - Verify: fake-stream tests assert the exact login line sequence and PONG
     behavior (same style as the reader's tests).
   - Pitfall: the write token comes from the NEW env var (slice 01), never
     from the read token variable.

3. Implement `send` with protocol hygiene.
   - What: refuse messages over the IRC limit (account for the
     `PRIVMSG #channel :` overhead) or containing `\r`/`\n`/control chars;
     otherwise write the framed line.
   - Why now: hygiene is the sender's only content responsibility (PRD: no
     content moderation here).
   - Affects: sender module.
   - Verify: framing test, oversize refusal test, control-char refusal test.
   - Pitfall: refusal is a typed error the caller records — not a silent drop.

4. Implement reconnect with bounded backoff.
   - What: on connection loss, retry with capped exponential backoff;
     `send` during reconnection raises; `stop()` interrupts cleanly.
   - Why now: a network blip must degrade gracefully, not kill the run.
   - Affects: sender module.
   - Verify: fake-stream tests simulating disconnection and recovery.
   - Pitfall: never re-send a message that failed mid-write — the caller
     decides (it will skip the turn).

## Acceptance criteria

- [ ] Sender logs in, joins, answers PING, and frames `PRIVMSG` correctly against a fake stream.
- [ ] Oversized and control-character messages are refused with typed errors.
- [ ] Connection loss triggers bounded-backoff reconnect; `send` meanwhile raises.
- [ ] `stop()` closes the connection cleanly from any state.
- [ ] No real network in any test; no other module writes `PRIVMSG`.
- [ ] The write token value never appears in logs, errors, or artifacts.

## Blocked by

- Blocked by [01-send-config-type-and-check.md](./01-send-config-type-and-check.md)

## User stories addressed

- User story 8
- User story 23
- User story 25
- User story 27
- User story 29
