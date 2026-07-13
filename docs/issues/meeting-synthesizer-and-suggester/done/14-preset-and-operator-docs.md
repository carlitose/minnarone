## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Create example config presets for the new styles and write operator
documentation explaining how to use the meeting synthesizer and suggester.

## Step-by-step implementation plan

1. **Create `examples/teams-meeting-assistant.yaml`.**
   A ready-to-use preset with both new styles active:
   ```yaml
   adapter: os_capture
   mode: private
   commentator:
     language: it
     profiles:
       meeting_synthesizer:
         interval_s: 180
       suggester: {}
   ```
   Include the standard `os_capture`, VAD, ASR, and VLM sections (copy from
   `examples/teams-commentator.yaml` as base).
   *Verify:* `python -m minnarone examples/teams-meeting-assistant.yaml --check`
   passes.

2. **Create `examples/teams-meeting-full.yaml` (optional variant).**
   A preset with all three profiles: `operator` + `meeting_synthesizer` +
   `suggester` — for operators who want commentary, summaries, and
   suggestions simultaneously.
   *Verify:* `--check` passes.

3. **Write operator documentation.**
   Create `docs/meeting-assistant-operator.md` (or add a section to the
   existing `docs/twitch-operator.md`) covering:
   - What the meeting synthesizer does and how to configure the interval.
   - What the suggester does and how it uses facts.
   - How to write facts files for interlocutors.
   - How to combine profiles (e.g. operator + synthesizer + suggester).
   - TUI panel layout with the new panels.
   - Cost estimates (from the PRD's Further Notes).
   - Troubleshooting: what if the suggester is too noisy (shorten facts,
     adjust the prompt), what if the synthesizer is too frequent (increase
     `interval_s`).
   *Verify:* docs are self-consistent and reference real config fields.

4. **Update CLAUDE.md if needed.**
   If the project's CLAUDE.md references commentator styles or config
   format, update it for the new profiles format.
   *Verify:* CLAUDE.md is accurate.

## Acceptance criteria

- [ ] `examples/teams-meeting-assistant.yaml` exists and passes `--check`
- [ ] Operator documentation covers both new styles
- [ ] Documentation explains how to combine profiles
- [ ] Documentation includes cost estimates
- [ ] All referenced config fields are accurate

## Blocked by

- Blocked by [13-tui-panels-and-dashboard-diagnostics.md](./13-tui-panels-and-dashboard-diagnostics.md)

## User stories addressed

- User story 11
