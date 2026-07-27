# ADR: Live Media Backpressure Boundary

## Status

Accepted

## Context

In the local Twitch commentator runtime, the operator reported that only chat was
working while audio and video were visible in the TUI only as failures or queue
pressure. The observed events included:

- `video/unknown: failed to initialize local Qwen2-VL caption backend`
- `audio/queue: dropped=<n>`
- `vlm=busy` / no video captions

Three independent diagnosis passes converged on the same mechanism: Twitch media
capture is producing audio and video events, but local model-backed perception is
slower than live input. Chat keeps working because it bypasses the media model
queue and is dispatched directly. Audio and video are routed through
`BoundedLocalPerceptionQueue`, where each channel has a single worker. The video
worker can be monopolized by Qwen2-VL captioning full 1080p frames; the audio
worker can be monopolized by ASR/speaker processing. When the workers are busy,
the queue fills and new media is dropped.

Evidence gathered during diagnosis:

- `uv run python -m minnarone .local/twitch-commentator.local.yaml --check`
  passed with the local config.
- A capture-only smoke run against `retireinprogress` captured audio and video
  successfully: 11 audio events and 2 video frames in 10 seconds, with no
  failures.
- Live runtime probes produced audio and video events with no adapter failures,
  while the media perception queue showed audio drops and zero processed video
  captions.
- A direct live Twitch frame was full HD (`1080x1920x3` RGB), and Qwen2-VL
  captioning of a real captured frame timed out after 120 seconds on the local
  machine.

The system must stay local/console-only for observation: no public Twitch
messages, no secret leakage, and no unbounded artifact writes.

## Decision

Treat audio/video as lossy live perception streams and put explicit real-time
backpressure policy at the media/model boundary.

Video perception must prioritize the newest usable frame, downscale frames before
Qwen2-VL, and avoid FIFO backlogs of stale frames. Audio perception must avoid
unbounded raw chunk backlog and keep model work bounded enough that the operator
sees current transcripts instead of ever-growing dropped counters. Queue pressure
is expected operational behavior, but it must be controlled and observable.

## Options Considered

### Option 1: Increase Queue Sizes

- Make `perception_queue_size` larger.
- Considered because it is the smallest configuration change.
- Benefit: fewer immediate drops during short runs.
- Drawback: it stores stale media and increases latency; Qwen/ASR still cannot
  catch up, so the operator sees old captions or no captions.

### Option 2: Disable Audio/Video Until Faster Hardware Exists

- Keep chat-only runtime stable and document audio/video as manual smoke tools.
- Benefit: no overload in the live UI.
- Drawback: contradicts the product goal: Minnarone must observe local Twitch
  audio and video, not only chat.

### Option 3: Explicit Lossy Real-Time Media Boundary

- Downscale video before VLM inference.
- Coalesce/drop stale video frames while the VLM is busy.
- Keep audio model work bounded and observable.
- Benefit: preserves live behavior; the newest information wins, and the UI can
  show meaningful captions/transcripts.
- Drawback: some media will intentionally be skipped under load.

## Consequences

The live runtime becomes a real-time observer rather than an archival media
processor. It may skip frames or chunks under load, but skipped work is counted
and visible. Operators should tune model/device settings for quality, but the
default runtime should not collapse into stale FIFO backlog.

Video captions should become possible on this machine because Qwen2-VL receives
bounded-size images instead of full 1080p arrays. Audio should degrade through
controlled drops or shorter utterances instead of starving the UI with an
unbounded backlog.

Tests should verify behavior at public boundaries: queue policy, video frame
preprocessing, and runtime snapshots. Live Twitch/Qwen/Whisper acceptance remains
manual because it depends on stream availability and local hardware.

## Implementation Notes

Implement the decision in vertical slices:

1. Add image bounding before Qwen2-VL inference.
   - The boundary should live in the VLM caption backend or a small helper owned
     by it, because Qwen2-VL owns model input shape.
   - Preserve in-memory processing; do not write frames to disk.
   - Keep dimensions configurable with conservative defaults.

2. Add latest-frame semantics for video work.
   - Video queue overload should drop stale queued video frames in favor of the
     newest frame.
   - The UI should continue to report drops, failures, and queue depth.

3. Keep audio bounded.
   - Avoid turning raw 1-second chunks into an infinite ASR backlog.
   - Prefer shorter utterance limits and clear queue counters over increasing
     capacity.

4. Add focused tests.
   - Use fake frames/captioners/model inputs for deterministic tests.
   - Do not require live Twitch, Qwen2-VL, Whisper, Streamlink, FFmpeg, or
     credentials in automated tests.

## Follow-Up Work

- `docs/tickets/live-media-backpressure-runtime/done/01-live-media-throughput-boundary.md`
