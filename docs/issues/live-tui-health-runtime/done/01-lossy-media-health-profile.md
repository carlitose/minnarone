## What to build

Make the live TUI health line reflect the real state of local Twitch audio/video
after the media backpressure fix. Controlled lossy drops are expected in live
media streams and must stay visible, but they should not force `queue=failed`
when audio/video workers are processing successfully and writing perceptions.

Also tune the local operator config so audio and video can run together on this
machine: Qwen must use the proven small input budget and short generation limit.

## Step-by-step implementation plan

1. Fix queue health semantics.
   - What to change: in dashboard health, treat queue drops without failed,
     cleanup, abandoned, or last_error as lossy/degraded but not failed.
   - Why now: video latest-frame and bounded audio queue intentionally drop stale
     work under load; the screenshot shows those drops as `queue=failed`.
   - Verify: tests where drops-only queues render non-failed, while real failures
     still render failed.
   - Pitfalls: do not hide counters; technical event lines should still show
     dropped counts.

2. Preserve source health for productive media.
   - What to change: when audio/video/asr/vlm have produced transcriptions or
     captions, they should render `ok` even if controlled drops occurred.
   - Why now: the user's final acceptance is the TUI health line, not only raw
     store writes.
   - Verify: dashboard tests with audio/video perceptions plus drops show
     audio/video/asr/vlm ok and queue not failed.
   - Pitfalls: real queue failures (`failed`, `cleanup_failures`, `abandoned`,
     `last_error`) must still surface as failed.

3. Tune local VLM profile.
   - What to change: keep `.local/twitch-commentator.local.yaml` on the proven
     lightweight VLM profile: 224 max edge, 50k pixels, 16 max tokens, 30s
     timeout, low video FPS.
   - Why now: audio+video together timed out at the heavier profile but produced
     both speech and captions with the lighter profile.
   - Verify: bounded audio+video runtime probe shows nonzero `audio/speech` and
     `video/caption`.
   - Pitfalls: do not change public example defaults too aggressively; examples
     can stay conservative.

4. Verify TUI-shaped runtime.
   - What to change: run a TUI/fake-TUI or live snapshot harness while the runtime
     is running, not only after shutdown.
   - Why now: shutdown can create cleanup-timeout statuses that are irrelevant to
     the active TUI.
   - Verify: snapshot while running shows audio/video/asr/vlm/queue non-failed,
     with transcriptions and captions present.

## Acceptance criteria

- [x] Drops-only queue pressure no longer renders `queue=failed`.
- [x] Real queue failures still render `queue=failed`.
- [x] Technical/event lines still expose dropped counts.
- [x] Productive audio/video snapshots render audio/video/asr/vlm healthy.
- [x] Local config uses the lightweight VLM profile proven for this machine.
- [x] A bounded runtime probe writes both `audio/speech` and `video/caption`.
- [x] A TUI-shaped live snapshot while running shows audio/video/asr/vlm/queue non-failed.
- [x] Relevant tests, full pytest, and `make quality` pass.

## Verification evidence

- `uv run --extra dev pytest tests/test_dashboard.py tests/test_config.py -q`: passed, 67 tests.
- `make test`: passed, 560 tests.
- `make quality`: passed.
- Bounded in-process runtime probe through `build_agent`, the real
  `BoundedLocalPerceptionQueue`, real `PerceptionStore`, and
  `observability_snapshot()` while the agent task was still active: passed with
  `audio_speech=1`, `video_caption=1`, `queue_dropped=38`, and live health
  `audio:ok,video:ok,asr:ok,vlm:ok,queue:ok`.
- `.local/twitch-commentator.local.yaml` loaded with `video_fps=0.2` and VLM
  profile `max_image_edge=224`, `max_image_pixels=50000`,
  `max_new_tokens=16`, `timeout_seconds=30.0`.

## Blocked by

None.
