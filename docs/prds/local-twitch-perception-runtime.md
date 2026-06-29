# PRD - Local Twitch Perception Runtime

## Problem Statement

Minnarone can now connect to Twitch and prove that chat, audio, and video bytes
are available through manual smoke runs. That is not enough to make it behave
like the original Minnarone. The current Twitch work is capture-only: chat is
normalized into perceptions, but audio remains raw PCM and video remains raw
JPEG samples. The main `python -m minnarone` runtime also does not yet wire
`adapter: twitch` into a live agent run.

The user wants to recreate the original Minnarone perception architecture as
closely as possible: Twitch chat, audio, and video should be converted into
textual perceptions locally, written to the same `perceptions.jsonl` contract,
and then consumed by the existing Senser/Reactor/PromptBuilder loop. The LLM may
remain cloud-hosted through OpenRouter, matching the documented design: local
perception, cloud reaction.

The immediate output target is private to the operator: console/TUI comments.
Sending public messages to Twitch chat is intentionally deferred until the local
perception loop is correct and observable.

## Solution

Build a live Twitch runtime that turns the existing Twitch source adapter into a
full local perception pipeline:

- Twitch chat stays text-first and flows through the existing chat perceiver.
- Twitch audio is processed locally with VAD, ASR, speaker embeddings, and
  online diarization before it reaches the perception store.
- Twitch video is decoded locally with Streamlink + PyAV, sampled, deduplicated
  with hashing, captioned locally with Qwen2-VL, and written as video
  perceptions.
- The existing agent runtime consumes those perceptions and produces comments in
  console/TUI through the existing public output path.

The target contract is the same central store used by the rest of the framework:

```json
{"source": "chat", "type": "msg", "speaker": "viewer_name", "text": "..."}
{"source": "audio", "type": "speech", "speaker": "streamer", "text": "..."}
{"source": "audio", "type": "speech", "speaker": "speaker_1", "text": "..."}
{"source": "audio", "type": "speech", "speaker": "?", "text": "..."}
{"source": "video", "type": "caption", "text": "..."}
```

This shape is included because it is the durable integration contract between
local perception and the existing reaction loop.

## User Stories

1. As an operator, I want `adapter: twitch` to run in the main Minnarone app, so that live Twitch data reaches the real agent loop.
2. As an operator, I want Twitch chat to become normal chat perceptions, so that Minnarone can react to messages from viewers.
3. As an operator, I want Twitch audio to be transcribed locally, so that Minnarone can understand what is being said without sending audio to the cloud.
4. As an operator, I want voice activity detection before ASR, so that silence and background noise do not waste ASR work.
5. As an operator, I want utterance-level ASR rather than fixed one-second chunks, so that transcriptions are closer to natural speech.
6. As an operator, I want speaker labels on audio perceptions, so that Minnarone can distinguish the main speaker from other audio sources.
7. As an operator, I want online speaker clustering without manual enrollment, so that a new channel can be tested without pre-recording a voiceprint.
8. As an operator, I want the dominant speaker after warmup to be labeled `streamer`, so that the Senser can keep the original streamer-conversation behavior.
9. As an operator, I want non-dominant speakers to keep stable labels such as `speaker_1`, so that the prompt can refer consistently to other voices.
10. As an operator, I want uncertain or too-short audio segments to be labeled `?`, so that bad speaker guesses do not look authoritative.
11. As an operator, I want noisy ASR to still write approximate text, so that the downstream LLM can reason from gist rather than requiring perfect transcription.
12. As an operator, I want Twitch video to be decoded with Streamlink + PyAV, so that the runtime matches the original Minnarone architecture.
13. As an operator, I want video frames sampled at a controlled cadence, so that the local VLM does not run on every frame.
14. As an operator, I want visual deduplication before captioning, so that unchanged scenes do not create repeated captions or wasted model calls.
15. As an operator, I want Qwen2-VL captions written as video perceptions, so that Minnarone can comment on what is visible on stream.
16. As an operator, I want internal video captions in English, so that local VLM quality is favored while final comments can remain Italian.
17. As an operator, I want Minnarone to comment to me in console/TUI first, so that I can evaluate behavior before any public Twitch output exists.
18. As an operator, I want the TUI to show chat, transcription, video captions, triggers, and messages, so that I can debug what Minnarone perceived and why it reacted.
19. As an operator, I want model configuration in YAML or environment, so that I can swap model size, thresholds, and cadence without editing code.
20. As an operator, I want missing model files or system tools to fail clearly, so that setup errors are actionable.
21. As an operator, I want a bounded live pipeline, so that slow ASR or VLM work cannot grow memory forever during a stream.
22. As an operator, I want per-channel failures to be visible, so that chat can keep working if video captioning fails.
23. As an operator, I want smoke/debug commands for audio perception and video captioning, so that model setup can be validated before running the full agent.
24. As a developer, I want real backends behind the existing `Vad`, `Asr`, `SpeakerTagger`, and `Captioner` protocols, so that the core perceivers remain model-agnostic.
25. As a developer, I want online diarization isolated as a deep module, so that clustering thresholds and labels can be tested without ASR or Twitch.
26. As a developer, I want the VAD collector isolated as a deep module, so that frame sizing, padding, and utterance boundaries are deterministic in tests.
27. As a developer, I want ASR and speaker embedding to run on the same VAD-trimmed utterance, so that transcription and speaker labels describe the same audio event.
28. As a developer, I want ASR and embedding work to be queueable, so that blocking model calls do not stall Twitch readers.
29. As a developer, I want video sampling and dedup isolated from Qwen2-VL, so that expensive captioning can be tested with a fake captioner.
30. As a developer, I want `adapter: twitch` wiring to remain optional, so that existing non-Twitch configs are not forced to provide Twitch credentials or model paths.
31. As a developer, I want the existing smoke capture commands to remain useful, so that raw Twitch capture can still be debugged independently.
32. As a maintainer, I want all automated tests to avoid live Twitch, OpenRouter, and real model downloads, so that CI remains deterministic.
33. As a maintainer, I want model-backed tests to be opt-in/manual, so that local hardware differences do not make the suite flaky.
34. As a future operator, I want public Twitch chat output to plug in later through `OutputRouter`, so that it can be enabled only after console/TUI behavior is trusted.
35. As a future operator, I want multi-host speaker labeling later, so that channels with several regular hosts can be represented better than a single dominant `streamer`.

