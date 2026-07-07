## Parent PRD

[twitch-public-chat-output.md](../../prds/twitch-public-chat-output.md)

## What to build

The operator's two hands on the live channel, in the TUI: a **promote**
keybinding (shadow → live, accepted only when config arms live) and a
**kill-switch** keybinding (live → shadow, instant). Both give unmistakable
status-bar feedback, both are recorded as run events, and both must be
deliberate actions (distinct keys or confirmation — never a single toggle you
can fat-finger twice). This makes live reachable only through the `--tui`
runtime, per the PRD: the plain console runtime tops out at shadow by
construction.

## Step-by-step implementation plan

1. Expose safe transition commands from the runtime to the TUI.
   - What: a narrow command surface (promote / engage kill-switch) that the
     TUI can call on the running agent, delegating to the policy transitions
     from slice 02; results (accepted/rejected + reason) come back for
     display.
   - Why now: the TUI is read-only today; sending state transitions needs an
     explicit, minimal command channel rather than giving the TUI the policy
     object.
   - Affects: agent command surface, TUI wiring.
   - Verify: unit tests on the command surface with a fake policy.
   - Pitfall: keep the TUI read-only for everything else; these two commands
     are the only mutations.

2. Add the keybindings with deliberate semantics.
   - What: two distinct keys; promote requires a confirmation step (e.g.
     press twice within a short window or a modal confirm); kill-switch acts
     immediately on first press — asymmetry is intentional (enabling public
     output is slow, stopping it is instant).
   - Why now: the command surface exists; UX lands on top.
   - Affects: TUI app keymap and status bar.
   - Verify: TUI tests — promote rejected when config does not arm live;
     accepted promote flips the next decision to send; kill-switch flips back
     to shadow immediately.
   - Pitfall: no keybinding may disengage the kill-switch implicitly;
     returning to live is always a fresh, confirmed promote.

3. Record and display transitions.
   - What: promote/kill-switch/auto-degrade transitions are run events with
     actor (`operator` / `auto`) and reason; status bar shows the current
     state prominently (e.g. `send=shadow(armed)`, `send=live`,
     `send=shadow(kill)`).
   - Why now: audit and live feedback close the loop for the acceptance runs.
   - Affects: event vocabulary (extends slice 03/04 surfaces), status bar.
   - Verify: event fixtures include transitions; replay shows them.
   - Pitfall: the status indicator must be visible without opening any tab —
     it is the single most important operator signal during live runs.

## Acceptance criteria

- [ ] Promote key flips shadow → live only when config arms live, with confirmation.
- [ ] Kill-switch key flips live → shadow instantly on first press.
- [ ] Rejected promotes show a reason and change nothing.
- [ ] All transitions (including auto-degrade) are recorded with actor and reason, and visible in replay.
- [ ] The status bar always shows the current send state.
- [ ] The console (non-TUI) runtime has no transition path: live is TUI-only.

## Blocked by

- Blocked by [04-send-observability.md](./04-send-observability.md)
- Blocked by [07-live-mode-behind-gates.md](./07-live-mode-behind-gates.md)

## User stories addressed

- User story 9
- User story 32
- User story 33
- User story 34
