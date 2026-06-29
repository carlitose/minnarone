## Parent PRD

[original-live-observability-tui.md](../../prds/original-live-observability-tui.md)

## What to build

Run the completed live TUI against a real Twitch channel and validate it with
human judgment against the original Minnarone screenshot intent. This is a HITL
acceptance slice because it requires live credentials, a live channel, local
models, OpenRouter, terminal visual inspection, and qualitative operator
judgment.

The goal is not pixel-perfect automation. The goal is to confirm the actual
operator experience: chat, audio, video captions, Minnarone comments, memory,
prompt debugging, and source health are all visible and faithful enough to the
original workflow.

## Step-by-step implementation plan

1. Prepare a bounded live run.
   - What to change: choose a currently live Twitch channel, load local runtime
     configuration, and set a clear timebox for the acceptance run.
   - Why this comes first: the test requires live inputs and should not run
     indefinitely.
   - Affects: manual operator workflow.
   - Verify: credentials, local model paths, OpenRouter key, and Twitch channel
     are ready before starting.
   - Pitfalls: never paste secrets into issue notes or terminal output intended
     for documentation.

2. Start the runtime with the TUI.
   - What to change: launch the live command with `--tui`.
   - Why this comes now: the full integrated path is what this issue validates.
   - Affects: end-to-end runtime.
   - Verify: the TUI opens, the status bar identifies the channel/run, and the
     live runtime begins processing.
   - Pitfalls: if the selected channel goes offline, switch channels and record
     that fact without treating it as a code failure.

3. Validate main dashboard panels.
   - What to change: visually confirm `CHAT`, `TRASCRIZIONE`, `VIDEO`,
     `MINNARONE`, `MEMORIA`, `EVENTI`, `IDLE`, `FINESTRA CHAT`, and `STREAMER`
     populate or show truthful empty states.
   - Why this comes now: these panels are the core original Minnarone experience.
   - Affects: human acceptance.
   - Verify: at least chat messages, audio speech, video captions, and one
     Minnarone comment are visible during the run.
   - Pitfalls: do not mark success if video captions are absent but the rest
     works; that was the original observability failure.

4. Validate source health and failures.
   - What to change: inspect the status bar and `EVENTI` for chat/audio/video,
     ASR, VLM, LLM, queue depth, dropped/failed work, and latest failure.
   - Why this comes now: the dashboard must make partial failures obvious.
   - Affects: human acceptance and follow-up tuning.
   - Verify: status reflects the observed run; any failure is visible and
     understandable.
   - Pitfalls: short early idle periods are acceptable, silent broken sources
     are not.

5. Validate prompt debugging.
   - What to change: open the `PROMPT` tab and inspect the latest prompt,
     trigger reason, model, token/cache/cost metadata, and redaction.
   - Why this comes now: prompt debugging is a first-class requirement.
   - Affects: human acceptance.
   - Verify: the prompt structure is preserved, secrets are not visible, and
     missing cost fields are labeled honestly.
   - Pitfalls: do not copy prompt text containing private chat into public issue
     notes.

6. Validate artifact retention behavior.
   - What to change: inspect the current run directory after the run and confirm
     perception logs and prompt captures are present and bounded.
   - Why this comes now: long local experimentation must not fill the disk.
   - Affects: operator workflow and run-session acceptance.
   - Verify: artifacts are under the local run area, prompts are capped/retained,
     and generated files are gitignored.
   - Pitfalls: do not manually delete evidence needed for replay before running
     the replay check.

7. Validate replay.
   - What to change: open replay mode against the just-finished run.
   - Why this comes now: replay should reproduce the dashboard without live
     services.
   - Affects: offline debug workflow.
   - Verify: replay shows the same major panels and prompt/debug state without
     starting Twitch, local models, or OpenRouter.
   - Pitfalls: replay does not need to animate in real time for this first
     acceptance pass.

8. Record results and follow-ups.
   - What to change: summarize the channel, duration, panels observed, source
     counts, failures, visual mismatch from screenshots, and any tuning or UI
     follow-up issues.
   - Why this comes last: the acceptance slice should produce actionable
     evidence, not just a pass/fail claim.
   - Affects: release readiness and future issues.
   - Verify: notes contain no secrets and clearly state whether acceptance
     passed.
   - Pitfalls: do not block completion on perfect ASR, perfect diarization, or
     pixel-perfect visual regression; those are out of scope.

## Acceptance criteria

- [ ] A bounded live `--tui` run starts and stops cleanly.
- [ ] The main dashboard shows chat, audio transcription, video captions, Minnarone comments, memory, events, and conversation windows.
- [ ] The status bar shows truthful source health and counts for chat/audio/video/LLM/VLM where available.
- [ ] Partial failures are visible rather than hidden.
- [ ] The `PROMPT` tab shows the latest exact redacted prompt and metadata.
- [ ] The run writes bounded local artifacts and does not expose generated artifacts to git.
- [ ] Replay opens the completed run without live services.
- [ ] No public Twitch messages are sent.
- [ ] Human visual inspection confirms the result is faithful enough to the original screenshots.
- [ ] Any remaining quality or visual gaps are recorded as follow-up work.

## Blocked by

- Blocked by [01-live-tui-launch-path.md](./01-live-tui-launch-path.md)
- Blocked by [02-bounded-run-artifacts.md](./02-bounded-run-artifacts.md)
- Blocked by [03-prompt-capture-and-retention.md](./03-prompt-capture-and-retention.md)
- Blocked by [04-tui-minnarone-output-sink.md](./04-tui-minnarone-output-sink.md)
- Blocked by [05-screenshot-faithful-dashboard-panels.md](./05-screenshot-faithful-dashboard-panels.md)
- Blocked by [06-source-health-and-event-status.md](./06-source-health-and-event-status.md)
- Blocked by [07-prompt-tab-in-tui.md](./07-prompt-tab-in-tui.md)
- Blocked by [08-replay-mode.md](./08-replay-mode.md)
- Blocked by [09-operator-docs-and-acceptance-checklist.md](./09-operator-docs-and-acceptance-checklist.md)

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
- User story 24
- User story 25
- User story 26
- User story 27
- User story 28
- User story 29
- User story 30
- User story 31
- User story 32
- User story 33
- User story 34
- User story 35
- User story 36
- User story 37
- User story 38
- User story 39
- User story 40
- User story 41
- User story 42
- User story 43
- User story 44
- User story 45
