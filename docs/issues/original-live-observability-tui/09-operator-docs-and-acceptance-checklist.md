## Parent PRD

[original-live-observability-tui.md](../../prds/original-live-observability-tui.md)

## What to build

Document the live TUI and replay workflows so an operator can run and evaluate
the new dashboard without reading the development chat. The docs should explain
the live `--tui` command, replay command, run artifact retention, prompt capture
retention, source health labels, each panel's meaning, and safety boundaries.

This slice comes after the implementation slices because the docs should match
the actual command names and behavior.

## Step-by-step implementation plan

1. Identify the existing operator documentation style.
   - What to change: review current setup and Twitch operator docs so the new
     TUI section uses the same vocabulary and command style.
   - Why this comes first: docs should extend the existing operator workflow
     rather than duplicate it.
   - Affects: operator-facing documentation.
   - Verify: the new section has a clear home and does not contradict existing
     setup instructions.
   - Pitfalls: do not include secrets, real tokens, or machine-specific local
     values.

2. Document live TUI startup.
   - What to change: add the command and prerequisites for launching the live
     runtime with `--tui`.
   - Why this comes now: this is the primary operator workflow.
   - Affects: operator docs and docs tests if present.
   - Verify: command examples match the implemented CLI surface.
   - Pitfalls: do not imply the TUI sends public Twitch messages or controls the
     runtime.

3. Explain every main dashboard panel.
   - What to change: describe `IDLE`, `FINESTRA CHAT`, `STREAMER`, `CHAT`,
     `EVENTI`, `MINNARONE`, `TRASCRIZIONE`, `VIDEO`, and `MEMORIA`.
   - Why this comes now: the screenshot-faithful layout has many dense panels.
   - Affects: operator docs.
   - Verify: descriptions match the implemented panel meanings.
   - Pitfalls: keep the explanation operational; avoid marketing copy.

4. Document source health and prompt debugging.
   - What to change: explain health labels, counts, queue depth, failures,
     VLM/ASR busy states, and the `PROMPT` tab's exact-prompt behavior.
   - Why this comes now: these are the main debugging tools.
   - Affects: operator docs.
   - Verify: examples mention best-effort token/cache/cost metadata and unknown
     fields.
   - Pitfalls: do not promise exact cost accounting unless the provider returns
     enough metadata.

5. Document run and prompt retention.
   - What to change: explain per-run artifact directories, latest-20 run
     retention, latest-50 prompt retention, and 200 KB prompt cap.
   - Why this comes now: the user explicitly wants to avoid filling the Mac.
   - Affects: operator docs.
   - Verify: docs state where artifacts are local and that they are gitignored.
   - Pitfalls: do not encourage committing run artifacts.

6. Document replay mode and acceptance checklist.
   - What to change: add replay command usage and a manual checklist for
     confirming chat, audio, video, Minnarone comments, memory, prompt tab, and
     source health on a real run.
   - Why this comes last: replay and acceptance are the final workflows.
   - Affects: operator docs and manual QA checklist.
   - Verify: a human can follow the checklist without chat history.
   - Pitfalls: do not include live Twitch/OpenRouter checks in automated CI
     docs tests.

## Acceptance criteria

- [ ] Docs include the live `--tui` command and prerequisites.
- [ ] Docs include replay command usage.
- [ ] Docs explain every main dashboard panel.
- [ ] Docs explain `PROMPT` tab behavior, exact prompt preservation, and redaction.
- [ ] Docs explain source health labels, counts, queue depth, and failures.
- [ ] Docs explain run and prompt retention limits.
- [ ] Docs clearly state the TUI is read-only and does not send public Twitch messages.
- [ ] Docs include a manual live acceptance checklist.

## Blocked by

- Blocked by [01-live-tui-launch-path.md](./01-live-tui-launch-path.md)
- Blocked by [02-bounded-run-artifacts.md](./02-bounded-run-artifacts.md)
- Blocked by [03-prompt-capture-and-retention.md](./03-prompt-capture-and-retention.md)
- Blocked by [04-tui-minnarone-output-sink.md](./04-tui-minnarone-output-sink.md)
- Blocked by [05-screenshot-faithful-dashboard-panels.md](./05-screenshot-faithful-dashboard-panels.md)
- Blocked by [06-source-health-and-event-status.md](./06-source-health-and-event-status.md)
- Blocked by [07-prompt-tab-in-tui.md](./07-prompt-tab-in-tui.md)
- Blocked by [08-replay-mode.md](./08-replay-mode.md)

## User stories addressed

- User story 45
