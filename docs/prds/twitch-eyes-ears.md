# PRD — Twitch Eyes and Ears for Minnarone

## Problem Statement

Minnarone oggi ha gia' il core di reazione, il `SourceAdapter` astratto, il
perception store, i perceiver audio/video/chat e il wiring dell'agente. Manca
pero' il pezzo che lo renda simile al progetto originale descritto nel
transcript: una sorgente reale capace di guardare una live Twitch, leggere la
chat, estrarre audio e campionare video, senza passare dalla cattura generica
del sistema operativo.

L'utente vuole costruire gli "occhi e orecchie" di Minnarone: una pipeline di
input live che produca eventi grezzi coerenti con i contratti esistenti e che,
nel tempo, possa essere arricchita con ASR, diarizzazione e captioning reali.
Il primo valore da ottenere non e' ancora "Minnarone capisce tutto"; e' "il
framework si collega davvero a Twitch, produce eventi live per chat/audio/video,
li espone tramite il port esistente e permette di ispezionare sample grezzi".

Il rischio principale e' mescolare troppe responsabilita' in una volta sola:
Twitch IRC, Streamlink, FFmpeg, ASR, VLM, LLM, output chat e loop completo
dell'agente. Questo PRD separa l'adapter di sorgente dai backend di percezione
reali, cosi' il lavoro resta testabile e incrementale.

## Solution

Costruire un adapter Twitch dietro il port esistente `SourceAdapter`.
L'adapter pubblico sara' unico dal punto di vista dell'applicazione:
`TwitchStreamAdapter`. Internamente sara' composto da tre reader separati e
testabili:

- chat reader: legge messaggi Twitch IRC autenticati in modalita' read-only;
- audio reader: usa Streamlink e FFmpeg per estrarre chunk PCM mono 16 kHz;
- video reader: usa Streamlink e FFmpeg per estrarre frame JPEG a bassa
  frequenza.

Il core dell'agente non deve sapere nulla di Twitch, Streamlink, FFmpeg, IRC o
OAuth. Deve continuare a ricevere solo `RawEvent` etichettati per canale:

```python
RawEvent(channel="chat", payload={"text": "...", "speaker": "username"}, ts=...)
RawEvent(channel="audio", payload=AudioChunk(samples=pcm_bytes, sample_rate=16000, source_label="stream", ts=...), ts=...)
RawEvent(channel="video", payload=VideoFrame(pixels=jpeg_bytes, source_label="stream", ts=...), ts=...)
```

Questo snippet e' incluso perche' e' il contratto chiave della feature: definisce
il confine tra adapter Twitch e core Minnarone. Non e' un'implementazione, ma la
shape decisionale degli eventi.

Il primo milestone deve includere uno smoke script manuale, separato dal CLI
principale, che avvia la cattura Twitch per un tempo limitato, salva percezioni
chat testuali, salva un numero limitato di sample audio/video grezzi e produce
statistiche finali. L'integrazione nel CLI principale arrivera' dopo che lo
smoke e' stabile.

## User Stories

