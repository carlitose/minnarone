---
ticket_schema: 1
ticket_id: "06"
execution_mode: HITL
blocked_by:
  - "04"
  - "05"
---

# Run the shadow rehearsal and one live Twitch canary

## Parent Spec

[twitch-consented-discovery.md](../../specs/twitch-consented-discovery.md)

## What to Build

Validate the completed behavior in a bounded shadow rehearsal and, only if all
gates pass, one attended live canary on the explicitly authorized channel.
Audit the public consequence against the approved interaction contract.

Cover the feature spec's Target Behavior, External Contracts and Safety,
Failure Modes, Verification Strategy, and Rollout.

## Acceptance Criteria

- [ ] Authorization is current, the dedicated account and token identities
      validate, the target is locally allow-listed, and `--check` passes.
- [ ] A representative shadow run confirms acceptable content, timing,
      qualifying-interaction classification, link cap, budgets, and zero
      unrelated promotion.
- [ ] The live-capable session starts in shadow and is promoted only by the
      attended operator through the TUI.
- [ ] The canary stays inside the duration and message limits approved in
      ticket 02.
- [ ] At least one qualifying interaction is observed or explicitly invited by
      the authorized broadcaster; no fake viewer interaction or vote/link
      solicitation is manufactured.
- [ ] Any disclosure/link response is truthful, contextual, within cap, and
      visible in chat; unrelated replies contain no repository promotion.
- [ ] The kill-switch is exercised and immediately returns the session to
      shadow with no queued-message burst.
- [ ] Run events and public chat agree on sent/unsent outcomes, with zero
      self-trigger loops, over-budget sends, or sends outside the channel.
- [ ] The committed audit is aggregate and secret-free; raw chat, credentials,
      private consent, and unnecessary personal data remain uncommitted.
- [ ] Any failed safety or promotion criterion ends the canary before diagnosis.

## Frontier

Dependency-blocked on the validated behavior candidate in ticket 04 and explicit
authorization/local readiness in ticket 05. This is the only ticket in the
initial workstream authorized to create a public Twitch message.

## Step-by-Step Implementation Plan

1. Reconfirm authorization, identities, local allow-list, budgets, artifact
   handling, stop conditions, and operator availability.
2. Run the complete session in shadow for the approved rehearsal window and
   review every would-be disclosure/link decision.
3. If and only if every gate passes, arm live, start shadowed, observe context,
   and manually promote through the TUI.
4. Keep the kill-switch at hand, stop on the first contract violation, and
   exercise the switch deliberately before completion.
5. Compare public chat with run events, capture aggregate metrics and operator
   observations, delete/retain artifacts according to the approved boundary,
   and write a secret-free audit.

## Testing Plan

Before live, run all ticket-04 automated checks and the existing public-send
targeted suites. During shadow/live, use the operator checklist and record
timestamps and decision reasons. Afterward, reconcile actual chat against
events and rerun secret scanning on the candidate audit.

## Out of Scope

- A second channel, repeated sessions, unattended operation, or automatic
  expansion.
- Increasing rate/link caps in response to weak engagement.
- Publishing raw chat logs, prompts, tokens, or private authorization evidence.
