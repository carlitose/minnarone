## Parent PRD

[original-live-observability-tui.md](../../prds/original-live-observability-tui.md)

## What to build

Make live runtime artifacts run-scoped and bounded. A TUI live run should write
its perception log and later debug artifacts into a dedicated local run
directory instead of mixing new channel data into an old root-level file. The
runtime should keep only the latest 20 run directories by default and must never
delete the active run.

This work comes after the TUI launch path because run-session setup belongs at
runtime startup. It comes before prompt capture and replay because both rely on
stable per-run storage.

## Step-by-step implementation plan

1. Define the run-session contract.
   - What to change: introduce a small runtime concept that identifies the
     current run directory, perception log path, prompt/debug directory, start
     time, channel, and retention policy.
   - Why this comes first: every artifact writer needs one shared place to ask
     where current-run files belong.
   - Affects: runtime startup workflow and artifact path selection.
   - Verify: unit tests can create a run session in a temporary local root and
     inspect the expected paths.
   - Pitfalls: do not use secrets, OAuth tokens, or raw channel URLs in directory
     names.

2. Create a per-run perception store path when the operator has not supplied a
   custom store path.
   - What to change: default live runs should write the perception JSONL inside
     the current run directory.
   - Why this comes now: it makes the existing central record run-scoped before
     adding more artifact types.
   - Affects: store path selection and CLI/runtime configuration.
   - Verify: a fake live startup creates a run directory and points the store at
     the run-local perception log.
   - Pitfalls: do not unexpectedly override an explicit user-provided store
     path; document or surface which path is active.

3. Keep perception logging active in TUI mode.
   - What to change: ensure opening the TUI does not replace or disable JSONL
     persistence.
   - Why this comes now: the UI is not the only record of what happened.
   - Affects: live runtime output/store wiring.
   - Verify: tests with fake perceptions confirm records are still appended
     while TUI mode is selected.
   - Pitfalls: do not couple persistence to successful Textual rendering.

4. Implement latest-20 run retention.
   - What to change: prune older completed run directories when creating a new
     run, keeping the newest 20 by default.
   - Why this comes now: run-scoped artifacts must not become unbounded.
   - Affects: run-session manager and local data cleanup.
   - Verify: tests create more than 20 fake runs and confirm only the newest are
     retained.
   - Pitfalls: never delete the active run; avoid deleting directories that do
     not match the runtime's own run-directory naming scheme.

5. Ensure local artifacts are ignored by version control.
   - What to change: confirm the local runs area is excluded from commits.
   - Why this comes now: perception logs and prompt captures can include private
     chat and operator context.
   - Affects: repository hygiene and operator documentation later.
   - Verify: status checks do not show generated run artifacts as tracked or
     untracked files.
   - Pitfalls: do not ignore source files or issue/PRD documentation.

## Acceptance criteria

- [ ] A live TUI run creates a dedicated local run directory.
- [ ] The default perception JSONL for that run is written inside the run directory.
- [ ] Explicit user-supplied store paths are respected or clearly handled.
- [ ] TUI mode still writes perception logs to disk.
- [ ] The runtime keeps only the latest 20 owned run directories by default.
- [ ] The active run is never pruned.
- [ ] Generated run artifacts are gitignored local data.

## Blocked by

- Blocked by [01-live-tui-launch-path.md](./01-live-tui-launch-path.md)

## User stories addressed

- User story 31
- User story 32
- User story 33
- User story 44
