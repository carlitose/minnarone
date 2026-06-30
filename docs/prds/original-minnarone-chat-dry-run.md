## Problem Statement

Minnarone now has the local Twitch perception skeleton: chat, audio, and video
can be converted into textual perceptions, the existing Senser/Reactor loop can
consume those perceptions, and the live TUI can show what the runtime is doing.
The next missing step is behavioral: the current commentator stance explains
the stream to the local operator, while the original Minnarone behaved like a
Twitch chat participant and generated the exact chat message it would have
posted.

The operator wants to recreate that original behavior, but only as a local
dry-run for now. Minnarone should write comments in the style of the original
Minnarone prompt shown in the screenshots: informal Twitch Italian, short,
context-aware, no AI/bot disclosure, explicit continuity with previous
conversations, and the two-line `RE`/`MSG` response format. The output must be
visible in console/TUI, but it must not be sent to Twitch chat.

The current prompt has useful safety and observability infrastructure, but it
does not yet copy the original prompt structure, does not pass the agent's own
recent messages into the prompt, and does not normalize the LLM's `RE`/`MSG`
response into a stable TUI/console display.

## Solution

Add an opt-in local "original chat dry-run" commentator style. In this style,
Minnarone still runs in private/local mode, but the prompt asks the LLM to act
as Minnarone the Twitch chat user, not as an operator-facing explainer. The
runtime should generate the same kind of message the original Minnarone would
have sent to chat, then show both `RE` and `MSG` in the TUI/console.

The feature should preserve the existing operator-commentary style. The new
style is selected explicitly by configuration, so existing `commentator.enabled`
runs keep their current "commenta per l'operatore" behavior unless the operator
opts into the original-chat style.

The prompt should be rebuilt around the screenshot structure:

- stable system prefix with Twitch-chat persona and behavior rules;
- permanent memory from `soul` and `facts`;
- dynamic current situation with short-term memory, recent chat, audio/video
  perceptions, and recent Minnarone messages;
- response format requiring exactly `RE` and `MSG`;
- trigger-specific situation text at the bottom, so the immediate instruction
  remains salient.

The output path should add a small deep module that parses and normalizes the
LLM response into a stable result with `reason`, `message`, and `end_conv`
fields. The TUI/console should display both lines. When the model chooses
`MSG: #end_conv`, the runtime should show that decision as a skipped message and
close the relevant conversation window, instead of silently hiding it.

Seed memory files should be added for local use so the prompt is not empty.
`soul` should describe Minnarone's persona. `facts` should describe the current
channel/streamer facts from the screenshots as a starting point. Automatic fact
authoring from the live stream remains out of scope.

## User Stories

