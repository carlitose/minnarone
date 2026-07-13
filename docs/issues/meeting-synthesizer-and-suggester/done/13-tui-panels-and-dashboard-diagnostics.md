## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Add SINTETIZZATORE and SUGGERIMENTI panels to the TUI Textual dashboard.
Update `DashboardState` to aggregate diagnostics from multiple Reactors.
Make the TUI layout adaptive — panels appear only when the corresponding
profile is active.

## Step-by-step implementation plan

1. **Add per-profile output fields to `DashboardState`.**
   Add fields to hold the recent messages from each profile's
   `MinnaroneOutputStream`. These feed the new TUI panels. Also add
   per-Reactor diagnostics (last trigger time, last LLM call, errors) so
   the status bar reflects all active profiles.
   *Verify:* `DashboardState` with multi-profile data constructs correctly.

2. **Update `snapshot()` to aggregate multi-Reactor state.**
   `snapshot()` currently reads from a single Reactor. Update it to iterate
   over all active Reactors and collect:
   - Per-profile output messages (from per-profile streams)
   - Per-profile trigger/LLM diagnostics
   These feed both the panels and the status bar.
   *Verify:* snapshot with 3 active Reactors returns data for each.
   *Pitfall:* `snapshot()` must remain a pure read-only aggregator — no
   mutation, no `tick()` calls.

3. **Add `render_panels()` entries for SINTETIZZATORE and SUGGERIMENTI.**
   Add two new `DashboardPanel` entries:
   - **SINTETIZZATORE** — renders recent messages from the
     `MEETING_SYNTHESIZER` stream.
   - **SUGGERIMENTI** — renders recent messages from the `SUGGESTER` stream.
   Only include the panel if the corresponding profile is active.
   *Verify:* `render_panels()` includes the new panels when profiles are
   active, excludes them when not.

4. **Update `render_status_bar()` for multi-profile.**
   The status bar should show health information for all active profiles
   (e.g. "SYN: ok | SUG: ok | OP: idle"). Keep it concise — one segment
   per profile.
   *Verify:* status bar reflects all active profiles.

5. **Update the TUI Textual layout.**
   The current TUI uses a 3x3 grid. Adding two panels requires adapting
   the layout. Options:
   - Expand to 4x3 or 3x4.
   - Use a flexible layout that adjusts based on active panel count.
   - Add a new tab (like the existing PROMPT tab) for the new panels.
   Recommendation: add the new panels to the existing grid, expanding it.
   The panels should be positioned logically (synthesizer near MEMORIA,
   suggester near MINNARONE output).
   *Verify:* TUI renders without overflow on a standard 80x24 terminal.
   *Pitfall:* the layout must degrade gracefully — if only the synthesizer
   is active (no suggester), the grid should not have an empty panel.

6. **Write tests.**
   - `DashboardState` with multi-profile: correct panels returned.
   - `render_panels()` includes SINTETIZZATORE only when profile active.
   - `render_panels()` includes SUGGERIMENTI only when profile active.
   - `render_status_bar()` shows all active profiles.
   - TUI builds without error with new panels.
   Prior art: `test_dashboard.py`, `test_dashboard_tui.py`.

## Acceptance criteria

- [ ] SINTETIZZATORE panel renders meeting summaries from the synthesizer stream
- [ ] SUGGERIMENTI panel renders suggestions from the suggester stream
- [ ] Panels appear only when corresponding profile is active
- [ ] Status bar reflects all active profiles
- [ ] `snapshot()` aggregates multi-Reactor diagnostics
- [ ] TUI layout adapts to the number of active panels
- [ ] Dashboard tests pass

## Blocked by

- Blocked by [12-per-profile-tui-output-routing.md](./12-per-profile-tui-output-routing.md)

## User stories addressed

- User story 8
