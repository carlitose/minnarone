# YouTube Live adapter and media boundary decision

## Type

Decision

## Status

Accepted as the candidate internal architecture on 2026-08-02. This decision
does not authorize or select a YouTube media-capture implementation.

## Context

Minnarone's core already consumes platform-neutral `RawEvent` values and has a
neutral bounded `MergingSourceAdapter`. Twitch media classes, however, accept a
Twitch channel, normalize it, construct a Twitch URL/quality, and own media
opening/processing. Adding YouTube by copying that stack would duplicate
lifecycle and cleanup; renaming those contracts “generic” would hide their
Twitch semantics.

The [platform research](../research/youtube-live-platform-contract.md) found a
supported chat-only path but no official raw viewer-media API. YouTube policy
blocks the proposed non-API playback/separated audio-video route until every
applicable clause is resolved by YouTube/compliance, or a different authorized
source is selected.

The [offline prototype](../prototypes/youtube-live-adapter-boundary.md) compared
specific duplicated readers with a typed media source/opener. Both preserved
event shapes, merge priority, failure isolation, and cleanup. The typed branch
also rejected arbitrary URLs and concentrated media ownership at one deep seam.

## Decision

1. Keep YouTube target normalization, discovery, lifecycle, chat transport,
   authentication, cursor/pacing, and message normalization platform-specific.
2. Reuse `SourceAdapter`, `RawEvent`, `MergingSourceAdapter`, `AudioChunk`,
   `VideoFrame`, perceivers, and bounded queues unchanged.
3. If and only if an authorized second media source exists, introduce a typed,
   validated resolved-media descriptor plus an injected opener at the deepest
   open/read/close boundary. It must not accept arbitrary URLs, configurable
   commands, or shell strings.
4. Do not generalize Twitch config, channel types, discovery, chat readers,
   sender, token guards, router, public-send policy, or operator wording merely
   to accommodate YouTube.
5. Do not implement a YouTube playback resolver under the present policy
   evidence. Chat-only development is independent and may proceed through its
   own human and credential gates.

## Goals

- One neutral stream of canonical chat/audio/video events.
- Preserve bounded backpressure with chat priority.
- Isolate a failed channel and close every resource once.
- Make the media authorization/capture edge explicit and fakeable.
- Keep platform identities, credentials, and lifecycle semantics honest.

## Non-goals

- YouTube playback/capture, Streamlink, yt-dlp, FFmpeg, or PyAV selection.
- Live chat sending or OAuth account selection.
- Multi-platform sessions or channel aggregation.
- Compatibility aliases or production migration in this ticket.
- Generalization of perception, prompting, reaction, or storage.

## Contract

Conceptually:

```text
platform resolver(validated target, media kind, quality)
  -> ResolvedMediaSource

media opener.open(ResolvedMediaSource)
  -> readable + closable media resource

neutral media reader(resource)
  -> RawEvent(channel="audio", payload=AudioChunk)
   | RawEvent(channel="video", payload=VideoFrame)
```

The descriptor is a capability/result of validation, not an operator-supplied
locator. It carries a typed media kind, a safe resource identity, a bounded
quality choice, and only the metadata the opener needs. Any real provider
implementation constructs fixed URL/argv details internally after platform and
policy checks.

YouTube chat does not pass through this port. It is a separate reader because
its video/chat discovery, API key/OAuth split, resume tokens, pacing, event
types, and errors are YouTube contracts.

## Semantic invariants

- `SourceAdapter` remains unaware of Twitch, YouTube, URLs, credentials, and
  processes.
- Each injected reader exposes exactly one mapped channel.
- Queue capacity remains bounded; a priority chat event may evict media, while
  media never evicts chat.
- One reader failure is recorded and does not stop productive sibling readers.
- `start()` is idempotent; `stop()` is safe before/after start; each owned media
  resource closes once within the cleanup bound. A completed stop permits a
  clean later start, and a failed open does not latch a half-started reader.
- Audio payloads remain `AudioChunk`; video payloads remain `VideoFrame`; text
  chat remains compatible with `ChatPerceiver`.
- No credential, raw token, arbitrary URL, shell string, or operator-configured
  command crosses the media port.
- A synthetic or technically functional opener never clears an external policy
  or consent gate.

## Failure modes

| Failure | Required result |
| --- | --- |
| Invalid target/URL form | Reject before discovery or media resolution. |
| Resolver cannot produce an authorized source | Media channel unavailable; chat may continue. |
| Media open/decode fails | Record that channel failure, clean up, preserve healthy siblings. |
| Queue full | Drop media before priority chat and increment per-channel stats. |
| Cleanup hangs | Apply existing bounded cleanup and surface the failure. |
| Chat lifecycle/auth/quota fails | Use YouTube-specific classification; never substitute a media or write credential. |
| Policy status unresolved | Do not construct a production YouTube media resolver. |

## Security and data

- Resolve from a validated YouTube video ID for chat; never silently retarget a
  persistent live page.
- Read/shadow uses no write credential. OAuth send capability remains absent
  until its own ticket and human gates.
- A future opener receives structured data, never a shell command.
- Media and chat retention/deletion obligations remain explicit; this boundary
  does not imply persistence is permitted.
- Chat stable IDs are needed for resume/dedup/self-echo, but the current
  `ChatPerceiver` discards them. A later chat/sender design must address that
  loss without broadening this media decision.

## Alternatives

### Duplicate YouTube-specific readers

Rejected as the target architecture. It is explicit and safe for a throwaway
tracer, but repeats audio/video start, stop, open, error, and cleanup behavior.
It remains an acceptable temporary implementation only if no second authorized
media source ever exists and no shared production seam is justified.

### Pass raw media URLs to generic readers

Rejected. It expands the capture surface, weakens platform validation, and
makes policy/scheme/host allow-listing an implicit reader responsibility.

### Rename Twitch contracts as generic

Rejected. `TwitchAudioReader`, `TwitchVideoStreamOpener`,
`StreamlinkFfmpegPipeline`, channel normalization, Twitch URL construction, and
`audio_only` still encode Twitch behavior.

## Future implementation slices

1. Implement chat-only YouTube target/discovery/read adapter behind existing
   `MergingSourceAdapter`; preserve stable external IDs at the appropriate
   adapter/event seam.
2. Run the bounded read-only HITL smoke and settle account/project/target,
   quota, deletion, and derived-data compliance gates.
3. If a media source is authorized, write a production spec for the typed
   descriptor/opener and migrate one Twitch seam with regression tests before
   adding a second provider.
4. Add YouTube media only after the exact source and policy determination are
   recorded. Otherwise keep the YouTube adapter chat-only.
5. Address public-send safety, identity, consent, self-echo, and metadata
   persistence in their dedicated tickets.

## Verification strategy

- Unit: target/source validation, typed kind/quality, rejection of URL/command
  strings, idempotent lifecycle, payload type checks.
- Simulated integration: resolver → opener → neutral reader → merge → canonical
  events; partial failure, bounded queue priority, and cleanup.
- Regression: existing Twitch merge/audio/video tests when a production seam is
  eventually changed.
- Live/manual: chat read smoke in ticket 03. Media requires its external policy,
  consent, environment, and source gates first; simulation cannot substitute.

## Unresolved questions and gates

- Effective OAuth channel/Brand Account identity and public-send consent model.
- Exact live-chat quota costs, numeric text limit, and cursor lifetime where
  official documentation remains silent.
- Compliance interpretation of LLM-derived output from YouTube API chat data.
- Authorized non-YouTube viewer-media source, or a YouTube/compliance decision
  resolving every applicable media-policy clause.
