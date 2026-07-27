## Parent PRD

[original-live-observability-tui.md](../../../prds/original-live-observability-tui.md)

## What to build

Replace the minimal TUI body with the main read-only dashboard layout that
matches the original Minnarone screenshots as closely as practical. The layout
must use the agreed panel names and visual hierarchy:

- Top: `IDLE`, `FINESTRA CHAT`, `STREAMER`
- Middle: `CHAT`, `EVENTI`, `MINNARONE`
- Bottom: `TRASCRIZIONE`, `VIDEO`, `MEMORIA`

Each panel should be scrollable or bounded so the layout remains usable on
normal terminal sizes. This slice does not need the full health status logic or
the `PROMPT` tab yet; it focuses on the main visual dashboard and content
placement.

## Step-by-step implementation plan

1. Expand the pure dashboard state to include all panel content needed for the
   main view.
   - What to change: ensure the state can provide recent chat, conversation
     windows, streamer window, recent triggers/events, Minnarone messages,
     audio transcriptions, video captions, and current summary.
   - Why this comes first: Textual widgets should render state, not collect data
     themselves.
   - Affects: dashboard snapshot model and pure render helpers.
   - Verify: pure tests can build a fake state with content for every panel.
   - Pitfalls: do not expose raw audio bytes, raw frame payloads, speaker
     centroids, or secrets.

2. Define formatting rules for each panel.
   - What to change: decide how each panel converts dashboard state into concise
     monospace lines while preserving original Italian labels.
   - Why this comes now: stable formatting makes the Textual layer thin and
     easier to test.
   - Affects: dashboard formatting helpers and TUI renderer.
   - Verify: tests confirm `FINESTRA CHAT` and `CHAT` show different content.
   - Pitfalls: do not rename `FINESTRA CHAT`; that name is intentional to avoid
     confusion.

3. Build the Textual grid matching the screenshot proportions.
   - What to change: replace the single text dump with a dark terminal-style
     grid, thin colored borders, uppercase titles, and dense monospace panels.
   - Why this comes now: panel contracts are ready and can be wired into the
     visual layout.
   - Affects: TUI module and stylesheet/theme.
   - Verify: a construction test with fake state finds all required panel
     titles and sample content.
   - Pitfalls: avoid decorative card styling; this should feel like the original
     terminal dashboard, not a web app.

4. Make panels scrollable or bounded.
   - What to change: ensure long chat, transcript, video, memory, and prompt-like
     text cannot resize the layout or overlap adjacent panels.
   - Why this comes now: the original layout is dense and live content is
     unbounded.
   - Affects: Textual widget configuration and panel update behavior.
   - Verify: fake long content stays inside its panel during TUI smoke tests.
   - Pitfalls: do not let dynamic text change grid proportions on every update.

5. Render live updates from the snapshot provider.
   - What to change: refresh panel content on the existing TUI interval using
     the latest dashboard state.
   - Why this comes last: the layout must be stable before live updates.
   - Affects: TUI update loop.
   - Verify: tests with a changing fake provider show updated content appears in
     the correct panels.
   - Pitfalls: avoid expensive work on each refresh; aggregation belongs in the
     snapshot provider.

## Acceptance criteria

- [ ] The TUI main view shows panels titled `IDLE`, `FINESTRA CHAT`, `STREAMER`, `CHAT`, `EVENTI`, `MINNARONE`, `TRASCRIZIONE`, `VIDEO`, and `MEMORIA`.
- [ ] The panel ordering follows the PRD's top, middle, and bottom rows.
- [ ] `FINESTRA CHAT` and `CHAT` are separate panels with separate meanings.
- [ ] Chat, audio transcription, video captions, Minnarone comments, and memory can all render from fake dashboard state.
- [ ] Long panel content remains bounded or scrollable without corrupting the layout.
- [ ] The view is read-only and contains no runtime controls.
- [ ] Automated tests cover state formatting and TUI construction with fake data.

## Blocked by

- Blocked by [01-live-tui-launch-path.md](./01-live-tui-launch-path.md)
- Blocked by [04-tui-minnarone-output-sink.md](./04-tui-minnarone-output-sink.md)

## User stories addressed

- User story 2
- User story 5
- User story 6
- User story 7
- User story 11
- User story 12
- User story 15
- User story 28
- User story 29
- User story 30
- User story 38
