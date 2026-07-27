## Parent PRD

[local-twitch-perception-runtime.md](../../prds/local-twitch-perception-runtime.md)

## What to build

Document setup, model installation, configuration, and manual validation for the
local Twitch perception runtime. An operator should be able to install system
tools and local models, run isolated audio/video checks, and understand what a
successful full commentator run looks like.

This slice should not change runtime behavior except where lightweight
validation commands or examples are needed to make documentation executable.

## Step-by-step implementation plan

1. Document system prerequisites.
   - What to change: list required system tools for Twitch capture, PyAV video,
     and local model execution.
   - Why now: operators need to separate system setup from Python package setup.
   - Affects: operator docs.
   - Verify: docs include commands to check installed tools.
   - Pitfalls: do not imply Streamlink/FFmpeg/PyAV model dependencies are all
     installed by one Python package.

2. Document Python extras or dependency groups.
   - What to change: explain which optional dependencies are needed for
     webrtcvad, faster-whisper, sherpa-onnx, PyAV, and Qwen2-VL runtime.
   - Why now: core Minnarone should remain usable without heavy local models.
   - Affects: packaging docs and install instructions.
   - Verify: install instructions are explicit for local perception.
   - Pitfalls: avoid forcing heavy dependencies into the base install unless
     intentionally decided.

3. Document model downloads and paths.
   - What to change: explain expected ASR, speaker embedding, and VLM model
     choices and where operators should configure their paths/identifiers.
   - Why now: missing model files are the most likely setup failure.
   - Affects: model setup docs.
   - Verify: docs name recommended defaults from the PRD and mention that
     alternatives are configurable.
   - Pitfalls: avoid hardcoding one user-specific absolute path.

4. Document Apple Silicon recommendations.
   - What to change: provide practical guidance for the known target machine:
     Apple M2 Max, 32 GB RAM.
   - Why now: model runtime choices need hardware-specific notes.
   - Affects: operator docs.
   - Verify: recommendations are framed as starting points, not guarantees.
   - Pitfalls: do not promise exact latency or quality.

5. Add isolated validation workflows.
   - What to change: document or provide commands for VAD-only, ASR-only,
     speaker-clustering, PyAV-frame, and VLM-caption checks.
   - Why now: operators must be able to isolate failures before full runtime.
   - Affects: smoke/debug docs and optional commands.
   - Verify: each validation step has a clear success signal.
   - Pitfalls: do not require live Twitch for every validation; allow local
     fixture checks where possible.

6. Document full commentator run.
   - What to change: show the expected config shape and command for console/TUI
     commentator mode.
   - Why now: this is the end-user workflow of the PRD.
   - Affects: examples and operator docs.
   - Verify: docs state clearly that no public Twitch messages are sent.
   - Pitfalls: do not paste real tokens or recommend committing secrets.

7. Add troubleshooting.
   - What to change: cover missing model, bad Twitch credentials, offline
     channel, no utterances, empty ASR, speaker over/under-clustering, no video
     frames, repeated captions, and VLM timeout.
   - Why now: local perception has many environmental failure modes.
   - Affects: operator handoff.
   - Verify: every common failure points to a concrete check or knob.
   - Pitfalls: avoid vague "try again" advice.

## Acceptance criteria

- [x] Docs explain required system tools and how to check them.
- [x] Docs explain optional local-perception Python dependencies.
- [x] Docs identify recommended ASR, speaker embedding, and VLM models.
- [x] Docs include Apple Silicon starting recommendations.
- [x] Docs include isolated validation workflows for audio and video.
- [x] Docs include a full console/TUI commentator run workflow.
- [x] Docs clearly state that public Twitch output is still out of scope.
- [x] Troubleshooting covers model, capture, diarization, video, and VLM failures.

## Blocked by

- Blocked by [04-local-asr-audio-perceptions.md](./04-local-asr-audio-perceptions.md)
- Blocked by [05-online-speaker-clustering-labels.md](./05-online-speaker-clustering-labels.md)
- Blocked by [08-local-qwen2-vl-caption-backend.md](./08-local-qwen2-vl-caption-backend.md)

## User stories addressed

- User story 19
- User story 20
- User story 23
- User story 31
- User story 33
