## Parent PRD

[twitch-eyes-ears.md](../../prds/twitch-eyes-ears.md)

## What to build

Compose the chat, audio and video readers behind one public
`TwitchStreamAdapter` that implements the existing `SourceAdapter` port. The
adapter should expose one lifecycle, one async `RawEvent` stream, bounded queue
behavior, per-channel error isolation, event/drop/failure stats and clean task
and process shutdown.

This slice turns the independent capture paths into the source adapter that the
main agent can eventually inject, while still keeping Twitch-specific details at
the edge of the system.

## Step-by-step implementation plan

1. Define the public adapter construction contract.
   - What to change: accept channel name, quality, enabled channel flags, audio chunk duration, video FPS and queue size.
   - Why now: all reader implementations exist and need a single application-facing entry point.
   - Affects: Twitch adapter API and future config integration.
   - Verify: constructing the adapter with different enabled channel flags reports the expected `channels()` set.
   - Pitfalls: do not require audio/video settings when those channels are disabled.

2. Compose reader tasks behind one lifecycle.
   - What to change: make `start()` create enabled reader tasks and `stop()` cancel them and release resources.
   - Why now: `SourceAdapter` requires one lifecycle for the source.
   - Affects: adapter lifecycle, task cleanup and process cleanup.
   - Verify: fake readers start once, stop cleanly and do not leak tasks on repeated start/stop.
   - Pitfalls: `start()` must be idempotent; a second call must not duplicate readers.

3. Route reader output through a bounded queue.
   - What to change: have reader tasks publish `RawEvent` values into one bounded async queue consumed by `events()`.
   - Why now: the source port exposes one event stream, not separate per-channel streams.
   - Affects: adapter event stream and backpressure behavior.
   - Verify: fake readers from multiple channels produce events through one consumer stream.
   - Pitfalls: an unbounded queue can grow forever on live streams.

4. Add explicit overflow behavior and counters.
   - What to change: record dropped event counts when the queue is full, with preference for preserving low-volume chat over high-volume raw media.
   - Why now: bounded queues need visible failure behavior.
   - Affects: adapter stats and smoke diagnostics.
   - Verify: tests simulate queue pressure and assert dropped counts are visible.
   - Pitfalls: do not block reader tasks forever in a way that deadlocks process stdout readers.

5. Isolate per-channel failures.
   - What to change: when one reader fails, record its failure and allow other readers to continue until all are stopped or failed.
   - Why now: live stream components fail independently; the operator should still get partial value.
   - Affects: adapter error handling, `events()` termination policy and stats.
   - Verify: fake chat failure does not stop fake audio/video, and fake video failure does not stop chat/audio.
   - Pitfalls: do not swallow failures silently; they must appear in stats.

6. Define stream termination.
   - What to change: make `events()` continue while the adapter is running and at least one reader may still produce events; terminate cleanly after stop or all readers complete/fail.
   - Why now: callers need predictable stream behavior.
   - Affects: `SourceAdapter.events()` implementation.
   - Verify: tests cover stop-driven termination and all-readers-done termination.
   - Pitfalls: avoid hanging forever after all readers have failed.

7. Add unified stats snapshot.
   - What to change: expose produced counts, dropped counts, failures and running/stopped status for smoke reporting.
   - Why now: the smoke command needs one place to report capture health.
   - Affects: adapter observability.
   - Verify: stats update correctly across successful events, drops and failures.
   - Pitfalls: do not expose mutable internal state directly.

8. Exercise the adapter through the existing source-port expectations.
   - What to change: add tests that treat `TwitchStreamAdapter` as a `SourceAdapter`.
   - Why now: this slice must prove ports-and-adapters compatibility.
   - Affects: source adapter contract tests.
   - Verify: `channels()`, `start()`, `events()` and `stop()` behave through the public interface.
   - Pitfalls: tests should use fake readers and not real Twitch or subprocesses.

## Acceptance criteria

- [ ] `TwitchStreamAdapter` implements the existing source adapter lifecycle.
- [ ] `channels()` reflects enabled chat/audio/video channels.
- [ ] Reader output is exposed as one async stream of `RawEvent` values.
- [ ] Queue overflow is bounded and counted.
- [ ] Per-channel failures are recorded while other channels continue.
- [ ] Stop cancels reader tasks and closes any child processes through reader cleanup.
- [ ] Stats report produced counts, dropped counts and failures.
- [ ] Tests use fake readers and require no live network or external tools.
- [ ] Existing tests and quality checks pass.

## Blocked by

- Blocked by [01-chat-only-twitch-smoke.md](./01-chat-only-twitch-smoke.md)
- Blocked by [02-raw-audio-capture-smoke.md](./02-raw-audio-capture-smoke.md)
- Blocked by [03-raw-video-capture-smoke.md](./03-raw-video-capture-smoke.md)

## User stories addressed

- User story 9
- User story 10
- User story 11
- User story 18
- User story 19
- User story 23
- User story 24
- User story 31
- User story 32
- User story 34
- User story 35
