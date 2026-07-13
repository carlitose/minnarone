## Parent PRD

[twitch-public-chat-output.md](../../prds/twitch-public-chat-output.md)

## What to build

Self-echo protection (PRD "Self-echo handling" decision): once Minnarone
sends publicly, the read connection sees his own messages come back as
regular chat perceptions from the bot account. Those perceptions must stay in
the store untouched (log fidelity, replay), but the Senser must never treat a
chat perception whose speaker equals the bot's send-account username as a
mention or trigger — even under fuzzy name matching — and the prompt builder
must surface them through the existing own-recent-messages anti-repetition
section, never as third-party recent chat.

Without this slice, Minnarone's first live message could open a conversation
window with himself and loop.

## Step-by-step implementation plan

1. Thread the bot identity to the Senser and prompt builder.
   - What: the send-account username (lowercased) becomes an optional
     construction parameter of the Senser and of the recent-chat selection
     for the prompt; absent (non-send configs) means no filtering.
   - Why now: identity must be explicit config/state, not guessed from env
     at tick time.
   - Affects: Senser construction, app assembly, prompt-recent selection.
   - Verify: construction unit tests; behavior unchanged when identity is
     absent.
   - Pitfall: key on the SEND account username, not the read login — they
     can differ (grill decision).

2. Exclude self perceptions from trigger detection.
   - What: chat perceptions with speaker == bot identity are skipped by
     mention detection (including fuzzy matching) and never open or refresh
     conversation windows as an interlocutor.
   - Why now: this is the loop-prevention core.
   - Affects: Senser tick logic.
   - Verify: unit tests — a stored self message containing the bot's own
     name produces zero triggers; a third-party mention still does.
   - Pitfall: self messages may still legitimately close/continue windows as
     "the agent replied" signals only via the existing reactor-side state,
     not via chat perception.

3. Route self perceptions into the own-messages prompt section.
   - What: recent-chat selection for the prompt excludes self messages from
     the third-party chat window; they are represented by the existing
     "own recent messages" anti-repetition section (already fed by the
     Reactor's history).
   - Why now: prevents the LLM from replying to "another user" that is
     actually itself.
   - Affects: prompt-recent selection.
   - Verify: prompt-builder test — a self chat perception does not appear in
     the recent-chat block.
   - Pitfall: do not double-inject (once from store, once from reactor
     history); the reactor history is the single source for own messages.

## Acceptance criteria

- [ ] Self chat perceptions remain in `perceptions.jsonl` unmodified.
- [ ] Self perceptions never produce mention/window triggers, including fuzzy matches on the bot's own name.
- [ ] Self perceptions never appear as third-party chat in the prompt.
- [ ] Behavior is unchanged for configs without a send identity.
- [ ] Replay of a run containing self messages renders them in the chat log.

## Blocked by

- Blocked by [01-send-config-type-and-check.md](./01-send-config-type-and-check.md)

## User stories addressed

- User story 26
- User story 31
