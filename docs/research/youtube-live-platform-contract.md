# YouTube Live platform contract

**Research date:** 2026-08-02

**Scope:** public live discovery, live-chat read/write, OAuth, quota, lifecycle,
data policy, and viewer media. No credentials, API calls, playback, capture, or
public send were used.

## Direct answer

Minnarone can add a YouTube chat-only shadow path without giving the read side
permission to publish:

1. configure one explicit YouTube `video_id`, normalized from a supported
   watch/live/short URL;
2. resolve its current `activeLiveChatId` with
   [`videos.list`](https://developers.google.com/youtube/v3/docs/videos/list);
3. read text chat with
   [`liveChatMessages.streamList`](https://developers.google.com/youtube/v3/live/docs/liveChatMessages/streamList)
   using an API key, retaining its resume token and stable message/author IDs;
4. keep an OAuth credential with a write scope physically absent until a later,
   attended live-send feature is approved.

This does **not** provide Twitch-equivalent audio/video perception. The YouTube
Data and Live Streaming APIs expose metadata and broadcaster ingest management,
not raw viewer PCM or frames. The official IFrame Player API embeds and controls
playback, but does not expose those bytes. Although Streamlink can technically
open some public, unprotected YouTube live streams, the
[`YouTube API Services Developer Policies`](https://developers.google.com/youtube/terms/developer-policies)
contain several distinct restrictions. Prior written approval is named as an
exception for downloading/caching audiovisual content, but the separate
prohibitions on non-API access, separating audio/video, and background playback
do not state that general exception. Production YouTube media capture is
therefore **policy-blocked**, not selected.

## Requirement-to-decision matrix

| Area | Current platform fact | Minnarone decision | Confidence / gate |
| --- | --- | --- | --- |
| Target | `videos.list(part=liveStreamingDetails,id=...)` exposes `activeLiveChatId` only while a video is actively live and has live chat. | Canonical config target is an explicit `video_id`; URL forms are input conveniences only. | Supported by official API docs. |
| Discovery | `search.list` can find videos but is ambiguous and has a separate daily call bucket. `liveBroadcasts.list` lists broadcasts owned by the authorized user. | Do not make channel search the normal runtime path. A human selects the intended video. | Supported; scheduled-event automation remains out of scope. |
| Chat read | `streamList` pushes messages, orders them oldest to newest, and returns a token usable to resume. It accepts an API key or OAuth. | Prefer gRPC `streamList`; allow paced REST `list` only as a fallback. | Supported; real API smoke is ticket 03. |
| Chat normalization | Message IDs and author channel IDs are stable keys; display names are presentation. Deletes/bans are distinct event types, while some non-text events may update an existing ID. | P0 emits only `textMessageEvent` as chat text, carries stable IDs, and does not invent text for administrative events. A future general event store needs upsert semantics, not only a seen-ID set. | Contract supported; exact internal payload is a later production ticket. |
| Chat write | `liveChatMessages.insert(part=snippet)` requires a user OAuth token with `youtube` or `youtube.force-ssl`; an API key cannot write. | Separate read/shadow and send credentials/capabilities. No write scope in tickets 01-05. | Supported; identity and consent are HITL gates. |
| OAuth | Installed apps use a system browser plus loopback redirect and PKCE. OOB copy/paste is deprecated. Service accounts are not a YouTube channel identity. | Local installed-app flow only; secure token storage, scope verification, refresh/revocation, fail closed. | Supported; no OAuth flow was opened. |
| Quota | Default allocation is 10,000 units/day for the combined non-separated endpoints; `search.list` and `videos.insert` have separate 100-call/day buckets. Every request costs at least one and reset is midnight Pacific Time. | Budget discovery independently; prefer streaming over polling; stop/fall back on quota exhaustion. | Exact where the current table says so; live-chat method cost is undocumented. |
| Media | Data/Live Streaming APIs do not expose viewer PCM/frame streams. IFrame playback stays inside the YouTube player. | No production YouTube media resolver. A fake typed media boundary may still be prototyped. | Hard policy gate: a YouTube/compliance determination resolving every applicable clause, or a separately authorized source. |
| Data/policy | Clients must be honest about identity/actions, provide privacy/revocation/deletion controls, refresh or delete most stored API data within 30 days, and honor deletion promptly and within 7 days. | Explicit disclosure, purpose-bound storage, deletion path, no credentials in artifacts, and no dormant claim that retention is automated. | Supported; operator policy remains to be specified before live use. |

## Discovery and lifecycle contract

### Canonical target

The durable configured value should be a YouTube `video_id`. A resolver may
accept only explicitly recognized forms, such as `youtube.com/watch?v=<id>`,
`youtu.be/<id>`, and `youtube.com/live/<id>`, and normalize them before any API
boundary. Arbitrary URLs and channel names are not target identifiers.

For an arbitrary public target, request
`videos.list(part=liveStreamingDetails,snippet,status,id=<video_id>)`. Relevant
fields are documented on the
[`video` resource](https://developers.google.com/youtube/v3/docs/videos):

- `scheduledStartTime` describes a scheduled live;
- `actualStartTime` appears after the broadcast begins;
- `actualEndTime` appears after it ends;
- `activeLiveChatId` exists only while the broadcast is currently live and chat
  is available, and is removed after completion.

Consequences:

- scheduled or offline is a normal waiting state, not a malformed target;
- live with no `activeLiveChatId` means chat is absent/disabled/unavailable and
  must fail closed for chat ingestion;
- complete means stop, do not keep polling an old chat ID;
- a persistent channel live page can later point at a different video, so the
  original `video_id` must never silently retarget a session.

[`liveBroadcasts.list`](https://developers.google.com/youtube/v3/live/docs/liveBroadcasts/list)
is useful only for broadcasts belonging to the authenticated user. It is not a
general third-party discovery contract. An owner-side query for the current
live would use `broadcastStatus=active` and `broadcastType=all`; the latter
avoids the endpoint's `event` default excluding persistent broadcasts.
[`search.list`](https://developers.google.com/youtube/v3/docs/search/list)
may support an explicit discovery tool later, but its ambiguity, pagination,
event-type filters, and separate quota bucket make it a poor runtime default.

## Live-chat read contract

### Preferred transport

The official [streaming live-chat guide](https://developers.google.com/youtube/v3/live/streaming-live-chat)
recommends `liveChatMessages.streamList` over repeated REST polling. The gRPC
channel is `youtube.googleapis.com:443`. A request supplies the live chat ID,
selected parts, and optionally a prior page token. `maxResults` is supported
from 200 through 2,000, defaults to 500, and limits a response; the initial
history can contain fewer items and events older than that initial window are
not subsequently retrieved. The stream:

- accepts an API key or OAuth token;
- delivers an initial recent history and then new messages, oldest to newest;
- supplies `nextPageToken`, which is the resume point after a disconnect;
- reduces polling and quota pressure compared with REST.

Reconnect must reuse the last successfully committed token and tolerate
replayed items. Text ingestion deduplicates on `(liveChatId,
liveChatMessage.id)`; it must not deduplicate on text, timestamp, or display
name. A future all-event store needs upsert semantics because a `giftEvent` can
reuse an ID to update its combo count. Stable author identity is
`authorDetails.channelId` / `snippet.authorChannelId`.

The current gRPC status alone cannot reliably distinguish a chat that ended
from one that was disabled. On stream termination, re-read video/live-chat
state before classifying the lifecycle outcome.

### REST fallback

[`liveChatMessages.list`](https://developers.google.com/youtube/v3/live/docs/liveChatMessages/list)
returns `nextPageToken` and `pollingIntervalMillis`. The next request must use
that token and must not occur before the server-supplied interval. Faster
polling can return `rateLimitExceeded`. Backoff does not authorize polling
faster than the next advertised interval.

### Event mapping

The [`liveChatMessage` resource](https://developers.google.com/youtube/v3/live/docs/liveChatMessages)
uses typed events. For the first tracer bullet:

- accept only `textMessageEvent` into the textual chat perceiver;
- preserve message ID, author channel ID, published timestamp, and display name
  at the adapter boundary;
- treat `messageDeletedEvent` and `userBannedEvent` as administrative/tombstone
  events if/when observed, not fabricated utterances. The resource
  documentation warns that a tombstone is not emitted at deletion time, so the
  adapter cannot promise complete real-time retraction;
- count or diagnose unsupported types rather than flattening Super Chat,
  membership, polls, gifts, or moderation state into plain text.

An append-only local perception already emitted cannot honestly be described
as erased merely because YouTube later reports a deletion. Retention and
deletion of local/derived artifacts need a separate explicit operator path.

### Failure classification

The signal/error column below is the external fact documented by the live-chat
methods. The response column is a conservative Minnarone decision, not a claim
that YouTube mandates that exact local behavior.

| Platform signal or fact | Minnarone response (project decision) |
| --- | --- |
| `liveChatDisabled` | Stop/read no text; surface disabled, do not retry tightly. |
| `liveChatEnded` | End the channel normally and re-check video lifecycle. `chatEndedEvent` can arrive later and is absent for default broadcast chat, so it is not the sole end signal. |
| `liveChatNotFound` | Re-resolve from the configured video; never guess another chat. |
| Invalid/expired page token | Re-resolve conservatively; require replay-safe dedup. |
| `rateLimitExceeded`; REST also supplies `pollingIntervalMillis` | Respect server pacing and add bounded exponential backoff with jitter. |
| `quotaExceeded` / daily limit | Fail closed until quota reset or operator action; do not rotate projects/keys. |
| Authentication/authorization failure | Disarm the affected capability; never turn a read failure into a write-token fallback. |
| Media reader failure (an internal, not YouTube, condition) | Do not stop healthy chat in a composed adapter; exercise this decision in ticket 02. |

## Live-chat write and identity

The write boundary is
[`liveChatMessages.insert(part=snippet)`](https://developers.google.com/youtube/v3/live/docs/liveChatMessages/insert).
The request names the `liveChatId`, sets `snippet.type=textMessageEvent`, and
sets `snippet.textMessageDetails.messageText`. It requires a user token with one
of these scopes:

- `https://www.googleapis.com/auth/youtube`
- `https://www.googleapis.com/auth/youtube.force-ssl`

An API key cannot send. The request body does not select an author/channel. It
is reasonable to expect the effective public identity to be a YouTube channel
associated with the authorized Google user, which can involve
account/channel/Brand Account selection, but the current insert documentation
does not fully specify that selection. Ticket 03 must observe it explicitly. A
service account has no linked YouTube channel and is not an acceptable
replacement.

The current official insert/resource pages do not publish a numeric API message
length contract or a numeric quota cost for `insert`. Minnarone must therefore
record both as `unknown` at this stage, validate locally against a conservative
project budget later, and handle an API validation/quota error without retrying
stale content. `insert` has no documented idempotency key, so an ambiguous
result must not be retried automatically: doing so could duplicate a public
message. Product-UI limits or historical quota tables are not substituted for
a current API guarantee. A rejected body can surface `messageTextInvalid` and
send-specific per-user rate limits.

Official policy requires transparent identity/data/actions, user control, and
express consent for actions taken on a user's behalf. The existing two-key TUI
promotion is a useful technical gate, but research alone does not prove whether
session-level promotion is sufficient for YouTube or whether each message needs
additional approval. That remains an explicit HITL/policy decision before live
send.

## OAuth and capability separation

Google's [OAuth guide for installed apps](https://developers.google.com/identity/protocols/oauth2/native-app)
requires the authorization-code flow through the system browser, a loopback
redirect on desktop, `state`, and PKCE. The deprecated out-of-band copy/paste
flow must not be implemented. Google's
[general OAuth expiration rules](https://developers.google.com/identity/protocols/oauth2#expiration)
state that an external consent screen left in `Testing`
normally produces refresh tokens that expire after seven days for YouTube
scopes, so it cannot be mistaken for an operational credential. Google's
[OAuth best practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices)
require secure token storage, least privilege, granted-scope verification,
refresh handling, and revocation/deletion handling.

| Runtime level | Allowed credential | Allowed capability |
| --- | --- | --- |
| Research/prototype | none | Static docs and synthetic events only. |
| Chat shadow | API key, stored as a secret outside config/artifacts | Discover configured video and read chat only. |
| OAuth rehearsal | User OAuth, no send invocation | Validate selected channel, granted scope, expiry/refresh/revocation, and fail-closed gates. |
| Live send | Separate user OAuth write capability, attended and manually promoted | Insert a bounded text message only after policy/identity/consent gates pass. |

Do not request write scope before the write feature exists. Access and refresh
tokens must never enter YAML, prompts, logs, fixtures, reports, or run artifacts.
Revocation is performed through Google's OAuth revocation endpoint and local
token deletion; a revocation or refresh failure disarms send.

## Quota contract

The current [quota calculator/table](https://developers.google.com/youtube/v3/determine_quota_cost)
was updated 2026-06-01 and changed older assumptions:

| Operation | Current documented cost/bucket |
| --- | --- |
| `videos.list` | 1 unit from the combined default allocation. |
| Other non-separated endpoints | Default combined allocation: 10,000 units/day. |
| `search.list` | Separate default bucket: 100 calls/day; each call uses one call. |
| `videos.insert` | Separate default bucket: 100 calls/day; each call uses one call. Not used here. |
| `liveChatMessages.list` | Exact numeric cost not listed: **unknown**. |
| `liveChatMessages.streamList` | Exact numeric cost not listed: **unknown**. |
| `liveChatMessages.insert` | Exact numeric cost not listed: **unknown**. |

Every request, including an invalid request and each additional page, consumes
at least one unit/call from its applicable allocation. Daily quota resets at
midnight Pacific Time. Legacy claims such as fixed 5- or 50-unit live-chat
costs are not used without a current official row.

Minnarone still needs its own stricter budgets. A sensible first read smoke
uses one configured video, bounded duration/message count, streaming transport,
no search, and an immediate stop on quota/auth/lifecycle errors. Project/key
rotation to evade quota is prohibited.

## Media playback and the hard blocker

### What official APIs expose

- [`liveStreams`](https://developers.google.com/youtube/v3/live/docs/liveStreams)
  represents a broadcaster's ingest stream. `cdn.ingestionInfo` contains
  addresses used to send content **to** YouTube, not a viewer playback feed.
- The [`video` resource](https://developers.google.com/youtube/v3/docs/videos)
  exposes metadata and `player.embedHtml`.
- The [IFrame Player API](https://developers.google.com/youtube/iframe_api_reference)
  embeds and controls an official visible player; it does not expose raw PCM,
  frames, or a reusable manifest to Minnarone's perceivers.

### Third-party tooling

Streamlink 8.5.0 (released 2026-08-01) documents YouTube live support while
excluding VOD and protected videos. Its Python API can return a readable stream
and its CLI can write to stdout, so it is technically compatible with a
Streamlink/FFmpeg/PyAV-style pipeline for some public, unprotected lives.
Minnarone's lock currently resolves Streamlink 8.4.0; comparison of 8.4.0 to
8.5.0 shows no YouTube plugin change. This technical result is not permission.

The YouTube Developer Policies, updated 2026-06-24, contain distinct rules:

- downloading, importing, backing up, caching, or storing audiovisual content
  is forbidden **without prior written approval**;
- separate clauses prohibit separating/isolation/modification of audio/video,
  non-YouTube-API access to audiovisual content, background playback, and
  circumvention of geographic/access restrictions; those clauses do not state
  the same blanket approval exception.

**Decision:** do not implement Streamlink, yt-dlp, direct manifest, FFmpeg, or
PyAV capture for YouTube. Ticket 02 may exercise a fake validated media-source
port to learn the internal architecture, but no YouTube resolver/opener is
production-eligible. A download approval alone does not clear the other
clauses. The blocker clears only with an exception/interpretation specific to
the complete proposed path, confirmed by YouTube and the project's compliance
owner, or with a separately authorized source that does not derive viewer media
from YouTube—for example, a broadcaster-provided pre-YouTube feed. An
operator-visible `os_capture` experiment is not automatically exempt and would
require its own policy/consent assessment.

## Data, transparency, and deletion

The [Developer Policies](https://developers.google.com/youtube/terms/developer-policies)
and [Required Minimum Functionality](https://developers.google.com/youtube/terms/required-minimum-functionality)
require an API client to be honest about its identity, what data it collects,
and actions it takes; provide an accessible privacy policy; let users revoke
access; and provide deletion handling. Most stored authorized/API data must be
refreshed or deleted within 30 days. A user's deletion request must be handled
as soon as possible and within seven days.

Minnarone consequences:

- disclose the bot and purpose; do not instruct it to deny automation;
- document the target channel's authority/consent separately from an allow-list;
- store no Google/YouTube credentials or raw API responses in run artifacts;
- minimize chat fields and retention, and distinguish manual deletion from any
  future automated retention feature;
- delete perceptions, prompts, summaries, debug events, and derived copies when
  required, not only the primary chat record;
- provide a revocation and opt-out contact before any live use.

The policy also restricts creating new or derived data or metrics from YouTube
API Data. The current text does not clearly resolve whether an ephemeral LLM
candidate based on chat is permissible. This is a compliance gate for any
public/live feature, not a claim that the use is either approved or forbidden.

## Facts, project decisions, and inferences

### Documented facts

- `activeLiveChatId`, streaming/polling tokens, OAuth scopes, lifecycle fields,
  error names, quota buckets, and the media-policy prohibitions above are
  stated in the cited official documentation.
- Streamlink supports some public unprotected YouTube live URLs but is not a
  YouTube playback API.
- No real request, credential, channel, media, or send was exercised here.

### Reversible project decisions

- explicit `video_id` targeting;
- gRPC stream first and REST polling fallback;
- text-only P0 normalization with stable IDs;
- API-key read capability physically separated from OAuth write capability;
- no runtime channel search.

### Inferences that require later evidence or human authority

- A pre-YouTube broadcaster feed is likely a cleaner multimodal source, but its
  contract and consent still need verification.
- The existing TUI promotion may be an adequate session gate, but YouTube
  consent requirements need a deliberate policy decision.
- A fake typed media-source port may reduce Twitch/YouTube duplication; ticket
  02 must test this without implying that YouTube capture is approved.

## Remaining gates

1. **HITL identity:** select the Google user, YouTube channel/Brand Account,
   Cloud project, target video, and authorized relationship to that target.
2. **Credential/environment:** create an API key with appropriate restrictions
   and run a bounded read-only smoke; no key belongs in the repository.
3. **Policy/consent:** decide and record disclosure, bot control, data deletion,
   broadcaster consent, whether live messages need per-message approval, and
   obtain a compliance interpretation for LLM-derived chat output.
4. **Media policy:** obtain a YouTube/compliance determination that explicitly
   resolves every applicable media clause for the exact path, not only the
   download/cache rule, or select and authorize a source outside YouTube viewer
   playback.
5. **Unknown live-chat quota/message limit:** measure only through a bounded,
   authorized smoke and retain `unknown` where official docs stay silent.

Tickets 03 and 04 may proceed only on chat/read boundaries. Ticket 05 remains
blocked for YouTube-derived audio/video even if the internal prototype passes.

## Primary sources

All sources below were consulted on 2026-08-02. Page update dates are included
where the publisher exposed one during the research.

- Google, [YouTube Live chat streaming guide](https://developers.google.com/youtube/v3/live/streaming-live-chat), updated 2026-06-25.
- Google, [`liveChatMessages.streamList`](https://developers.google.com/youtube/v3/live/docs/liveChatMessages/streamList) and [`liveChatMessages.list`](https://developers.google.com/youtube/v3/live/docs/liveChatMessages/list), updated 2025-10-31.
- Google, [`liveChatMessages.insert`](https://developers.google.com/youtube/v3/live/docs/liveChatMessages/insert), updated 2026-07-09.
- Google, [`liveChatMessage` resource](https://developers.google.com/youtube/v3/live/docs/liveChatMessages), updated 2026-06-25.
- Google, [`videos.list`](https://developers.google.com/youtube/v3/docs/videos/list) and [`video` resource](https://developers.google.com/youtube/v3/docs/videos), updated 2026-07-08.
- Google, [`search.list`](https://developers.google.com/youtube/v3/docs/search/list), updated 2026-06-01.
- Google, [`liveBroadcasts.list`](https://developers.google.com/youtube/v3/live/docs/liveBroadcasts/list), updated 2025-08-28.
- Google, [Quota costs](https://developers.google.com/youtube/v3/determine_quota_cost), updated 2026-06-01.
- Google, [YouTube API authentication](https://developers.google.com/youtube/v3/guides/authentication).
- Google, [OAuth 2.0 for native apps](https://developers.google.com/identity/protocols/oauth2/native-app).
- Google, [OAuth 2.0 expiration rules](https://developers.google.com/identity/protocols/oauth2#expiration), consulted 2026-08-02.
- Google, [OAuth 2.0 best practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices).
- YouTube, [Developer Policies](https://developers.google.com/youtube/terms/developer-policies), updated 2026-06-24.
- YouTube, [Required Minimum Functionality](https://developers.google.com/youtube/terms/required-minimum-functionality).
- YouTube, [Policy compliance guide](https://developers.google.com/youtube/terms/developer-policies-guide), updated 2026-05-04.
- YouTube, [IFrame Player API](https://developers.google.com/youtube/iframe_api_reference).
- Streamlink, [YouTube plugin support](https://streamlink.github.io/plugins.html#youtube), [Python API](https://streamlink.github.io/api_guide/quickstart.html#opening-streams-to-read-data), and [8.5.0 release](https://github.com/streamlink/streamlink/releases/tag/8.5.0).
