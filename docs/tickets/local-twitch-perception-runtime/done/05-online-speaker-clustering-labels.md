## Parent PRD

[local-twitch-perception-runtime.md](../../prds/local-twitch-perception-runtime.md)

## What to build

Complete the local audio path by adding online speaker embeddings, clustering,
and labels. Each VAD utterance should be transcribed and embedded from the same
audio segment, assigned to an online speaker cluster, and written as an audio
perception with `streamer`, `speaker_N`, or `?`.

This slice explicitly avoids manual enrollment. The first version follows the
approved design: the dominant speaker after warmup is frozen as `streamer`.

## Step-by-step implementation plan

1. Add a sherpa-onnx speaker embedding backend.
   - What to change: implement a backend that accepts one VAD utterance and
     returns a normalized speaker embedding.
   - Why now: ASR perceptions exist; they now need a speaker label.
   - Affects: speaker tagging backend and model setup.
   - Verify: fake extractor tests work in CI; real extractor can be checked
     manually with a local utterance.
   - Pitfalls: keep sherpa-onnx imports isolated from core tests when unused.

2. Add embedding model configuration.
   - What to change: expose embedding model path, provider, thread count, and
     expected dimension.
   - Why now: CAM++ is the initial recommendation, but the implementation should
     remain replaceable.
   - Affects: config and operator docs.
   - Verify: missing model files fail clearly.
   - Pitfalls: do not bake a downloaded model path into code.

3. Implement online clustering as a deep module.
   - What to change: assign normalized embeddings to centroids using cosine
     similarity, update matched centroids, and create new clusters below the
     threshold.
   - Why now: clustering must be independently testable without ASR or Twitch.
   - Affects: speaker tagging logic.
   - Verify: synthetic vectors cluster predictably.
   - Pitfalls: avoid depending on vector object identity; test mathematical
     behavior.

4. Add talk-time and streamer freeze.
   - What to change: track accumulated speech duration per cluster, choose the
     dominant cluster after a warmup window, and freeze that cluster as
     `streamer`.
   - Why now: the approved MVP uses one dominant speaker instead of enrollment.
   - Affects: speaker label mapping and Senser behavior.
   - Verify: the dominant cluster becomes `streamer` after warmup and remains
     stable even if another speaker later talks more.
   - Pitfalls: label churn will confuse the prompt and TUI.

5. Handle short and uncertain utterances.
   - What to change: avoid centroid updates for utterances shorter than the
     configured minimum duration and emit `?` for unreliable assignments.
   - Why now: short utterances can damage clusters.
   - Affects: clustering and label policy.
   - Verify: short utterances can be transcribed without changing centroids.
   - Pitfalls: do not overuse `?`; it should mean uncertainty, not normal
     non-streamer speech.

6. Compose ASR and embedding over the same utterance.
   - What to change: ensure the text and speaker label written to one perception
     come from the same VAD-trimmed audio buffer.
   - Why now: mismatched windows produce misleading perceptions.
   - Affects: audio perception composition and work queue.
   - Verify: tests assert one utterance produces one coherent perception.
   - Pitfalls: do not run embedding on a different chunk boundary than ASR.

7. Add tuning knobs and diagnostics.
   - What to change: expose clustering threshold, warmup duration, min update
     duration, and basic cluster stats.
   - Why now: thresholds are domain-specific and must be tuned from real runs.
   - Affects: config and observability.
   - Verify: tests can set a tiny warmup window for deterministic behavior.
   - Pitfalls: avoid hardcoding 0.6 as if it were universally correct.

## Acceptance criteria

- [ ] A sherpa-onnx embedding backend exists behind the speaker-tagging boundary.
- [ ] Online clustering assigns, creates, and updates speaker centroids by cosine similarity.
- [ ] The dominant speaker after warmup is frozen as `streamer`.
- [ ] Other stable clusters are labeled `speaker_N`.
- [ ] Short or unreliable utterances can emit `?` and do not corrupt centroids.
- [ ] ASR text and speaker label are produced from the same VAD utterance.
- [ ] Thresholds and warmup settings are configurable.
- [ ] Automated tests use synthetic embeddings and fake extractors.

## Blocked by

- Blocked by [04-local-asr-audio-perceptions.md](./04-local-asr-audio-perceptions.md)

## User stories addressed

- User story 6
- User story 7
- User story 8
- User story 9
- User story 10
- User story 25
- User story 27
- User story 35
