# YouTube Live identity and read-only smoke

## Type

Decision

## Status

Accepted by the product owner and observed in a bounded HITL smoke on
2026-08-03. This closes the decision and live-read evidence requested by ticket
03; it does not authorize public send.

## Context

Ticket 03 had to choose the target relationship and future public identity,
keep write capability absent, and demonstrate that one explicit YouTube Live
target can be discovered and read without persisting credentials or audience
content. The current external API contract is recorded in the
[YouTube Live platform report](../research/youtube-live-platform-contract.md).

The production YouTube adapter does not exist yet. The live observation used a
bounded, disposable REST probe; ticket 04 still owns the tested runtime adapter
and its preferred `liveChatMessages.streamList` transport.

## Human decisions

- The selected target is one explicit public video ID supplied by the operator.
  Its value is not retained in the repository or in a smoke artifact; future
  runs keep the selected target only in local operator configuration.
- The target belongs to a third party. The operator attests that the target is
  authorized for this read-only rehearsal. No creator identity or private
  authorization record is stored in the repository, and this attestation does
  not authorize public send.
- Minnarone's future public identity will be a dedicated YouTube channel or
  Brand Account, separate from a personal channel. The effective OAuth channel
  selection must still be observed before ticket 07 can send.
- Before any public participation, the dedicated channel/profile will clearly
  disclose that Minnarone is an AI. The read-only API-key smoke has no visible
  chat identity and exercised no public action.
- The system remains in shadow. Public send requires the separate safety,
  sender, promotion, and acceptance gates in tickets 06-08.
- No raw message, display name, author ID, message ID, chat ID, API response,
  prompt, or derived audience text is retained from this smoke. Only the
  aggregate, sanitized observations in this decision are durable.
- The API key may remain in the local gitignored `.env` while tickets 04 and 05
  are developed and tested. It must never enter YAML, documentation, logs,
  commands, fixtures, screenshots, or chat.

## Capability decision

The read side uses an API key restricted by the operator to YouTube Data API
v3. No OAuth credential, refresh token, service account, or write scope exists
for this path. An API key can discover/read public live-chat data but cannot
call `liveChatMessages.insert`, which requires user OAuth with a write-capable
YouTube scope.

This split is an invariant:

```text
local API key ──> explicit video discovery ──> live-chat read

OAuth write credential: physically absent
public sender:          not constructed
```

## Observed smoke evidence

The probe loaded the API key from `.env` without printing it, resolved
`activeLiveChatId` for the explicit video, and used the documented REST
`liveChatMessages.list` fallback. It respected every returned
`pollingIntervalMillis` value and stopped on the duration bound.

| Observation | Result |
| --- | --- |
| Target | One explicit operator-provided `video_id`, value not retained; no search or silent retargeting |
| Credential | Local API key; no OAuth and no send capability |
| Duration and cap | 60,000 ms; maximum 100 unique events |
| Outcome | Success; 72 unique `textMessageEvent` observations |
| Pacing | 29 requests; final returned interval 1,930 ms |
| Resume | A next-page/resume token was present |
| Stop | Automatic at the duration bound |
| Persistence | No raw chat, names, IDs, responses, or tokens saved |

A second one-page probe mapped one live text event in memory to the existing
canonical shape `RawEvent(channel="chat", payload={"text", "speaker"}, ts)`.
The production `ChatPerceiver` accepted it as `Perception(chat/msg)`. The probe
confirmed that stable message and author channel IDs were present, but printed
and saved none of their values. This proves only the observed API-to-current
chat-perceiver segment; it is not evidence that the ticket 04 adapter already
exists.

## Outcome classification

The bounded probe kept these outcomes distinct rather than treating silence as
a generic failure:

| Condition | Sanitized outcome |
| --- | --- |
| `videos.list` returns no item | `video_absent` |
| Scheduled but not started | `live_not_started` |
| `actualEndTime` is present | `live_ended` |
| No active chat on another video state | `chat_disabled_or_inactive` |
| Active chat returns no events before the bound | `no_messages` |
| HTTP/API rejection | `api_error` with status and documented reason only |
| Network timeout/failure | `network_failure` without URL or credential |
| Text event reaches the canonical shape | `success` |

Authentication, quota, and rate failures remain separate through the API error
reason. A read failure must stop/fail closed; it must never fall back to a
future write token.

## Operator checklist

Before a read rehearsal:

- obtain or reconfirm authority for the exact target;
- select one explicit video ID rather than channel search;
- confirm `YOUTUBE_API_KEY` exists only in local secret storage and `.env` is
  ignored by Git;
- keep OAuth/write credentials absent;
- set duration and event caps before making the first request;
- retain only aggregate states, counts, pacing, and redacted diagnostics.

After a rehearsal:

- confirm the process stopped within its bound and no raw artifact was written;
- keep the key locally only while it is needed for tickets 04/05;
- on loss of authority, suspected exposure, or end of need, delete the key in
  Google Cloud Console under **APIs & Services → Credentials**, remove the
  `YOUTUBE_API_KEY` entry from `.env`, stop active readers, and delete any local
  smoke/run directories and derived copies;
- remain in shadow until the later public-send gates are deliberately passed.

## Failure and stop conditions

Stop the read path on target mismatch, authorization withdrawal, API-key
failure, quota exhaustion, chat end/disable, repeated rate failure, credential
exposure, or inability to keep artifacts bounded and redacted. None of these
conditions permits project/key rotation, a write-token fallback, or automatic
retargeting.

## Remaining gates

- Ticket 04 must implement the YouTube chat-only shadow adapter with fake-first
  tests and a bounded operator path. The live probe here does not substitute
  for those tests.
- Ticket 07 must validate that OAuth actually selects the dedicated Minnarone
  channel/Brand Account, including self-echo identity and revocation behavior.
- Ticket 08 must repeat the attended acceptance against the then-frozen runtime
  and re-confirm target authority and disclosure before any public action.

## Verification boundary

Observed live: explicit video discovery, active chat discovery, paced REST
reading, stable-ID presence, one in-memory canonical chat mapping, and bounded
stop. Not observed: gRPC `streamList`, production adapter lifecycle,
disconnect/resume, every failure response, OAuth identity, or public send.
