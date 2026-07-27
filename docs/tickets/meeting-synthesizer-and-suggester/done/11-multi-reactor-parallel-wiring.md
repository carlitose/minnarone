## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Make `Agent.run()` spawn N Reactor loops concurrently — one per active profile
in `commentator.profiles`. All Reactors share the PerceptionStore, Summarizer,
and LLMProvider, but each has its own Senser, PromptBuilder, and OutputRouter.

This slice transforms the single-Reactor wiring (slices 09/10) into
multi-Reactor wiring, enabling configs like
`operator + meeting_synthesizer + suggester` running in parallel.

## Step-by-step implementation plan

1. **Refactor `build_agent` to produce multiple Reactors.**
   Instead of building a single Reactor, iterate over
   `config.commentator.active_styles()` and build one Reactor per style.
   Each Reactor gets:
   - Its own Senser (configured with the appropriate `trigger_mode`)
   - Its own PromptBuilder (configured with the `CommentatorStyle`)
   - Its own OutputRouter (for now, all use the same ConsoleOutputRouter —
     per-profile routing comes in slice 12)
   - Shared: store, summarizer.current_summary lambda, LLMProvider
   Store the Reactors in a list on the Agent.
   *Verify:* `build_agent` with 3 profiles produces an Agent with 3 Reactors.
   *Pitfall:* when no profiles are active (e.g. public mode without
   commentator), the Agent should still work with zero Reactors (only
   perception pump + summarizer run).

2. **Update `Agent.run()` to launch N reactor loops.**
   Currently `Agent.run()` gathers three tasks: reactor, summarizer,
   perception pump. Change to: N reactor tasks + 1 summarizer + 1 perception
   pump. All are concurrent `asyncio.Task`s gathered together.
   *Verify:* all tasks start and run concurrently.
   *Pitfall:* if one Reactor task fails, the others should still be cancelled
   gracefully (same error handling as the existing single-Reactor case).

3. **Verify CadenceLoop intervals per Reactor.**
   Each Reactor's CadenceLoop should tick at the appropriate interval:
   - OPERATOR / ORIGINAL_CHAT: 0.5s (existing default)
   - MEETING_SYNTHESIZER: 0.5s (the periodic Senser handles its own timer
     internally; the CadenceLoop just needs to tick often enough)
   - SUGGESTER: 0.5s (must react quickly to new perceptions)
   *Verify:* all Reactors tick at reasonable cadence.
   *Pitfall:* don't confuse the CadenceLoop interval (how often `tick()` is
   called) with the synthesizer's `interval_s` (how often the Senser emits
   `synthesis_tick`).

4. **End-to-end test with multiple profiles.**
   - Config with `operator` + `meeting_synthesizer` + `suggester`.
   - Fake perceptions: a mention of the agent name (triggers OPERATOR) +
     a speech utterance (triggers SUGGESTER) + time passes (triggers
     MEETING_SYNTHESIZER).
   - Three FakeLLMProviders or a single provider that responds differently
     based on prompt content.
   - Verify all three Reactors produce output.
   *Verify:* three distinct outputs appear, each from its respective Reactor.
   *Pitfall:* the shared LLMProvider receives concurrent calls — ensure
   the FakeLLMProvider is thread/async-safe (or accept sequential execution
   since the real OpenRouter client serializes internally).

5. **Test: zero-profile config still works.**
   A public-mode config with no commentator profiles should produce an Agent
   that runs perception pump + summarizer only (no Reactors).
   *Verify:* `Agent.run()` completes without errors.

## Acceptance criteria

- [ ] `build_agent` creates one Reactor per active profile
- [ ] `Agent.run()` launches N reactor loops + summarizer + perception pump concurrently
- [ ] All Reactors share store, summarizer, and LLM
- [ ] Each Reactor has its own Senser, PromptBuilder, and Router
- [ ] Multi-profile config produces output from all active profiles
- [ ] Zero-profile config works (no Reactors, only pump + summarizer)
- [ ] Graceful shutdown: cancelling one task cancels all

## Blocked by

- Blocked by [09-meeting-synthesizer-single-reactor-e2e.md](./09-meeting-synthesizer-single-reactor-e2e.md)
- Blocked by [10-suggester-single-reactor-e2e.md](./10-suggester-single-reactor-e2e.md)

## User stories addressed

- User story 7
- User story 10
- User story 13
