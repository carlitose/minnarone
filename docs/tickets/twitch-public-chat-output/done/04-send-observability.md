## Parent PRD

[twitch-public-chat-output.md](../../prds/twitch-public-chat-output.md)

## What to build

Operator visibility for the send path, before live exists: the TUI and
dashboard text model show the send state (mode, promoted/kill-switch state,
budget remaining in both windows, consecutive failures, last decision with
reason), the `MINNARONE` panel distinguishes shadow vs sent messages with
markers, the status bar gains a `send` source health label using the existing
ok/idle/busy/failed vocabulary, and replay renders runs containing send
events. The write token joins the existing redaction rules.

## Step-by-step implementation plan

1. Extend the observability snapshot with send state.
   - What: the agent snapshot exposes a read-only send section fed by the
     policy (mode, promoted, kill-switch, budget counters, failures, last
     decision/reason).
   - Why now: the snapshot is the single source for TUI, dashboard text, and
     tests.
   - Affects: observability snapshot model.
   - Verify: snapshot unit tests with a fake policy state.
   - Pitfall: expose plain data, not the policy object — the dashboard is
     read-only by design.

2. Render send state in the dashboard and status bar.
   - What: a send section in the dashboard text model; `send` health label
     (`ok` after a successful decision flow, `failed` after send failures,
     `idle` before any decision); shadow/sent markers on `MINNARONE` panel
     entries.
   - Why now: shadow rehearsal (slice 10) is only trustworthy if visible.
   - Affects: dashboard text model, TUI panels, health-label mapping.
   - Verify: panel/snapshot tests in the existing dashboard test style.
   - Pitfall: keep marker rendering in the text model so the plain console
     path benefits too.

3. Make replay understand send events.
   - What: replay reconstructs send decisions from `events.jsonl` and shows
     them like the live dashboard (markers, counters).
   - Why now: acceptance runs are audited through replay.
   - Affects: replay event loading.
   - Verify: replay test over a fixture run containing shadow/sent/dropped
     events.
   - Pitfall: unknown event kinds from older runs must not break replay.

4. Extend redaction to the write token.
   - What: the new write-token env var name joins the redaction patterns for
     prompt captures, dashboard rendering, and event recording.
   - Why now: the token exists in the environment from slice 01 onward.
   - Affects: redaction rules and their tests.
   - Verify: redaction unit tests with a fake token value in text.
   - Pitfall: redact by pattern and by known-value, matching how the existing
     tokens are handled.

## Acceptance criteria

- [ ] TUI/status bar show send mode, promotion/kill-switch state, budget remaining, failures, and last decision reason.
- [ ] `MINNARONE` panel entries are visually distinct for shadow vs sent.
- [ ] `send` appears as a source health label with truthful states.
- [ ] Replay renders runs containing send events without live services.
- [ ] The write token is redacted everywhere the read token already is.

## Blocked by

- Blocked by [03-shadow-router-tracer-bullet.md](./03-shadow-router-tracer-bullet.md)

## User stories addressed

- User story 2
- User story 11
- User story 12
- User story 13
- User story 27
