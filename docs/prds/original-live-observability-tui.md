## Problem Statement

The operator can now run Minnarone against a live Twitch channel with chat,
local audio transcription, local speaker labels, local video captioning, and
private Italian commentary. The runtime is working, but the operator still has
to inspect multiple terminal outputs and `perceptions.jsonl` manually to know
what is happening. This makes it too easy to believe "everything works" while a
single channel is silently missing, as happened when chat/audio/commentary were
working but video captions were not.

The original Minnarone workflow included a dense terminal UI that showed the
live perception streams, sensor events, conversation windows, summaries,
Minnarone messages, and prompt/debug state in one place. The current Textual
dashboard is only a thin text dump of a snapshot. It is useful for tests, but it
does not match the original operator experience and does not make the live
runtime easy to inspect.

The user wants a terminal UI that copies the original screenshot layout as
closely as practical, shows every live signal in real time, exposes the exact
prompt sent to OpenRouter, and remains safe for long local runs by rotating
runtime artifacts instead of letting files grow without bounds.

## Solution

Build an integrated, read-only Textual TUI for Minnarone's live runtime. The TUI
will launch with the main command using a `--tui` option, run alongside the
existing agent loop, and render a dashboard that is visually faithful to the
original screenshots: dark terminal theme, monospace text, thin colored borders,
uppercase panel titles, dense scrolling panels, and a status bar.

The main dashboard will show:

- Top row: `IDLE`, `FINESTRA CHAT`, `STREAMER`
- Middle row: `CHAT`, `EVENTI`, `MINNARONE`
- Bottom row: `TRASCRIZIONE`, `VIDEO`, `MEMORIA`
- Status bar: channel, uptime, source health, counts, queue depth, model,
  token/cache metadata when available, and latest failure.

The `MINNARONE` panel will show private comments without the `[PRIVATE]` prefix
when the TUI is active. In non-TUI mode, the current console output behavior
stays unchanged.

The TUI will also include a separate `PROMPT` tab that shows the exact prompt
sent to OpenRouter for the latest reaction, with only secret redaction. It will
show best-effort model metadata such as model name, prompt tokens, completion
tokens, cached tokens, cache-write tokens, and cost if the provider returns it
or if a later pricing layer can compute it.

Runtime artifacts will be made safer:

- Every live run writes into a per-run directory under a local runs area rather
  than always appending to the project-root perception file.
- Prompt debug captures are saved with strict retention: keep only the latest
  50 prompts and cap each saved prompt at 200 KB, for roughly 10 MB maximum.
- Recent runs are retained with a bounded policy, initially keeping the latest
  20 run directories.

Add a replay mode after the live integrated TUI. Replay mode should render the
same dashboard from an existing perception log and saved prompt/debug artifacts
without starting Twitch, local models, or OpenRouter. Replay is for debugging
and visual validation without spending money or requiring a live channel.

## User Stories

1. As a Minnarone operator, I want one TUI that shows chat, audio, video, and
   comments together, so that I can understand what the runtime is doing without
   tailing multiple files.
2. As a Minnarone operator, I want the UI to copy the original screenshot layout,
   so that the new runtime feels like the original Minnarone.
3. As a Minnarone operator, I want a visible status bar for chat, audio, video,
   LLM, and VLM health, so that I immediately notice when one subsystem is not
   working.
4. As a Minnarone operator, I want video caption counts visible, so that I do
   not mistake a chat/audio-only run for a complete multimodal run.
5. As a Minnarone operator, I want recent video captions in a dedicated `VIDEO`
   panel, so that I can verify what Minnarone thinks it sees.
6. As a Minnarone operator, I want recent audio transcriptions in
   `TRASCRIZIONE`, so that I can evaluate ASR quality and speaker labeling.
7. As a Minnarone operator, I want chat messages in a `CHAT` panel, so that I can
   compare Minnarone's comments against current chat context.
8. As a Minnarone operator, I want `MINNARONE` messages in their own panel, so
   that I can read private commentary without console layout corruption.