1. As an operator, I want Minnarone to generate messages like the original Twitch bot, so that the new runtime can be evaluated against the original behavior.
2. As an operator, I want this behavior to be local-only, so that no experimental output is sent publicly to Twitch.
3. As an operator, I want to choose the original-chat style explicitly, so that the existing operator-commentary behavior remains available.
4. As an operator, I want the TUI to show both `RE` and `MSG`, so that I can see what Minnarone is responding to and what it would have written.
5. As an operator, I want `MSG: #end_conv` to be visible as a skip decision, so that I can understand why Minnarone decided not to speak.
6. As an operator, I want `#end_conv` to still close the conversation window, so that the conversation state behaves like the original design.
7. As an operator, I want the prompt to copy the original screenshot structure, so that prompt debugging and behavior tuning start from the proven Minnarone shape.
8. As an operator, I want the prompt to keep the trigger-specific instruction at the bottom, so that the LLM focuses on the immediate situation.
9. As an operator, I want recent chat, audio, and video perceptions included, so that messages can reference what is happening live.
10. As an operator, I want the current short-term summary included, so that Minnarone can keep continuity across longer sessions.
11. As an operator, I want Minnarone's own recent messages included, so that it avoids repeating the same joke or point.
12. As an operator, I want seed `soul` and `facts` memory, so that the first run has personality and channel context.
13. As an operator, I want facts to remain manually authored for now, so that the runtime does not invent durable memory.
14. As an operator, I want the original-chat style to remain Italian, so that it matches the original Minnarone examples.
15. As an operator, I want the prompt to include Twitch emote guidance, so that Minnarone uses Twitch-native expressions instead of generic emoji.
16. As an operator, I want Minnarone to avoid assistant-like phrasing, so that messages read like chat comments.
17. As an operator, I want Minnarone to avoid forced enthusiasm and fake social-manager tone, so that comments stay natural.
18. As an operator, I want Minnarone to avoid revealing it is a bot or AI in this style, so that the dry-run matches the original prompt.
19. As an operator, I want the prompt to recognize misspellings of Minnarone's name, so that audio/chat noise does not prevent reactions.
20. As an operator, I want the LLM to be allowed to not answer, so that Minnarone does not force bad messages.
21. As an operator, I want the console path to show the same normalized `RE`/`MSG` shape as the TUI, so that non-TUI debugging is usable.
22. As an operator, I want prompt captures to show the exact original-chat prompt, so that I can inspect and tune the model input.
23. As an operator, I want prompt caching preserved where possible, so that long runs do not become unnecessarily expensive.
24. As an operator, I want the stable prefix to stay stable across turns with the same config and memory, so that provider caching can work.
25. As an operator, I want only dynamic stream context to change per turn, so that prompt diffs are understandable.
26. As a developer, I want output normalization isolated behind a small interface, so that malformed LLM responses can be tested without live OpenRouter.
27. As a developer, I want prompt style selection isolated from Twitch capture, so that the feature can be tested with fake perceptions.
28. As a developer, I want existing operator-commentary tests to keep passing, so that this feature does not regress current behavior.
29. As a developer, I want original-chat prompt tests to assert section order and key instructions, so that later prompt edits do not accidentally erase important behavior.
30. As a developer, I want the Reactor to pass recent self messages into prompt building, so that the prompt, not only the dedup gate, has access to conversational continuity.
31. As a developer, I want `#end_conv` handling to remain coordinated with the Senser, so that output normalization does not bypass conversation-window state.
32. As a developer, I want the dashboard state to remain read-only, so that rendering `RE`/`MSG` cannot mutate runtime behavior.
33. As a developer, I want no live Twitch, model downloads, or OpenRouter calls in automated tests, so that CI remains deterministic.
34. As a maintainer, I want the new config field to reject unknown values clearly, so that invalid styles fail early.
35. As a maintainer, I want local seed memory documented, so that future operators know what `soul` and `facts` are responsible for.
36. As a future operator, I want the public Twitch output boundary to stay closed, so that enabling original-chat dry-run does not accidentally become public bot mode.

## Implementation Decisions

- Add an explicit commentator style with at least two values: the current
  operator-facing style and the new original-chat dry-run style.
- The original-chat style requires private/local output mode. It must not
  create a Twitch send path, require chat write scopes, or call any public
  output adapter.
- Preserve the current operator-commentary prompt as the default behavior for
  existing commentator configs.
- Add an original-chat prompt renderer inside the prompt-building boundary
  rather than branching in the TUI or output router. The prompt is a reaction
  concern, not a presentation concern.
- Keep the existing anti-injection fence around perceived content. The original
  screenshots did not include this exact fence, but the current runtime already
  has it and it protects the prompt against chat/audio/video injection.
- The original-chat stable prefix should include the screenshot-derived rules:
  Minnarone is a Twitch chat user, writes one Italian chat message, uses
  informal lowercase Twitch language, stays pertinent to what is happening now,
  maintains continuity, avoids assistant tone, does not reveal bot/AI status,
  handles name misspellings, uses Twitch emotes sparingly, and avoids repeating
  itself.
- The permanent memory section should be populated from the existing `soul` and
  `facts` memory abstraction. `soul` describes Minnarone. `facts` describes the
  streamer/channel and any durable known context.
