## Parent PRD

[local-twitch-perception-runtime.md](../../prds/local-twitch-perception-runtime.md)

## What to build

Add the runtime video frame path that matches the original Minnarone design:
Streamlink obtains the Twitch stream and PyAV decodes sampled frames for local
perception. This replaces the FFmpeg JPEG smoke shortcut for the real runtime,
while preserving the existing smoke command as a capture diagnostic.

This slice stops before captioning. It should prove that the main runtime can
receive sampled `VideoFrame` events from PyAV.

## Step-by-step implementation plan

1. Define the PyAV runtime boundary.
   - What to change: introduce a video reader/decoder path that uses Streamlink
     and PyAV to emit `VideoFrame` payloads.
   - Why now: the approved runtime must be faithful to original Minnarone, not
     the JPEG smoke shortcut.
   - Affects: Twitch video source implementation.
   - Verify: existing FFmpeg JPEG smoke still works independently.
   - Pitfalls: do not remove the diagnostic smoke path.

2. Add fakeable stream and decode abstractions.
   - What to change: isolate subprocess/stream resolution and frame decoding so
     tests can use fixtures or fake frames.
   - Why now: CI cannot depend on live Twitch or actual media decoding.
   - Affects: testability of video source.
   - Verify: fake decoded frames produce `VideoFrame` values.
   - Pitfalls: avoid tests that require a network stream.

3. Implement time-based sampling.
   - What to change: emit candidate frames at a configured interval rather than
     every decoded frame.
   - Why now: VLM captioning will be expensive downstream.
   - Affects: video runtime cadence.
   - Verify: fixture frames at known timestamps produce expected sampled frames.
   - Pitfalls: frame-count sampling can behave differently across stream frame
     rates; prefer time-based semantics where practical.

4. Preserve lifecycle and cleanup behavior.
   - What to change: ensure Streamlink/PyAV resources stop cleanly on runtime
     cancellation or stream failure.
   - Why now: live video streams are long-running and failure-prone.
   - Affects: source adapter lifecycle.
   - Verify: fake failures are recorded and cleanup does not hang.
   - Pitfalls: do not leave child processes or decode loops running after stop.

5. Integrate with the bounded work queue.
   - What to change: route sampled video frames through the media work path
     created earlier.
   - Why now: even frame decode and later captions must respect backpressure.
   - Affects: local perception work queue and stats.
   - Verify: slow fake consumers produce bounded queue behavior.
   - Pitfalls: do not let video overload starve chat.

6. Add manual live video runtime smoke.
   - What to change: provide a bounded command or documented run that proves
     PyAV-sampled frames arrive without captioning.
   - Why now: operators need to isolate capture/decode from VLM issues.
   - Affects: docs and manual validation.
   - Verify: a live channel produces sampled frame counts.
   - Pitfalls: this success does not imply captioning is implemented.

## Acceptance criteria

- [x] Runtime video can use Streamlink + PyAV to emit sampled `VideoFrame` events.
- [x] Sampling cadence is configurable and time-based or otherwise clearly documented.
- [x] Tests can use fake decoded frames without live Twitch.
- [x] Stream/decode failures are recorded without killing unrelated channels.
- [x] Cleanup does not leave decode tasks or child processes running.
- [x] The existing FFmpeg JPEG smoke remains available as a diagnostic path.
- [x] Manual validation can prove PyAV frame production before captioning.

## Blocked by

- Blocked by [02-bounded-local-perception-work-queue.md](./02-bounded-local-perception-work-queue.md)

## User stories addressed

- User story 12
- User story 13
- User story 21
- User story 22
- User story 23
- User story 29
- User story 31
- User story 32
