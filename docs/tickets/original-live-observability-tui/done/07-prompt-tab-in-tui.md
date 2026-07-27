## Parent PRD

[original-live-observability-tui.md](../../../prds/original-live-observability-tui.md)

## What to build

Add a separate `PROMPT` tab or read-only view to the Textual UI. It should show
the latest exact redacted prompt sent to OpenRouter, plus trigger reason,
status, model name, prompt/completion tokens, cached/cache-write tokens, and
cost when available. The prompt text should preserve ordering and section
boundaries; it should not be prettified into a different prompt.

This slice depends on prompt capture and the main dashboard layout. It keeps
prompt debugging available without crowding the live observation dashboard.

## Step-by-step implementation plan

1. Confirm the prompt snapshot shape exposed by the dashboard state.
   - What to change: use the latest prompt observation and metadata from the
     pure state rather than reading prompt files directly in the TUI.
   - Why this comes first: the TUI should be presentation-only.
   - Affects: TUI renderer and dashboard state contract.
   - Verify: fake dashboard states can represent no prompt yet, a successful
     prompt, and a failed LLM call.
   - Pitfalls: do not make the prompt tab depend on a live OpenRouter call.

2. Add read-only tab navigation.
   - What to change: provide a main dashboard tab and a `PROMPT` tab with
     minimal keyboard navigation and quit behavior.
   - Why this comes now: the prompt view should be separate from the main live
     panels.
   - Affects: Textual app structure and keybindings.
   - Verify: tests can construct the app and inspect or exercise tab/action
     names without a live terminal.
   - Pitfalls: do not add runtime-mutating controls in this slice.

3. Render prompt metadata.
   - What to change: show trigger label/reason, provider/model, status,
     timestamps or age, token/cache fields, cost if available, and sanitized
     error summary.
   - Why this comes now: metadata lets the operator understand cost and failure
     behavior before reading the full prompt.
   - Affects: prompt tab layout and status formatting.
   - Verify: fake metadata appears with absent fields handled gracefully.
   - Pitfalls: do not show misleading zero cost when cost is unknown; label it
     as unavailable or best-effort.

4. Render the exact redacted prompt body.
   - What to change: display the prompt body in a scrollable region preserving
     line order, section boundaries, and spacing as much as Textual allows.
   - Why this comes now: prompt-debugging depends on fidelity.
   - Affects: prompt tab rendering.
   - Verify: a fake multi-section prompt appears unchanged except for redacted
     secrets.
   - Pitfalls: do not wrap or reformat in a way that obscures the prompt's real
     structure.

5. Handle empty and error states.
   - What to change: show a clear placeholder before the first LLM call and a
     safe error state when prompt capture exists but the provider failed.
   - Why this comes last: live runs spend time before the first reaction.
   - Affects: prompt tab rendering.
   - Verify: fake empty and failed states render without exceptions.
   - Pitfalls: do not make empty prompt state look like broken prompt capture.

## Acceptance criteria

- [ ] The TUI has a separate `PROMPT` tab or read-only view.
- [ ] The prompt view displays the latest exact redacted prompt from dashboard state.
- [ ] Prompt structure, ordering, and section boundaries are preserved.
- [ ] Trigger reason, model, status, token/cache metadata, and cost when available are visible.
- [ ] Unknown token/cache/cost fields degrade gracefully.
- [ ] Secrets remain redacted in the prompt tab.
- [ ] The prompt tab adds no runtime-mutating controls.

## Blocked by

- Blocked by [03-prompt-capture-and-retention.md](./03-prompt-capture-and-retention.md)
- Blocked by [05-screenshot-faithful-dashboard-panels.md](./05-screenshot-faithful-dashboard-panels.md)

## User stories addressed

- User story 16
- User story 17
- User story 18
- User story 19
- User story 20
- User story 29