- Seed memory should be copied as local starting content from the screenshots.
  It is a bootstrap artifact, not an auto-memory system.
- The dynamic situation should include the current channel, short-term memory,
  recent chat, recent audio/video perceptions, and recent Minnarone messages.
- The Reactor should pass recent self messages to prompt building. These
  messages already exist for deduplication; the prompt needs them for continuity
  and anti-repetition.
- The output contract for original-chat LLM responses is:

```text
RE: <what Minnarone is responding to, 3-6 words>
MSG: <the chat message> or #end_conv
```

  This small contract is included because it is the key behavioral boundary
  between the LLM and the local TUI/console display.

- Add a dedicated output normalizer for this contract. It should accept small
  formatting deviations, preserve both lines for display, and identify
  `#end_conv` as a control decision.
- The TUI and console should show both `RE` and `MSG` for original-chat output.
  They should not strip `RE`.
- If the normalized message is `#end_conv`, display it as a skipped decision,
  for example with a clear `(skip)` marker, and close the relevant conversation
  window when an interlocutor exists.
- Human typing delay and near-duplicate suppression still apply to real
  messages. The implementation should be careful not to suppress the visibility
  of `#end_conv` decisions in original-chat debug output.
- Prompt observation should continue to capture the exact prompt sent to the LLM
  after redaction, including the new original-chat sections.
- No browser UI, public Twitch send path, or auto-memory should be introduced
  by this PRD.

## Step-by-Step Implementation Plan

1. Define the commentator style configuration.
   - What to change: extend the commentator configuration with an explicit style
     field that defaults to the current operator-facing behavior and accepts the
     new original-chat value.
   - Why this comes first: the rest of the work needs a stable switch that can
     be tested without changing existing runtime behavior.
   - Affects: configuration schema, config validation, examples, operator docs.
   - Verify: old configs without a style still load and produce the current
     prompt; invalid style values fail with a clear config error.
   - Pitfalls: do not make all private/commentator runs use the new prompt
     automatically.

2. Define the original-chat prompt contract.
   - What to change: write a durable prompt contract from the screenshots:
     stable persona rules, permanent memory, current situation, recent chat,
     audio/video perceptions, recent self messages, response format, and
     trigger-specific situation.
   - Why this comes now: implementation and tests need a precise target before
     adding branches to the builder.
   - Affects: prompt-building interface and prompt tests.
   - Verify: a design-level test fixture can describe the expected sections and
     section order before model integration.
   - Pitfalls: do not copy dynamic example content from screenshots as fixed
     runtime text; only copy the reusable rules and structure.

3. Add recent self messages to the prompt-building input.
   - What to change: allow prompt building to receive a bounded list of
     Minnarone's own recent normalized outputs.
   - Why this comes before the prompt renderer: the original screenshot prompt
     explicitly includes previous Minnarone messages for continuity and
     anti-repetition.
   - Affects: Reactor-to-prompt interface, prompt builder tests, fake Reactor
     tests.
   - Verify: a fake prior Minnarone message appears in the dynamic original-chat
     prompt and does not alter the stable prefix.
   - Pitfalls: do not put self-history in the cacheable prefix, and do not
     expose unbounded history.

4. Implement the original-chat prompt rendering path.
   - What to change: when the selected style is original-chat, render the
     screenshot-inspired prompt instead of the operator-commentary prompt.
   - Why this comes after the inputs are ready: the renderer needs memory,
     summary, recent perceptions, trigger, and self-history.
   - Affects: prompt builder behavior and prompt observation output.
   - Verify: unit tests assert the prompt contains the original sections in
     order, includes key behavior rules, keeps memory sections, keeps the
     trigger instruction last, and preserves anti-injection fences for perceived
     content.
   - Pitfalls: avoid making the stable prefix depend on timestamps, recent
     perceptions, trigger reason, summary, or self-history.

