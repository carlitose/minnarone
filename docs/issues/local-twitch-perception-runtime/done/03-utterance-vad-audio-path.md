## Parent PRD

[local-twitch-perception-runtime.md](../../prds/local-twitch-perception-runtime.md)

## What to build

Build the real-time VAD utterance boundary layer for Twitch audio. Raw PCM from
Twitch should be split into legal `webrtcvad` frames, passed through a
streaming collector with ring-buffer padding/hangover, and emitted as complete
speech utterances ready for ASR and speaker embedding.

This slice does not transcribe. It proves that Minnarone can turn the existing
PCM audio stream into utterance-level speech segments.

## Step-by-step implementation plan

1. Define the VAD input contract.
   - What to change: document and enforce PCM requirements for the VAD path:
     mono, 16-bit, 16 kHz, and exact 10/20/30 ms frames.
   - Why now: `webrtcvad` rejects invalid frame sizes and sample formats.
   - Affects: audio backend configuration and validation.
   - Verify: invalid sample rates or frame sizes fail clearly in tests.
   - Pitfalls: do not feed arbitrary chunk sizes directly to `webrtcvad`.

2. Add frame splitting with remainder handling.
   - What to change: split incoming PCM bytes into exact 30 ms frames and carry
     incomplete trailing bytes into the next call.
   - Why now: live audio arrives as chunks, not necessarily aligned to VAD
     frames.
   - Affects: VAD collector input stream.
   - Verify: byte fixtures split into the correct frame count and preserve
     trailing partial frames.
   - Pitfalls: dropping partial frames will lose audio and create boundary
     artifacts.

3. Implement the collector state machine.
   - What to change: implement the NOT_TRIGGERED/TRIGGERED collector with a
     padding ring buffer and hangover silence behavior.
   - Why now: Minnarone needs utterances, not individual speech frames.
   - Affects: `Vad` backend behavior.
   - Verify: speech surrounded by silence yields one utterance with padding;
     silence-only input yields none.
   - Pitfalls: avoid flushing an utterance on every tiny pause; use hangover.

4. Add max utterance duration.
   - What to change: force-flush very long utterances after a configurable
     maximum duration.
   - Why now: ASR should not receive unbounded live buffers.
   - Affects: VAD collector and downstream model latency.
   - Verify: long continuous speech is split into bounded utterances.
   - Pitfalls: do not make the max duration so short that natural sentences are
     chopped excessively.

5. Expose VAD tuning in config.
   - What to change: add or prepare knobs for aggressiveness, frame duration,
     padding duration, and max utterance duration.
   - Why now: real streams vary in noise and speaking style.
   - Affects: config schema and docs.
   - Verify: defaults match the PRD: mode 2, 30 ms frames, 300 ms padding.
   - Pitfalls: keep defaults useful; avoid requiring every config to specify all
     low-level knobs.

6. Add an audio VAD smoke/debug path.
   - What to change: provide a way to run Twitch audio through VAD and report
     utterance counts/durations without ASR.
   - Why now: operators need to validate VAD before model-heavy steps.
   - Affects: manual diagnostics.
   - Verify: live audio produces utterances when people speak and near-zero
     utterances on silence/noise.
   - Pitfalls: this is not an ASR success signal; it only proves segmentation.

## Acceptance criteria

- [ ] PCM input is validated for `webrtcvad` frame compatibility.
- [ ] Incoming PCM chunks are split into exact VAD frames with partial-frame carryover.
- [ ] The VAD collector emits complete utterances using padding/hangover behavior.
- [ ] Long utterances are force-flushed by a configurable maximum duration.
- [ ] Defaults are mode 2, 30 ms frames, and 300 ms padding.
- [ ] Deterministic tests cover silence, speech, trailing partial frames, and long speech.
- [ ] A manual VAD diagnostic can report utterance counts/durations without ASR.

## Blocked by

- Blocked by [02-bounded-local-perception-work-queue.md](./02-bounded-local-perception-work-queue.md)

## User stories addressed

- User story 4
- User story 5
- User story 23
- User story 26
- User story 31
- User story 32