9. As a Minnarone operator, I want private comments shown without `[PRIVATE]` in
   the panel, so that the panel stays clean and readable.
10. As a Minnarone operator, I want non-TUI mode to keep printing `[PRIVATE]`,
    so that existing console workflows do not change.
11. As a Minnarone operator, I want `IDLE`, `FINESTRA CHAT`, and `STREAMER`
    windows visible, so that I can see why the Senser is or is not opening a
    conversation context.
12. As a Minnarone operator, I want the top chat conversation panel named
    `FINESTRA CHAT`, so that it is not confused with the live chat log panel.
13. As a Minnarone operator, I want `EVENTI` to show Senser triggers, so that I
    can understand why Minnarone decided to comment.
14. As a Minnarone operator, I want `EVENTI` to also show technical events and
    failures, so that debugging does not require separate logs.
15. As a Minnarone operator, I want `MEMORIA` to show the current short-term
    summary, so that I can inspect the context Minnarone carries between turns.
16. As a Minnarone operator, I want the current prompt in a `PROMPT` tab, so that
    I can verify the exact input sent to OpenRouter.
17. As a Minnarone operator, I want prompt display to preserve the exact prompt
    structure, so that prompt-debugging is faithful and not a prettified guess.
18. As a Minnarone operator, I want secrets redacted in prompt/debug output, so
    that OAuth tokens and API keys cannot leak through the UI or saved files.
19. As a Minnarone operator, I want token/cache metadata shown when available, so
    that I can understand cost and caching behavior during live runs.
20. As a Minnarone operator, I want cost display to be best-effort, so that the
    UI remains useful even if provider pricing metadata is absent.
21. As a Minnarone operator, I want source counts in the status bar, so that I
    can quickly see counts for chat messages, audio speech, and video captions.
22. As a Minnarone operator, I want queue depth and dropped/failed counters in
    the status bar or events, so that backpressure is visible.
23. As a Minnarone operator, I want VLM busy/failure state visible, so that I can
    tell whether captions are slow, failed, or simply deduplicated.
24. As a Minnarone operator, I want ASR busy/failure state visible, so that I can
    distinguish silence from a broken audio pipeline.
25. As a Minnarone operator, I want OpenRouter errors visible, so that model
    deprecations or auth problems are obvious.
26. As a Minnarone operator, I want the dashboard to be read-only, so that
    looking at state cannot accidentally alter the live agent.
27. As a Minnarone operator, I want no controls in the first TUI version, so that
    the runtime remains simple and safe while observability stabilizes.
28. As a Minnarone operator, I want no terminal video preview, so that I can keep
    the TUI fast and watch the Twitch stream separately in a browser.
29. As a Minnarone operator, I want each panel scrollable, so that the layout can
    stay faithful to the screenshots even on smaller terminals.
30. As a Minnarone operator, I want the layout proportions to match the original
    screenshot, so that muscle memory and visual comparison are easy.
31. As a Minnarone operator, I want run artifacts separated by run, so that a
    new channel does not mix with an old stream context.
32. As a Minnarone operator, I want perception logs still written to disk, so
    that the UI is not the only record of what happened.
33. As a Minnarone operator, I want old run artifacts retained only up to a
    limit, so that long experimentation does not fill the Mac's disk.
34. As a Minnarone operator, I want prompts saved with retention and size caps,
    so that prompt debugging does not create unbounded data.
35. As a Minnarone operator, I want replay mode over old runs, so that I can
    debug or demo UI behavior without Twitch, local models, or OpenRouter.
36. As a Minnarone operator, I want replay mode to preserve the same panel
    layout, so that live and offline debugging feel identical.
37. As a Minnarone developer, I want the snapshot model to remain pure and
    testable, so that UI tests do not need a live terminal or Twitch stream.
38. As a Minnarone developer, I want the Textual widgets to stay thin, so that
    layout code does not absorb runtime business logic.
