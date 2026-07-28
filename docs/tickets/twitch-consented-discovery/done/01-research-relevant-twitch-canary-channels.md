---
ticket_schema: 1
ticket_id: "01"
execution_mode: AFK
blocked_by: []
---

# Research relevant Twitch canary channels

## Parent Spec

[twitch-consented-discovery.md](../../specs/twitch-consented-discovery.md)

## What to Build

Produce a current, public-evidence shortlist of Twitch channels where an invited
multimodal AI participant is relevant to the stream and where the operator can
request broadcaster permission. This is research only: do not contact anyone,
join chat as the bot, or add a live allow-list entry.

Cover the feature spec's Channel Selection Contract and the wayfinder's
candidate-evidence frontier.

## Acceptance Criteria

- [ ] Define a rubric covering relevance, language, category, audience band,
      live window, operator availability, public contact path, and known
      bot/link rules.
- [ ] Record 10-15 current candidates using public information, with evidence
      URLs and access dates for every material claim.
- [ ] For each candidate, distinguish confirmed rules from `unknown`; do not
      infer permission from an open chat or the presence of other bots.
- [ ] Recommend 3-5 candidates for human review and explain each inclusion and
      exclusion against the same rubric.
- [ ] Exclude Enkk and avoid collecting private contact information, chat logs,
      credentials, or personal data not needed for the decision.
- [ ] Save the durable research under `docs/research/` and link it from the
      wayfinding map.

## Frontier

Ready. The output enables the HITL cohort and policy decision in ticket 02.

## Step-by-Step Implementation Plan

1. Define the evidence fields and rejection criteria from the parent spec.
2. Discover candidate categories and channels from current public Twitch
   surfaces and first-party channel information.
3. Verify public schedule, channel relevance, rules, and contact/permission
   route; date every observation.
4. Score candidates consistently, record unknowns, and select a review set
   without contacting them.
5. Write the research artifact and update only the candidate-evidence state in
   the wayfinding map.

## Testing Plan

Manually open every cited source, check that candidate names and URLs resolve,
verify that no private/session URL or credential is recorded, and compare the
shortlist against every rubric field. Run Markdown/link checks available in the
repository and `git diff --check`.

## Out of Scope

- Contacting broadcasters, moderators, or viewers.
- Running Minnarone, joining chat, or sending any message.
- Selecting the final canary channel on the author's behalf.
- Ranking channels by follower count alone.