1. As an operator, I want to provide a Twitch channel name, so that Minnarone can observe that live stream.
2. As an operator, I want Minnarone to read Twitch chat, so that chat messages enter the same perception flow used by the existing reactor.
3. As an operator, I want chat reading to be authenticated but read-only at first, so that the same credentials can later support output without sending messages now.
4. As an operator, I want Twitch chat messages to preserve the sender name, so that later reactions can target the right person.
5. As an operator, I want Minnarone to extract live audio from Twitch, so that ASR can be attached in a later milestone.
6. As an operator, I want audio chunks to be normalized to mono 16 kHz PCM, so that future ASR backends can consume a predictable format.
7. As an operator, I want Minnarone to extract live video frames from Twitch, so that VLM captioning can be attached in a later milestone.
8. As an operator, I want video frames to be sampled at a low configurable frequency, so that the capture does not waste CPU, disk or model calls.
9. As an operator, I want chat, audio and video to share one adapter lifecycle, so that starting and stopping Twitch capture is one operation.
10. As an operator, I want failures in one channel not to immediately kill the others, so that chat can still work if stream audio/video is unavailable.
11. As an operator, I want the smoke run to print per-channel counts, so that I can see which pieces are actually producing data.
12. As an operator, I want the smoke run to save a few raw audio chunks, so that I can inspect whether FFmpeg produced valid PCM.
13. As an operator, I want the smoke run to save a few raw video frames, so that I can inspect whether FFmpeg produced usable images.
14. As an operator, I want the smoke run to write chat perceptions to a JSONL file, so that I can verify the existing perception store contract end to end.
15. As an operator, I want the smoke run to have a fixed duration, so that a debug command does not run forever by accident.
16. As an operator, I want credentials to come from environment variables, so that secrets are not committed in config files.
17. As an operator, I want the Twitch channel and capture knobs to live in config/CLI options, so that they are session settings rather than secrets.
18. As a developer, I want Twitch-specific logic hidden behind `SourceAdapter`, so that OS-level and browser-level capture can be added later without changing the agent core.
19. As a developer, I want the public adapter to be one object but internally composed of readers, so that each reader can be tested in isolation.
20. As a developer, I want IRC parsing tested without real Twitch, so that CI remains deterministic.
21. As a developer, I want process handling tested without real Streamlink or FFmpeg, so that lifecycle behavior is covered without network dependencies.
22. As a developer, I want the adapter to launch subprocesses without shell interpolation, so that channel names and tokens cannot become shell injection vectors.
23. As a developer, I want a bounded event queue, so that a slow consumer cannot let live capture grow memory forever.
24. As a developer, I want overflow behavior to be explicit and counted, so that dropped events are visible in smoke statistics.
25. As a developer, I want the first milestone to avoid heavy Twitch bot libraries, so that the adapter has a small dependency surface.
26. As a developer, I want Streamlink and FFmpeg treated as system prerequisites, so that the runtime path matches the operator's terminal environment.
27. As a developer, I want the adapter to normalize OAuth tokens with or without the `oauth:` prefix, so that setup is forgiving.
28. As a developer, I want configuration validation to fail clearly for missing Twitch channel or credentials, so that setup errors are actionable.
29. As a developer, I want the first milestone to avoid real ASR/VLM, so that adapter correctness is not blocked by model selection.
30. As a developer, I want later ASR/VLM work to plug into the existing `Vad`, `Asr`, `SpeakerTagger` and `Captioner` protocols, so that the adapter does not become a model pipeline.
31. As a maintainer, I want the existing tests to stay green, so that adding Twitch capture does not regress OS-capture abstractions or fake adapters.
32. As a maintainer, I want the PRD to preserve the ports-and-adapters boundary, so that Twitch does not leak into `Agent`, `Senser`, `Reactor` or `PromptBuilder`.
33. As a maintainer, I want the smoke script to be manual rather than part of CI, so that CI does not depend on Twitch availability, OAuth credentials or live channels.
34. As a future operator, I want the same design to allow OS-level capture later, so that Minnarone can observe local applications when Twitch is not the source.
35. As a future operator, I want the same design to allow browser-level capture later, so that a browser tab can become the source without changing reaction logic.

## Implementation Decisions

