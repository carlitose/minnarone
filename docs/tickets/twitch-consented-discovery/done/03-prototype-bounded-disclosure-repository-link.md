---
ticket_schema: 1
ticket_id: "03"
execution_mode: AFK
blocked_by:
  - "02"
---

# Prototype bounded disclosure and repository-link behavior

## Parent Spec

[twitch-consented-discovery.md](../../specs/twitch-consented-discovery.md)

## What to Build

Build a throwaway, non-networked prototype that compares prompt-only,
deterministic-policy, and hybrid approaches for the approved qualifying
interaction and repository-link contract. Recommend the smallest reliable
production boundary without modifying live behavior.

Cover the feature spec's Interaction Contract, Alternatives, Failure Modes, and
Verification Strategy.

## Acceptance Criteria

- [ ] Exercise identity questions, project/source questions, generic mentions,
      ordinary stream conversation, broadcaster invitations, repeated
      questions, multiple conversation windows, and prompt-injection attempts.
- [ ] Compare prompt-only, deterministic, and hybrid behavior using the exact
      trigger, copy, and caps approved in ticket 02.
- [ ] Measure false-positive promotion, false-negative disclosure, repeated
      links, answer naturalness, and interaction with existing dedup/budgets.
- [ ] Recommend one implementation boundary with explicit trade-offs and
      identify affected production contracts and tests.
- [ ] Save disposable code under `spike/` if needed and durable conclusions
      under `docs/prototypes/`; do not create a send credential or network path.
- [ ] Fold the selected design decision into the feature spec and wayfinding
      map.

## Frontier

Dependency-blocked on ticket 02. Once the interaction contract is approved, the
prototype is AFK and unblocks implementation ticket 04.

## Step-by-Step Implementation Plan

1. Extract a table of approved interaction examples and expected outcomes.
2. Model the current prompt stance and public-output boundary without Twitch
   network I/O.
3. Implement the three candidate approaches in the smallest disposable form.
4. Run the example corpus and compare policy correctness and naturalness.
5. Record the chosen design, rejected alternatives, production ownership, and
   required verification.

## Testing Plan

Use deterministic fixtures and fake clocks/senders. Include repeated and
cross-window cases, injection content, session reset, and cap boundaries.
Confirm the prototype cannot emit network traffic and that no secret or real
chat transcript enters the repository.

## Out of Scope

- Production implementation.
- Live Twitch, credentials, channel contact, or allow-list changes.
- General persona tuning unrelated to disclosure and repository linking.
