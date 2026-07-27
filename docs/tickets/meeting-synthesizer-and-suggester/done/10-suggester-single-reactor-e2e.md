## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Wire a complete end-to-end path for the SUGGESTER style: a config with a single
`suggester` profile produces a Reactor with on_perception Senser + SUGGESTER
prompt + `#nothing` handling + console output. This is the tracer bullet that
proves the suggester works in isolation.

## Step-by-step implementation plan

1. **Wire the SUGGESTER profile in `build_agent`.**
   When `config.commentator.profiles` contains `SUGGESTER`, build:
   - A Senser with `trigger_mode="on_perception"`.
   - A PromptBuilder with `commentator_style=SUGGESTER`.
   - A ConsoleOutputRouter (or TuiPrivateOutputRouter if TUI is active).
   - A Reactor connecting these + the shared LLM, store, summary provider,
     and `#nothing` handling (from slice 08).
   Single-profile only (multi-Reactor comes in slice 11).
   *Verify:* `build_agent` with a SUGGESTER config produces an Agent.
   *Pitfall:* the Reactor loop cadence should be fast (~0.5s) so the
   suggester reacts quickly to new speech perceptions.

2. **Verify facts injection end-to-end.**
   The PromptBuilder for SUGGESTER injects interlocutor facts. Verify this
   works through the full wiring: facts loaded from `facts_dir`, speaker
   identified from the perception, facts included in the prompt sent to the
   LLM.
   *Verify:* with a `facts/alice.md` file and a speech perception from
   "alice", the LLM receives a prompt mentioning Alice's facts.

3. **End-to-end test: suggestion produced.**
   - Config with `suggester` profile.
   - Fake perceptions: a speech utterance from a known interlocutor.
   - FakeLLMProvider returns a suggestion ("ask about the budget").
   - Verify console output contains the suggestion as `[PRIVATE]`.
   *Verify:* output appears after the speech perception.

4. **End-to-end test: #nothing silence.**
   - Same setup, but FakeLLMProvider returns `#nothing`.
   - Verify NO console output is produced.
   *Verify:* output stream is empty.

5. **End-to-end test: non-speech ignored.**
   - Fake perceptions: a chat message (source=CHAT) and a video caption
     (source=VIDEO).
   - Verify neither triggers a suggestion evaluation.
   *Verify:* no LLM calls made.

6. **Verify `--check` works.**
   *Verify:* `python -m minnarone <config> --check` with `suggester` profile
   exits 0.

## Acceptance criteria

- [ ] Config with a single `suggester` profile is valid
- [ ] `build_agent` wires Senser(on_perception) + PromptBuilder(SUGGESTER) + Router
- [ ] Suggestion produced on speech perception → `[PRIVATE]` output
- [ ] `#nothing` response → no output
- [ ] Non-speech perceptions do not trigger evaluation
- [ ] Interlocutor facts injected in the prompt
- [ ] `--check` passes

## Blocked by

- Blocked by [03-consumer-migration-and-config-files.md](./03-consumer-migration-and-config-files.md)
- Blocked by [05-senser-on-perception-trigger-mode.md](./05-senser-on-perception-trigger-mode.md)
- Blocked by [07-suggester-prompt-template.md](./07-suggester-prompt-template.md)
- Blocked by [08-nothing-sentinel-in-reactor.md](./08-nothing-sentinel-in-reactor.md)

## User stories addressed

- User story 4
- User story 5
- User story 6
- User story 11
