## Parent PRD

[twitch-eyes-ears.md](../../prds/twitch-eyes-ears.md)

## What to build

Add the first raw audio capture path for Twitch. Given a Twitch channel, use
Streamlink and FFmpeg as external tools to extract live audio, normalize it to
mono 16 kHz signed 16-bit little-endian PCM, wrap it in the existing
`AudioChunk` payload contract, and save a limited number of raw PCM samples in
the smoke artifacts.

This slice does not transcribe audio. It proves that the adapter can produce
well-shaped audio input for a later ASR backend.

The key payload decision from the PRD is:

```python
RawEvent(channel="audio", payload=AudioChunk(samples=pcm_bytes, sample_rate=16000, source_label="stream", ts=...), ts=...)
```

This snippet is included because it fixes the audio contract between Twitch
capture and the existing audio perceiver boundary.

## Step-by-step implementation plan

1. Add a fakeable process runner boundary.
   - What to change: introduce a small abstraction for launching and stopping Streamlink/FFmpeg subprocesses.
   - Why now: audio and video readers both need robust process lifecycle behavior, and tests must avoid real processes.
   - Affects: media reader workflow, subprocess cleanup, failure reporting.
   - Verify: fake process tests cover stdout reads, non-zero exit status, cancellation and stop cleanup.
   - Pitfalls: never use shell string interpolation; external commands must be invoked with argument lists.

2. Define audio byte chunking.
   - What to change: calculate chunk sizes from sample rate, sample width, channel count and configured chunk duration.
   - Why now: audio output must be chunked predictably before it can become `AudioChunk` payloads.
   - Affects: audio reader API and smoke sample naming.
   - Verify: fake byte streams produce fixed-size chunks for the configured duration.
   - Pitfalls: do not assume FFmpeg emits complete semantic speech segments; this slice emits raw fixed-duration audio chunks.

3. Implement the raw audio reader.
   - What to change: build the Streamlink/FFmpeg pipeline that produces PCM bytes and publishes audio `RawEvent` values.
   - Why now: process handling and chunking are ready, so the reader can focus on event production.
   - Affects: Twitch audio reader and adapter queue publishing.
   - Verify: fake stdout bytes produce `AudioChunk` values with `sample_rate=16000`, `source_label="stream"` and timestamps.
   - Pitfalls: do not run VAD or ASR here; model backends remain out of scope.

4. Extend the smoke artifact writer for audio.
   - What to change: save a capped number of audio chunks as raw PCM files and count audio events in stats.
   - Why now: operators need a concrete artifact to verify FFmpeg output before ASR exists.
   - Affects: smoke output directory structure and stats.
   - Verify: fake audio events create a limited set of `.pcm` files and update stats.
   - Pitfalls: cap the number of saved files; live audio is unbounded.

5. Add audio options to the smoke command.
   - What to change: allow enabling/disabling audio, setting chunk duration and selecting stream quality.
   - Why now: manual debugging needs knobs to isolate audio from chat and later video.
   - Affects: smoke CLI workflow.
   - Verify: disabling audio skips process launch; invalid chunk durations fail clearly.
   - Pitfalls: keep Streamlink and FFmpeg as system prerequisites, not CI requirements.

6. Document the audio prerequisite path.
   - What to change: document that Streamlink and FFmpeg must be available on `PATH`, and describe how to inspect `.pcm` artifacts.
   - Why now: this slice introduces external tools.
   - Affects: operator setup guide.
   - Verify: docs explain what success looks like for a capture-only audio smoke.
   - Pitfalls: do not imply ASR is implemented by this slice.

## Acceptance criteria

- [ ] Audio process handling is covered by fake process tests.
- [ ] Audio chunk sizing is deterministic and tested.
- [ ] Audio reader emits `RawEvent(channel="audio")` with `AudioChunk` payloads matching the PRD contract.
- [ ] The smoke workflow can save a capped set of raw `.pcm` audio samples.
- [ ] Audio event counts and failures appear in smoke stats.
- [ ] Disabling audio prevents audio subprocess launch.
- [ ] No automated test requires Streamlink, FFmpeg, Twitch or live network.
- [ ] Existing tests and quality checks pass.

## Blocked by

- Blocked by [01-chat-only-twitch-smoke.md](./01-chat-only-twitch-smoke.md)

## User stories addressed

- User story 5
- User story 6
- User story 12
- User story 21
- User story 22
- User story 26
- User story 29
- User story 30
- User story 31
- User story 33