39. As a Minnarone developer, I want prompt capture to be a small boundary around
    LLM calls, so that the Reactor does not grow ad-hoc debug branches.
40. As a Minnarone developer, I want output routing to support a TUI sink, so
    that comments can be rendered in the UI without printing over the Textual
    layout.
41. As a Minnarone developer, I want status and health data normalized before
    rendering, so that the TUI can show clear `ok`, `idle`, `busy`, and `failed`
    states consistently.
42. As a Minnarone developer, I want tests with fake perceptions, fake LLM
    metadata, and fake runtime stats, so that CI never requires live Twitch or
    model downloads.
43. As a Minnarone developer, I want the TUI import to remain optional, so that
    users without the `tui` extra can still import and run non-TUI code.
44. As a Minnarone developer, I want prompt files and replay artifacts to be
    gitignored local data, so that secrets or large logs are not committed.
45. As a Minnarone developer, I want documentation to explain live and replay
    commands, so that future operators do not need the chat history to run the
    UI.

## Implementation Decisions

- Use a terminal Textual UI, not a browser UI.
- Copy the original screenshot style as closely as practical: dark background,
  monospace text, thin colored panel borders, uppercase titles, dense text, and
  fixed multi-panel layout.
- Integrate the live UI into the main Minnarone command via a `--tui` flag.
- Keep the first version read-only. No pause, force-comment, channel switch,
  FPS tuning, or store-clearing controls.
- Keep writing perception logs to disk even when the TUI is open.
- Do not render a live video preview in terminal. The operator watches Twitch in
  a browser; the TUI shows video captions and video diagnostics.
- Use `FINESTRA CHAT` for the top conversation-window panel to avoid confusing
  it with the live `CHAT` log panel.
- Main dashboard layout:
  - Top: `IDLE`, `FINESTRA CHAT`, `STREAMER`
  - Middle: `CHAT`, `EVENTI`, `MINNARONE`
  - Bottom: `TRASCRIZIONE`, `VIDEO`, `MEMORIA`
- Add a separate `PROMPT` tab for the exact latest prompt sent to OpenRouter.
- In TUI mode, do not print private comments to stdout. Route them into the
  `MINNARONE` panel. In non-TUI mode, keep current console output with
  `[PRIVATE]`.
- Prompt display and prompt debug files must contain the exact prompt, except
  for secret redaction.
- Prompt debug retention: keep latest 50 prompt captures, cap each saved prompt
  at 200 KB, and delete older captures automatically.
- Run artifact retention: write each run to a per-run local directory and keep
  the latest 20 runs by default.
- Token/cache/cost display is best-effort. Show provider metadata when present;
  do not fail the UI when fields are absent.
- Add replay mode after the live TUI foundation. Replay reads existing run
  artifacts and renders the same dashboard without starting Twitch, local
  models, or OpenRouter.
- Preserve the existing pure dashboard snapshot idea. Expand it rather than
  putting aggregation logic directly in Textual widgets.
- Textual remains an optional dependency. Non-TUI imports and non-TUI runtime
  must not require it.
- The UI must never expose raw audio bytes, raw frame payloads, API keys,
  Twitch OAuth tokens, or speaker centroids.

## Step-by-Step Implementation Plan

1. Inventory and formalize the current observable state.
   - What to change: define the complete data the TUI needs: recent chat,
     recent audio, recent video captions, recent Minnarone messages, current
     summary, recent triggers, conversation windows, queue stats, adapter stats,
     video stats, speaker stats, latest LLM metadata, latest prompt metadata,
     and failures.
   - Why now: the UI should render a clean state object, not reach into runtime
     internals panel by panel.
   - Affects: dashboard snapshot model, Reactor observability, Summarizer
     observability, LLM provider observability, output routing.
   - Verify: a fake runtime state can be transformed into one dashboard state
     without importing Textual.
   - Pitfalls: do not call live mutating methods from the snapshot; snapshot
     must remain read-only.

