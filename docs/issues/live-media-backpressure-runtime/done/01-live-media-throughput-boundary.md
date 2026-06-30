## Parent ADR

[2026-06-29-live-media-backpressure-boundary.md](../../adrs/2026-06-29-live-media-backpressure-boundary.md)

## What to build

Make the live Twitch audio/video path usable on the local machine instead of
letting chat be the only healthy source. Audio and video capture already produce
events; the fix is at the model-backed perception boundary where slow ASR/VLM
work creates stale queues and drops.

This slice should keep Minnarone console-only/local for observation. It must not
send public Twitch messages and must not write unbounded raw media to disk.

## Step-by-step implementation plan

1. Add bounded VLM image preprocessing.
   - What to change: before Qwen2-VL inference, convert the frame to RGB and
     downscale it to a conservative maximum edge/pixel budget.
   - Why now: current live frames can be full 1080p RGB arrays, which makes local
     Qwen2-VL too slow to produce captions.
   - Affects: `src/minnarone/vlm.py` and `QwenVlConfig`.
   - Verify: tests prove a large image is resized before reaching the processor,
     while small images are left unchanged.
   - Pitfalls: do not write resized frames to disk; do not mutate caller-owned
     images in place.

2. Add latest-frame semantics for video queue overload.
   - What to change: when the video perception queue is full, discard stale queued
     video work and enqueue the newest video frame if possible.
   - Why now: a FIFO backlog makes Qwen describe old frames long after the stream
     has moved on.
   - Affects: `src/minnarone/perception_queue.py` and queue stats/tests.
   - Verify: tests fill a video queue, submit a newer frame, and assert the stale
     frame is dropped while the newest frame is processed.
   - Pitfalls: do not apply this to chat; chat must remain direct and preferred.

3. Keep audio overload controlled and visible.
   - What to change: ensure audio queue overload remains bounded, counted, and
     does not starve chat/video. Adjust local runtime config defaults where
     needed for this machine.
   - Why now: audio drops are acceptable under load only if they are intentional
     and diagnosable.
   - Affects: queue policy, `.local/twitch-commentator.local.yaml` if local
     tuning is needed, and docs if behavior changes.
   - Verify: tests cover audio drop counters, and live smoke still captures raw
     audio/video without failures.
   - Pitfalls: do not solve this by making queues huge.

4. Improve operator-facing failure language if needed.
   - What to change: make model busy/backpressure messages distinguish slow local
     inference from capture failure.
   - Why now: the previous screenshot looked like Twitch/video was broken even
     when capture was working.
   - Affects: dashboard health or event formatting only if current messages are
     misleading after the queue fix.
   - Verify: dashboard tests continue to show queue drops/failures without
     leaking secrets or raw media.
   - Pitfalls: keep TUI read-only; no runtime-mutating controls.

5. Verify with automated and local runtime checks.
   - What to change: add focused tests and run the existing quality gates.
   - Why now: this touches shared live runtime behavior.
   - Affects: relevant unit/integration tests.
   - Verify:
     - targeted tests for VLM resizing and queue latest-frame behavior pass
     - full pytest passes
     - `make quality` passes
     - capture-only smoke still captures audio/video on a live channel
     - a bounded live TUI/run shows at least one video caption or a bounded,
       clearly reported model timeout without queue explosion
   - Pitfalls: automated tests must not require Twitch credentials, Streamlink,
     FFmpeg, Qwen2-VL, or Whisper.

## Acceptance criteria

- [x] Large video frames are downscaled before Qwen2-VL receives them.
- [x] Video queue overload prefers the newest frame over stale queued frames.
- [x] Audio/video queue pressure remains bounded and visible.
- [x] Chat remains direct/read-only and is not dropped because of media work.
- [x] Automated tests cover the new behavior without live Twitch or local models.
- [x] `uv run --extra dev pytest -q` passes.
- [x] `make quality` passes.
- [x] A bounded local smoke or live run proves audio/video capture still works.

## Verification evidence

- `uv run --extra dev pytest tests/test_vlm.py tests/test_perception_queue.py tests/test_config.py -q`: passed.
- `uv run --extra dev pytest -q`: passed after review fixes.
- `make quality`: passed after review fixes.
- `uv run minnarone-twitch-smoke --channel retireinprogress --duration 8 --output ./.smoke/live-media-throughput-boundary-postfix --no-chat --audio --video --quality best --audio-chunk-seconds 0.25 --max-audio-samples 1 --video-fps 0.5 --max-video-frames 1`: passed with bounded audio/video artifacts.
- Runtime video probe through `adapter -> queue -> VideoPerceiver -> Qwen2-VL -> store`: wrote 6 `video/caption` perceptions in 30 seconds under `.smoke/live-runtime-video-postfix/perceptions.jsonl`.
- Runtime audio probe through `adapter -> queue -> AudioPerceiver -> VAD/ASR/speaker -> store`: processed 59 audio chunks with 0 drops/failures and wrote 7 `audio/speech` perceptions under `.smoke/live-runtime-audio-postfix/perceptions.jsonl`.
- Review follow-up fixed: video latest-frame semantics now apply before every video enqueue, not only after `QueueFull`; VLM conversion/downscale runs under the same busy/timeout guard; resize dimensions are guaranteed to stay within the configured pixel budget.

## Blocked by

None.

## Non-goals

- Do not replace Qwen2-VL, Whisper, Streamlink, FFmpeg, or Twitch auth.
- Do not add public Twitch chat output.
- Do not store raw live media beyond the existing bounded smoke artifacts.
- Do not make the TUI a runtime control surface.
