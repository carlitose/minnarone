## Parent PRD

[original-live-observability-tui.md](../../../prds/original-live-observability-tui.md)

## What to build

Add a TUI-aware output path for Minnarone's private comments. When the live TUI
is active, private comments should appear in the dashboard's `MINNARONE` stream
without the `[PRIVATE]` prefix and should not print over the terminal UI. When
the TUI is not active, existing console output must stay unchanged, including
the `[PRIVATE]` prefix.

This slice is independent from the final layout. It creates the output contract
needed by the `MINNARONE` panel.

## Step-by-step implementation plan

1. Identify the current output-routing contract.
   - What to change: inspect how private and public comments are routed today
     and which safety rules prevent public Twitch sends.
   - Why this comes first: the TUI sink must preserve output safety while
     changing presentation.
   - Affects: output router interface and agent assembly.
   - Verify: existing console-router tests describe the current non-TUI output.
   - Pitfalls: do not introduce a public send path as part of this work.

2. Add a TUI sink for private messages.
   - What to change: provide an output destination that records Minnarone
     messages into an in-memory observable stream suitable for the dashboard.
   - Why this comes now: the dashboard needs structured messages rather than
     terminal text scraping.
   - Affects: output routing and dashboard state aggregation.
   - Verify: fake private comments are captured in order with timestamps or
     enough metadata for rendering.
   - Pitfalls: keep the sink local-only; it must not write to Twitch chat.

3. Suppress normal stdout printing only in TUI mode.
   - What to change: wire the TUI branch to use the sink instead of normal
     console printing for private comments.
   - Why this comes now: Textual layout breaks if background prints continue.
   - Affects: TUI runtime assembly and output routing.
   - Verify: tests show TUI mode captures comments without writing `[PRIVATE]`
     to the provided stream.
   - Pitfalls: do not suppress diagnostics that should become technical events
     later; only move private comments away from stdout.

4. Preserve non-TUI behavior exactly.
   - What to change: leave existing console mode output behavior intact.
   - Why this comes now: the live runtime already works and should not regress.
   - Affects: non-TUI agent assembly.
   - Verify: existing or new tests confirm console mode still prints private
     comments with `[PRIVATE]`.
   - Pitfalls: avoid global flags that affect both modes accidentally.

5. Surface captured messages through the dashboard snapshot.
   - What to change: include recent Minnarone messages from the TUI sink in the
     pure dashboard state.
   - Why this comes last: the UI panel should render from snapshot data, not
     from the sink directly.
   - Affects: dashboard snapshot model.
   - Verify: fake sink messages appear in dashboard state and render text
     without `[PRIVATE]`.
   - Pitfalls: keep retention bounded in memory so a long run does not grow an
     unbounded message list.

## Acceptance criteria

- [ ] TUI mode routes private Minnarone comments into an observable dashboard stream.
- [ ] TUI mode does not print private comments over the terminal layout.
- [ ] The dashboard version of private comments omits the `[PRIVATE]` prefix.
- [ ] Non-TUI mode still prints private comments with `[PRIVATE]`.
- [ ] No public Twitch message path is introduced or enabled.
- [ ] Recent Minnarone messages are available in the pure dashboard snapshot.

## Blocked by

- Blocked by [01-live-tui-launch-path.md](./01-live-tui-launch-path.md)

## User stories addressed

- User story 8
- User story 9
- User story 10
- User story 40
