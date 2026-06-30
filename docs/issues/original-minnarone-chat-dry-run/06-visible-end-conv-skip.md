## Parent PRD

[original-minnarone-chat-dry-run.md](../../prds/original-minnarone-chat-dry-run.md)

## What to build

Make `MSG: #end_conv` visible and meaningful in original-chat dry-run mode. When
the LLM decides not to speak, the operator should see a skipped `RE`/`MSG`
decision locally, and the relevant conversation window should close when there
is an interlocutor.

This slice builds on the `RE`/`MSG` normalizer. It should not make `#end_conv`
look like a real chat message that would have been sent publicly.

## Step-by-step implementation plan

1. Detect `#end_conv` in normalized output.
   - What to change: ensure the normalizer marks responses where the normalized
     message is exactly the end-conversation sentinel.
   - Why this comes first: runtime behavior should depend on a structured flag,
     not repeated string parsing.
   - Affects: output normalizer tests.
   - Verify: `MSG: #end_conv` sets an end-conversation flag.
   - Pitfalls: do not treat words containing the sentinel as a command.

2. Define skipped display text.
   - What to change: decide and implement the local display for skipped
     decisions, preserving both `RE` and `MSG` and adding a clear skip marker.
   - Why this comes before Reactor wiring: tests need a canonical expected
     output.
   - Affects: normalizer display contract and dashboard tests.
   - Verify: skipped display is human-readable and not confused with a sent
     chat message.
   - Pitfalls: do not silently hide the decision; visibility is required.

3. Close the relevant conversation window.
   - What to change: when a normalized original-chat response is an end-conv
     decision and the trigger has an interlocutor, call the existing window
     close mechanism.
   - Why this comes after detection: the Reactor can now use the structured
     flag.
   - Affects: Reactor and Senser coordination.
   - Verify: a fake conversation window closes after `MSG: #end_conv`.
   - Pitfalls: idle triggers may not have an interlocutor; handle that without
     error.

4. Route the skipped decision locally.
   - What to change: send the skipped display text to the local output stream or
     console in original-chat dry-run.
   - Why this comes after window closure: state and display should agree.
   - Affects: output routing and dashboard state.
   - Verify: fake router captures skipped display text.
   - Pitfalls: existing HumanLikeness may drop empty/end-conv messages; ensure
     original-chat skip visibility is not lost.

5. Avoid treating skipped decisions as normal self messages.
   - What to change: decide whether skipped decisions should enter the recent
     self-message history used for prompt continuity and dedup.
   - Why this comes near the end: history behavior affects future prompts.
   - Affects: Reactor self-history and prompt context.
   - Verify: tests document the chosen behavior. A conservative choice is to
     record skipped decisions for observability but not as real chat messages.
   - Pitfalls: if skipped decisions are treated like normal messages, the LLM
     may over-focus on them later.

6. Add regression tests around normal messages.
   - What to change: ensure non-`#end_conv` original-chat messages still route
     normally and can trigger typing delay/dedup behavior as before.
   - Why this comes last: special-case handling must not break ordinary output.
   - Affects: Reactor tests.
   - Verify: normal `MSG` output still appears locally and does not close
     windows.
   - Pitfalls: do not apply skip behavior to operator-commentary mode.

## Acceptance criteria

- [ ] `MSG: #end_conv` is detected as an end-conversation decision.
- [ ] The local display preserves `RE` and `MSG` and marks the decision as skipped.
- [ ] The relevant conversation window closes when an interlocutor exists.
- [ ] Idle `#end_conv` decisions do not crash when there is no interlocutor.
- [ ] Skipped decisions are visible in dashboard/console output.
- [ ] Normal original-chat messages still route normally.
- [ ] Operator-commentary mode is unaffected.

## Blocked by

- Blocked by [05-re-msg-normalizer-and-local-display.md](./done/05-re-msg-normalizer-and-local-display.md)

## User stories addressed

- User story 5
- User story 6
- User story 20
- User story 31