## Implementation Decisions

- Preserve the architecture from the existing PRDs: local perception writes
  textual records to `perceptions.jsonl`; the reaction loop reads the store and
  calls the cloud LLM.
- The first runtime output is console/TUI only. Public Twitch chat output is out
  of scope for this PRD.
- `adapter: twitch` must be wired into the reference app runtime. The existing
  validated Twitch config shape becomes operational instead of future-facing.
- Twitch chat remains read-only and authenticated through environment variables.
- Audio capture continues to normalize Twitch stream audio to mono 16 kHz
  signed 16-bit PCM before perception.
- Audio perception must be utterance-based, not fixed-chunk-based. PCM is split
  into 30 ms frames for VAD; the VAD collector emits complete utterances.
- Use `webrtcvad` as the VAD implementation. Initial parameters: mode 2,
  30 ms frames, 300 ms padding/hangover.
- Use `faster-whisper` with `large-v3-turbo` as the ASR backend. Initial ASR
  behavior should disable previous-text conditioning for independent live
  utterances.
- Use `sherpa-onnx` speaker embeddings, initially CAM++ 192-dimensional
  embeddings, as the speaker representation.
- Do not use `sherpa-onnx` offline diarization for the live path. It is a batch
  file-level workflow and does not match open-ended live streaming.
- Implement online speaker clustering as a local deep module: normalize
  embeddings, compare cosine similarity to centroids, update matching centroids,
  and create new clusters when similarity is below threshold.
- Initial clustering threshold is 0.6. This is a starting value, not a universal
  truth; it must be configurable and tuned from real captures.
- Do not require enrollment in the first version. The dominant speaker after a
  warmup window is labeled `streamer`; other clusters become `speaker_N`.
- Initial warmup for `streamer` selection is 60 seconds. After warmup, freeze the
  chosen `streamer` cluster to avoid label churn.
- Utterances shorter than 1 second may be transcribed but should not update
  speaker centroids. Very short or unreliable matches may emit speaker `?`.
- ASR and embedding may run concurrently over the same utterance. The design
  should allow thread or worker queues so model inference does not block source
  capture.
- Video runtime should use Streamlink + PyAV, matching the original
  architecture. The existing FFmpeg JPEG smoke remains a diagnostic path, not
  the final runtime video implementation.
- Video frames are sampled by time/cadence and deduplicated before captioning.
  Initial cadence should be conservative, such as one candidate frame every
  10 seconds.
- Dedup should answer "is there a meaningful visual change?" before calling the
  VLM. The first implementation can use a simple stable hash or perceptual hash,
  but the interface should allow better frame-difference logic later.
