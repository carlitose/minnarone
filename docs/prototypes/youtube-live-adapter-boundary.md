# YouTube Live adapter/media boundary prototype

**Date:** 2026-08-02

**Status:** disposable offline spike; no production behavior

## Question

What is the smallest boundary that lets a future YouTube Live adapter produce
the existing chat, audio, and video `RawEvent` shapes while preserving merge,
backpressure, cleanup, and per-channel failure isolation?

## Branches exercised

1. **Specific readers:** duplicate YouTube-specific chat/audio/video reader
   lifecycles and compose them directly with `MergingSourceAdapter`.
2. **Typed media source:** keep discovery/chat YouTube-specific, but resolve
   audio/video to a validated `ResolvedMediaSource` consumed by a neutral media
   reader and injected opener.

## Assumptions

- All events, media, IDs, and streams are synthetic.
- The 11-character target validation is a prototype input constraint, not an
  official promise that YouTube will never change its identifier format.
- A typed source tests an internal design only. It does not establish that a
  YouTube media resolver is permitted or available.

## Useful result

Both branches preserve the existing `SourceAdapter` and `RawEvent` contract,
but the typed media-source branch removes repeated media lifecycle/opening code
without making discovery or chat falsely generic. It rejects raw URLs at the
media opener and keeps the validated platform target upstream.

**Candidate decision:** keep YouTube discovery and chat platform-specific;
reuse `MergingSourceAdapter`, `AudioChunk`, `VideoFrame`, perceivers, and bounded
queue behavior unchanged; introduce a deep typed media source/opener boundary
only when a policy-approved second media source exists. Do not implement a
YouTube playback resolver now.

## Run it

From the repository root:

```bash
uv run python -m spike.youtube_live_adapter_boundary.demo
uv run pytest spike/youtube_live_adapter_boundary/test_prototype.py
```

Observed on 2026-08-02:

- demo exited `0`, reported `offline: true`, three canonical channels for both
  branches, one start/stop per reader, and every synthetic stream closed;
- `28 passed` for the focused test suite;
- isolated Ruff lint and format checks passed;
- no network, browser, subprocess, credential, or live-media dependency is
  imported by the prototype module.

## Synthetic trace

| Channel | `RawEvent.payload` | Shape observed | Existing consumer boundary |
| --- | --- | --- | --- |
| `chat` | `dict` | `text`, `speaker`, plus synthetic message/author/chat IDs | `ChatPerceiver` accepts the text/speaker pair. |
| `audio` | `AudioChunk` | mono-style synthetic bytes, 16 kHz, `source_label="youtube"` | Existing audio event/type contract. |
| `video` | `VideoFrame` | synthetic pixel bytes, `source_label="youtube"` | Existing video event/type contract. |

The extra chat IDs deliberately survive the adapter boundary, but the current
`ChatPerceiver` persists only text and display speaker. Stable message and
author IDs are therefore lost downstream. This is real self-echo/dedup friction
for a future sender, not something this prototype changes.

## Exercised behavior

| Behavior | Specific readers | Typed media source |
| --- | --- | --- |
| Canonical chat/audio/video shapes | Passed | Passed |
| Idempotent start/stop | One start and one stop per reader | One start and one stop per reader |
| Stop before start | Safe; first later run succeeds | Safe; first later run succeeds |
| Restart after completed stop | Second three-channel run succeeds | Second run opens fresh streams and succeeds |
| Cleanup after natural completion/stop | All reader stops observed | All reader stops and stream closes observed |
| Video open/read failure | Failure recorded; chat/audio continue | Resolver/opener failure recorded; chat/audio continue |
| One-time media open failure | Not an opener boundary in this branch | Failed start leaves no latched state; next run succeeds |
| Chat failure | Failure recorded; audio/video continue | Failure recorded; audio/video continue |
| Empty audio channel | Normal completion; chat/video continue | Normal completion; chat/video continue |
| Queue size `1` | Chat kept; media dropped | Chat kept; media dropped |
| Raw URL at media boundary | Not applicable; reader owns platform target | Rejected by descriptor and opener |
| Network/process/browser/credentials | None | None |

For both branches, the queue-pressure run produced one chat event, dropped zero
chat events, and dropped media. This behavior comes from the unchanged
`MergingSourceAdapter(priority_channels=("chat",))`, not from branch-specific
queue code.

