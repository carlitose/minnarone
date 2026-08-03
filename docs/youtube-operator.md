# YouTube Live shadow

This guide covers two production-safe rehearsal paths for one explicit live
video. Chat-only shadow uses read-only chat ingestion and the existing
`ChatPerceiver`; the optional full shadow adds local audio and screen
perception from a visible Chrome player. Candidate reactions remain local as
`[SHADOW]`. The chat-only configuration has no OAuth, no sender, no insert
endpoint, and no audio or video.

The contract follows the ticket-01 platform research and the bounded ticket-03
read smoke: `videos.list(part=liveStreamingDetails)` resolves the ephemeral
`activeLiveChatId`; `liveChatMessages.list` advances with `nextPageToken` and
waits at least the returned `pollingIntervalMillis` before the next request.

## Prerequisites and API key

Create or select a Google Cloud project, enable **YouTube Data API v3**, and
create an API key under **APIs & Services → Credentials**. Restrict the key to
YouTube Data API v3 and apply an appropriate application restriction for the
machine when possible. Put it only in a local gitignored `.env`:

```dotenv
YOUTUBE_API_KEY=your-local-read-key
```

Do not put the key in YAML, commands, screenshots, tickets, logs, fixtures, or
run artifacts. The read path does not accept an OAuth token, refresh token,
service account, or write scope. An API key can read public live chat but cannot
publish a message.

The cloud-console key options do not change Minnarone's runtime shape:

- **API restriction:** select YouTube Data API v3.
- **Application restriction:** use the restriction supported by the machine
  and deployment; do not disable an existing restriction merely to make a
  smoke pass.
- **OAuth consent screen / OAuth client:** not needed for this chat-only ticket.
- **Service account:** not used and not a YouTube public chat identity.

## Configuration

Copy [`examples/youtube-chat-shadow.example.yaml`](../examples/youtube-chat-shadow.example.yaml)
to a local workspace and replace the synthetic `video_id` with the exact
11-character ID selected by the operator. Supported `https://youtu.be/<id>`,
`https://youtube.com/watch?v=<id>`, and `https://youtube.com/live/<id>` inputs
are normalized once; channel pages, search, arbitrary URLs, and automatic
retargeting are rejected.

```yaml
mode: public
adapter: youtube
youtube:
  video_id: abcDEF123_-
  max_results: 500
  max_retries: 3
  retry_base_seconds: 1.0
  retry_max_seconds: 30.0
  dedup_capacity: 4096
  request_timeout_seconds: 10.0
disclosure:
  announce_ai: true
commentator:
  profiles:
    original_chat: {}
```

The `youtube` section is strict. It has no `send`, OAuth, audio, or video
field. `max_results` follows the documented 200–2000 range. The dedup window is
bounded and keyed by `(liveChatId, messageId)`; it does not deduplicate equal
text or display names.

## Validate and run

Validate construction first:

```bash
uv run python -m minnarone path/to/youtube.local.yaml --check
```

`--check` is offline and lazy: it validates the config, local memory/prompts,
and presence of `YOUTUBE_API_KEY`, but it does not call YouTube, discover a
chat, or prove quota/network availability. Start an attended console or TUI
shadow run only after that succeeds:

```bash
uv run python -m minnarone path/to/youtube.local.yaml
uv run python -m minnarone path/to/youtube.local.yaml --tui
```

Console candidates have the `[SHADOW]` prefix. Under the TUI they appear with
the same marker in the `MINNARONE` panel and do not leak through stdout. No
configuration in this ticket can promote them or construct a sender.

Stop with `Ctrl-C`. Server pacing waits are interruptible. Requests have a
finite timeout and temporary/rate failures use bounded, jittered exponential backoff;
quota or authentication failures stop fail-closed rather than rotating keys or
falling back to a future write credential.

## Full multimodal shadow via Chrome and OS capture

The full path keeps YouTube chat on the API reader and obtains media from a
visible Chrome window that the operator opens, positions, and starts manually.
Chrome is **operator-managed**: Minnarone does not start or control the browser,
install an extension, attach through CDP, or capture a tab directly. The first
version is **full-monitor** capture, so use a dedicated monitor or a clean
desktop and disable notifications.

Install the capture and perception extras needed by the selected local models:

```bash
uv sync --extra os-capture --extra audio --extra vlm --extra tui
```

Copy
[`youtube-full-shadow.example.yaml`](../examples/youtube-full-shadow.example.yaml)
to a gitignored local workspace. Set the same explicit `youtube.video_id` used
for the chat rehearsal, then set only the existing top-level `os_capture`
block:

```yaml
adapter: youtube
youtube:
  video_id: abcDEF123_-
os_capture:
  audio: true
  video: true
  audio_chunk_seconds: 1.0
  video_fps: 1.0
  monitor: 1
```

Audio remains mono PCM 16 kHz with `source_label="system"`; video remains a
sampled `VideoFrame` from the configured monitor. The existing
VAD/ASR/speaker and VLM perceivers consume those payloads, and their bounded
work queue exposes processed, dropped, failed, cancelled, and cleanup counts.
The `youtube` block does not duplicate monitor, fps, chunk, model, or media
settings.

### Prepare the visible player

1. Open the exact target in visible Chrome and start playback manually.
2. Put Chrome on the dedicated monitor selected by `os_capture.monitor`.
3. On macOS, grant the terminal **Screen Recording** permission. Restart the
   terminal after changing the permission if the OS asks for it.
