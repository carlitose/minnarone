---
ticket_schema: 1
ticket_id: "05"
execution_mode: HITL
blocked_by:
  - "02"
---

# Obtain broadcaster permission and prepare the canary channel

## Parent Spec

[twitch-consented-discovery.md](../../specs/twitch-consented-discovery.md)

## What to Build

Obtain explicit broadcaster authorization for one approved canary channel and
prepare a secret-free local handoff for shadow rehearsal. Contact and consent
are human actions; the agent may prepare copy and check public facts but must
not send outreach without the author's direct action.

Cover the feature spec's Channel Selection Contract, External Contracts and
Safety, and revocation failure mode.

## Acceptance Criteria

- [ ] The author contacts only a ticket-02-approved candidate using an accurate,
      non-deceptive request that explains AI participation, shadow rehearsal,
      live behavior, repository linking, operator attendance, and the
      kill-switch.
- [ ] The broadcaster explicitly authorizes the dedicated bot account and the
      bounded canary; silence, an open chat, or another bot's presence does not
      count.
- [ ] The repository records only sanitized authorization status, evidence
      date, channel, approved scope, expiry/review point, and verifier; private
      messages remain outside Git.
- [ ] The dedicated account and separate read/write credentials are prepared
      outside Git and correspond to the configured bot identity.
- [ ] The channel enters only a local, uncommitted allow-list after permission,
      and the local config passes `--check`.
- [ ] Revocation and moderator stop instructions have an explicit immediate
      response: kill-switch/stop and allow-list removal.
- [ ] If the candidate declines or does not answer, move only to an approved
      backup after human confirmation; do not broaden outreach automatically.

## Frontier

Dependency-blocked on ticket 02 and then blocked on an external broadcaster
decision. It can proceed in parallel with tickets 03-04 but must complete
before ticket 06.

## Step-by-Step Implementation Plan

1. Prepare the permission request from the approved pilot contract.
2. Have the author send it through the candidate's public contact path.
3. Record the response privately and commit only sanitized authorization
   metadata.
4. Prepare the dedicated bot identity, local credentials, local config, and
   allow-list without exposing values.
5. Validate the local configuration and document the revocation/stop procedure.

## Testing Plan

Manually verify the consenting account's authority and approved scope. Run
secret scans and inspect the staged diff before any commit. Run `--check` with
environment values present but never print them. Confirm a config without the
channel in the allow-list fails closed for live.

## Out of Scope

- Treating moderator/viewer enthusiasm as broadcaster permission.
- Committing credentials, private messages, or raw consent screenshots.
- Starting shadow or live operation.
- Contacting Enkk or unapproved backup candidates.