2. Add prompt and LLM-call observability.
   - What to change: add a narrow observer boundary around each LLM completion
     request. It should record the exact prompt, trigger context when available,
     model name, timestamps, response metadata, token/cache fields, status, and
     sanitized errors.
   - Why now: the `PROMPT` tab and prompt retention both depend on this event.
   - Affects: LLM provider boundary and Reactor/Summarizer call sites.
   - Verify: fake LLM calls produce prompt snapshots and metadata without making
     network calls.
   - Pitfalls: do not duplicate prompt-building logic; capture the prompt after
     it is built and before it is sent.

3. Implement secret redaction for prompt/debug artifacts.
   - What to change: reuse or extend the existing dashboard sanitization rules
     so prompt text, errors, and debug files redact OAuth tokens, bearer tokens,
     OpenRouter keys, raw bytes, control characters, and other sensitive values.
   - Why now: prompt capture should be safe before writing anything to disk.
   - Affects: dashboard sanitization utilities and prompt recorder.
   - Verify: tests with fake secrets confirm no secret literal appears in
     rendered prompt text or saved prompt files.
   - Pitfalls: do not over-redact normal chat content; redaction should target
     secrets and unsafe payloads, not make the prompt useless.

4. Build a bounded prompt recorder.
   - What to change: create a small module that writes prompt debug records to a
     local prompt directory with max-record and max-byte limits. It should keep
     only the latest 50 prompt captures and cap each prompt at 200 KB.
   - Why now: this isolates disk-retention behavior before UI integration.
   - Affects: prompt observability and run artifact workflow.
   - Verify: unit tests create more than 50 prompts and confirm older files are
     deleted; oversized prompts are truncated safely.
   - Pitfalls: do not write prompts outside local run/debug directories; do not
     allow unbounded file growth.

5. Add per-run artifact management.
   - What to change: create a run-session manager that chooses a run directory
     for each live run, stores the perception log there, stores prompt captures
     there, and retains only the latest 20 run directories by default.
   - Why now: the UI and replay both need clean, separated run artifacts.
   - Affects: default store path selection, CLI launch workflow, docs.
   - Verify: starting two runs produces two separate run directories; old runs
     are pruned when the limit is exceeded.
   - Pitfalls: do not delete the active run; do not move user-supplied store
     paths unexpectedly without clear configuration.

6. Add a TUI-aware output router or output sink.
   - What to change: provide an output path that captures Minnarone messages for
     the dashboard panel while suppressing stdout printing when `--tui` is
     active.
   - Why now: Textual layouts break if normal console output continues.
   - Affects: output routing and Agent assembly.
   - Verify: with a fake LLM response, non-TUI mode prints as before, while TUI
     mode records the message for the dashboard and does not print it.
   - Pitfalls: do not change public/private safety rules; TUI output is still
     local-only and must never send Twitch messages.

7. Expand the pure dashboard state.
   - What to change: add fields for current summary, latest prompt, LLM metadata,
     source health, uptime, run path, and technical events. Keep these as simple
     dataclasses/lists.
   - Why now: Textual should render from one stable interface.
   - Affects: dashboard state and snapshot provider.
   - Verify: pure tests assert each new field is populated from fake sources.
   - Pitfalls: do not expose raw frame/audio payloads or centroids.

8. Normalize source health.
   - What to change: derive `ok`, `idle`, `busy`, `failed`, and `unknown` status
     per source: chat, audio, video, ASR, speaker, VLM, LLM, queue, adapter.
   - Why now: the status bar needs concise truth, not raw counters.
   - Affects: dashboard state and status bar rendering.
   - Verify: fake stats produce expected health labels, including the case where
     chat/audio work but video captions are zero or failed.
   - Pitfalls: zero video captions is not always failure if no frames have been
     sampled yet; combine counters, failures, and uptime carefully.

