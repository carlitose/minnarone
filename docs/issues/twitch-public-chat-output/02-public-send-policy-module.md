## Parent PRD

[twitch-public-chat-output.md](../../prds/twitch-public-chat-output.md)

## What to build

`PublicSendPolicy`: the pure, deterministic decision module at the heart of
public output safety (PRD "Implementation Decisions", policy bullet). Given a
candidate message, the target channel, and the current time (injected clock),
it returns a decision object `{action: send | shadow | drop, reason}` based on
its internal state: configured mode, armed/promoted/kill-switch state,
allow-list, sliding budget windows, and consecutive-failure count.

The module performs no I/O and never sleeps. It mirrors the design of the
existing `HumanLikeness` filter: pure logic, injectable dependencies,
exhaustive unit tests. Key semantics from the PRD (grill decisions):

- Sessions configured `live` start NOT promoted: decisions are `shadow` until
  an explicit `promote()` transition; `engage_kill_switch()` reverts to
  shadow; promotion is rejected unless the config arms live.
- Budget is consumed by both `send` and `shadow` outcomes (rehearsal fidelity)
  and enforced as sliding windows per minute and per hour.
- `record_failure()` counts consecutive sender failures and auto-engages the
  kill-switch at the configured threshold; `record_success()` resets it.
- Allow-list is re-checked at decision time (defense in depth), even though
  config validation already gated it.

## Step-by-step implementation plan

1. Define the decision and state types.
   - What: a frozen decision dataclass (`action`, `reason` — reasons as a
     small closed vocabulary, e.g. `mode_off`, `not_promoted`, `kill_switch`,
     `channel_not_allowed`, `budget_minute`, `budget_hour`, `ok`), and the
     policy class constructed from the slice-01 send config plus an injected
     clock callable.
   - Why now: the decision vocabulary is the contract for the router,
     events, and TUI in later slices.
   - Affects: new policy module.
   - Verify: types are importable and construction validates inputs.
   - Pitfall: no `time.time()` calls inside — clock is injected, like the
     injected sleep in the Reactor.

2. Implement mode/state gating.
   - What: `off` → drop(`mode_off`)? No — `off` never reaches the policy in
     practice (router selection), but the policy must still answer safely:
     return drop with `mode_off`. `shadow` → shadow. `live` → shadow until
     promoted, send after promotion, shadow again after kill-switch.
   - Why now: the state machine is the core; budget refines it.
   - Affects: policy module.
   - Verify: unit tests for every `{mode, promoted, kill-switch}` combination.
   - Pitfall: promotion must be rejected (no state change, explicit result)
     when mode is not `live`.

3. Implement sliding-window budget.
   - What: per-minute and per-hour windows over decision timestamps; both
     `send` and `shadow` outcomes consume budget; `drop` does not.
   - Why now: rate safety completes the decision logic.
   - Affects: policy module.
   - Verify: window-edge unit tests with a fake clock (message at t, window
     boundary at t+60/t+3600), exhaustion and recovery.
   - Pitfall: prune old timestamps on each decision to keep memory bounded.

4. Implement failure accounting and auto-degrade.
   - What: `record_failure()`/`record_success()`; at `failure_threshold`
     consecutive failures the kill-switch engages automatically (same state
     as the manual one, distinct reason recorded by the caller).
   - Why now: completes the safety loop for slice 07.
   - Affects: policy module.
   - Verify: threshold reached → next decision is shadow; success resets the
     count; manual disengage restores live only via explicit `promote()`.
   - Pitfall: auto-engage must not silently disengage — only an explicit
     operator action does.

## Acceptance criteria

- [ ] Pure module: no I/O, no real clock, no sleeping.
- [ ] Every `{mode, promoted, kill-switch, allow-list, budget}` combination yields the documented action and reason.
- [ ] Budget windows are sliding, consumed by send AND shadow, edge-exact under a fake clock.
- [ ] `failure_threshold` consecutive failures auto-engage the kill-switch; success resets the streak.
- [ ] Promotion is rejected unless the config arms `live`.
- [ ] Unit test suite covers reasons exhaustively (densest suite of the epic, per the PRD's testing decisions).

## Blocked by

- Blocked by [01-send-config-type-and-check.md](./01-send-config-type-and-check.md)

## User stories addressed

- User story 7
- User story 8
- User story 22
- User story 30
- User story 32
- User story 33
