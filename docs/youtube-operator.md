# YouTube Live chat-only shadow

This guide covers the first production YouTube path: one explicit live video,
read-only chat ingestion, the existing `ChatPerceiver`, and candidate reactions
shown locally as `[SHADOW]`. It has no OAuth, no sender, no insert endpoint, and
no audio or video. Chrome/player media capture belongs to the later full-shadow
ticket.

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