- Use ports and adapters. Twitch capture is an adapter behind the existing source port. The core agent consumes `RawEvent` only.
- Build one public `TwitchStreamAdapter`, internally composed of three deep modules: a chat reader, an audio reader and a video reader.
- Do not create three separate public adapters for the first milestone. The application-facing unit is "watch this Twitch channel".
- Use Twitch IRC for chat. Authenticate with bot username and OAuth token, but do not send chat messages in this milestone.
- Use Streamlink and FFmpeg as external system tools for live stream extraction. They are prerequisites, not Python package dependencies.
- Do not introduce a heavy Twitch library for the first milestone. Use standard-library async networking for IRC unless a later need justifies a library.
- Use `streamlink` to resolve/read the Twitch stream and FFmpeg to extract audio/video streams into simple pipe formats.
- Audio payloads emitted by the adapter are `AudioChunk` values with PCM signed 16-bit little-endian bytes, mono, 16 kHz, `source_label="stream"`.
- Video payloads emitted by the adapter are `VideoFrame` values with JPEG bytes and `source_label="stream"`.
- The first adapter milestone does not distinguish streamer speech from video playback speech. Everything extracted from Twitch audio is labeled as stream-origin audio. Speaker tagging and diarization are backend perception work.
- The adapter exposes `channels()` based on enabled channel flags. Expected channels are any enabled subset of `chat`, `audio` and `video`.
- The adapter owns an async queue of `RawEvent` objects. Reader tasks publish to that queue; `events()` consumes from it.
- The queue is bounded. If it overflows, the adapter records dropped-event counts. Prefer preserving chat events over raw media events when deciding what to drop, because chat is already textual and low volume.
- Failure is isolated per reader. If chat fails, audio/video may continue. If video fails, chat/audio may continue. A complete setup failure is reported clearly.
- The smoke command exits successfully if at least one channel produced events and exits non-zero if no channel produced events or required configuration is invalid.
- Provide a smoke artifact writer that saves:
  - a perception JSONL file for chat messages;
  - a limited set of raw PCM audio chunks;
  - a limited set of raw JPEG video frames;
  - a JSON stats file with counts and failures.
- The smoke script is intentionally separate from the main agent CLI at first. It validates capture without also involving LLM calls, the reactor, output routing or model backends.
- Add a future-facing Twitch config shape without forcing full CLI integration in the first slice:

```yaml
adapter: twitch
twitch:
  channel: nomecanale
  quality: best
  chat: true
  audio: true
  video: true
  audio_chunk_seconds: 1.0
  video_fps: 1.0
```

This snippet is included because it is the configuration contract the later CLI
integration should converge toward.

- Credentials are environment variables:
  - `TWITCH_BOT_USERNAME`
  - `TWITCH_OAUTH_TOKEN`
- The token may be supplied with or without `oauth:` and should be normalized internally.
- Keep `OPENROUTER_API_KEY` unrelated to the smoke. The capture smoke must not require an LLM key.
- Add an optional `twitch` extra only if packaging needs a named feature switch. It should not pull heavy libraries by default.
- Document system prerequisites explicitly: `streamlink` and `ffmpeg` must be installed and available on `PATH`.

## Step-by-Step Implementation Plan

1. Define the Twitch adapter boundaries.
   - What to change: introduce the public Twitch source adapter and the internal reader concepts.
   - Why now: every later step depends on a stable lifecycle and event contract.
   - Affects: source adapter workflow, channel naming, queue semantics.
   - Verify: the adapter can be instantiated with chat/audio/video flags and reports the correct channel set.
   - Pitfalls: do not import or reference Twitch from the core source port; keep Twitch-specific code at the adapter edge.

2. Implement IRC message parsing as a pure module.
   - What to change: parse Twitch IRC `PRIVMSG` lines and IRC tags into a small chat event representation.
   - Why now: parsing is deterministic and should be correct before networking exists.
   - Affects: chat reader contract.
   - Verify: lines with tags, display names, escaped tag values and plain usernames produce the expected text and speaker.
   - Pitfalls: do not let raw IRC protocol text leak into `RawEvent` payloads; preserve the displayed or login username consistently.

3. Implement the Twitch chat reader with fakeable I/O.
   - What to change: connect to Twitch IRC, authenticate, join a channel, reply to ping and publish chat events.
   - Why now: chat is the fastest path to real perceptions because it is already text.
   - Affects: chat reader lifecycle and adapter queue.
   - Verify: with a fake stream/socket, the reader authenticates, joins, handles `PING`, parses `PRIVMSG` and stops cleanly.
   - Pitfalls: keep it read-only; do not send `PRIVMSG` output in this milestone.

