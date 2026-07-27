## Parent PRD

[twitch-eyes-ears.md](../../prds/twitch-eyes-ears.md)

## What to build

Build the first end-to-end Twitch capture tracer bullet: connect to Twitch IRC
with bot credentials, read chat messages in read-only mode, convert them into
the existing chat `RawEvent` contract, and provide a manual smoke workflow that
writes those messages to a perception JSONL file.

This slice proves the smallest useful Twitch path without Streamlink, FFmpeg,
ASR, VLM, the reactor, or output routing. It should establish the Twitch adapter
edge without leaking Twitch-specific details into the core source port.

The key contract from the PRD is:

```python
RawEvent(channel="chat", payload={"text": "...", "speaker": "username"}, ts=...)
```

This snippet is included because it defines the boundary between Twitch IRC and
the existing `ChatPerceiver`/perception-store workflow.

## Step-by-step implementation plan

1. Define the chat event parsing contract.
   - What to change: introduce a pure parser for Twitch IRC chat messages that returns a normalized chat text, speaker and timestamp-ready event data.
   - Why now: parsing can be tested without network access and should be correct before any socket logic exists.
   - Affects: IRC parsing API contract and chat reader test surface.
   - Verify: tagged `PRIVMSG` lines, display-name tags, login fallback and ordinary message text parse correctly.
   - Pitfalls: do not expose raw IRC lines as payloads; the core should receive only normalized chat payloads.

2. Add OAuth token normalization.
   - What to change: accept tokens with or without the `oauth:` prefix and normalize them before IRC authentication.
   - Why now: credentials are required before a live IRC connection can work.
   - Affects: Twitch chat authentication workflow.
   - Verify: `abc` and `oauth:abc` both produce the same IRC `PASS` value.
   - Pitfalls: never log the token and never write it into smoke artifacts.

3. Build a fakeable Twitch chat reader.
   - What to change: implement a read-only IRC reader that authenticates, joins a channel, replies to `PING`, parses `PRIVMSG`, and publishes chat `RawEvent` values.
   - Why now: this is the first real source reader and establishes the async reader pattern for later audio/video readers.
   - Affects: reader lifecycle, async I/O abstraction, adapter queue publishing.
   - Verify: fake stream tests cover auth commands, join command, ping/pong handling, message parsing and clean stop.
   - Pitfalls: do not implement sending chat messages; output to Twitch is out of scope for this PRD.

4. Add a chat-only smoke writer.
   - What to change: consume chat `RawEvent` values and write them through the existing chat perception flow into a JSONL perception file.
   - Why now: a smoke command needs a visible artifact that proves chat events reached the core data shape.
   - Affects: smoke workflow and perception-store integration.
   - Verify: a fake chat event stream produces valid chat perceptions with speaker and text.
   - Pitfalls: keep this capture-only; do not require `OPENROUTER_API_KEY`.

5. Add a manual chat-only smoke command.
   - What to change: create a command or example script that accepts channel, duration and output path, reads Twitch credentials from environment variables and runs chat capture for a fixed time.
   - Why now: operators need a minimal live check before audio/video complexity is added.
   - Affects: examples/manual tooling.
   - Verify: missing channel or credentials fail with clear messages; fake or unit-level tests do not require real Twitch.
   - Pitfalls: do not run this smoke as part of CI; live Twitch and OAuth are manual dependencies.

6. Keep quality gates green.
   - What to change: add focused tests for parser, token normalization, chat reader and smoke writer.
   - Why now: future slices will reuse these boundaries.
   - Affects: automated test suite and quality workflow.
   - Verify: the existing test command and quality command still pass.
   - Pitfalls: avoid brittle tests that assert private task names or exact low-level socket implementation.

## Acceptance criteria

- [ ] Twitch IRC `PRIVMSG` parsing is covered by deterministic unit tests.
- [ ] OAuth token normalization is covered without exposing secrets in logs or fixtures.
- [ ] A fake chat reader test proves auth, join, ping/pong, message parsing and clean stop.
- [ ] Chat `RawEvent` payloads match the PRD contract.
- [ ] A chat-only smoke workflow writes valid chat perceptions to a JSONL file.
- [ ] The smoke workflow does not require `OPENROUTER_API_KEY`.
- [ ] Real Twitch access remains manual and is not required by automated tests.
- [ ] Existing tests and quality checks pass.

## Blocked by

None - can start immediately.

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 4
- User story 14
- User story 15
- User story 16
- User story 20
- User story 25
- User story 27
- User story 28
- User story 31
- User story 32
- User story 33
