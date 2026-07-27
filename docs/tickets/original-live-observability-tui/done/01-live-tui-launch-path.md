## Parent PRD

[original-live-observability-tui.md](../../../prds/original-live-observability-tui.md)

## What to build

Add the first end-to-end live TUI launch path for Minnarone. The operator should
be able to start the normal live runtime with a `--tui` option and see a Textual
application fed by the existing pure observability snapshot. This slice does not
need the final screenshot-faithful layout yet; it proves the lifecycle contract:
optional Textual dependency, live agent running in the background, dashboard
state polling in the foreground, and clean shutdown.

This work is first because every later UI slice depends on a reliable way to run
the TUI without breaking the existing non-TUI runtime.

## Step-by-step implementation plan

1. Confirm the current non-TUI launch flow and dashboard snapshot contract.
   - What to change: identify where the live agent is assembled, where command
     options are parsed, and how the current dashboard snapshot is exposed.
   - Why this comes first: the TUI path should reuse the working runtime instead
     of creating a second execution path.
   - Affects: CLI orchestration, agent lifecycle, dashboard snapshot provider.
   - Verify: existing non-TUI tests still describe the current behavior before
     adding the new branch.
   - Pitfalls: do not import Textual at module import time for users who did not
     install the TUI extra.

2. Add a `--tui` command option that selects the live TUI branch.
   - What to change: extend the command surface so the operator can request the
     Textual UI explicitly.
   - Why this comes now: later slices can build features behind the same stable
     entry point.
   - Affects: command parsing and operator-facing help.
   - Verify: parsing tests can distinguish normal mode, check mode, and TUI
     mode without launching Twitch.
   - Pitfalls: do not make `--tui` imply public Twitch output or any runtime
     controls.

3. Wire the live agent to a snapshot provider consumed by the TUI.
   - What to change: start the agent loop and provide a zero-argument callable
     that returns the latest dashboard state to the Textual app.
   - Why this comes now: it establishes the read-only boundary between runtime
     and presentation.
   - Affects: agent assembly, dashboard state polling, TUI builder.
   - Verify: a fake agent can be used in tests to prove the TUI branch polls a
     snapshot provider.
   - Pitfalls: the TUI must not mutate the agent, store, reactor, queues, or
     adapters.

4. Add clean shutdown behavior for the TUI branch.
   - What to change: ensure exiting the Textual app or pressing Ctrl-C stops the
     live runtime and leaves no background tasks running.
   - Why this comes now: live model and Twitch tasks are expensive and should
     not be orphaned.
   - Affects: runtime lifecycle and async task management.
   - Verify: tests with fakes can assert stop/cleanup hooks are called when the
     TUI exits.
   - Pitfalls: avoid swallowing exceptions silently; failures should be visible
     to later status/event surfaces.

5. Preserve optional dependency behavior.
   - What to change: keep Textual imports guarded so non-TUI imports and normal
     runtime still work without installing the TUI extra.
   - Why this comes now: this protects existing operator workflows while the UI
     evolves.
   - Affects: import boundaries and packaging extras.
   - Verify: an import-guard test confirms a missing Textual install produces a
     clear error only when the TUI is requested.
   - Pitfalls: do not move core dashboard dataclasses into the Textual module.

## Acceptance criteria

- [ ] The main command accepts a `--tui` option.
- [ ] `--tui` starts a Textual app backed by the live agent snapshot provider.
- [ ] The first TUI view can be minimal but shows live dashboard text or state.
- [ ] Exiting the TUI stops the live runtime cleanly.
- [ ] Non-TUI mode behaves as before.
- [ ] Importing and running non-TUI code does not require Textual.
- [ ] Automated tests cover command parsing, TUI branch selection, optional import behavior, and clean fake shutdown.

## Blocked by

None - can start immediately

## User stories addressed

- User story 1
- User story 26
- User story 27
- User story 37
- User story 38
- User story 43
