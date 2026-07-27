## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Add the concept of `trigger_mode` to the Senser, and implement the `periodic`
mode that emits a `synthesis_tick` trigger at a fixed interval. This is the
trigger strategy for the MEETING_SYNTHESIZER style.

The existing behavior (mention + continuation + idle) becomes the `reactive`
mode (default). The Senser interface stays the same (`tick()` returns triggers);
only the internal logic branches on the mode.

## Step-by-step implementation plan

1. **Add `synthesis_tick` to trigger kinds.**
   The `Trigger` dataclass has a `kind` field (or similar). Add
   `synthesis_tick` as a new valid kind. This trigger carries no interlocutor
   or perception — it's purely timer-driven.
   *Verify:* `Trigger(kind="synthesis_tick", ...)` constructs correctly.
   *Pitfall:* check the `Trigger` contract — if `perception` is required,
   make it optional for timer triggers.

2. **Add `trigger_mode` parameter to the Senser.**
   The Senser constructor receives an optional `trigger_mode` (default:
   `"reactive"`). In `reactive` mode, the Senser behaves exactly as today.
   In `periodic` mode, it only runs the timer logic (no mention detection,
   no continuation detection, no conversation windows, no idle).
   *Verify:* Senser with `trigger_mode="reactive"` produces the same output
   as before.
   *Pitfall:* use the injectable clock (same pattern as `idle_comment`) for
   deterministic testing of the periodic timer.

3. **Implement periodic timer logic.**
   In `periodic` mode, `tick()` checks if `interval_s` has elapsed since the
   last `synthesis_tick` was emitted. If yes, emit one `synthesis_tick`
   trigger. If not, return an empty list. The Senser in periodic mode does
   NOT read perceptions for content — it only tracks time.
   *Verify:* with a fake clock, advancing by `interval_s` produces exactly
   one trigger; advancing by less produces none; advancing by `2 * interval_s`
   produces one (not two — it's cadence, not catchup).
   *Pitfall:* the periodic Senser still needs the perception store position
   cursor to stay current (so it doesn't re-process old perceptions when
   the mode is later combined with other modes). Or — if the periodic Senser
   truly ignores perceptions, it doesn't need a store at all. Decide based
   on whether the MEETING_SYNTHESIZER Reactor reads perceptions via the
   Senser or directly from the store.

4. **Write tests.**
   - `reactive` mode: existing tests pass unchanged.
   - `periodic` mode: emits `synthesis_tick` at correct intervals.
   - `periodic` mode: no mention/continuation/idle triggers.
   - `periodic` mode: deterministic with injected clock.
   Prior art: `test_senser.py`, especially the `idle_comment` timer tests.

## Acceptance criteria

- [ ] Senser accepts `trigger_mode` parameter (default `"reactive"`)
- [ ] `reactive` mode behavior unchanged (all existing tests green)
- [ ] `periodic` mode emits `synthesis_tick` at configured intervals
- [ ] `periodic` mode does not emit mention/continuation/idle triggers
- [ ] Timer uses injectable clock for deterministic testing

## Blocked by

None — the Senser is independently testable.

## User stories addressed

- User story 3