4. Route YouTube audio through the system output that capture observes.
   Windows and Linux can expose native output loopback. macOS has no native
   SoundCard loopback: configure an operator-managed virtual device such as
   **BlackHole** before the run. Minnarone does not install or configure it.
5. Keep the run attended. Anything shown on that monitor can enter local
   artifacts and prompts.

### Bounded capture-only smoke tests

Run audio and video separately before starting models or the agent. These
`minnarone-oscapture-smoke` commands are capture-only: **no LLM** and **no
sender** are constructed. Duration and raw artifacts are capped explicitly.

```bash
uv run minnarone-oscapture-smoke \
  --duration 30 \
  --output ./.smoke/youtube-os-audio \
  --audio \
  --audio-chunk-seconds 1.0 \
  --max-audio-samples 3
```

```bash
uv run minnarone-oscapture-smoke \
  --duration 30 \
  --output ./.smoke/youtube-os-video \
  --video \
  --video-fps 1.0 \
  --monitor 1 \
  --max-video-frames 3
```

Inspect `stats.json`, at most three `raw/audio/*.pcm` samples, and at most
three `raw/video/*.jpg` frames. These smokes prove only local raw capture; they
do not prove YouTube API access, ASR, speaker attribution, VLM captions, or the
combined runtime.

### Validate and run full shadow

Validation remains offline and lazy with respect to YouTube, Chrome,
`soundcard`, `mss`, and local model loading:

```bash
uv run python -m minnarone path/to/youtube-full-shadow.local.yaml --check
```

The check validates configuration, local paths and wiring; it does not open an
API connection, a browser, or a capture device, and it does not prove that the
selected model/device will initialize on the first media event. Then run the
attended shadow:

```bash
uv run python -m minnarone path/to/youtube-full-shadow.local.yaml --tui
```

Every candidate remains `[SHADOW]`; this path has no sender or live promotion.
Stop with `Ctrl-C`. Reader/device and perception-worker cleanup is bounded; if
a channel is stuck or slow, inspect merger failures and queue cleanup counters
before the next run.

### Silence and black-frame diagnosis

| Symptom | Check |
| --- | --- |
| Audio `silenzio` / zero chunks | Confirm Chrome is playing through the selected default output. On macOS verify BlackHole routing, then rerun only the audio smoke. |
| `frame neri` or empty video | Confirm `monitor`, Screen Recording permission, and that Chrome is visible on that display; rerun only the video smoke. |
| Wrong/private pixels captured | Stop immediately, move Chrome to a dedicated monitor, clear the bounded run/smoke artifacts, and restart deliberately. |
| Chat failure with healthy media | Inspect the YouTube lifecycle outcome/key/quota; local media shuts down independently. |
| Media/model failure with healthy chat | Inspect source-merger and perception-queue diagnostics for the named channel; chat can continue. |
| Growing drops | Reduce `video_fps`, increase sampling, or choose a faster local model; do not remove queue/artifact bounds. |

This path does not use Streamlink, yt-dlp, media URLs/manifests,
FFmpeg/PyAV playback, shell commands, browser extensions, CDP, or
`chrome.tabCapture` for YouTube media.

## Lifecycle outcomes

The reader keeps these states distinct in diagnostics/tests:

| Outcome | Meaning and response |
| --- | --- |
| `video_absent` | The explicit `videos.list` target was not returned; stop. |
| `live_not_started` | The selected broadcast is scheduled/offline; stop this run and retry deliberately later. |
| `live_ended` | `actualEndTime` or `liveChatEnded`; close normally and never reuse the old chat ID. |
| `chat_disabled` | A started live has no active chat or the API reports it disabled; stop. |
| `no_messages` | A paced page contained no supported text events; this is silence, not a network failure. |
| `auth_failed` | The API key/project restriction was rejected; stop and inspect the local Cloud setup. |
| `quota_exhausted` | Daily quota is unavailable; stop until reset/operator action. Do not rotate projects or keys. |
| `rate_limited` / `temporary_failure` | Retry only within the configured bound, then stop. |

Only `textMessageEvent` becomes a canonical `RawEvent(channel="chat")`.
Minnarone carries the public display name plus stable message/author/chat IDs
at the adapter boundary, then the existing `ChatPerceiver` stores only the
text and speaker used by the current core. Profile-image URLs and raw Google
payloads do not enter prompts or perceptions.

## Authority, disclosure, and artifacts

A public YouTube live does not authorize public send. Reconfirm authority for
the exact target before each rehearsal. This read-only decision also does not
authorize a later OAuth identity or message insertion. Those remain separate
attended gates.

Use an honest AI disclosure for any future public Minnarone channel/profile.
`disclosure.announce_ai: true` keeps the local prompt stance explicit, but it is
not evidence that a public profile or creator agreement exists.

Shadow still processes audience data. A run can contain `perceptions.jsonl`,
summaries, `debug/prompts/`, and `debug/events.jsonl`, including chat text and
derived copies. `retention.perceptions_days` is reserved/inert: it performs no
automatic deletion. Keep runs purpose-bound and gitignored. After authority is
withdrawn, an opt-out/deletion request arrives, the key is exposed, or the data
is no longer needed:

1. stop every reader;
2. remove/rotate the key in Google Cloud Console and delete its local `.env`
   value when appropriate;
3. perform manual deletion of the complete affected local run directory and
   any derived copies;
4. do not publish raw runs, prompts, names, IDs, or API responses as evidence.

For this ticket, safe durable evidence is limited to aggregate counts, outcome
names, bounded timing, and redacted diagnostics.
