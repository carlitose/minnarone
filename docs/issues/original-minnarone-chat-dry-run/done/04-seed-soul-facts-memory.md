## Parent PRD

[original-minnarone-chat-dry-run.md](../../../prds/original-minnarone-chat-dry-run.md)

## What to build

Add a usable local memory seed for the original-chat dry-run. The first local
run should not have empty `soul` and `facts`; Minnarone should have a basic
persona and the channel should have starting facts copied or adapted from the
readable screenshot material.

This slice is intentionally manual-memory only. It should not implement
auto-memory, fact extraction from live streams, or cross-session updates.

## Step-by-step implementation plan

1. Decide where local seed memory lives.
   - What to change: place seed `soul` and `facts` where the local config can
     resolve them immediately, or update the local config to point to the chosen
     location.
   - Why this comes first: the prompt cannot use seed memory unless the runtime
     can load it.
   - Affects: local runtime workspace, example config, docs.
   - Verify: loading the local config produces non-empty memory blocks.
   - Pitfalls: do not commit secrets, personal tokens, or large runtime
     artifacts.

2. Create a minimal Minnarone `soul`.
   - What to change: write concise persona facts from the screenshots: name,
     handle, approximate age, style, simple/direct comments, taste notes, and
     tone boundaries.
   - Why this comes before channel facts: the agent identity is independent of
     any streamer.
   - Affects: memory loaded into the prompt's permanent section.
   - Verify: the prompt includes the `soul` text in permanent memory.
   - Pitfalls: keep this as seed content, not an overfit biography that makes
     the model inflexible.

3. Create starting channel facts.
   - What to change: add a facts entry for the current channel/streamer with
     stable facts visible in the screenshots, such as streamer identity,
     background, and durable interests.
   - Why this follows `soul`: facts are the second half of permanent memory and
     should be separately editable.
   - Affects: facts loading and prompt memory rendering.
   - Verify: facts are loaded with a recognizable entity header and included in
     the original-chat prompt.
   - Pitfalls: do not include ephemeral stream events as durable facts.

4. Document how to edit seed memory.
   - What to change: update operator-facing docs or examples explaining what
     `soul` and `facts` are, how they differ, and that they are manually
     authored for now.
   - Why this comes after files exist: docs should reference the actual local
     workflow.
   - Affects: README/operator docs/examples.
   - Verify: docs state that auto-memory is out of scope.
   - Pitfalls: do not imply facts are generated or verified automatically.

5. Add tests or checks for non-empty memory in local dry-run examples.
   - What to change: if the project has docs/config tests for examples, add a
     check that the local original-chat config points at loadable memory.
   - Why this comes last: the target files and docs now exist.
   - Affects: operator docs tests or config smoke tests.
   - Verify: missing memory still degrades gracefully in generic runtime tests.
   - Pitfalls: do not make the framework globally require these local files.

## Acceptance criteria

- [ ] Local original-chat dry-run has non-empty `soul` memory.
- [ ] Local original-chat dry-run has at least one non-empty facts entry.
- [ ] The prompt includes seed memory in the permanent memory section.
- [ ] Docs explain `soul` versus `facts`.
- [ ] Docs state that facts are manually authored for now.
- [ ] Generic runtime behavior still tolerates missing memory files.

## Blocked by

- Blocked by [01-opt-in-original-chat-style-skeleton.md](./01-opt-in-original-chat-style-skeleton.md)

## User stories addressed

- User story 12
- User story 13
- User story 35
