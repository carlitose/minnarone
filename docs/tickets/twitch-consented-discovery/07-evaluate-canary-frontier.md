---
ticket_schema: 1
ticket_id: "07"
execution_mode: AFK
blocked_by:
  - "06"
---

# Evaluate the canary and decide the Twitch discovery frontier

## Parent Spec

[twitch-consented-discovery.md](../../specs/twitch-consented-discovery.md)

## What to Build

Compare the canary audit with the ticket-02 outcome thresholds and decide
whether the next frontier is expand, revise, repeat only because evidence is
inconclusive, or stop. Preserve weak results instead of compensating with more
channels or louder promotion.

Cover the feature spec's Goal, Failure Modes, and Rollout, and maintain the
wayfinding map.

## Acceptance Criteria

- [ ] Separate reach signals (chat exposure, link visibility, GitHub traffic,
      stars) from real-user evidence (setup attempt, useful question/issue,
      follow-up consent, actionable feedback).
- [ ] Compare observed promotion/disclosure correctness, message naturalness,
      moderation response, operator burden, and safety events with every
      approved threshold.
- [ ] Do not infer installations from clones or interest from passive viewers.
- [ ] Classify the outcome as `expand`, `revise`, `inconclusive`, or `stop`,
      with evidence for the classification and explicit uncertainties.
- [ ] Fold durable decisions and resolved unknowns into the feature spec and
      wayfinding map; remove stale frontier items.
- [ ] If expansion is justified, propose only a bounded next cohort and create
      new canonical tickets through `to-tickets`; do not contact or run them.
- [ ] If results are weak, record them honestly and avoid automatic reposting,
      rate increases, or unconsented channels.

## Frontier

Dependency-blocked on the canary audit from ticket 06. The ticket is AFK because
it analyzes recorded evidence and does not perform external actions.

## Step-by-Step Implementation Plan

1. Normalize the approved thresholds and the secret-free canary evidence.
2. Trace the funnel from channel exposure to qualifying interaction, repository
   visit, setup attempt, and actionable user evidence without overclaiming.
3. Evaluate safety, social fit, operator effort, and product signal separately.
4. Select one disposition and document alternatives and uncertainty.
5. Update the map and, only when justified, emit the next bounded ticket set.

## Testing Plan

Recalculate all reported counts from the preserved aggregate evidence, verify
timestamps and source boundaries, and have the disposition checked against the
ticket-02 thresholds. Run link/Markdown checks and `git diff --check`.

## Out of Scope

- Contacting channels, sending messages, or running Minnarone.
- Treating stars or traffic alone as success.
- Expanding the campaign without a new explicit human authorization step.
