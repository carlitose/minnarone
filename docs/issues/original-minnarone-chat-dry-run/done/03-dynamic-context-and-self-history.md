## Parent PRD

[original-minnarone-chat-dry-run.md](../../../prds/original-minnarone-chat-dry-run.md)

## What to build

Make the original-chat prompt useful in real runs by feeding it the dynamic
context Minnarone needs: current short-term summary, recent chat, recent audio
transcriptions, recent video captions, and Minnarone's own recent messages.

This slice turns the prompt from a static style shell into a context-aware
original Minnarone prompt. It should keep all dynamic data out of the stable
prefix.

## Step-by-step implementation plan

1. Pass recent self messages into prompt building.
   - What to change: extend the Reactor-to-prompt call so the prompt builder can
     receive a bounded list of Minnarone's recent outputs.
   - Why this comes first: self-history is already owned by the Reactor and is
     needed by the prompt before formatting can be complete.
   - Affects: Reactor, prompt builder interface, prompt tests.
   - Verify: a fake previous Minnarone message appears in the original-chat
     dynamic prompt.
   - Pitfalls: do not expose the live mutable deque; pass a defensive list.

2. Render short-term memory in the original-chat prompt.
   - What to change: include the current summarizer text in the dynamic
     situation area.
   - Why this follows self-history: both are dynamic continuity inputs and must
     stay outside the cacheable prefix.
   - Affects: prompt builder dynamic section.
   - Verify: a fake summary appears after the stable prefix and before the final
     trigger instruction.
   - Pitfalls: empty summaries should not produce noisy or misleading text.

3. Split recent perceptions by source.
   - What to change: render recent chat messages, audio speech, and video
     captions in separate or clearly labeled dynamic sections matching the
     original prompt vocabulary.
   - Why this comes now: the LLM needs to reason differently about chat, voice,
     and screen context.
   - Affects: prompt formatting helpers and prompt tests.
   - Verify: fake chat/audio/video perceptions each appear in the prompt.
   - Pitfalls: do not accidentally filter out video captions because the Senser
     triggers only on chat/audio.

4. Avoid confusing trigger duplication.
   - What to change: decide how the trigger perception appears relative to
     recent context. It should be clear which event caused the reaction.
   - Why this comes after source rendering: source-specific sections can easily
     duplicate the trigger unless handled deliberately.
   - Affects: prompt formatting and trigger rendering.
   - Verify: tests show the trigger is visible in the final situation and is not
     repeated in a way that contradicts the instruction.
   - Pitfalls: exact dedup by value can remove legitimate repeated chat lines;
     prefer clarity over clever filtering.

5. Include the option to not answer.
   - What to change: ensure idle and weak-continuation prompts tell the model it
     may use `MSG: #end_conv` when there is nothing good to say.
   - Why this comes after dynamic context: the model can decide to skip only if
     it has enough context to judge relevance.
   - Affects: trigger-specific situation text.
   - Verify: tests for idle and continuation prompts include `#end_conv`.
   - Pitfalls: do not make `#end_conv` the normal answer for all triggers; it is
     a fallback.

6. Guard stable prefix invariance.
   - What to change: add tests proving summary, recent perceptions, and
     self-history do not change the stable prefix.
   - Why this comes last: all dynamic inputs are now present.
   - Affects: prompt builder tests.
   - Verify: prefix bytes remain identical with different dynamic inputs.
   - Pitfalls: a timestamp or recent message in the prefix breaks provider
     caching.

## Acceptance criteria

- [ ] The Reactor passes recent self messages to prompt building.
- [ ] Original-chat prompts include current summary when available.
- [ ] Original-chat prompts include recent chat, audio, and video context.
- [ ] Minnarone's own recent messages appear in a dynamic anti-repetition/continuity section.
- [ ] Trigger-specific text remains clear and last.
- [ ] Idle/weak-continuation situations allow `MSG: #end_conv`.
- [ ] Dynamic inputs do not change the stable prefix.

## Blocked by

- Blocked by [02-screenshot-faithful-prompt-contract.md](./02-screenshot-faithful-prompt-contract.md)

## User stories addressed

- User story 9
- User story 10
- User story 11
- User story 20
- User story 30