- Use local Qwen2-VL or a compatible local VLM behind the existing `Captioner`
  protocol. Model size and runtime provider are configuration concerns.
- Video captions are internal context and should be generated in English by
  default, matching the screenshots and favoring VLM quality. The final LLM
  output remains Italian.
- Add a commentator-oriented runtime mode or prompt stance for console/TUI
  output. The original bot persona can remain, but the first target is "commenta
  a me cosa sta succedendo", not "post publicly to Twitch".
- Keep model and threshold configuration explicit: ASR model, compute mode,
  embedding model path, clustering threshold, warmup duration, VAD aggressivity,
  video sample cadence, VLM model, and caption language should not be hardcoded
  in a way that blocks tuning.
- Keep the ports-and-adapters boundary: Twitch-specific code stays at the source
  edge; model-specific code stays behind perception backend interfaces; the
  Senser/Reactor/PromptBuilder consume only perceptions.

## Step-by-Step Implementation Plan

1. **Define runtime scope and configuration knobs.**
   - What to change: extend the operational Twitch config to include local
     audio/video perception settings, model paths, thresholds, warmup timing,
     and whether output is console/TUI only.
   - Why now: downstream modules need stable configuration contracts before
     wiring begins.
   - Affects: config schema, examples, operator docs.
   - Verify: existing non-Twitch configs still load; Twitch configs validate
     with clear errors for missing required local model settings.
   - Pitfalls: do not put secrets in YAML; Twitch credentials stay in
     environment variables.

2. **Wire `adapter: twitch` into the reference app with chat-only perception.**
   - What to change: make the main app construct `TwitchStreamAdapter` from
     config and inject it into the existing agent builder.
   - Why now: this proves the runtime bridge before model-heavy audio/video
     work is added.
   - Affects: app builder, CLI runtime, Twitch config workflow.
   - Verify: with audio/video disabled, live Twitch chat reaches
     `perceptions.jsonl` and the existing Reactor can print console output.
   - Pitfalls: do not make non-Twitch runs require Twitch credentials.

3. **Add a bounded perception work queue.**
   - What to change: introduce queueing between high-volume raw events and
     model-backed perception work for audio/video.
   - Why now: ASR and VLM calls are slower than chat parsing; the runtime needs
     backpressure before expensive models are enabled.
   - Affects: perception pump, adapter consumption, observability counters.
   - Verify: fake slow processors do not cause unbounded memory growth, and
     dropped/skipped media work is counted.
   - Pitfalls: do not drop chat in favor of media; chat remains low-volume and
     immediately useful.

4. **Implement the VAD collector as a deep module.**
   - What to change: build a streaming VAD component that accepts PCM bytes,
     splits them into legal 10/20/30 ms frames, maintains ring-buffer state, and
     emits utterances.
   - Why now: ASR and speaker embedding both depend on utterance boundaries.
   - Affects: `Vad` backend, audio perception workflow.
   - Verify: deterministic PCM fixtures produce expected utterance boundaries;
     silence does not emit speech; speech followed by hangover silence closes an
     utterance.
   - Pitfalls: `webrtcvad` requires 16-bit mono PCM at supported sample rates
     and exact frame durations.

5. **Implement the faster-whisper ASR backend.**
   - What to change: add a real `Asr` implementation that transcribes one VAD
     utterance at a time using `large-v3-turbo`.
   - Why now: once utterance boundaries exist, ASR can become a focused backend.
   - Affects: `Asr` protocol implementation, model configuration, manual model
     setup docs.
   - Verify: a short local PCM/WAV utterance produces plausible text; empty or
     non-speech segments produce no perception.
   - Pitfalls: avoid carrying previous text across unrelated utterances unless
     deliberately enabled; it can create hallucinated continuity.

6. **Implement speaker embedding extraction.**
   - What to change: add a backend that converts the same VAD utterance into a
     normalized speaker embedding with `sherpa-onnx`.
   - Why now: speaker clustering needs embeddings independent of ASR text.
   - Affects: speaker tagging backend, model setup docs.
   - Verify: repeated utterances from the same fixture speaker produce high
     similarity, and different fixture speakers produce lower similarity where
     fixtures are available.
   - Pitfalls: embeddings from very short speech are unreliable; do not update
     centroids from short utterances.