9. Rebuild the Textual app layout.
   - What to change: replace the single `Static` body with a panel grid matching
     the original screenshot proportions. Each panel should be scrollable and
     independently updated from the dashboard state.
   - Why now: once the state shape is complete, the UI can remain presentation
     only.
   - Affects: Textual TUI module and CSS/theme.
   - Verify: smoke test can construct the app with fake state; render text
     content appears in the expected panels.
   - Pitfalls: avoid panel-in-panel card design; this is a terminal dashboard,
     not a web layout.

10. Implement the main dashboard tab.
    - What to change: render `IDLE`, `FINESTRA CHAT`, `STREAMER`, `CHAT`,
      `EVENTI`, `MINNARONE`, `TRASCRIZIONE`, `VIDEO`, and `MEMORIA` with the
      agreed labels and ordering.
    - Why now: this is the core operator experience.
    - Affects: Textual renderer and dashboard formatting helpers.
    - Verify: fake state with sample chat/audio/video/messages/summary renders
      in the correct panels.
    - Pitfalls: do not conflate `FINESTRA CHAT` with `CHAT`; they mean different
      things.

11. Implement the `PROMPT` tab.
    - What to change: add a second tab or mode that shows the latest exact
      redacted prompt, trigger reason, model, token/cache metadata, and status.
    - Why now: prompt debugging is a first-class requirement, but should not
      crowd the live dashboard.
    - Affects: Textual app, prompt observer, dashboard state.
    - Verify: a fake captured prompt appears unchanged except redaction.
    - Pitfalls: do not reformat the prompt in a way that hides exact ordering or
      section boundaries.

12. Add keyboard navigation.
    - What to change: provide minimal read-only keybindings: dashboard tab,
      prompt tab, scroll focused panel, quit. Keep controls non-mutating.
    - Why now: panels are scrollable and the prompt can be long.
    - Affects: Textual app only.
    - Verify: app constructs with bindings; tests can inspect action names or
      smoke-run the app object.
    - Pitfalls: do not add runtime control actions in this PRD.

13. Integrate `--tui` into the main CLI.
    - What to change: add an option that builds the agent, creates the run
      session, wires the TUI output sink, starts the agent task, and starts the
      Textual app reading `agent.observability_snapshot`.
    - Why now: the TUI is meant to be live and integrated, not a separate tail
      command only.
    - Affects: CLI orchestration and Agent run lifecycle.
    - Verify: fake/injected agent tests can prove `--tui` selects the TUI path
      without launching live Twitch.
    - Pitfalls: ensure clean shutdown on Ctrl-C or app exit; do not orphan model
      workers or stream tasks.

14. Preserve non-TUI behavior.
    - What to change: ensure existing command behavior without `--tui` remains
      unchanged, including console `[PRIVATE]` output and current check mode.
    - Why now: observability should not regress working live runs.
    - Affects: CLI and output routing tests.
    - Verify: existing CLI and app tests still pass.
    - Pitfalls: do not make `textual` required for non-TUI execution.

15. Add replay-mode data model.
    - What to change: define how replay reads a run directory or perception log:
      perceptions, prompt captures, optional metadata, and optionally synthetic
      source stats. The first replay can be time-independent and show final
      state; later replay can animate by timestamp.
    - Why now: replay shares most rendering with live TUI and should not become
      a separate UI.
    - Affects: replay loader and dashboard state construction.
    - Verify: recorded fixture logs render into dashboard state without Twitch,
      local models, or OpenRouter.
    - Pitfalls: do not require every old run to have prompt captures; replay
      should degrade gracefully.

16. Add a replay command.
    - What to change: expose a separate command or CLI option that opens the TUI
      against a run directory or perception log.
    - Why now: it completes the offline debug workflow after live TUI exists.
    - Affects: CLI command surface and docs.
    - Verify: command parses arguments and builds the TUI with a fake replay
      provider in tests.
    - Pitfalls: replay must never call OpenRouter or start capture adapters.

17. Update operator documentation.
    - What to change: document live `--tui`, replay mode, prompt retention, run
      rotation, source health indicators, and how to read each panel.
    - Why now: operators should not need the development chat to understand the
      UI.
    - Affects: README and Twitch operator docs.
    - Verify: docs tests cover key commands and wording.
    - Pitfalls: do not imply the TUI sends Twitch messages or controls the
      runtime.