4. Implement subprocess process management for media readers.
   - What to change: add a small process runner abstraction for launching and stopping Streamlink/FFmpeg pipelines.
   - Why now: audio and video readers both need robust subprocess lifecycle handling.
   - Affects: reader internals, cleanup, error reporting.
   - Verify: fake process objects can simulate stdout bytes, process exit and cancellation.
   - Pitfalls: pass arguments as lists, never through shell strings; ensure `stop()` terminates child processes.

5. Implement the audio reader.
   - What to change: use Streamlink/FFmpeg to produce fixed-duration PCM chunks and wrap each chunk in an audio payload.
   - Why now: audio is one of the two main "ears" inputs, and the payload contract already exists.
   - Affects: audio reader, `RawEvent(channel="audio")` production.
   - Verify: fake stdout bytes are chunked into `AudioChunk` values with sample rate 16 kHz, source label `stream` and increasing timestamps.
   - Pitfalls: do not run ASR here; this reader only captures normalized audio bytes.

6. Implement the video reader.
   - What to change: use Streamlink/FFmpeg to produce JPEG frames at the configured FPS and wrap each frame in a video payload.
   - Why now: video is the "eyes" input, and later captioning depends on reliable frame extraction.
   - Affects: video reader, `RawEvent(channel="video")` production.
   - Verify: fake frame bytes are emitted as `VideoFrame` values with source label `stream` and timestamps.
   - Pitfalls: do not caption frames here; this reader only captures sampled frame bytes.

7. Compose readers inside the public adapter.
   - What to change: make `TwitchStreamAdapter.start()` create reader tasks and `stop()` cancel them and close resources.
   - Why now: individual readers exist and can be composed behind one source adapter.
   - Affects: `SourceAdapter` implementation, queue behavior, per-channel degradation.
   - Verify: fake readers produce events through a single async `events()` stream and stop cleanly.
   - Pitfalls: avoid task leaks; cancellation must not leave FFmpeg/Streamlink processes running.

8. Add explicit stats and failure state.
   - What to change: track produced counts, dropped counts, reader failures and final stop reason.
   - Why now: smoke testing live streams needs diagnostics beyond pass/fail.
   - Affects: adapter observability and smoke artifact writer.
   - Verify: simulated reader failures are reflected in stats while other readers continue.
   - Pitfalls: do not convert every transient reader failure into a full adapter failure unless all readers are dead.

9. Build the smoke artifact writer.
   - What to change: consume `RawEvent` values and write chat perceptions, limited audio samples, limited video frames and stats.
   - Why now: the adapter needs a manual validation path before main CLI integration.
   - Affects: smoke workflow, output directory structure.
   - Verify: a fake event stream creates `perceptions.jsonl`, `raw/audio`, `raw/video` and `stats.json`.
   - Pitfalls: cap saved raw files; a live stream can generate unbounded data.

10. Add the manual smoke script.
    - What to change: create a command that accepts channel, duration, output directory and optional channel toggles.
    - Why now: the smoke writer and adapter are ready for manual execution.
    - Affects: examples/manual tooling.
    - Verify: running with fake or disabled channels handles missing settings clearly; real run instructions are documented.
    - Pitfalls: do not require `OPENROUTER_API_KEY`; the smoke is capture-only.

11. Extend configuration modeling for future integration.
    - What to change: add a Twitch-specific config section or parsing path that can validate channel, quality and channel flags.
    - Why now: the smoke can use CLI flags initially, but the main app needs a durable config shape.
    - Affects: configuration schema and examples.
    - Verify: valid Twitch config loads; missing channel or invalid durations fail with clear errors.
    - Pitfalls: do not make Twitch fields required for existing `os_capture` configs.