7. **Implement online speaker clustering and labeling.**
   - What to change: create a testable module that assigns embeddings to
     centroids by cosine similarity, updates centroids, creates new clusters,
     accumulates talk time, freezes the dominant cluster as `streamer`, and
     labels uncertain segments.
   - Why now: this is the core of online diarization and should be tested without
     ASR, VAD, Twitch, or sherpa.
   - Affects: `SpeakerTagger` implementation, TUI speaker labels.
   - Verify: synthetic embeddings cluster predictably; the dominant speaker
     becomes `streamer` after warmup; labels remain stable after freeze.
   - Pitfalls: thresholds are domain-specific; expose them for tuning.

8. **Compose the full local audio perceiver.**
   - What to change: wire VAD, ASR, embedding extraction, and online clustering
     behind the existing audio perceiver contract so audio events write
     `source=audio`, `type=speech` perceptions.
   - Why now: individual audio backends are testable; composition can now prove
     the full behavior.
   - Affects: audio perception runtime, perception store, TUI transcription
     panel.
   - Verify: a controlled audio stream produces transcription lines with
     `streamer`, `speaker_N`, or `?`; raw audio smoke remains available.
   - Pitfalls: ASR and embedding results must describe the same utterance, not
     different windows.

9. **Implement Streamlink + PyAV video frame source.**
   - What to change: add a runtime video reader/decoder path that uses
     Streamlink for the Twitch stream and PyAV for frame decoding/sampling.
   - Why now: the final video path should match the original Minnarone design,
     not the JPEG smoke shortcut.
   - Affects: Twitch video runtime, video event payloads.
   - Verify: fake or fixture video input emits sampled `VideoFrame` values; live
     manual smoke shows frame production without FFmpeg JPEG files.
   - Pitfalls: keep subprocess and decoder cleanup robust; live streams can
     fail or stall.

10. **Implement visual dedup before captioning.**
    - What to change: isolate frame hashing/frame-difference logic so unchanged
      frames are skipped before VLM invocation.
    - Why now: VLM captioning is expensive and should only run when something
      changed.
    - Affects: `VideoPerceiver` sampling/dedup behavior.
    - Verify: identical or near-identical frames call no captioner; changed
      frames pass through.
    - Pitfalls: exact byte hashes may miss visually identical frames with minor
      encoding differences; design the interface so perceptual hashing can
      replace a simpler first pass.

11. **Implement the Qwen2-VL caption backend.**
    - What to change: add a local `Captioner` implementation that produces short
      English descriptions from sampled frames.
    - Why now: sampling and dedup are in place, so the expensive model is called
      only on candidate frames.
    - Affects: `Captioner` protocol implementation, model setup, video
      perception.
    - Verify: a fixture image produces a concise English caption; errors are
      reported without killing chat/audio.
    - Pitfalls: model size/provider choices are hardware-sensitive; keep them
      configurable and document recommended defaults for Apple Silicon.

12. **Compose the full local video perceiver.**
    - What to change: wire PyAV frame events through sampling/dedup/captioning
      into `source=video`, `type=caption` perceptions.
    - Why now: individual video components are ready; the perception store can
      now receive true visual context.
    - Affects: video perception runtime, perception store, TUI video panel.
    - Verify: live run writes useful video captions at the expected cadence.
    - Pitfalls: avoid repeated captions for unchanged scenes; noisy captions are
      acceptable, repeated spam is not.

13. **Add commentator-oriented runtime behavior.**
    - What to change: add configuration or prompt stance for operator-facing
      commentary in Italian, using the same perceptions, memory, summary, and
      triggers.
    - Why now: once true local perceptions exist, the output should match the
      user's desired first product: a private commentator.
    - Affects: prompt configuration, output routing, examples.
    - Verify: the agent comments in console/TUI about live stream context without
      sending Twitch messages.
    - Pitfalls: do not remove the existing public-chat persona; make this a
      runtime mode or config stance.

14. **Extend observability for model-backed perception.**
    - What to change: show audio transcription labels, speaker cluster state,
      video caption timestamps, dropped media work, and per-channel failures in
      the dashboard or debug output.
    - Why now: local perception quality needs live tuning.
    - Affects: TUI/dashboard, stats snapshots, operator docs.
    - Verify: during a live run the operator can see whether failures are in
      capture, VAD, ASR, speaker tagging, video decoding, or VLM.
    - Pitfalls: avoid dumping secrets or huge raw frames/audio into logs.

