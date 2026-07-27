## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Add the `SUGGESTER` branch to `PromptBuilder.build()`. This prompt evaluates
whether the operator should ask a question or mention something, based on
what was just said and the facts about the interlocutor.

## Step-by-step implementation plan

1. **Add the SUGGESTER branch in `PromptBuilder.build()`.**
   When `commentator_style == SUGGESTER`, build a prompt with:
   - **Stable prefix (cacheable):** rules for the suggester role — you are a
     private assistant helping the operator during a meeting. Your job is to
     suggest questions to ask or things to remember/mention. You know the
     operator's history with each interlocutor via the facts. If there is
     nothing useful to suggest right now, respond with `#nothing` and nothing
     else. Include soul and facts.
   - **Dynamic section:** the perception that triggered (the speech utterance
     with speaker), current summary, recent perceptions (fenced/sanitized).
   - **Situation:** the `suggestion_eval` trigger — "someone just said X,
     evaluate if the operator should ask or mention something."
   *Verify:* the prompt contains the expected sections.
   *Pitfall:* the `#nothing` sentinel must be explicitly documented in the
   prompt rules so the LLM knows it's an option.

2. **Inject interlocutor facts.**
   The PromptBuilder already loads facts from `facts_dir`. For the SUGGESTER,
   the facts of the triggering interlocutor (speaker) should be prominently
   included — not just in the generic facts section but highlighted in the
   situation text: "this is what you know about {speaker}: {facts}".
   *Verify:* with a `facts/enkk.md` file and a speech perception from "enkk",
   the prompt includes Enkk's facts in the situation.
   *Pitfall:* if no facts exist for the speaker, the prompt should still work
   (just without the interlocutor-specific section).

3. **Use the configured language.**
   Same as MEETING_SYNTHESIZER: prompt instructions in `self._language`.
   *Verify:* language change affects prompt text.

4. **Write tests.**
   - SUGGESTER prompt contains suggester rules section.
   - `#nothing` sentinel is documented in the prompt.
   - Interlocutor facts are injected when available.
   - Missing facts for speaker → prompt still valid.
   - Recent perceptions fenced and sanitized.
   - Stable prefix is cacheable.
   Prior art: `test_prompt_builder.py`, facts injection tests.

## Acceptance criteria

- [ ] `PromptBuilder.build()` produces a valid prompt for `SUGGESTER`
- [ ] Prompt documents the `#nothing` sentinel
- [ ] Interlocutor-specific facts are injected when available
- [ ] Prompt degrades gracefully when no facts exist for the speaker
- [ ] Stable prefix is cacheable
- [ ] Anti-injection fencing applied

## Blocked by

- Blocked by [01-enum-values-and-profile-config-types.md](./01-enum-values-and-profile-config-types.md) (needs the enum value)

## User stories addressed

- User story 4
- User story 5
