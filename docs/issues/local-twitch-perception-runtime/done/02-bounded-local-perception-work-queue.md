## Parent PRD

[local-twitch-perception-runtime.md](../../prds/local-twitch-perception-runtime.md)

## What to build

Add a bounded local perception work queue for model-backed audio and video
processing. The goal is to keep live Twitch capture stable when ASR, speaker
embedding, or VLM work is slower than incoming media.

This slice should be demoable without real models: fake slow media processors
should prove that the runtime does not grow memory forever, that chat remains
preferred, and that dropped or skipped media work is visible in diagnostics.

## Step-by-step implementation plan

1. Identify the media handoff point.
   - What to change: find where raw audio/video `RawEvent` values leave the
     source adapter and enter perception dispatch.
   - Why now: the queue belongs between live capture and slow model-backed
     perception, not inside the core Reactor.
   - Affects: perception pump, source adapter consumption, runtime stats.
   - Verify: chat can still flow directly or with highest priority.
   - Pitfalls: do not add backpressure that blocks subprocess stdout forever.

2. Define queue behavior and counters.
   - What to change: specify bounded capacity, media drop policy, per-channel
     queued/processed/dropped/failure counts, and shutdown behavior.
   - Why now: overflow behavior must be explicit before workers are introduced.
   - Affects: runtime observability contract.
   - Verify: queue full scenarios are deterministic in tests.
   - Pitfalls: do not silently drop data; operators need counts.

3. Implement a fakeable worker abstraction.
   - What to change: make audio/video work run through injectable processors so
     tests can simulate slow processing and failures.
   - Why now: real ASR and VLM are not part of this slice.
   - Affects: local perception runtime boundary.
   - Verify: fake processors can complete, fail, or hang in controlled tests.
   - Pitfalls: do not bind this queue to a specific model implementation.

4. Preserve chat priority.
   - What to change: ensure chat events are not dropped in favor of high-volume
     media work.
   - Why now: chat is already textual, low volume, and useful for the agent even
     when media is degraded.
   - Affects: drop policy and event ordering.
   - Verify: under simulated media overload, chat still reaches the store.
   - Pitfalls: do not let a full video queue starve chat perception.

5. Add clean shutdown.
   - What to change: stop workers, drain or cancel queued work according to a
     bounded timeout, and record cleanup failures.
   - Why now: live capture must not leave orphaned tasks.
   - Affects: runtime lifecycle, tests.
   - Verify: cancellation does not hang and stats record timeout/failure cases.
   - Pitfalls: do not swallow cancellation exceptions in a way that hides real
     cleanup bugs.

6. Add tests with fake slow processors.
   - What to change: exercise normal processing, queue overflow, processor
     failure, and shutdown.
   - Why now: this module exists to protect runtime behavior under stress.
   - Affects: unit and integration tests around the perception pump.
   - Verify: memory stays bounded and counts match expected behavior.
   - Pitfalls: avoid timing-flaky tests; use controllable fake awaitables.

## Acceptance criteria

- [ ] Audio/video model-backed perception work is bounded by a configurable queue.
- [ ] Queue overflow is explicit and counted per channel.
- [ ] Chat remains preferred and is not dropped because media processing is slow.
- [ ] Worker failures are recorded without killing unrelated channels.
- [ ] Shutdown cancels or drains work within a bounded timeout.
- [ ] Tests use fake processors and require no live Twitch or local models.

## Blocked by

- Blocked by [01-twitch-runtime-chat-only-console-path.md](./01-twitch-runtime-chat-only-console-path.md)

## User stories addressed

- User story 21
- User story 22
- User story 28
- User story 32
