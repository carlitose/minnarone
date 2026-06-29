## Parent PRD

[local-twitch-perception-runtime.md](../../prds/local-twitch-perception-runtime.md)

## What to build

Add the real local VLM caption backend behind the existing `Captioner` boundary.
Sampled and deduplicated Twitch frames should be captioned locally with Qwen2-VL
or a compatible local Qwen2-VL runtime, producing concise English video
perceptions.

This slice keeps automated tests fake-backed and makes real model validation
manual/opt-in.

## Step-by-step implementation plan

1. Choose the local Qwen2-VL runtime integration boundary.
   - What to change: define a caption backend interface that can call a local
     Qwen2-VL model without leaking model-specific details into `VideoPerceiver`.
   - Why now: the fake-caption path already proves the perception shape.
   - Affects: `Captioner` implementation and model setup.
   - Verify: fake captioner tests still pass unchanged.
   - Pitfalls: do not make the core video perceiver import heavy model packages.

2. Add model configuration.
   - What to change: expose model identifier/path, device/provider, quantization
     or runtime options, max output length, prompt language, and timeout.
   - Why now: local VLM feasibility depends on hardware and model size.
   - Affects: config schema and operator docs.
   - Verify: missing or invalid model setup fails clearly.
   - Pitfalls: do not assume one provider works on every machine.

3. Define the caption prompt.
   - What to change: create a concise instruction that asks for short English
     descriptions of visible stream context.
   - Why now: captions are internal context for the LLM, not user-facing prose.
   - Affects: video perception quality.
   - Verify: manual fixture images produce short, useful descriptions.
   - Pitfalls: avoid long captions that bloat prompts.

4. Add frame conversion for the model.
   - What to change: convert `VideoFrame` payloads from PyAV/array format into
     the image input expected by the VLM backend.
   - Why now: the backend must consume the same frames accepted by dedup.
   - Affects: caption backend.
   - Verify: fixture frames survive conversion with expected dimensions/color.
   - Pitfalls: avoid unnecessary disk writes for every frame.

5. Handle failures and timeouts gracefully.
   - What to change: if local VLM captioning fails or times out, record the
     failure and allow chat/audio to continue.
   - Why now: local model inference can be slow or memory-sensitive.
   - Affects: work queue and diagnostics.
   - Verify: fake timeout/failure tests do not kill the whole runtime.
   - Pitfalls: do not retry aggressively and create a backlog.

6. Add manual model validation.
   - What to change: document a local image/frame caption smoke command or
     workflow.
   - Why now: real VLM outputs are hardware/model-dependent and should be
     verified outside CI.
   - Affects: operator docs.
   - Verify: an operator can run one image through the real backend and see an
     English caption.
   - Pitfalls: do not require large model downloads in normal test runs.

## Acceptance criteria

- [x] A local Qwen2-VL-compatible backend exists behind the `Captioner` protocol.
- [x] Caption model/runtime settings are configurable.
- [x] Captions are concise and English by default.
- [x] Frame conversion avoids unnecessary persistent raw files.
- [x] VLM failures/timeouts are recorded without killing chat/audio.
- [x] Automated tests use fake captioners and require no VLM download.
- [x] Manual validation docs explain how to test the real local caption backend.

## Blocked by

- Blocked by [07-video-dedup-with-fake-captions.md](./07-video-dedup-with-fake-captions.md)

## User stories addressed

- User story 15
- User story 16
- User story 23
- User story 24
- User story 29
- User story 33
