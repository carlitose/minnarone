## Parent PRD

[local-twitch-perception-runtime.md](../../prds/local-twitch-perception-runtime.md)

## What to build

Make the existing future-facing `adapter: twitch` configuration operational in
the main Minnarone runtime for the narrowest safe path: Twitch chat only, real
agent loop, console output only.

This slice proves the runtime bridge before local ASR, diarization, PyAV, or VLM
work is introduced. A successful demo reads live Twitch chat through the
Twitch adapter, writes chat perceptions to the normal perception store, lets the
existing Senser/Reactor/PromptBuilder process them, and prints responses through
the existing console public output path. It must not send messages to Twitch.

## Step-by-step implementation plan

1. Review the existing Twitch config shape and app builder behavior.
   - What to change: identify where the validated `adapter: twitch` config is
     currently accepted but not turned into a runtime `SourceAdapter`.
   - Why now: this slice should only make the existing shape operational, not
     redesign configuration.
   - Affects: config workflow, app assembly, CLI runtime.
   - Verify: existing `adapter: os_capture` and non-Twitch configs still load.
   - Pitfalls: do not require Twitch credentials unless the selected adapter is
     actually Twitch and chat is enabled.

2. Add a factory path for Twitch source construction.
   - What to change: build the unified Twitch source adapter from config when
     `adapter: twitch` is selected.
   - Why now: the agent already accepts an injected source adapter; this is the
     missing runtime bridge.
   - Affects: app assembly, `SourceAdapter` injection contract.
   - Verify: with fake credentials and fake readers in tests, the agent receives
     chat `RawEvent` values through the same path as other adapters.
   - Pitfalls: keep Twitch-specific details at the adapter edge; do not leak IRC
     concepts into Senser, Reactor, or PromptBuilder.

3. Keep this slice chat-only by default for runtime validation.
   - What to change: allow the Twitch runtime to run with audio and video
     disabled, even if later config fields exist.
   - Why now: live chat perception proves end-to-end app wiring without heavy
     local models.
   - Affects: runtime defaults, example config, validation behavior.
   - Verify: `twitch.chat: true`, `twitch.audio: false`, `twitch.video: false`
     starts without Streamlink/FFmpeg media processing.
   - Pitfalls: do not break existing capture-only smoke commands.

4. Ensure console-only output.
   - What to change: keep the existing console output router as the only runtime
     output for this path.
   - Why now: this PRD explicitly defers public Twitch chat output.
   - Affects: output routing, operator expectations.
   - Verify: a response prints to stdout with the existing public prefix and no
     Twitch `PRIVMSG` path exists in this slice.
   - Pitfalls: do not request new Twitch OAuth scopes for sending messages.

5. Add deterministic tests for the app wiring.
   - What to change: use fake Twitch readers or a fake adapter to drive the main
     agent path without live Twitch or network.
   - Why now: CI must prove the runtime bridge without credentials.
   - Affects: app tests, CLI tests, config tests.
   - Verify: chat perception reaches the store and a fake LLM response reaches
     the console router.
   - Pitfalls: do not test private implementation details such as task names.

6. Add a short operator example.
   - What to change: document or add an example config for chat-only Twitch
     runtime with console output.
   - Why now: operators need a safe command before local models are installed.
   - Affects: examples and docs.
   - Verify: the example clearly says no public Twitch messages are sent.
   - Pitfalls: do not include real credentials in files.

## Acceptance criteria

- [ ] `adapter: twitch` can construct and inject a Twitch source adapter in the main runtime.
- [ ] A chat-only Twitch runtime path can be tested without audio/video model dependencies.
- [ ] Chat `RawEvent` values become normal chat perceptions in the main perception store.
- [ ] The existing agent loop can react and print to console through the public console router.
- [ ] No Twitch chat messages are sent by this slice.
- [ ] Missing Twitch chat credentials fail clearly only when Twitch chat is enabled.
- [ ] Existing non-Twitch configs remain valid.
- [ ] Automated tests require no live Twitch, OAuth token, OpenRouter call, or local model download.

## Blocked by

None - can start immediately.

## User stories addressed

- User story 1
- User story 2
- User story 17
- User story 19
- User story 20
- User story 30
- User story 31
- User story 32
