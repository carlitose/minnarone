## Parent PRD

[local-twitch-perception-runtime.md](../../prds/local-twitch-perception-runtime.md)

## What to build

Add the first local ASR-backed audio perception path. VAD utterances from Twitch
audio should be transcribed locally with `faster-whisper large-v3-turbo` and
written as normal audio speech perceptions. Speaker labeling is deliberately
minimal in this slice: emit `?` until online speaker clustering lands.

This creates a demoable local audio understanding path before diarization.

## Step-by-step implementation plan

1. Define the ASR backend contract.
   - What to change: implement or wrap the existing `Asr` protocol with a real
     faster-whisper backend that accepts one VAD utterance.
   - Why now: the VAD slice provides natural utterance boundaries.
   - Affects: audio perceiver backend, model configuration.
   - Verify: a fake ASR backend can still be used in automated tests.
   - Pitfalls: keep faster-whisper imports isolated so environments without the
     extra dependency can still run core tests when the backend is unused.

2. Add model configuration.
   - What to change: expose ASR model name/path, device/provider choice, compute
     type, language, beam size, and previous-text conditioning.
   - Why now: local performance depends on hardware and model settings.
   - Affects: config schema and operator docs.
   - Verify: defaults match the PRD: `large-v3-turbo` and
     previous-text conditioning disabled.
   - Pitfalls: do not hardcode CUDA-only settings on Apple Silicon.

3. Convert VAD utterance bytes to model input.
   - What to change: normalize 16-bit PCM utterance bytes to the numeric format
     expected by faster-whisper.
   - Why now: ASR must operate on the same utterance emitted by VAD.
   - Affects: ASR adapter layer.
   - Verify: test fixtures preserve duration and sample rate through conversion.
   - Pitfalls: do not resample silently unless the sample rate is known and
     intentionally changed.

4. Write speech perceptions with unknown speaker.
   - What to change: compose VAD + ASR so non-empty transcriptions append
     `source=audio`, `type=speech`, `speaker=?` perceptions.
   - Why now: this proves useful audio-to-text before diarization.
   - Affects: perception store and audio perceiver composition.
   - Verify: empty ASR output creates no perception; non-empty output creates
     one perception with the expected text.
   - Pitfalls: do not produce perceptions for whitespace-only text.

5. Add clear model setup failures.
   - What to change: fail with actionable messages when the model is missing or
     the backend cannot initialize.
   - Why now: local model setup is operator-sensitive.
   - Affects: CLI/runtime errors and docs.
   - Verify: tests can simulate model init failure without downloading models.
   - Pitfalls: do not include secrets or huge stack traces in normal operator
     errors.

6. Add automated and manual checks.
   - What to change: automated tests use fake model wrappers; manual checks run
     a short audio file or live bounded capture through real ASR.
   - Why now: model output is not deterministic enough for ordinary CI.
   - Affects: test suite and operator docs.
   - Verify: fake tests assert behavior; manual docs describe plausible success.
   - Pitfalls: do not require real faster-whisper in CI.

## Acceptance criteria

- [ ] A real faster-whisper ASR backend exists behind the `Asr` protocol.
- [ ] ASR configuration includes model, compute/provider, language, and previous-text behavior.
- [ ] VAD utterances can become `audio/speech` perceptions with speaker `?`.
- [ ] Empty or whitespace ASR results produce no perception.
- [ ] Missing or invalid ASR model setup fails clearly.
- [ ] Automated tests use fake ASR and require no model download.
- [ ] Manual validation instructions cover a real local ASR smoke.

## Blocked by

- Blocked by [03-utterance-vad-audio-path.md](./03-utterance-vad-audio-path.md)

## User stories addressed

- User story 3
- User story 5
- User story 11
- User story 23
- User story 24
- User story 27
- User story 33
