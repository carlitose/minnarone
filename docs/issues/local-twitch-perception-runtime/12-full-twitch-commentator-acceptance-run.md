## Parent PRD

[local-twitch-perception-runtime.md](../../prds/local-twitch-perception-runtime.md)

## What to build

Run and document the full live acceptance path for the Local Twitch Perception
Runtime: Twitch chat, local audio perception, local video captioning, the normal
Minnarone reaction loop, and console/TUI commentary. This is a HITL validation
slice because it requires live credentials, local model setup, and qualitative
operator judgment.

The expected outcome is not perfect transcription or perfect diarization. The
expected outcome is useful real-time textual perception and Italian commentary
without sending public Twitch messages.

## Step-by-step implementation plan

1. Prepare the environment.
   - What to change: use the documented setup to ensure Twitch credentials,
     Streamlink, PyAV, local ASR, speaker embedding, and VLM models are ready.
   - Why now: this slice validates the complete system, not installation in
     isolation.
   - Affects: operator workflow.
   - Verify: isolated checks from the setup docs pass before the full run.
   - Pitfalls: do not debug all components at once if a prerequisite check
     fails.

2. Run a bounded live session.
   - What to change: start the configured Twitch commentator runtime for a fixed
     duration on a live channel.
   - Why now: bounded runs avoid runaway model cost/CPU usage while validating
     behavior.
   - Affects: end-to-end runtime.
   - Verify: the run starts, captures chat, processes audio/video, and exits or
     is stopped cleanly.
   - Pitfalls: do not leave model workers or stream processes running.

3. Inspect the perception store.
   - What to change: verify `perceptions.jsonl` contains chat messages, audio
     speech with speaker labels, and video captions.
   - Why now: the perception store is the central contract of the architecture.
   - Affects: acceptance criteria and debugging.
   - Verify: records use the expected `source`, `type`, `speaker`, and `text`
     fields.
   - Pitfalls: do not judge success from raw artifacts alone; this PRD requires
     textual perceptions.

4. Inspect observability.
   - What to change: use TUI/debug output to confirm queue counts, speaker
     cluster state, captions, failures, and triggers.
   - Why now: live tuning depends on visibility.
   - Affects: operator acceptance.
   - Verify: failures are absent or explained; drops are bounded and visible.
   - Pitfalls: a zero-failure run is ideal, but minor ASR noise is acceptable.

5. Evaluate commentary quality.
   - What to change: review console/TUI comments for relevance to live chat,
     speech, and visible stream context.
   - Why now: the product goal is a private commentator, not only data capture.
   - Affects: qualitative acceptance.
   - Verify: at least one comment clearly references current live context from
     chat/audio/video.
   - Pitfalls: do not require public-chat naturalness yet; public output is out
     of scope.

6. Verify safety boundaries.
   - What to change: confirm no Twitch `PRIVMSG` or public send path was used.
   - Why now: output to Twitch is explicitly deferred.
   - Affects: safety acceptance.
   - Verify: token scopes and logs show read-only behavior for this run.
   - Pitfalls: do not paste tokens or secrets into issue comments or artifacts.

7. Record results and follow-up issues.
   - What to change: summarize model settings, thresholds, observed latency,
     failure counts, perception quality, and recommended tuning.
   - Why now: the next iteration depends on empirical behavior.
   - Affects: follow-up planning.
   - Verify: notes are actionable and avoid secrets.
   - Pitfalls: do not mark this complete if the run only proves raw capture and
     not textual local perception.

## Acceptance criteria

- [ ] A bounded live run captures Twitch chat, audio, and video.
- [ ] `perceptions.jsonl` contains chat `msg`, audio `speech`, and video `caption` records.
- [ ] Audio records include `streamer`, `speaker_N`, or `?` speaker labels.
- [ ] Video captions are concise English internal context.
- [ ] Console/TUI output produces Italian commentary for the operator.
- [ ] No public Twitch messages are sent.
- [ ] Queue/failure stats are inspectable after or during the run.
- [ ] Any quality or latency problems are recorded as follow-up tuning work.

## Blocked by

- Blocked by [05-online-speaker-clustering-labels.md](./05-online-speaker-clustering-labels.md)
- Blocked by [08-local-qwen2-vl-caption-backend.md](./08-local-qwen2-vl-caption-backend.md)
- Blocked by [09-commentator-mode-console-tui.md](./09-commentator-mode-console-tui.md)
- Blocked by [10-local-perception-observability.md](./10-local-perception-observability.md)
- Blocked by [11-operator-setup-and-model-validation-docs.md](./11-operator-setup-and-model-validation-docs.md)

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 4
- User story 5
- User story 6
- User story 7
- User story 8
- User story 9
- User story 10
- User story 11
- User story 12
- User story 13
- User story 14
- User story 15
- User story 16
- User story 17
- User story 18
- User story 19
- User story 20
- User story 21
- User story 22
- User story 23

## Autopilot status

Blocked-needs-human as of 2026-06-26. Dependencies 05, 08, 09, 10, and 11 are
complete, and the operator workflow is documented, but this issue is a live HITL
acceptance run. The current agent process does not have `OPENROUTER_API_KEY`,
`TWITCH_BOT_USERNAME`, or `TWITCH_OAUTH_TOKEN` in its environment, and the
remaining acceptance criteria require a bounded live Twitch session plus
operator judgment of the Italian commentary quality.

No secrets were inspected or recorded. Do not move this issue to `done/` until a
real run has produced chat `msg`, audio `speech`, video `caption`, local
commentary, observable queue/failure stats, and confirmation that no public
Twitch messages were sent.
