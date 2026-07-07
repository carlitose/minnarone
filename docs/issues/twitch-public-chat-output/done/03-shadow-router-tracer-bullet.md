## Parent PRD

[twitch-public-chat-output.md](../../prds/twitch-public-chat-output.md)

## What to build

The tracer bullet: `TwitchPublicOutputRouter` wired end-to-end in shadow-only
form. With the Twitch adapter, `mode: public`, and `twitch.send.mode: shadow`,
a generated message flows trigger → prompt → LLM → original-chat
normalization → `HumanLikeness` (typing delay, dedup, `#end_conv`) → policy →
local display with a `[SHADOW]` marker → run event with action and reason. No
sender exists yet: the router can only shadow or drop.

Two contract points from the PRD grill decisions land here:

- With the Twitch adapter and `mode: public`, the prompt uses the
  `original_chat` contract unconditionally (public persona IS the original).
- `twitch.send.mode: off` keeps today's behavior byte-identical (plain
  console router).

## Step-by-step implementation plan

1. Build the router with policy-only composition.
   - What: an `OutputRouter` implementation taking the policy, a local
     display sink (console/TUI), and the event recorder. On
     `route(message, PUBLIC)`: decide via policy; `shadow` → display with
     marker + event; `drop` → event only. `PRIVATE` routing is not this
     router's job.
   - Why now: the thin composition proves the whole pipeline without network
     risk.
   - Affects: new router module; run-event vocabulary gains send decisions
     (action + reason + channel).
   - Verify: unit tests with a fake policy and fake display: each action
     produces the right display and event.
   - Pitfall: record the event even when nothing is displayed (drop) — the
     audit trail is the point.

2. Wire router selection in the app.
   - What: extend the mode-based router selection: Twitch adapter +
     `mode: public` + send mode `shadow` → the new router; send mode `off` →
     existing console router, unchanged.
   - Why now: selection is config-driven (public/private is configuration,
     not a fork — PRD reuse decision).
   - Affects: app assembly.
   - Verify: app-level test in the style of the existing "runtime reacts
     without sending chat" tests: shadow produces shadow events and no
     network component is constructed.
   - Pitfall: do not touch the private/commentator paths.

3. Bind the public prompt to the original-chat contract.
   - What: with Twitch adapter + `mode: public`, the prompt builder uses the
     `original_chat` specs (`RE:`/`MSG:`, `#end_conv`) — the same contract
     already validated in the private dry-run.
   - Why now: shadow output must rehearse the real public persona or the
     rehearsal is meaningless.
   - Affects: app assembly / reactor construction (style selection).
   - Verify: app-level test asserting the public prompt contains the
     original-chat response-format section; `#end_conv` messages become skip
     decisions, not shadow messages.
   - Pitfall: `commentator.*` config keeps meaning private mode only; no new
     combinations.

4. Preserve internal-state bookkeeping semantics.
   - What: shadow outcomes update the Reactor's own-message history and the
     Senser's continuation state exactly as a sent message; drops update
     nothing (turn skipped).
   - Why now: the PRD's rehearsal-fidelity decision; later slices rely on it.
   - Affects: reactor routing outcome handling.
   - Verify: unit test — a shadow message appears in `recent_messages()` and
     dedup applies to the next candidate; a dropped message does not.
   - Pitfall: `HumanLikeness` drop (dedup) and policy drop are different
     events; keep their reasons distinct in the record.

## Acceptance criteria

- [ ] With send mode `shadow`, a full pipeline run displays `[SHADOW]` messages and records send events with action and reason.
- [ ] With send mode `off`, behavior is byte-identical to today (console router, no send events).
- [ ] Public mode on Twitch uses the original-chat prompt contract; `#end_conv` closes windows without emitting a shadow message.
- [ ] Shadow updates own-message history and window continuation; drop skips the turn.
- [ ] No network send component exists anywhere in this slice.

## Blocked by

- Blocked by [01-send-config-type-and-check.md](./01-send-config-type-and-check.md)
- Blocked by [02-public-send-policy-module.md](./02-public-send-policy-module.md)

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 17
- User story 21
- User story 24
