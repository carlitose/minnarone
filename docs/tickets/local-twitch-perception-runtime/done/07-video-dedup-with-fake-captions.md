## Parent PRD

[local-twitch-perception-runtime.md](../../prds/local-twitch-perception-runtime.md)

## What to build

Add the video perception path up to fake captioning: sampled PyAV frames should
pass through visual deduplication and write video caption perceptions only when
the scene is meaningfully new. Use a fake captioner in this slice so the
behavior is deterministic and does not require Qwen2-VL.

This creates the complete video integration shape before the real local VLM is
introduced.

## Step-by-step implementation plan

1. Define the visual change decision.
   - What to change: specify how the first implementation decides whether a
     sampled frame is new enough to caption.
   - Why now: dedup must be explicit before calling any captioner.
   - Affects: video perceiver behavior and config.
   - Verify: identical frames skip captioning; changed frames pass through.
   - Pitfalls: exact hashes are easy but may be too strict; keep the interface
     replaceable for perceptual hashing or frame-difference logic.

2. Implement frame hashing/dedup as a focused module or policy.
   - What to change: isolate the dedup logic from frame decoding and captioning.
   - Why now: it should be testable without PyAV or VLM.
   - Affects: video sampling/dedup boundary.
   - Verify: fixtures cover repeated frames and changed scenes.
   - Pitfalls: do not mix timestamp into the visual hash.

3. Wire dedup into video perception.
   - What to change: sampled `VideoFrame` events should call the captioner only
     when dedup says the frame is worth describing.
   - Why now: this is the final shape the real VLM will use.
   - Affects: `VideoPerceiver` composition and work queue.
   - Verify: fake captioner call counts match dedup decisions.
   - Pitfalls: repeated unchanged frames must not spam identical perceptions.

4. Use fake captions to write real video perceptions.
   - What to change: use an injectable fake captioner that returns deterministic
     English descriptions.
   - Why now: the perception store path can be verified before Qwen2-VL.
   - Affects: perception store and TUI video panel data.
   - Verify: changed frames append `source=video`, `type=caption` perceptions.
   - Pitfalls: do not assert real model wording in tests.

5. Add config for cadence and dedup threshold.
   - What to change: expose sample interval and dedup sensitivity, even if the
     first dedup method is simple.
   - Why now: live streams vary from static talking heads to fast gameplay.
   - Affects: config schema and docs.
   - Verify: tests can tune sample interval and dedup behavior.
   - Pitfalls: avoid overly chatty defaults.

6. Add tests covering the full fake-caption video path.
   - What to change: drive fake frames through sample/dedup/fake caption/store.
   - Why now: this is the video equivalent of a tracer bullet.
   - Affects: video integration tests.
   - Verify: only expected frames write perceptions.
   - Pitfalls: avoid depending on image library internals in behavior tests.

## Acceptance criteria

- [x] Sampled frames are deduplicated before captioning.
- [x] Dedup logic is testable without PyAV or Qwen2-VL.
- [x] Fake captioner calls occur only for frames accepted by dedup.
- [x] Accepted frames write `video/caption` perceptions.
- [x] Repeated unchanged frames do not spam perceptions.
- [x] Sample cadence and dedup sensitivity are configurable.
- [x] Automated tests require no real VLM.

## Blocked by

- Blocked by [06-pyav-twitch-video-frame-runtime.md](./06-pyav-twitch-video-frame-runtime.md)

## User stories addressed

- User story 13
- User story 14
- User story 15
- User story 29
- User story 32