12. Document setup and manual verification.
    - What to change: document `streamlink`, `ffmpeg`, Twitch username/token, channel config and smoke command.
    - Why now: the feature depends on external tools and credentials.
    - Affects: operator guide.
    - Verify: a developer can read the docs and know exactly what to install and export.
    - Pitfalls: do not document tokens in files; keep secrets in environment variables.

13. Preserve the existing quality gate.
    - What to change: ensure all new code passes the current quality and test commands.
    - Why now: the repo now has a pre-commit quality hook and should stay clean.
    - Affects: all new modules and tests.
    - Verify: automated unit tests pass; quality checks pass.
    - Pitfalls: live Twitch smoke must not be part of automated tests.

14. Defer main agent integration until smoke is trusted.
    - What to change later: wire `adapter: twitch` into the reference app so `Agent.run()` can receive Twitch events.
    - Why later: capture must be debugged independently before adding LLM/reaction complexity.
    - Affects later: app builder and CLI runtime.
    - Verify later: a fake Twitch adapter can drive `Agent.run()` end to end before live credentials are used.
    - Pitfalls: do not make the main app require Twitch credentials when using non-Twitch adapters.

## Testing Decisions

Good tests for this feature verify external behavior at module boundaries. They
should not assert private task names, exact subprocess implementation details or
the real output of Twitch, Streamlink or FFmpeg. Live integration is useful, but
it belongs in manual smoke runs rather than CI.

- Test IRC parsing as pure behavior: raw IRC lines in, normalized chat event out.
- Test OAuth normalization: tokens with and without `oauth:` produce the same auth string.
- Test chat reader behavior with fake async I/O: authentication, join, ping/pong, message parsing and stop.
- Test media process runner behavior with fake processes: stdout reading, non-zero exits, cancellation and cleanup.
- Test audio reader behavior with fake byte streams: chunk sizing, `AudioChunk` metadata and event emission.
- Test video reader behavior with fake frame streams: frame boundaries, `VideoFrame` metadata and event emission.
- Test `TwitchStreamAdapter` composition with fake readers: enabled channel set, event queue, per-channel failure isolation and clean stop.
- Test queue overflow behavior: dropped counts are recorded and the adapter does not grow memory unbounded.
- Test smoke artifact writer with fake `RawEvent` streams: chat JSONL, raw PCM files, raw JPEG files and stats JSON.
- Test config parsing for Twitch fields without requiring Twitch credentials.
- Reuse prior art from the repo: fake source adapters, contract tests for audio/video perceivers, app wiring tests and capture adapter boundary tests.
- Do not run real Twitch, Streamlink, FFmpeg, OAuth or live network in automated tests.

## Out of Scope

- Real ASR backend implementation.
- Real VAD backend implementation.
- Real speaker diarization or streamer-vs-video speaker tagging.
- Real VLM or captioning backend implementation.
- Sending messages to Twitch chat.
- Full main CLI integration of `adapter: twitch` into the running agent.
- OS-level capture.
- Browser-level capture.
- Twitch EventSub, subscriptions, raids, follows or other structured Twitch events.
- Bandwagon behavior.
- TUI changes beyond using existing observability concepts.
- CI tests that require live Twitch, valid credentials, Streamlink or FFmpeg.

## Further Notes

- The first useful manual command should prove capture, not cognition. Seeing
  chat perceptions and raw media samples on disk is success for milestone one.
- The transcript tolerates imperfect perception. Audio transcription can be
  noisy later as long as it gives the reactor enough semantic signal. This PRD
  therefore prioritizes reliable source capture and clean event contracts over
  model quality.
- The design keeps OS-level and browser-level capture viable. They can become
  separate adapters behind the same source port, with different internals but
  identical `RawEvent` output.
- Security matters even in a local tool: launch external commands without shell
  interpolation, do not log OAuth tokens and do not write secrets into smoke
  artifacts.
- If future model backends need arrays instead of bytes, conversion should live
  in backend-specific adapters for `Asr` or `Captioner`, not in the Twitch source
  adapter.
