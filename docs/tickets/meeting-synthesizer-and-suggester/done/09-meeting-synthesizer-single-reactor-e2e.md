## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Wire a complete end-to-end path for the MEETING_SYNTHESIZER style: a config
with a single `meeting_synthesizer` profile produces a Reactor with periodic
Senser + MEETING_SYNTHESIZER prompt + console output. This is the tracer bullet
that proves the synthesizer works in isolation.

## Step-by-step implementation plan

1. **Wire the MEETING_SYNTHESIZER profile in `build_agent`.**
   When `config.commentator.profiles` contains `MEETING_SYNTHESIZER`, build:
   - A Senser with `trigger_mode="periodic"` and `interval_s` from the
     profile config.
   - A PromptBuilder with `commentator_style=MEETING_SYNTHESIZER`.
   - A ConsoleOutputRouter (or TuiPrivateOutputRouter if TUI is active).
   - A Reactor connecting these + the shared LLM, store, and summary
     provider.
   For this slice, handle only the case of a single profile (the multi-Reactor
   wiring comes in slice 11).
   *Verify:* `build_agent` with a MEETING_SYNTHESIZER config produces an
   Agent without errors.
   *Pitfall:* the Reactor's `CadenceLoop` interval should match the
   synthesizer's needs — the Senser handles its own timer, but the Reactor
   loop cadence should tick frequently enough to not miss synthesis ticks
   (0.5s default is fine).

2. **Connect the summary provider.**
   The MEETING_SYNTHESIZER Reactor needs access to the Summarizer's
   `current_summary`. This is already wired as a `summary_provider` lambda
   in the existing Reactor. Ensure the same lambda is passed to the new
   Reactor.
   *Verify:* the prompt includes the current summary.

3. **End-to-end test with fake LLM.**
   Create a test that:
   - Constructs a config with `adapter: os_capture`, `mode: private`,
     `commentator.profiles.meeting_synthesizer.interval_s: 5`.
   - Provides fake perceptions (a few speech utterances).
   - Uses a `FakeLLMProvider` that returns a fixed summary response.
   - Advances the fake clock past `interval_s`.
   - Verifies that the console output contains the LLM's response as
     `[PRIVATE]`.
   *Verify:* output appears after `interval_s`, not before.
   *Pitfall:* the Summarizer also needs to run (it feeds the summary to the
   prompt). Either pre-seed a summary or run the Summarizer once before
   the Reactor tick.

4. **Verify `--check` works.**
   A config with only `meeting_synthesizer` profile should pass `--check`
   (config validation only, no runtime).
   *Verify:* `python -m minnarone <config> --check` exits 0.

## Acceptance criteria

- [ ] Config with a single `meeting_synthesizer` profile is valid
- [ ] `build_agent` wires Senser(periodic) + PromptBuilder(MEETING_SYNTHESIZER) + Router
- [ ] Reactor produces `[PRIVATE]` output at the configured interval
- [ ] Summary from Summarizer is included in the prompt
- [ ] End-to-end test with fake LLM passes
- [ ] `--check` passes

## Blocked by

- Blocked by [03-consumer-migration-and-config-files.md](./03-consumer-migration-and-config-files.md)
- Blocked by [04-senser-periodic-trigger-mode.md](./04-senser-periodic-trigger-mode.md)
- Blocked by [06-meeting-synthesizer-prompt-template.md](./06-meeting-synthesizer-prompt-template.md)

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 11
