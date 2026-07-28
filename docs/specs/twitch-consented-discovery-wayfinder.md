# Consented Twitch discovery

## Type

Wayfinding spec

## Status

Active

## Destination

Run one bounded, attended Minnarone canary in a relevant Twitch channel whose
broadcaster explicitly authorized the bot. Minnarone participates naturally,
discloses that it is AI on a qualifying direct interaction, and mentions the
GitHub repository at most once per session without unsolicited promotion.

The canary produces enough evidence to decide whether to expand to a small
authorized cohort, revise the behavior, or stop the Twitch discovery path.

## Decisions So Far

- The author selected Twitch participation as the next discovery direction:
  choose relevant channels and run Minnarone live rather than publishing only
  static promotional content.
- The intended promotion is light and reactive. Minnarone may identify itself
  as AI and point to GitHub when people engage about its identity or project.
- Broadcaster permission is a hard gate before live. This follows the current
  [public bot safety research](../research/public-twitch-bot-safety.md) and
  [operator guide](../twitch-operator.md#allow-list-workflow).
- The runtime already provides the required safety floor: dedicated bot
  account, validated separate credentials, allow-list, conservative budgets,
  shadow-first startup, manual TUI promotion, attended-only operation, and an
  immediate kill-switch.
- `disclosure.announce_ai` is effective in the current prompt implementation
  and cannot be contradicted by an override. A deterministic promotion trigger
  and repository-link cap are not yet part of that contract.
- The detailed product boundary is recorded in
  [twitch-consented-discovery.md](twitch-consented-discovery.md).
- Ticket 01 produced the dated public-evidence report
  [Relevant Twitch channels for a consented Minnarone canary](../research/twitch-consented-discovery-channels.md):
  15 candidates were assessed with one rubric, five were recommended for
  review, and no channel was contacted or treated as implicitly consenting.
- On 2026-07-28, the author completed ticket 02's decision gate: the primary is
  CodeWithTheItalians, followed by MrDboy and Brookzerker; the canary language
  is English; and the trigger, exact copy, caps, attended window, and outcome
  classes are now recorded in the
  [feature spec](twitch-consented-discovery.md).
- Ticket 03's non-networked
  [prototype](../prototypes/twitch-consented-disclosure.md) rejected
  prompt-only enforcement and a fully canned deterministic response. It
  selected a hybrid boundary where deterministic policy owns eligibility,
  exact copy, caps, cadence, and reset while the model answers contextually.
- The existing repo-promotion follow-up ticket uses a legacy Markdown contract
  and failed canonical `ticket-parse`; this workstream therefore uses a new
  Ticket Envelope v1 folder rather than inferring its mode or blockers.

## Not Yet Specified

- The first broadcaster who grants explicit permission.
- The exact calendar window accepted by that broadcaster for the canary.

## Out of Scope

- Joining or sending in a third-party channel without broadcaster permission.
- Mass outreach, automated outreach, unsolicited repository links, repeated
  self-promotion, vote solicitation, or using Minnarone to advertise itself in
  unrelated replies.
- Contacting, tagging, or implying endorsement by Enkk.
- Removing or weakening shadow defaults, allow-lists, credential validation,
  budgets, artifact limits, anti-injection rules, or the kill-switch.
- Unattended live operation or simultaneous multi-channel sending.
- Paid advertising and a general Twitch growth campaign before the canary
  review.

## Frontier / Blocking Edges

- **Candidate evidence — resolved:** ticket 01 produced the dated
  [channel research](../research/twitch-consented-discovery-channels.md), with
  15 candidates, five recommendations, explicit unknown rules, and public
  permission-request routes. The report is evidence for selection, not
  authorization.
- **Human campaign boundary — resolved:** ticket 02 records the approved
  primary and backups, English copy, qualifying trigger, numeric caps,
  30-minute shadow and 45-minute live limits, and outcome classes in the
  [feature spec](twitch-consented-discovery.md).
- **Promotion design — resolved:** ticket 03 selected the
  [hybrid boundary](../prototypes/twitch-consented-disclosure.md) after a
  synthetic shadow-policy comparison.
- **Promotion implementation — ready AFK:** ticket 04 implements the
  default-off typed policy, exact-copy ownership, session/window caps,
  proactive cadence, and composition with the existing router safety gates.
- **Broadcaster authorization — ready HITL/external:** a public channel name in
  config is not permission. Ticket 05 prepares the request, then the author
  sends it and records sanitized authorization evidence.
- **Live evidence:** no canary may run until implementation, authorization, and
  shadow review are complete. Ticket 06 owns the only public consequence.
- **Expansion decision:** weak engagement must not trigger wider or louder
  promotion automatically. Ticket 07 judges the canary before new tickets are
  created.

## Ticket Plan

- **01 — research — AFK — completed/evidenced:** shortlisted 15 relevant
  Twitch channels and documented public fit, rules or `unknown`, live windows,
  and permission-request routes in the
  [research report](../research/twitch-consented-discovery-channels.md).
- **02 — grilling/decision — HITL — completed/evidenced:** the author approved
  CodeWithTheItalians with MrDboy and Brookzerker as ordered backups, English
  interaction, the qualifying trigger, exact copy, caps, attended duration,
  stop conditions, and outcome contract.
- **03 — prototype — AFK — completed/evidenced:** the non-networked comparison
  selected a hybrid policy boundary and recorded production contracts and
  limits in the [prototype report](../prototypes/twitch-consented-disclosure.md).
- **04 — task — AFK — ready:** implement and test the selected
  qualifying-interaction and repository-link contract without bypassing public
  send safety. Output: validated candidate.
- **05 — task — HITL — ready/external:** prepare the permission request, have
  the author obtain broadcaster permission, prepare the dedicated bot account,
  and create the sanitized allow-list handoff. Output: one authorized canary
  target; no credentials in Git.
- **06 — acceptance — HITL — blocked by 04 and 05:** run bounded shadow
  rehearsal followed by one attended live canary with the kill-switch at hand.
  Output: secret-free audit and observations.
- **07 — research/decision — AFK — blocked by 06:** compare canary evidence
  with the approved success/stop conditions and recommend expand, revise, or
  stop. Output: map update and any newly justified ticket plan.

## Next Review

Execute AFK ticket 04 against the selected hybrid boundary. Ticket 05 may
prepare the permission request separately, but the author must perform the
actual outreach; do not contact streamers, add live allow-list entries, or
start a public run while authorization is absent.
