# YouTube Live media via Chrome and OS capture

## Type

Decision

## Status

Accepted by the product owner on 2026-08-03. This decision supersedes the
media-source selection and policy gate in the earlier
[adapter/media decision](youtube-live-adapter-media-decision.md); that document
remains the historical result of ticket 02.

## Context

The YouTube chat path uses the official API, but Minnarone still needs local
`AudioChunk` and `VideoFrame` inputs for Twitch-equivalent perception. The
repository already has a production `os_capture` path:

- `soundcard` captures the system output loopback and emits mono 16 kHz PCM;
- `mss` captures a configured monitor and emits sampled screen frames;
- device sources open lazily, so `--check` remains offline and touches no
  hardware;
- the existing audio/video perceivers, bounded work queue, artifact caps, and
  diagnostics are shared.

The product owner chose visible Chrome playback plus local OS capture and does
not want YouTube policy review to block the technical plan. This document
records that product decision without making a legal or platform-approval
claim.

## Decision

1. The operator opens the target YouTube Live in a visible Chrome window and
   starts playback manually.
2. Minnarone captures the selected monitor through the existing screen source
   and the default system output through the existing audio loopback source.
3. YouTube chat remains a platform-specific API reader. Chat, OS audio, and OS
   video are composed as single-channel readers in one
   `MergingSourceAdapter`, with chat as the priority channel.
4. The first implementation captures a full monitor. It does not control
   Chrome, install an extension, use CDP, or use `chrome.tabCapture`.
5. Direct YouTube media extraction with Streamlink, yt-dlp, manifests, FFmpeg,
   or PyAV is not part of this path.
6. The existing top-level `os_capture` configuration is reused alongside
   `adapter: youtube`; no duplicate YouTube-specific monitor/audio settings are
   introduced.

## Target configuration

Conceptually:

```yaml
adapter: youtube

youtube:
  video_id: abcDEF123_-
  chat: true

os_capture:
  audio: true
  video: true
  audio_chunk_seconds: 1.0
  video_fps: 1.0
  monitor: 1
```

Ticket 04 owns the exact `youtube` schema. Ticket 05 adds the optional
`os_capture` companion block and rejects an enabled media path when its local
perceiver/backend is unavailable.

## Data flow

```text
YouTube API chat ──────────────────────────────> chat RawEvent

Chrome visible player ─> system output loopback ─> AudioChunk ─> audio RawEvent
                     └─> selected monitor ───────> VideoFrame ─> video RawEvent

chat/audio/video RawEvent ─> MergingSourceAdapter ─> existing perceivers
```

Chrome is not a runtime dependency or controlled process. It is an
operator-managed source of pixels and system sound.

## Goals

- Reach full YouTube shadow perception without a new media downloader.
- Reuse `OsCaptureConfig`, lazy device sources, `AudioChunk`, `VideoFrame`,
  ASR/speaker/VLM, merge/backpressure, and diagnostics.
- Keep chat productive when audio or video is silent or fails, and keep media
  productive when chat fails.
- Preserve offline `--check`, bounded queues, bounded artifacts, and attended
  operator setup.

## Non-goals

- Chrome automation, a Chrome extension, tab-only capture, or browser startup.
- Streamlink/yt-dlp/manifest playback and remote media decoding.
- Automatic installation or configuration of BlackHole on macOS.
- Cropping a browser window or suppressing notifications in the first version.
- Public chat send, OAuth write, live promotion, or ticket 07 behavior.
- Claiming that browser playback, loopback, or screen capture is universally
  available on every OS/hardware configuration.

## Semantic invariants

- `adapter: youtube` starts in shadow and cannot construct a sender in ticket
  05.
- `--check` validates configuration and wiring without opening Chrome,
  `soundcard`, `mss`, an API connection, or a model.
- Chat/audio/video each enter the merger as a single-channel `SourceAdapter`.
- Chat remains the merger priority; saturated queues drop media before chat and
  expose per-channel counters.