5. Split recent perception rendering by role.
   - What to change: render recent chat, audio transcription, and video captions
     in labels that match the original prompt vocabulary rather than one generic
     conversation block.
   - Why this comes after the first renderer: start with correct behavior, then
     improve readability and screenshot fidelity.
   - Affects: prompt formatting helpers.
   - Verify: fake chat/audio/video perceptions appear in the expected dynamic
     sections, and the trigger perception is not duplicated in a confusing way.
   - Pitfalls: do not drop non-chat perceptions; the value of this mode depends
     on multimodal context.

6. Add seed memory for local operation.
   - What to change: create local seed memory content for Minnarone's identity
     and channel facts, based on the readable screenshot material.
   - Why this comes now: prompt rendering can work without memory, but behavior
     quality needs a non-empty starting point.
   - Affects: local runtime workspace, examples, docs.
   - Verify: the local config resolves to non-empty `soul` and `facts`, and the
     prompt includes both in permanent memory.
   - Pitfalls: do not treat seed facts as automatically true forever; they are a
     starting point for the operator to edit.

7. Define the `RE`/`MSG` normalization interface.
   - What to change: add a small deep module that converts raw LLM text into a
     structured response with `reason`, `message`, `end_conv`, and display text.
   - Why this comes before wiring it into the Reactor: the parser is easy to
     test in isolation and should not be tangled with output routing.
   - Affects: output normalization contract and tests.
   - Verify: tests cover exact two-line output, extra spaces, lowercase labels,
     missing `RE`, missing `MSG`, extra prose, and `MSG: #end_conv`.
   - Pitfalls: do not make the parser brittle; LLMs occasionally add whitespace
     or preambles.

8. Wire normalization into original-chat reactions only.
   - What to change: after the LLM completes, normalize the response when the
     selected style is original-chat; keep other styles unchanged.
   - Why this comes after isolated parser tests: Reactor changes are riskier and
     should use a proven boundary.
   - Affects: Reactor finalization, HumanLikeness handoff, output routing,
     event recording.
   - Verify: fake LLM `RE/MSG` output reaches the output router in normalized
     display form; operator-commentary output remains unchanged.
   - Pitfalls: do not normalize summarizer responses; this applies only to
     reaction prompts, not short-term memory generation.

9. Preserve and display `#end_conv` decisions.
   - What to change: when normalized output has `message == #end_conv`, close
     the relevant conversation window and route a visible skipped decision to
     local TUI/console.
   - Why this comes after normal routing: it is a special case of the normalized
     output contract.
   - Affects: Reactor/Senser coordination and dashboard-visible output.
   - Verify: fake `MSG: #end_conv` closes the window, shows a skipped
     `RE/MSG` decision locally, and does not appear as a public chat send.
   - Pitfalls: the existing HumanLikeness behavior may drop empty/end-conv
     messages; original-chat debug visibility must be preserved deliberately.

10. Render original-chat output in TUI and console.
    - What to change: ensure the local output stream and console output preserve
      both normalized lines exactly enough for debugging.
    - Why this comes after Reactor wiring: the display should consume the
      normalized output, not reparse raw LLM text.
    - Affects: output sink, console router behavior, dashboard panel rendering.
    - Verify: dashboard state and TUI tests show both `RE` and `MSG` in the
      `MINNARONE` panel.
    - Pitfalls: avoid duplicating `[PRIVATE]` inside the TUI panel; TUI should
      stay clean.

11. Update local config and operator docs.
    - What to change: document the new style, local-only safety boundary,
      memory files, expected `RE/MSG` display, and how `#end_conv` appears.
    - Why this comes near the end: docs should reflect the implemented behavior
      and tested command surface.
    - Affects: README/operator handoff/examples.
    - Verify: docs explain that original-chat dry-run still sends nothing to
      Twitch.
    - Pitfalls: do not imply public Twitch posting is available or safe.

