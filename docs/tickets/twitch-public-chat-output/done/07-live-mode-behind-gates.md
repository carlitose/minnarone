## Parent PRD

[twitch-public-chat-output.md](../../prds/twitch-public-chat-output.md)

## What to build

Live sending end-to-end, behind every gate: the router composes the
`TwitchChatSender` so a `send` decision from the policy delivers a real
`PRIVMSG`, mirrored locally with a sent marker and recorded as a run event.
Sessions configured `live` arm the capability but start in shadow (promotion
comes in slice 08 via TUI; this slice exposes the policy transition and tests
it directly). Sender failures feed the policy's failure accounting
(auto-degrade to shadow at threshold), are recorded with reasons, and never
crash the agent — the turn is skipped, never queued for later.

Bookkeeping semantics per the PRD: a live send updates internal state like a
shadow one; a sender failure after a `send` decision consumes budget, records
`failed`, and updates state as if sent (conservative).

## Step-by-step implementation plan

1. Compose the sender into the router.
   - What: the router gains an optional sender; on a `send` decision it
     awaits `sender.send()`, then mirrors locally (sent marker) and records
     the event. Without a sender (shadow-only config) behavior is identical
     to slice 03.
   - Why now: policy, shadow path, and sender all exist and are tested.
   - Affects: router module, app assembly (construct the sender only when
     mode is `live`).
   - Verify: router unit tests with fake policy + fake sender for
     send/shadow/drop/failure paths.
   - Pitfall: never construct the sender (or read the write token) unless
     config mode is `live` — `off`/`shadow` must stay physically unable to
     send.

2. Map sender failures to policy and events.
   - What: typed sender errors → `policy.record_failure()` + a `failed` run
     event with the error category; success → `record_success()`. At the
     failure threshold the policy auto-engages the kill-switch; the router
     records the auto-degrade transition as its own event.
   - Why now: closes the auto-degrade loop designed in slice 02.
   - Affects: router module.
   - Verify: app-level test — N consecutive fake-sender failures flip
     subsequent decisions to shadow with the kill-switch reason.
   - Pitfall: a failed send skips the message (EC03) — no retry of the same
     text, no queue-and-burst.

3. Arm-but-shadowed session start.
   - What: app assembly constructs the policy un-promoted even when config
     says `live`; the promotion transition exists on the policy (slice 02)
     and is exercised here by tests; the TUI keybinding lands in slice 08.
   - Why now: the cold-start safety property must hold before any keybinding
     exists.
   - Affects: app assembly.
   - Verify: app-level test — live config + immediate trigger produces a
     shadow event, not a send.
   - Pitfall: nothing in the runtime may auto-promote; only the explicit
     transition does.

4. Runtime wiring completeness.
   - What: sender lifecycle (start/stop) joins the agent's task group with
     clean shutdown; send health feeds the snapshot (slice 04 surface).
   - Why now: the agent must stop cleanly with a live sender attached.
   - Affects: app assembly, shutdown path.
   - Verify: app-level start/stop test with a fake sender; no leaked tasks.
   - Pitfall: sender shutdown failures are reported like other adapter
     shutdown errors, not swallowed.

## Acceptance criteria

- [ ] With live config, promoted policy, and a fake sender: messages are sent, mirrored with a sent marker, and recorded.
- [ ] Live sessions start shadowed; nothing auto-promotes.
- [ ] Sender failures record `failed`, feed auto-degrade, and skip the turn; at threshold, decisions flip to shadow.
- [ ] `off`/`shadow` configs never construct the sender nor read the write token.
- [ ] Agent starts and stops cleanly with the sender in the task group.
- [ ] All tests use fake senders; no network.

## Blocked by

- Blocked by [02-public-send-policy-module.md](./02-public-send-policy-module.md)
- Blocked by [03-shadow-router-tracer-bullet.md](./03-shadow-router-tracer-bullet.md)
- Blocked by [05-twitch-chat-sender.md](./05-twitch-chat-sender.md)
- Blocked by [06-senser-self-echo-filter.md](./06-senser-self-echo-filter.md)

## User stories addressed

- User story 5
- User story 6
- User story 10
- User story 14
- User story 15
- User story 16
- User story 18
- User story 21
