## Parent PRD

[original-minnarone-chat-dry-run.md](../../prds/original-minnarone-chat-dry-run.md)

## What to build

Prove the full original-chat dry-run path with fake dependencies: fake
perceptions enter the store, the Senser/Reactor builds the original-chat prompt,
a fake LLM returns `RE`/`MSG`, the output is normalized and shown locally, and no
Twitch send path is used.

This slice is the automated acceptance layer for all AFK implementation slices.
It should avoid live Twitch, OpenRouter, local ASR, local VLM, and Textual
terminal dependencies.

## Step-by-step implementation plan

1. Create a fake original-chat runtime fixture.
   - What to change: assemble the app/runtime with original-chat style, fake
     memory, fake source adapter or direct store perceptions, fake LLM, and fake
     local output router.
   - Why this comes first: the test needs a deterministic end-to-end harness.
   - Affects: app wiring tests and Reactor integration tests.
   - Verify: the fixture starts without Twitch credentials or OpenRouter API
     keys.
   - Pitfalls: do not use real model providers or network calls.

2. Feed multimodal fake context.
   - What to change: provide chat, audio speech, and video caption perceptions
     that represent a small live stream situation.
   - Why this follows fixture setup: the prompt must prove it consumes the real
     perception contract.
   - Affects: perception store and prompt observation tests.
   - Verify: the generated prompt contains the fake context in the original-chat
     dynamic sections.
   - Pitfalls: do not assert exact model-generated prose; the LLM is fake.

3. Include self-history and summary.
   - What to change: seed a current summary and previous Minnarone message, then
     trigger a reaction.
   - Why this comes before output assertions: continuity is a core requirement
     of the prompt.
   - Affects: Reactor/prompt integration.
   - Verify: the prompt contains summary and self-history outside the stable
     prefix.
   - Pitfalls: do not make tests depend on private internal deques; use public
     behavior or stable test seams.

4. Return a fake `RE`/`MSG` response.
   - What to change: make the fake LLM return a deterministic original-chat
     response.
   - Why this comes after prompt assertions: the output side can now be
     verified independently of real LLM quality.
   - Affects: normalizer and output routing path.
   - Verify: local output contains canonical `RE` and `MSG` lines.
   - Pitfalls: ensure the fake response goes through the same path as a real
     provider response.

5. Assert local-only safety.
   - What to change: verify no Twitch `PRIVMSG` or public output route was used.
   - Why this is the key safety acceptance criterion.
   - Affects: output router tests and app wiring tests.
   - Verify: fake Twitch writer, if present, has no public sends.
   - Pitfalls: do not confuse console `[PRIVATE]` output with a Twitch send.

6. Exercise skipped output.
   - What to change: run a second fake LLM response with `MSG: #end_conv`.
   - Why this completes end-to-end coverage for the special case.
   - Affects: Reactor/Senser/dashboard behavior.
   - Verify: skipped display appears, and the relevant window closes.
   - Pitfalls: do not let HumanLikeness hide the skipped decision.

7. Keep prompt observation compatible.
   - What to change: ensure the prompt observer captures the original-chat
     prompt exactly as sent to the fake provider.
   - Why this comes last: prompt debugging is part of the operator acceptance
     path.
   - Affects: prompt observation and dashboard prompt state.
   - Verify: latest prompt observation includes original-chat sections and no
     secrets.
   - Pitfalls: do not reconstruct prompts from dashboard state; capture at the
     provider boundary.

## Acceptance criteria

- [ ] A fake end-to-end original-chat dry-run can execute without network or live Twitch.
- [ ] Fake chat/audio/video context appears in the prompt.
- [ ] Fake summary and self-history appear in the prompt outside the stable prefix.
- [ ] Fake `RE`/`MSG` LLM output appears locally in canonical form.
- [ ] No Twitch public send path is used.
- [ ] Fake `MSG: #end_conv` appears as a skipped decision and closes the window.
- [ ] Prompt observation captures the original-chat prompt.
- [ ] Existing operator-commentary end-to-end tests still pass.

## Blocked by

- Blocked by [02-screenshot-faithful-prompt-contract.md](./02-screenshot-faithful-prompt-contract.md)
- Blocked by [03-dynamic-context-and-self-history.md](./03-dynamic-context-and-self-history.md)
- Blocked by [04-seed-soul-facts-memory.md](./done/04-seed-soul-facts-memory.md)
- Blocked by [05-re-msg-normalizer-and-local-display.md](./done/05-re-msg-normalizer-and-local-display.md)
- Blocked by [06-visible-end-conv-skip.md](./done/06-visible-end-conv-skip.md)

## User stories addressed

- User story 1
- User story 2
- User story 22
- User story 28
- User story 33
- User story 36
