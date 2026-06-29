## Parent PRD

[local-twitch-perception-runtime.md](../../prds/local-twitch-perception-runtime.md)

## What to build

Extend observability for local model-backed Twitch perception. The operator
should be able to see chat messages, audio transcriptions with speaker labels,
speaker cluster state, video captions, queue drops, and per-channel failures in
the dashboard or debug output.

This slice turns local perception from a black box into something tunable.

## Step-by-step implementation plan

1. Inventory current dashboard/debug data.
   - What to change: identify what the existing TUI already shows for
     perceptions, triggers, windows, and agent messages.
   - Why now: extend existing observability rather than inventing a separate UI.
   - Affects: dashboard data model and display.
   - Verify: current dashboard tests still pass.
   - Pitfalls: do not couple display code to model implementation details.

2. Add media queue stats.
   - What to change: expose queued, processed, dropped, and failed counts for
     audio and video work.
   - Why now: slow model inference needs visible backpressure signals.
   - Affects: runtime stats and dashboard snapshot.
   - Verify: fake queue stats render in tests.
   - Pitfalls: avoid unbounded logs; show current counters/snapshots.

3. Add audio perception diagnostics.
   - What to change: show recent transcriptions, speaker labels, and basic
     cluster status such as cluster IDs, talk time, and current streamer cluster.
   - Why now: diarization thresholds need live tuning.
   - Affects: TUI transcription and diagnostics panels.
   - Verify: fake cluster state displays deterministically.
   - Pitfalls: do not expose raw audio bytes in the UI.

4. Add video perception diagnostics.
   - What to change: show recent caption timestamps, caption text, sampled frame
     counts, dedup skips, and VLM failures.
   - Why now: video captioning may fail because of capture, dedup, or model
     setup; operators need to distinguish those.
   - Affects: TUI video panel and stats.
   - Verify: fake captions and fake failures render without crashing.
   - Pitfalls: do not render huge frame payloads.

5. Add failure categorization.
   - What to change: categorize failures by capture, VAD, ASR, embedding,
     clustering, PyAV decode, dedup, VLM, and output where practical.
   - Why now: actionable troubleshooting depends on knowing the failing stage.
   - Affects: diagnostics contract.
   - Verify: tests can inject stage-labeled failures.
   - Pitfalls: do not swallow original error context completely; keep messages
     useful but safe.

6. Update tests and snapshots.
   - What to change: add dashboard model tests with fake local perception state.
   - Why now: UI should be stable without live models.
   - Affects: dashboard tests.
   - Verify: empty, healthy, overloaded, and failure states render.
   - Pitfalls: avoid brittle terminal layout assertions where a data-model test
     is enough.

## Acceptance criteria

- [x] Observability includes audio transcriptions with speaker labels.
- [x] Observability includes speaker cluster/talk-time/streamer-freeze state.
- [x] Observability includes video caption timestamps and recent caption text.
- [x] Queue processed/dropped/failure counts are visible.
- [x] Failures are categorized by local perception stage where practical.
- [x] Tests use fake state and require no live Twitch or local models.
- [x] Raw audio bytes, raw frame payloads, and secrets are not dumped into UI/logs.

## Blocked by

- Blocked by [02-bounded-local-perception-work-queue.md](./02-bounded-local-perception-work-queue.md)
- Blocked by [05-online-speaker-clustering-labels.md](./05-online-speaker-clustering-labels.md)
- Blocked by [08-local-qwen2-vl-caption-backend.md](./08-local-qwen2-vl-caption-backend.md)

## User stories addressed

- User story 18
- User story 20
- User story 21
- User story 22
- User story 23