15. **Document setup and manual validation.**
    - What to change: document system tools, Python extras, model downloads,
      recommended Apple Silicon settings, smoke commands, and success criteria.
    - Why now: model-backed local perception has environmental dependencies that
      must be explicit.
    - Affects: README/operator docs/examples.
    - Verify: a fresh operator can install prerequisites, run isolated audio and
      video checks, then run the full console/TUI commentator.
    - Pitfalls: do not imply CI runs live Twitch or heavy local models.

16. **Run full manual live acceptance.**
    - What to change: execute a bounded live run on a Twitch channel with chat,
      audio, video, local perceptions, LLM reaction, and console/TUI output.
    - Why now: all components are integrated.
    - Affects: end-to-end operator workflow.
    - Verify: `perceptions.jsonl` contains chat, speech, and captions; console
      output references live context; no public Twitch messages are sent.
    - Pitfalls: expect ASR and diarization imperfections; the pass criterion is
      useful real-time context, not perfect transcripts.

## Testing Decisions

Good tests should verify external behavior at module boundaries. They should not
assert private task names, exact thread scheduling, exact model outputs, or live
Twitch behavior. Model-backed tests should be separated from deterministic unit
tests and treated as manual or opt-in integration checks.

- Reuse existing test style from the codebase: fake adapters, fake process
  runners, fake VAD/ASR/speaker taggers, fake captioners, and store-level
  assertions.
- Test config parsing for new Twitch perception settings with no live Twitch or
  model files required.
- Test `adapter: twitch` runtime wiring with fake readers so the main agent can
  be driven end-to-end without network.
- Test VAD frame validation and collector state transitions with deterministic
  PCM fixtures.
- Test ASR backend behavior through a fake model wrapper for automated tests;
  keep real faster-whisper checks manual.
- Test speaker embedding extraction through a fake extractor in CI and optional
  real sherpa-onnx checks locally.
- Test online clustering with synthetic normalized vectors: assignment,
  centroid update, new-speaker creation, short-utterance handling, talk-time
  accumulation, streamer freeze, and `?` fallback.
- Test full audio composition using fake VAD/ASR/embedding/clustering to ensure
  one utterance writes one audio perception with the expected speaker label.
- Test PyAV video sampling with fixture video or fake decoded frames, not live
  Twitch.
- Test visual dedup with identical frames, slightly changed frames, and changed
  scene fixtures.
- Test Qwen2-VL caption backend through a fake captioner in CI and optional real
  local model checks manually.
- Test video composition with fake frames and fake captioner to ensure only
  changed sampled frames write caption perceptions.
- Test backpressure behavior with deliberately slow fake audio/video processors.
- Test TUI/dashboard data models with fake stats and fake perception stores.
- Manual acceptance tests should include:
  - audio-only local perception run writes speech perceptions;
  - video-only local perception run writes caption perceptions;
  - full Twitch run writes chat, audio, and video perceptions;
  - console/TUI output comments in Italian;
  - no public Twitch message is sent.

## Out of Scope

- Sending messages to Twitch chat.
- Twitch output router, public bot mode, moderation/rate-limit policy for public
  chat posting, and OAuth scopes beyond current read-only capture needs.
- Manual voiceprint enrollment as the default speaker-tagging strategy.
- Multi-host semantic labeling in the first version. Only one dominant
  `streamer` label is required initially.
- Perfect diarization, overlapped speech separation, or source separation.
- Offline batch diarization with `sherpa-onnx` as the live runtime path.
- Cloud audio transcription or cloud video captioning.
- Replacing the OpenRouter LLM provider.
- Bandwagon implementation.
- Auto-memory, RAG, TTS, structured Twitch events, raids, follows, subscriptions,
  or EventSub integration.
- CI jobs that download large models, require valid Twitch credentials, or
  depend on a live Twitch channel.

## Further Notes

- The original Minnarone material emphasizes that perception can be imperfect:
  transcripts may be noisy and speaker tags may occasionally be wrong. The
  system should degrade gracefully and preserve enough context for the LLM to
  infer the gist.
- Thresholds for speaker clustering are not universal. Start with 0.6 and tune
  from real captures; expose values in config so tuning does not require code
  changes.
- The user's current machine is an Apple M2 Max with 32 GB RAM, which is a
  plausible target for local ASR, speaker embeddings, and a small or quantized
  local VLM. Model choice should still be validated through isolated spikes
  before full runtime integration.
- The existing raw Twitch smoke artifacts remain valuable diagnostics. They
  should not be deleted or conflated with the model-backed runtime: capture-only
  smoke answers "do bytes arrive?", while this PRD answers "do useful textual
  perceptions arrive?".
