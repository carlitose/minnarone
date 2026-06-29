## Parent PRD

[local-twitch-perception-runtime.md](../../prds/local-twitch-perception-runtime.md)

## What to build

Add an operator-facing commentator mode that uses the existing reaction loop but
frames output as private Italian commentary in console/TUI. The mode should not
send public Twitch messages and should not delete the existing public-chat bot
persona.

This slice can start after the chat-only runtime path exists. It does not need
to wait for ASR or VLM because the prompt/output stance can be tested with fake
perceptions.

## Step-by-step implementation plan

1. Define the commentator stance.
   - What to change: add configuration for an operator-facing mode where
     Minnarone comments to the local user about what is happening.
   - Why now: output intent is distinct from public chat participation.
   - Affects: config, prompt stance, examples.
   - Verify: default behavior for existing configs is unchanged.
   - Pitfalls: do not hardcode this mode as the only personality.

2. Adjust prompt instructions for private commentary.
   - What to change: make the prompt tell the LLM to produce concise Italian
     comments for the operator, using chat/audio/video perceptions as context.
   - Why now: the same perceptions need a different output style than Twitch
     chat posts.
   - Affects: prompt builder inputs or memory/prompt configuration.
   - Verify: with fake perceptions, the fake or real LLM receives the correct
     stance.
   - Pitfalls: keep stable prompt sections cache-friendly where possible.

3. Keep console/TUI as the only output.
   - What to change: ensure commentator mode routes through console/TUI and has
     no Twitch send path.
   - Why now: public output is out of scope.
   - Affects: output routing.
   - Verify: no Twitch write credentials or send scopes are required.
   - Pitfalls: do not conflate `public` output enum with public Twitch sending
     in this mode.

4. Tune triggers for commentary.
   - What to change: decide whether idle/proactive triggers should be enabled
     more readily for local commentary than for public chat.
   - Why now: a commentator should say useful things even when not mentioned.
   - Affects: Senser configuration and examples.
   - Verify: fake time/perception tests can produce an idle comment without
     needing public chat interaction.
   - Pitfalls: avoid over-commenting; defaults should stay conservative.

5. Add tests with fake perceptions.
   - What to change: drive chat/audio/video fixture perceptions into the agent
     and assert console/TUI output receives a commentary-style response.
   - Why now: this mode can be validated before real local models land.
   - Affects: prompt/reaction integration tests.
   - Verify: no public Twitch output occurs.
   - Pitfalls: do not assert exact LLM text unless using a fake LLM.

6. Add an example config.
   - What to change: provide a Twitch commentator config that is clearly
     console/TUI-only.
   - Why now: this is the main operator-facing product for the PRD.
   - Affects: examples and docs.
   - Verify: the example names required environment variables and model settings
     without including secrets.
   - Pitfalls: do not imply public Twitch messages are enabled.

## Acceptance criteria

- [x] A commentator mode or stance exists for operator-facing Italian comments.
- [x] Existing public-chat persona behavior remains available.
- [x] Commentator output routes only to console/TUI.
- [x] No Twitch send scopes or public chat write path are required.
- [x] Trigger/cadence behavior is configurable for local commentary.
- [x] Tests use fake perceptions and fake LLM output.
- [x] Example config clearly describes console/TUI-only behavior.

## Blocked by

- Blocked by [01-twitch-runtime-chat-only-console-path.md](./01-twitch-runtime-chat-only-console-path.md)

## User stories addressed

- User story 17
- User story 18
- User story 34