- Audio remains mono 16 kHz PCM with `source_label="system"`; it must not be
  mislabeled as the local streamer microphone.
- Video remains sampled `VideoFrame` input from the configured monitor.
- A failed or silent media channel does not stop healthy chat. A failed chat
  channel does not prevent local audio/video cleanup.
- Shutdown closes readers and bounded perception workers exactly once within
  the existing cleanup timeouts.
- Twitch and standalone `adapter: os_capture` behavior remain unchanged.

## Failure modes

| Condition | Expected result |
| --- | --- |
| Chrome is closed, paused, or showing another page | Chat may continue; media becomes silent, static, or describes the visible replacement content. |
| Wrong monitor selected | Diagnostic smoke exposes unexpected/empty frames; operator corrects `os_capture.monitor`. |
| Screen Recording permission missing on macOS | Video smoke fails or produces black frames with an actionable diagnostic. |
| BlackHole/default output not configured on macOS | Audio smoke reports zero/silent chunks while chat and video remain independently testable. |
| Audio or video backend/model missing | Config/build fails closed for the enabled channel; `--check` does not install or download it. |
| Media producer or perceiver is slower than input | Existing bounded queues drop media and expose counters; memory does not grow without bound. |
| YouTube chat fails | The failure is recorded without leaking credentials; OS media readers still clean up normally. |
| Full-monitor capture includes unrelated windows or notifications | Operator uses a dedicated monitor/profile; artifacts remain bounded and are deleted manually when no longer needed. |

## Security and local data

Full-monitor capture can observe notifications, other applications, and private
content that appears on that display. The operator should use a dedicated
monitor or clean desktop, disable notifications, keep the run attended, and
inspect/delete `perceptions.jsonl`, prompts, screenshots, summaries, and debug
artifacts after the bounded run. Existing secret redaction and artifact limits
must not be weakened.

## Alternatives

### Chrome extension with `tabCapture`

Deferred. It can isolate one tab's audio/video after a user gesture, but adds an
extension, browser permissions, a local bridge, and another lifecycle. Create a
separate prototype ticket only if full-monitor capture is operationally
insufficient.

### Direct media extraction

Not selected. It introduces a second downloader/decoder path although the
repository already owns OS capture and local perception.

### Broadcaster-provided pre-YouTube feed

Still possible later, but unnecessary for the first attended local shadow path.

## Implementation slices

1. Extend the YouTube config/wiring from ticket 04 to accept the existing
   top-level `os_capture` block.
2. Expose or reuse the existing lazy OS audio/video reader construction without
   nesting a multi-channel `OsCaptureAdapter` inside another merger.
3. Compose YouTube chat plus the enabled single-channel OS readers in one
   `MergingSourceAdapter` with chat priority.
4. Reuse existing audio/video perceiver construction, bounded perception queue,
   diagnostics, smoke CLI, and artifact writer.
5. Add a sanitized full-shadow example and an operator guide for visible
   Chrome, monitor selection, permissions, BlackHole, isolated smoke commands,
   and attended shutdown.

## Verification strategy

- Unit: configuration combinations, unknown fields, required backends, lazy
  construction, and no sender/write credential.
- Simulated integration: fake YouTube chat plus synthetic `AudioChunk` and
  `VideoFrame` through merge, perceivers, queue pressure, partial failures, and
  cleanup.
- Regression: all Twitch and standalone OS-capture tests remain green.
- Manual/HITL: operator opens Chrome, then runs bounded chat/audio/video smokes
  separately before the combined shadow run. Hardware observation belongs to
  ticket 08 and is not fabricated by AFK tests.

## Remaining questions

- Whether full-monitor capture is sufficiently precise in normal operation. If
  not, investigate Chrome `tabCapture` in a separate prototype.
- Which monitor and audio routing the operator will use on the acceptance
  machine; these are runtime selections, not new config formats.