18. Run full verification.
    - What to change: run targeted dashboard/TUI tests, CLI tests, app wiring
      tests, then the full test suite and quality checks.
    - Why now: the feature touches runtime wiring, optional dependencies, and
      observability.
    - Affects: test/quality workflow.
    - Verify: all relevant tests pass; live manual smoke can be run afterward on
      a real channel.
    - Pitfalls: do not add CI tests that require live Twitch, Qwen, Whisper,
      sherpa-onnx model files, or OpenRouter credentials.

## Testing Decisions

- Good tests should verify observable behavior at module boundaries, not
  Textual internals or exact private widget structure.
- Keep the dashboard state model heavily tested without Textual. It is the
  canonical behavior layer for the TUI.
- Test the TUI with fake `DashboardState` providers. Construction and panel
  content are sufficient for automated tests; full terminal interaction remains
  manual smoke.
- Test prompt capture with fake LLM calls, fake metadata, fake errors, and fake
  secrets. Assert exact prompt preservation plus secret redaction.
- Test prompt retention by writing more than 50 prompt records and asserting
  old records are pruned.
- Test prompt size limits by writing an oversized prompt and asserting the saved
  representation is capped and clearly marked as truncated.
- Test run rotation with temporary directories, including active run safety and
  latest-20 retention.
- Test output routing in both modes: non-TUI prints/records as today, TUI mode
  routes to the dashboard sink without stdout pollution.
- Test source health with fake adapter/queue/video/speaker/LLM stats, including
  partial-success cases such as chat/audio working but video captions missing.
- Test replay with fixture perception logs and fixture prompt captures. Replay
  must not import heavy model backends or require network.
- Existing prior art includes dashboard snapshot tests, TUI import-guard smoke
  tests, CLI tests, app wiring tests, prompt builder tests, OpenRouter provider
  tests, and local perception observability tests.
- Do not add automated tests that require live Twitch, Streamlink network
  availability, OpenRouter credentials, Qwen model files, faster-whisper model
  downloads, or sherpa-onnx model files.
- Manual acceptance should run on a live Twitch channel and confirm all panels
  populate: chat, audio, video, Minnarone messages, memory, status bar, prompt
  tab, and source health.

## Out of Scope

- Browser-based dashboard or web UI.
- Terminal video preview or image rendering.
- Runtime controls such as pause, force-comment, channel switch, queue tuning,
  video FPS tuning, or clearing the store.
- Sending public Twitch messages.
- TTS/private audio output.
- Rich cost accounting based on a maintained provider pricing table. Cost is
  best-effort only unless provider metadata or a later pricing layer supplies
  enough information.
- Pixel-perfect automated visual regression against the screenshots.
- Live Twitch or OpenRouter calls in CI.
- Rewriting the prompt strategy, Senser behavior, ASR, diarization, or VLM
  caption model.
- Perfect speaker diarization or perfect video caption quality.
- Long-term memory authoring for `soul` and `facts`. The UI may show that memory
  is empty, but creating the persona files is separate work.

## Further Notes

The current runtime already proves the complete perception/commentary loop can
work: chat, audio speech, video captions, and private comments have all been
observed during a live run. The UI work is about making that truth visible and
hard to misunderstand.

The implementation should treat the Textual layer as presentation only. The
deep modules should be the snapshot/state aggregator, prompt observer/recorder,
run session manager, replay loader, and output sink. Those modules can be
tested headlessly and should remain stable even if the visual layout evolves.

The original screenshots are the visual reference. The one intentional label
change is `FINESTRA CHAT` for the top chat conversation window, because the user
explicitly wanted to avoid confusion with the live `CHAT` log panel.

The UI should surface missing pieces aggressively. A run where chat/audio/LLM
work but video captions are absent must look visibly incomplete, not "green".