## Alternative comparison

| Axis | Specific readers | Typed media source |
| --- | --- | --- |
| Cohesion | Platform behavior is obvious, but audio/video repeat the same lifecycle. | Discovery remains at the platform edge; media open/read/close is one deeper module. |
| Testability | Simple fakes, but every platform repeats failure and cleanup tests. | Resolver, opener, and neutral reader can be falsified independently. |
| Safety | Each reader can validate its own target, but multiple constructors can drift. | Only a validated descriptor crosses the opener; URL and shell strings are not part of the port. |
| Cleanup | Works, with repeated implementations. | One ownership point for the readable media resource. |
| Duplication | Highest: lifecycle plus open/read/error mapping per audio/video reader. | Lower at the deep media seam; platform discovery/chat are intentionally not shared. |
| Premature generality | Low naming risk, high copied behavior. | Controlled if limited to the resolved source/opener; high if platform config/discovery is also generalized. |
| Policy implication | None; fake only. | None; a successful fake opener is not approval for YouTube media. |

## Candidate interface

The spike used this conceptual shape:

```python
resolver.resolve(validated_target, media_kind, quality) -> ResolvedMediaSource
opener.open(resolved_source) -> readable_and_closable_media
neutral_reader(resolved_source, opener) -> RawEvent(audio | video)
```

`ResolvedMediaSource` carries safe identifiers, a typed media kind, and a safe
quality token. It carries neither an arbitrary URL nor a shell command. A real
resolver remains responsible for policy, platform target validation, and the
fixed implementation details required to obtain bytes.

This seam is intentionally below `SourceAdapter`: callers and perceivers still
see only `RawEvent`, and the platform adapter still owns which channels exist
and how discovery/chat authentication works.

## Concrete production impact

The disposition below is intentionally exact. “Future extraction” is gated and
is not an instruction to edit production in this ticket.

| File / contract | Disposition | Exact consequence |
| --- | --- | --- |
| `src/minnarone/source.py` — `SourceAdapter`, `RawEvent` | Leave unchanged | Both branches already satisfy this neutral port. |
| `src/minnarone/merge.py` — `MergingSourceAdapter`, `MergeStats` | Leave unchanged | Reuse bounded queue, priority, failure isolation, stats, and cleanup. |
| `src/minnarone/audio.py` — `AudioChunk`, audio perceiver | Leave unchanged | YouTube audio, if ever authorized, emits the same payload. |
| `src/minnarone/video.py` — `VideoFrame`, video perceiver | Leave unchanged | YouTube video, if ever authorized, emits the same payload. |
| `src/minnarone/chat.py` — `ChatPerceiver` | Leave unchanged for chat-only tracer; later metadata decision required | It accepts text/speaker today but discards stable YouTube IDs needed by send/dedup. |
| `src/minnarone/twitch_media.py` — `MediaProcess`, `ProcessRunner` | Reuse contracts; no rename required | Structured argv and fakeable process ownership remain useful. |
| `src/minnarone/twitch_media.py` — `StreamlinkFfmpegPipeline` | Keep Twitch-specific now; future extraction after gate | Split Twitch target resolution/URL construction from process pump only when an authorized second source exists. |
| `src/minnarone/twitch_audio.py` — `TwitchAudioReader` | Keep Twitch-specific now; future consumer of deep port | Preserve `audio_only` and Twitch defaults; a later migration may inject a resolved source/pipeline. |
| `src/minnarone/twitch_video.py` — `TwitchVideoStreamOpener`, `StreamlinkVideoStreamOpener` | Keep Twitch-specific; future adapter to deep port | Their current `open(channel, quality)` and Twitch URL are not neutral contracts. |
| `src/minnarone/twitch_video.py` — `TwitchPyAvVideoReader`, `VideoFrameDecoder` | Keep reader wrapper/name; reuse decoder seam | A later migration may inject a typed source/opener without changing `VideoFrame`. |
| `src/minnarone/twitch_stream.py` — `TwitchStreamAdapter._build_readers` | Leave Twitch-specific | It remains the Twitch composition root and regression baseline. |
| `src/minnarone/config.py` — `TwitchConfig`, `TwitchSendConfig` | Leave unchanged | Create a separate YouTube section later; do not add ambiguous platform aliases. |
| `src/minnarone/app.py` — Twitch adapter construction/injection seams | Extend only in chat production ticket | Select a new YouTube adapter explicitly; do not route YouTube through Twitch config or credentials. |
| Future `src/minnarone/youtube_target.py` — `YouTubeVideoId` | Create in chat ticket | Normalize only supported ID/URL forms and never silently retarget. |
| Future `src/minnarone/youtube_discovery.py` — discovery/lifecycle port | Create in chat ticket | Resolve configured video to ephemeral live-chat ID with a fakeable API boundary. |
| Future `src/minnarone/youtube_chat.py` — `YouTubeLiveChatReader` | Create in chat ticket | Own stream/list resume, pacing, event typing, stable IDs, and read credential only. |
| Future `src/minnarone/youtube_stream.py` — `YouTubeStreamAdapter` | Create in chat ticket | Compose YouTube readers through unchanged `MergingSourceAdapter`. |
| Future `src/minnarone/media_source.py` — `ResolvedMediaSource`, `MediaSourceOpener` | Create only after media gate and second source | Typed safe descriptor/open/close seam; no raw URL, argv, or shell string in config. |

