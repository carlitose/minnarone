## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Manual acceptance test on a real meeting (Teams, Zoom, or Meet) with the
meeting synthesizer and suggester active. Record the outcome — what worked,
what didn't, what needs tuning.

## Step-by-step implementation plan

1. **Prepare the environment.**
   - Ensure `os_capture` dependencies are installed (`soundcard`, `mss`).
   - Copy `examples/teams-meeting-assistant.yaml` to `.local/` and adjust
     model paths for the local machine.
   - Prepare facts files for expected meeting participants.
   - Run `--check` to validate the config.
   *Verify:* config validation passes.

2. **Run during a real meeting.**
   - Join a Teams/Zoom/Meet call.
   - Launch Minnarone with the `.local` config.
   - Observe the TUI during the meeting:
     - SINTETIZZATORE panel: does it produce readable summaries every
       ~3 minutes? Are the notes accurate?
     - SUGGERIMENTI panel: does it produce useful suggestions when someone
       says something relevant? Does it stay silent when there's nothing
       to suggest?
     - If OPERATOR is also active: do comments, summaries, and suggestions
       appear in separate panels without interference?
   - Note any issues: hallucinated suggestions, missed context, excessive
     noise, layout problems, latency.

3. **Record the outcome.**
   Write a short acceptance report in this issue file (or a linked file)
   covering:
   - Meeting duration and participant count.
   - Number of synthesizer outputs and quality assessment.
   - Number of suggester outputs, how many were useful.
   - `#nothing` silence rate (was it appropriate?).
   - Any prompt tuning needed.
   - Any TUI layout issues.
   - Cost (check OpenRouter usage after the session).

4. **File follow-up issues if needed.**
   If the acceptance reveals prompt tuning, layout fixes, or behavioral
   issues, file them as separate issues — don't block this acceptance on
   perfection.

## Acceptance criteria

- [ ] Minnarone runs on a real meeting with synthesizer + suggester active
- [ ] SINTETIZZATORE panel produces readable meeting notes
- [ ] SUGGERIMENTI panel produces at least some useful suggestions
- [ ] `#nothing` silence works (no empty/garbage output in suggester panel)
- [ ] TUI layout is usable during a live meeting
- [ ] Acceptance report recorded with observations

## Blocked by

- Blocked by [14-preset-and-operator-docs.md](./14-preset-and-operator-docs.md)

## User stories addressed

- All user stories (1-13)
