## Parent PRD

[original-minnarone-chat-dry-run.md](../../prds/original-minnarone-chat-dry-run.md)

## What to build

Run and record a human-in-the-loop manual acceptance pass for the original
Minnarone chat dry-run in the live TUI. The goal is to verify that the feature
feels like the original Minnarone behavior while staying local-only.

This issue is HITL because it requires live runtime setup, operator judgment of
message quality, and visual inspection of the TUI and prompt tab. It should not
be moved to done based only on automated tests.

## Step-by-step implementation plan

1. Prepare a local original-chat dry-run config.
   - What to change: enable commentator mode, select original-chat style, keep
     private/local output, and point the config at seed `soul` and `facts`.
   - Why this comes first: the acceptance run must exercise the intended
     operator workflow.
   - Affects: local config and operator environment.
   - Verify: `--check` passes before starting a live run.
   - Pitfalls: do not add Twitch write/send scopes.

2. Start a bounded TUI run.
   - What to change: run the live TUI for a controlled duration on a channel
     where chat/audio/video context is available.
   - Why this comes after config validation: avoid discovering config issues
     during a model-backed live run.
   - Affects: manual operator workflow.
   - Verify: TUI starts, panels update, and run can be stopped cleanly.
   - Pitfalls: do not leave stream/model workers running after the test.

3. Inspect perception panels.
   - What to change: confirm chat, transcription, and video panels contain
     useful textual perceptions.
   - Why this comes before judging output: output quality depends on perception
     quality.
   - Affects: manual acceptance notes.
   - Verify: at least chat and one of audio/video are visibly present; record if
     a channel is unavailable or degraded.
   - Pitfalls: noisy ASR is acceptable; absence of a whole perception channel
     should be called out.

4. Inspect the prompt tab.
   - What to change: verify the latest prompt uses the original-chat structure:
     Twitch rules, permanent memory, dynamic context, recent Minnarone messages,
     response format, and trigger-specific situation at the bottom.
   - Why this comes before output review: prompt correctness explains output
     behavior.
   - Affects: manual acceptance notes and follow-up tuning.
   - Verify: the prompt tab shows the exact captured prompt with secrets
     redacted.
   - Pitfalls: do not judge from a reconstructed or summarized prompt.

5. Inspect the `MINNARONE` panel.
   - What to change: confirm local output shows both `RE` and `MSG`.
   - Why this is the primary operator-visible behavior.
   - Affects: TUI display acceptance.
   - Verify: at least one normal message is visible in two-line form.
   - Pitfalls: the panel should not show duplicate `[PRIVATE]` prefixes or raw
     malformed LLM text.

6. Exercise or observe `#end_conv`.
   - What to change: if naturally produced, confirm `MSG: #end_conv` appears as
     a skipped decision and closes the relevant window. If not naturally
     produced, note that it was not observed in this run.
   - Why this is qualitative in live runs but deterministic in automated tests.
   - Affects: manual acceptance notes.
   - Verify: skipped decisions are visible when they occur.
   - Pitfalls: do not force unsafe prompt injection just to trigger the branch.

7. Verify local-only safety.
   - What to change: confirm no Twitch `PRIVMSG` or public send path was used.
   - Why this is the main safety boundary of the dry-run.
   - Affects: operator acceptance and issue status.
   - Verify: logs/config/scopes show read-only capture and local output only.
   - Pitfalls: do not paste secrets into acceptance notes.

8. Record results and follow-ups.
   - What to change: summarize channel, duration, model, prompt quality, output
     quality, failures, and any tuning work.
   - Why this comes last: future prompt tuning needs empirical notes.
   - Affects: issue completion notes or follow-up issues.
   - Verify: notes are actionable and avoid secrets.
   - Pitfalls: do not mark complete if the run only proves automated fake tests,
     not live TUI behavior.

## Acceptance criteria

- [ ] A bounded live TUI run starts with original-chat style enabled.
- [ ] The prompt tab shows the original-chat prompt structure.
- [ ] The `MINNARONE` panel shows at least one local `RE`/`MSG` output.
- [ ] Chat/audio/video perception availability is recorded.
- [ ] No Twitch public message is sent.
- [ ] `#end_conv` behavior is verified if observed, or explicitly noted as not observed.
- [ ] Prompt/output quality notes are recorded for follow-up tuning.
- [ ] No secrets are recorded in notes or artifacts.

## Blocked by

- Blocked by [07-end-to-end-fake-dry-run.md](./done/07-end-to-end-fake-dry-run.md)

## User stories addressed

- User story 1
- User story 2
- User story 4
- User story 7
- User story 9
- User story 10
- User story 11
- User story 22

## Autopilot status

Blocked-needs-human as of 2026-06-30. Dependency 07 is complete in the stacked
autopilot branch/PR, and the non-live config wiring check passes with placeholder
read-only IRC values:

```bash
TWITCH_BOT_USERNAME=dry_run TWITCH_OAUTH_TOKEN=oauth:dry_run \
  uv run --extra dev python -m minnarone \
  examples/twitch-original-chat.example.yaml --check
```

This issue remains open because the remaining acceptance criteria require a
bounded live TUI session, real runtime credentials/model setup, visual
inspection of the prompt and `MINNARONE` panels, and operator judgment of output
quality. No secrets were inspected or recorded. Do not move this issue to
`done/` until a real run confirms local `RE`/`MSG` output, perception
availability, prompt structure, `#end_conv` behavior if observed, and no public
Twitch sends.
