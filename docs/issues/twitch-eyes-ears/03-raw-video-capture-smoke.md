## Parent PRD

[twitch-eyes-ears.md](../../prds/twitch-eyes-ears.md)

## What to build

Add the first raw video capture path for Twitch. Given a Twitch channel, use
Streamlink and FFmpeg as external tools to sample live video frames at a low
configured rate, encode each sampled frame as JPEG bytes, wrap it in the
existing `VideoFrame` payload contract, and save a limited number of JPEG frames
in the smoke artifacts.

This slice does not caption images. It proves that the adapter can produce
well-shaped visual input for a later VLM backend.

The key payload decision from the PRD is:

```python
RawEvent(channel="video", payload=VideoFrame(pixels=jpeg_bytes, source_label="stream", ts=...), ts=...)
```

This snippet is included because it fixes the video contract between Twitch
capture and the existing video perceiver boundary.

## Step-by-step implementation plan

1. Reuse the media process runner boundary.
   - What to change: use the same fakeable process runner introduced for audio.
   - Why now: video should share subprocess lifecycle semantics instead of adding a second process-management pattern.
   - Affects: media reader consistency and cleanup workflow.
   - Verify: fake process tests still cover cancellation and failures for video-like stdout.
   - Pitfalls: do not duplicate process-runner logic in the video reader.

2. Define JPEG frame extraction semantics.
   - What to change: choose a frame boundary strategy for FFmpeg JPEG output and a configurable frames-per-second setting.
   - Why now: the reader must know how to split stdout into frame payloads before it can emit events.
   - Affects: video reader API and smoke sample naming.
   - Verify: fake byte streams containing multiple JPEG frames split into separate frame payloads.
   - Pitfalls: do not sample too frequently by default; video capture must remain cheap enough for live use.

3. Implement the raw video reader.
   - What to change: build the Streamlink/FFmpeg pipeline that produces JPEG frames and publishes video `RawEvent` values.
   - Why now: process handling and frame splitting are ready, so the reader can focus on event production.
   - Affects: Twitch video reader and adapter queue publishing.
   - Verify: fake frame bytes produce `VideoFrame` values with `source_label="stream"` and timestamps.
   - Pitfalls: do not run VLM captioning here; model backends remain out of scope.

4. Extend the smoke artifact writer for video.
   - What to change: save a capped number of video frames as `.jpg` files and count video events in stats.
   - Why now: operators need a concrete artifact to verify FFmpeg produced useful frames before captioning exists.
   - Affects: smoke output directory structure and stats.
   - Verify: fake video events create a limited set of `.jpg` files and update stats.
   - Pitfalls: cap the number of saved files; live video is unbounded.

5. Add video options to the smoke command.
   - What to change: allow enabling/disabling video and configuring video FPS.
   - Why now: manual debugging needs a way to isolate video from chat/audio and to tune capture cost.
   - Affects: smoke CLI workflow.
   - Verify: disabling video skips video subprocess launch; invalid FPS values fail clearly.
   - Pitfalls: do not make video a hard requirement for chat-only or audio-only smoke runs.

6. Document video smoke verification.
   - What to change: explain where JPEG frames are written and what a successful frame sample means.
   - Why now: this slice introduces visual artifacts.
   - Affects: operator setup guide.
   - Verify: docs distinguish raw frame capture from later VLM captioning.
   - Pitfalls: do not claim that Minnarone can understand the image yet.

## Acceptance criteria

- [ ] Video reader reuses the shared media process boundary.
- [ ] JPEG frame splitting or framing behavior is covered by deterministic tests.
- [ ] Video reader emits `RawEvent(channel="video")` with `VideoFrame` payloads matching the PRD contract.
- [ ] The smoke workflow can save a capped set of raw `.jpg` frame samples.
- [ ] Video event counts and failures appear in smoke stats.
- [ ] Disabling video prevents video subprocess launch.
- [ ] No automated test requires Streamlink, FFmpeg, Twitch or live network.
- [ ] Existing tests and quality checks pass.

## Blocked by

- Blocked by [01-chat-only-twitch-smoke.md](./01-chat-only-twitch-smoke.md)
- Blocked by [02-raw-audio-capture-smoke.md](./02-raw-audio-capture-smoke.md)

## User stories addressed

- User story 7
- User story 8
- User story 13
- User story 21
- User story 22
- User story 26
- User story 29
- User story 30
- User story 31
- User story 33
