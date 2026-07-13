## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Add the `MEETING_SYNTHESIZER` branch to `PromptBuilder.build()`. This prompt
takes the existing Summarizer's output and asks the LLM to format it as
human-readable meeting notes for the operator.

## Step-by-step implementation plan

1. **Add the MEETING_SYNTHESIZER branch in `PromptBuilder.build()`.**
   When `commentator_style == MEETING_SYNTHESIZER`, build a prompt with:
   - **Stable prefix (cacheable):** rules for the synthesizer role — you are
     a meeting note-taker, produce structured notes in the configured language,
     focus on: topics discussed, who said what, decisions made, action items.
     Include the soul (identity) and facts for interlocutor context.
   - **Dynamic section:** the current summary from the Summarizer + recent
     perceptions (last N from the store, using the same fencing/sanitization
     as OPERATOR mode).
   - **Situation:** the `synthesis_tick` trigger — "produce an updated summary
     of the meeting so far."
   *Verify:* the prompt contains the expected sections.
   *Pitfall:* keep the stable prefix byte-identical across builds (no dynamic
   data in it) to preserve prompt caching. The summary and recent perceptions
   go in the dynamic section only.

2. **Use the configured language.**
   The prompt instructions should be in `self._language` (from
   `CommentatorConfig.language`). The synthesizer asks the LLM to produce
   notes in that language.
   *Verify:* changing language to "en" changes the prompt instructions.

3. **Write tests.**
   - MEETING_SYNTHESIZER prompt contains synthesizer rules section.
   - Summary is injected in the dynamic section.
   - Recent perceptions are fenced and sanitized.
   - Stable prefix is byte-identical across two builds with same config.
   - Language setting affects prompt text.
   Prior art: `test_prompt_builder.py`, OPERATOR and ORIGINAL_CHAT tests.

## Acceptance criteria

- [ ] `PromptBuilder.build()` produces a valid prompt for `MEETING_SYNTHESIZER`
- [ ] Prompt contains synthesizer role rules, summary, and recent perceptions
- [ ] Stable prefix is cacheable (byte-identical across builds)
- [ ] Language is configurable
- [ ] Anti-injection fencing applied to perception data

## Blocked by

- Blocked by [01-enum-values-and-profile-config-types.md](./01-enum-values-and-profile-config-types.md) (needs the enum value)

## User stories addressed

- User story 1
- User story 2