### Leave unchanged

- `src/minnarone/source.py`: `SourceAdapter` and `RawEvent` are already neutral.
- `src/minnarone/merge.py`: bounded merge, chat priority, stats, cleanup bounds,
  and per-channel failure isolation already satisfy both branches.
- `src/minnarone/audio.py`: `AudioChunk` and audio perceiver contracts.
- `src/minnarone/video.py`: `VideoFrame` and video perceiver contracts.
- perception store, reactor, prompts, LLM providers, and output routing.

### Keep platform-specific

- YouTube target normalization, video/chat discovery, lifecycle, page/resume
  tokens, pacing, message normalization, API key/OAuth capability separation,
  and all error mapping.
- Twitch channel normalization and Twitch URL construction.
- Twitch config, reader credentials, sender, router, token guards, TUI wording,
  and public-send policy until their own tickets define a safe shared contract.

### Generalize only after a real second source is authorized

- Separate Twitch target/URL resolution from the distributed media seams in
  `twitch_media.py`, `twitch_audio.py`, and `twitch_video.py`, as itemized in
  the matrix above.
- Let a future audio/video reader accept a typed resolved source and opener
  instead of a Twitch `channel` from which it constructs a URL.
- Preserve argv lists and injected process/open boundaries; never accept shell
  strings or operator-provided commands.
- Keep Twitch wrappers/names stable unless a production ticket explicitly
  authorizes migration.

### Future YouTube modules, chat first

- validated target and lifecycle discovery;
- streaming live-chat reader and REST fallback;
- a YouTube adapter that composes chat through `MergingSourceAdapter`;
- no media resolver until the policy gate in the
  [platform contract](../research/youtube-live-platform-contract.md) clears.

## Rejected directions

- **Rename Twitch classes to generic without changing their contracts:** the
  channel normalization, Twitch URL, `audio_only`, error text, and thread/process
  ownership remain Twitch-specific.
- **Pass an arbitrary URL to reusable readers:** expands the capture boundary,
  makes allow-listing harder, and permits URL/scheme drift.
- **Pass configurable argv or shell strings:** expands command execution and is
  unnecessary for platform reuse.
- **Implement Streamlink/yt-dlp for YouTube because the fake succeeded:** the
  prototype has no evidentiary value for YouTube policy or live compatibility.

## Gates and limits

- The prototype is simulated/local evidence only; no YouTube API, player,
  Streamlink, FFmpeg, PyAV, browser, token, or channel was exercised.
- YouTube-derived media remains blocked pending a YouTube/compliance
  determination resolving every applicable clause, or a separately authorized
  media source.
- Ticket 03 can now test chat-only read because its adapter boundary does not
  depend on media. It still requires a human-selected target/account/project and
  a bounded API-key smoke.
- Before any live sender, the chat metadata loss at `ChatPerceiver` and the
  identity/consent/derived-data gates require explicit design decisions.

The durable decision is recorded in
[`youtube-live-adapter-media-decision.md`](../specs/youtube-live-adapter-media-decision.md).
