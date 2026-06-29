## Parent PRD

[original-live-observability-tui.md](../../prds/original-live-observability-tui.md)

## What to build

Add normalized source health and technical event visibility to the live TUI. The
operator should immediately see whether chat, audio, video, ASR, speaker, LLM,
and VLM are `ok`, `idle`, `busy`, `failed`, or `unknown`, along with source
counts, queue depth, dropped/failed counters, latest failure, and Senser
triggers. A run where chat/audio/LLM work but video captions are absent must
look visibly incomplete.

This slice builds on the main dashboard panels because it renders both a status
bar and richer `EVENTI` content.

## Step-by-step implementation plan

1. Inventory available runtime stats and failure signals.
   - What to change: identify existing counters and diagnostics for chat,
     audio, video, ASR, speaker, VLM, LLM, queues, adapters, triggers, and
     failures.
   - Why this comes first: health should be derived from real signals where
     available, not guessed in the renderer.
   - Affects: dashboard snapshot aggregation.
   - Verify: fake stats can represent success, idle, busy, failure, and missing
     data for each source.
   - Pitfalls: do not treat every zero count as failure immediately; early-run
     idle states are valid.

2. Define normalized health labels.
   - What to change: map raw stats into concise labels such as `ok`, `idle`,
     `busy`, `failed`, and `unknown` for each relevant source.
   - Why this comes now: the status bar needs stable language independent of raw
     module details.
   - Affects: dashboard state and status formatting.
   - Verify: unit tests cover key combinations, including video captions missing
     while chat/audio are active.
   - Pitfalls: avoid hiding partial failures behind a single global green state.

3. Add source counts and queue/backpressure fields.
   - What to change: expose counts for chat messages, audio speech, video
     captions, queue depth, dropped work, failed work, and latest failure where
     available.
   - Why this comes now: counts make health claims inspectable.
   - Affects: dashboard state and status/event rendering.
   - Verify: fake queue and source stats appear in the status bar or events.
   - Pitfalls: do not make the UI crash when a source does not provide a stat
     yet.

4. Populate `EVENTI` with Senser triggers and technical events.
   - What to change: combine recent trigger reasons, source state changes,
     failures, drops, and model errors into the `EVENTI` panel.
   - Why this comes now: the operator asked for both behavioral and technical
     events in the same place.
   - Affects: dashboard state aggregation and panel formatting.
   - Verify: fake trigger and failure events render together in chronological or
     clearly grouped order.
   - Pitfalls: keep event text concise; the panel should not become a raw log
     dump.

5. Render the status bar.
   - What to change: show channel, uptime, source health, source counts, queue
     depth, model/LLM state, token/cache summary when available, and latest
     failure in a compact bar.
   - Why this comes last: all normalized state is now available.
   - Affects: TUI main view and dashboard formatting.
   - Verify: construction tests with fake states show the expected status labels
     and counts.
   - Pitfalls: do not let long errors break the terminal layout; truncate or
     summarize safely.

## Acceptance criteria

- [ ] Dashboard state exposes normalized health for chat, audio, video, ASR, speaker, VLM, LLM, queue, and adapter where available.
- [ ] The status bar shows channel, uptime, source health, source counts, queue depth, model/LLM state, and latest failure.
- [ ] `EVENTI` includes Senser triggers and technical events/failures.
- [ ] Missing video captions are visible as incomplete or suspicious once enough runtime evidence exists.
- [ ] ASR/VLM busy or failed states are visible.
- [ ] OpenRouter errors are visible without leaking secrets.
- [ ] Tests cover partial-success cases and missing-stat graceful degradation.

## Blocked by

- Blocked by [05-screenshot-faithful-dashboard-panels.md](./05-screenshot-faithful-dashboard-panels.md)

## User stories addressed

- User story 3
- User story 4
- User story 13
- User story 14
- User story 21
- User story 22
- User story 23
- User story 24
- User story 25
- User story 41
- User story 42
