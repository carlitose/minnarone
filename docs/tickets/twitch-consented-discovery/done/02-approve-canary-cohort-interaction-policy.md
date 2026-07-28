---
ticket_schema: 1
ticket_id: "02"
execution_mode: HITL
blocked_by:
  - "01"
---

# Approve the canary cohort and interaction policy

## Parent Spec

[twitch-consented-discovery.md](../../specs/twitch-consented-discovery.md)

## What to Build

Turn the channel research into an author-approved pilot contract. Select one
primary canary channel and backups, then decide the exact qualifying
interaction, disclosure wording, repository-link cap, operating window, stop
conditions, and evidence threshold.

Cover the feature spec's Assumption Pending Human Confirmation, Interaction
Contract, Decisions, and Goal.

## Acceptance Criteria

- [ ] The author selects one primary candidate and at least one ordered backup,
      or explicitly stops the workstream if none is suitable.
- [ ] The qualifying interaction is unambiguous for identity questions,
      project questions, generic mentions, ordinary conversation, and an
      invitation from the broadcaster or moderator.
- [ ] Exact English disclosure/link copy is approved, including whether the
      response must answer another question before introducing Minnarone.
- [ ] Per-session and per-conversation disclosure/link caps are numeric and
      explicit.
- [ ] Canary duration, allowed proactive-message rate, attended window, and
      kill/stop conditions are explicit.
- [ ] Success, revise, inconclusive, and stop outcomes are distinguishable from
      reach-only metrics.
- [ ] Decisions are folded into the feature spec and wayfinding map without
      contacting a channel or enabling live.

## Frontier

Dependency-blocked on ticket 01, then requires the author's decisions. It
unblocks the behavior prototype and the authorization workflow.

## Step-by-Step Implementation Plan

1. Present the shortlist with the same evidence rubric used by ticket 01.
2. Ask only the decisions that materially alter public behavior or candidate
   selection.
3. Test the proposed trigger and copy against concrete chat examples, including
   ambiguous mentions and hostile attempts to force promotion.
4. Record the approved contract, numeric caps, operating window, and outcome
   thresholds in the parent spec and map.
5. Confirm that no selected channel has been contacted and no live config has
   been armed.

## Testing Plan

Run a tabletop review over representative interactions and verify that two
independent readers classify every example the same way. Check that all
required human decisions are written as decisions rather than assumptions.

## Out of Scope

- Contacting candidates or representing that they have agreed.
- Implementing code or changing prompts.
- Creating credentials, editing a live allow-list, or running Twitch.