12. Run focused automated verification.
    - What to change: run prompt, config, Reactor, dashboard, app wiring, and
      CLI tests affected by the new style.
    - Why this comes last: the feature crosses prompt construction, runtime
      wiring, and display.
    - Affects: local test workflow.
    - Verify: existing tests remain green, new original-chat tests cover the new
      contracts, and no test requires live Twitch/OpenRouter/local models.
    - Pitfalls: do not add flaky live acceptance tests to CI.

13. Run a manual dry-run acceptance session.
    - What to change: start a bounded local TUI run with original-chat style
      enabled and inspect the prompt tab plus `MINNARONE` panel.
    - Why this is last: the behavior is qualitative and needs live context after
      unit/integration safety is established.
    - Affects: operator workflow only.
    - Verify: the prompt matches the screenshot-derived structure, the panel
      shows `RE` and `MSG`, no Twitch message is sent, and at least one message
      references current live context.
    - Pitfalls: do not judge this solely by a single LLM answer; inspect prompt,
      perceptions, and output together.

## Testing Decisions

- Good tests should verify external behavior at module boundaries: config
  parsing, prompt text shape, normalized output contract, Reactor routing,
  dashboard state, and CLI wiring. They should not assert private helper names,
  task scheduling, or exact live model prose.
- Prompt tests should use fake memory and fake perceptions. They should assert
  section order, stable-prefix invariance, presence of key screenshot-derived
  instructions, dynamic placement of summary/perceptions/self-history, and
  trigger-specific instruction at the bottom.
- Config tests should verify default compatibility, valid original-chat style,
  invalid style errors, and the requirement that original-chat dry-run remains
  local/private.
- Output normalizer tests should be pure unit tests. Cover exact format,
  whitespace, missing labels, extra text, multiline messages, and `#end_conv`.
- Reactor tests should use fake LLM and fake output router. They should prove
  original-chat responses are normalized, both lines are routed locally, and
  `#end_conv` closes windows while remaining visible as a skip decision.
- Dashboard tests should use fake state/output streams and assert the
  `MINNARONE` panel displays `RE` and `MSG` without requiring Textual.
- TUI tests should remain construction/rendering smoke tests with fake
  dashboard state. Do not require a real terminal.
- App wiring tests should prove the selected style reaches the prompt builder
  and reaction path without live Twitch credentials, model downloads, or
  OpenRouter network calls.
- Operator docs tests, if present, should check that the docs mention local-only
  output, no Twitch sending, seed memory, and the `RE/MSG` display.
- Prior art in the codebase includes prompt builder tests, config tests, Reactor
  tests, dashboard snapshot tests, dashboard TUI smoke tests, app wiring tests,
  prompt observation tests, and Twitch operator docs tests.

## Out of Scope

- Sending messages to Twitch chat.
- Adding a Twitch write/output adapter.
- Requesting Twitch send scopes or moderating public output.
- Auto-generating durable `facts` from live stream content.
- Auto-updating `soul` or cross-session memory.
- Rewriting Senser trigger logic beyond what is necessary to display and close
  `#end_conv` decisions correctly.
- Implementing bandwagon as a non-LLM shortcut.
- Changing ASR, VLM, speaker diarization, video sampling, or perception queue
  behavior.
- Pixel-perfect reproduction of the screenshots.
- Browser UI or overlay UI.
- Live Twitch/OpenRouter/model-backed CI tests.

## Further Notes

The new style is intentionally a dry-run. It should produce "what Minnarone
would have written" while the output layer still guarantees local-only
visibility. That boundary is the main safety property of this PRD.

The original screenshots are a prompt reference, not immutable production copy.
Where the current runtime has stronger safety behavior, such as treating
perceived content as untrusted data, keep the stronger behavior unless it
directly prevents reproducing original Minnarone behavior.

The seed `soul` and `facts` content should be useful but modest. The operator
can edit it as the runtime is tested on different channels. The implementation
should make missing memory degrade gracefully, but the local default should no
longer be empty.

The prompt should preserve cacheability: stable rules and permanent memory at
the top, dynamic situation below, and trigger instruction last. This matches
the original design rationale and keeps long live sessions cost-conscious.
