## Parent PRD

[original-live-observability-tui.md](../../../prds/original-live-observability-tui.md)

## What to build

Add replay mode for the same Textual dashboard. The operator should be able to
open an existing run directory or perception log and inspect the dashboard and
prompt debug state without starting Twitch, local ASR/VLM models, or OpenRouter.
The first replay mode can render the final reconstructed state rather than
animated time playback.

This slice depends on run-scoped artifacts, prompt capture, and the main TUI
rendering because replay should reuse the same dashboard state and visual
surface as live mode.

## Step-by-step implementation plan

1. Define the replay input contract.
   - What to change: accept either a run directory or a perception JSONL path,
     and discover optional prompt/debug artifacts when present.
   - Why this comes first: replay should be forgiving enough to work with older
     or partial runs.
   - Affects: replay loader and command surface.
   - Verify: tests cover run-directory input, direct perception-log input, and
     missing prompt artifacts.
   - Pitfalls: do not require a live configuration file, Twitch credentials, or
     model paths for replay.

2. Reconstruct dashboard state from perceptions.
   - What to change: parse saved perceptions into recent chat, audio
     transcription, video caption, event, and summary-like dashboard fields.
   - Why this comes now: the TUI needs the same state shape as live mode.
   - Affects: replay loader and dashboard state construction.
   - Verify: fixture logs with chat `msg`, audio `speech`, and video `caption`
     records populate the expected panels.
   - Pitfalls: handle malformed or unknown records gracefully and surface them
     as replay events rather than crashing.

3. Load prompt captures into replay state.
   - What to change: read the latest prompt/debug capture from the run when
     available and expose it through the same prompt state used by live mode.
   - Why this comes now: the `PROMPT` tab should work the same offline and live.
   - Affects: replay loader and prompt dashboard state.
   - Verify: fixture prompt captures show in the prompt tab; missing captures
     produce a clear empty state.
   - Pitfalls: do not undo redaction or read secrets from environment during
     replay.

4. Add a replay command or option.
   - What to change: expose an operator command path that opens the Textual app
     against a replay state provider.
   - Why this comes now: replay needs a discoverable entry point.
   - Affects: CLI command surface and TUI app builder.
   - Verify: parser tests and fake replay-provider tests prove no live runtime
     is started.
   - Pitfalls: replay must never call OpenRouter, Streamlink, Twitch IRC, ASR,
     speaker extraction, or VLM backends.

5. Show replay-specific status.
   - What to change: make the status bar indicate replay mode, source path, and
     reconstructed counts.
   - Why this comes last: it prevents confusing offline inspection with a live
     run.
   - Affects: dashboard status formatting and TUI rendering.
   - Verify: fake replay state shows replay labels and counts in the status bar.
   - Pitfalls: do not label replay sources as live `ok`; distinguish replayed
     counts from current health.

## Acceptance criteria

- [ ] Replay can open a run directory or perception JSONL path.
- [ ] Replay renders the same main dashboard panels as live mode.
- [ ] Replay populates chat, audio, video, events, memory-like state, and Minnarone messages from saved artifacts when available.
- [ ] Replay populates the `PROMPT` tab from saved prompt captures when available.
- [ ] Replay starts no Twitch, Streamlink, ASR, speaker, VLM, or OpenRouter work.
- [ ] Replay status clearly indicates offline replay mode.
- [ ] Tests use fixture artifacts and require no network, credentials, or model files.

## Blocked by

- Blocked by [02-bounded-run-artifacts.md](./02-bounded-run-artifacts.md)
- Blocked by [03-prompt-capture-and-retention.md](./03-prompt-capture-and-retention.md)
- Blocked by [05-screenshot-faithful-dashboard-panels.md](./05-screenshot-faithful-dashboard-panels.md)
- Blocked by [07-prompt-tab-in-tui.md](./07-prompt-tab-in-tui.md)

## User stories addressed

- User story 35
- User story 36
- User story 42
