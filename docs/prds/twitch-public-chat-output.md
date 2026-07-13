# Twitch Public Chat Output (v2) — Shadow-First PRIVMSG Send

## Problem Statement

Minnarone can perceive a live Twitch stream (chat, audio, video) and generate
in-character Italian chat messages, but it is mute: every generated message is
routed to the local console or TUI only. The `PUBLIC` output mode exists in
configuration and in the `OutputRouter` contract, yet it currently prints to
the local console. The original Minnarone — the product this framework
recreates — was a real chat participant: it wrote messages in the Twitch chat
of the channel it watched, at human-like pace, indistinguishable from a human
viewer. Until the send path exists, the recreation is incomplete: the operator
can watch Minnarone "think" but the chat never sees him.

Sending public messages is also the single most dangerous capability in the
system. A bug, a prompt-injection slip, or a runaway trigger loop would be
visible to a real audience on a real channel. Today safety is guaranteed by
the *absence* of a send path; v2 must replace that absolute guarantee with
explicit, observable, operator-controlled boundaries.

## Solution

Give the existing `PUBLIC` output mode a real Twitch delivery path, built
shadow-first:

- A **send policy** decides, for every candidate public message, whether it is
  actually sent, only recorded as "would have been sent" (**shadow**), or
  dropped (budget exhausted, channel not authorized, kill-switch engaged). The
  policy is a pure, deterministic module — the same philosophy as
  `HumanLikeness`.
- A **Twitch chat sender** owns a write-capable IRC connection and delivers
  `PRIVMSG` lines to the channel, with reconnection and typed failures. It is
  the only place in the codebase allowed to write a `PRIVMSG`.
- **Shadow mode is the default and the first slice.** In shadow mode the full
  pipeline runs — trigger, prompt, LLM, original-chat normalization,
  human-likeness delay, dedup, budget accounting — and the final message is
  displayed and recorded exactly as if it had been sent, but no network write
  happens. Live sending is a separate, explicitly opted-in configuration state
  that additionally requires a write-scope token and an authorized channel.
- A **kill-switch** lets the operator (TUI keybinding) or the runtime itself
  (repeated send failures) degrade `live` to `shadow` instantly without
  stopping the agent, preserving observability of what Minnarone *would* keep
  saying.

The persona remains the original one: messages are generated with the
`original_chat` style contract (`RE:`/`MSG:`, `#end_conv`), pass through the
existing typing-delay and dedup filter, and Minnarone never reveals he is an
AI, in line with the current soul and the project's neutral disclosure stance
(FR27 tooling stays out of scope here).

## User Stories

1. As an operator, I want a `shadow` send mode where the whole public pipeline runs without network writes, so that I can validate live behavior with zero audience risk.
2. As an operator, I want shadow messages clearly labeled (e.g. `[SHADOW]`) in console and TUI, so that I never confuse a rehearsal with a real send.
3. As an operator, I want live sending to be off by default in every example config, so that no one enables public output by accident.
4. As an operator, I want live mode to refuse to start unless the target channel is in an explicit allow-list, so that Minnarone can only speak where the streamer authorized it.
5. As a streamer who authorized the bot, I want Minnarone to reply when chat users or I mention him, so that he behaves like a real participant.
6. As a streamer who authorized the bot, I want proactive comments to be rare and bounded, so that the bot adds life to chat without spamming it.
7. As an operator, I want a hard cap on messages per minute and per hour, so that a runaway trigger loop cannot flood a public chat.
8. As an operator, I want the send path to respect Twitch's own IRC rate limits with margin, so that the account is never temporarily banned for flooding.
9. As an operator, I want a kill-switch keybinding in the TUI that instantly degrades live sending to shadow, so that I can stop public output the moment something feels wrong.
10. As an operator, I want the runtime to auto-degrade to shadow after repeated consecutive send failures, so that a broken connection does not silently eat messages or retry-spam.
11. As an operator, I want every send decision (sent, shadow, dropped-budget, dropped-dedup, failed) recorded in run events with its reason, so that I can audit exactly what happened after a session.
12. As an operator, I want the TUI to show send state (mode, budget remaining, last send, failures), so that public output is observable live like every other source.
13. As an operator, I want sent messages to appear in the `MINNARONE` panel with a distinct sent marker, so that local output and public output are distinguishable at a glance.
14. As a viewer of the channel, I want Minnarone's messages to arrive at a human typing pace, so that the interaction feels like the original Minnarone, not a bot burst.
15. As a viewer of the channel, I want Minnarone to never send two nearly identical messages, so that he does not read as a broken script.
16. As a viewer of the channel, I want Minnarone to stop replying when the conversation is over (`#end_conv`), so that he knows when to shut up like a real person.
17. As the agent (Minnarone), I want my public messages generated with the original-chat persona contract, so that my public voice matches the original screenshots.
18. As the agent (Minnarone), I want to never reveal I am an AI even in public chat, so that I stay in character per my soul.
19. As an operator, I want the write-capable credential to be a separate environment variable from the read-only one, so that a config running read-only can never accidentally hold send power.
20. As an operator, I want `--check` to fail fast when live mode is configured without a write token or without an authorized channel, so that misconfiguration is caught before any capture starts.
21. As an operator, I want the send path to work through the same `OutputRouter` interface that console and TUI use, so that public/private stays a configuration, not a code fork.
22. As a developer, I want the send policy to be a pure module with injectable clock, so that budget and kill-switch behavior are unit-testable deterministically.
23. As a developer, I want the IRC sender isolated behind a small interface with a fake in tests, so that no test ever opens a real network connection.
24. As a developer, I want shadow mode implemented before the real sender, so that every downstream slice (TUI, events, budget) is validated before any network write exists.
25. As an operator, I want messages exceeding the IRC length limit to be dropped and recorded rather than truncated mid-sentence, so that garbled half-messages never reach public chat.
26. As an operator, I want prompt-injection attempts from chat to keep being treated as observed data, so that no chat user can trick Minnarone into sending something on command.
27. As an operator, I want secrets (send token) never written to artifacts, logs, or prompt captures, so that a shared debug bundle cannot leak credentials.
28. As an operator, I want a bounded live acceptance run on an authorized channel as the final slice, so that live sending is validated with human judgment before being considered done.
29. As a developer, I want the sender to reconnect with backoff after connection loss, so that a network blip degrades gracefully instead of killing the run.
30. As an operator, I want shadow mode to keep accounting the budget as if messages were sent, so that shadow rehearsals predict live pacing accurately.
31. As the agent (Minnarone), I want my own echoed chat messages never to count as mentions or triggers, so that I do not reply to myself in a loop.
32. As an operator, I want every live session to start in shadow and require my manual promotion from the TUI, so that no public message goes out before I judge the context warm.
33. As an operator, I want promotion to live to be possible only when the config explicitly arms it, so that a TUI keypress alone can never enable public output.
34. As an operator, I want the console (non-TUI) runtime to top out at shadow, so that unattended or headless runs are physically unable to send public messages.

## Implementation Decisions

- **Reuse over rebuild.** The generation half already exists and is validated
  live: original-chat prompt contract, `HumanLikeness` (typing delay ∝ length,
  dedup, `#end_conv`), Reactor routing via `OutputRouter.route(message, mode)`,
  run-event recording, TUI output sink. This PRD only adds the delivery half
  for `OutputMode.PUBLIC`.
- **Three send states, one config field**: `off` (today's behavior: public
  routes to console only), `shadow` (full pipeline + recording, no network),
  `live` (real `PRIVMSG`). Default `off`; examples ship `shadow` at most.
- **`PublicSendPolicy` — pure decision module (deep).** Input: candidate
  message, target channel, current time, and its own internal state
  (configured mode, kill-switch engaged, allow-list, budget window
  timestamps). Output: a decision object `{action: send|shadow|drop, reason}`.
  No I/O, injectable clock, mirrors the `HumanLikeness` design. Budget:
  sliding-window caps per minute and per hour, both configurable, both
  enforced in shadow too (accurate rehearsal). Twitch platform limits are
  respected by defaulting caps well under 20 messages / 30 s.
- **`TwitchChatSender` — the only PRIVMSG writer (deep).** Owns a dedicated
  write-capable IRC connection (separate from the read connection of the chat
  perception adapter, so the read path stays byte-for-byte untouched and
  provably read-only). Interface: `start()`, `stop()`, `send(text)`; typed
  errors; reconnect with bounded backoff; PING/PONG handling. Reuses the
  existing IRC stream abstraction of the chat adapter. Enforces the IRC
  message length limit by refusing (not truncating) oversized messages.
- **`TwitchPublicOutputRouter` — thin composition.** Implements
  `OutputRouter`. On `route(message, PUBLIC)`: ask `PublicSendPolicy`; on
  `send` → `TwitchChatSender.send()` and mirror to console/TUI with a sent
  marker; on `shadow` → console/TUI with shadow marker; on `drop` → record
  only. Every decision is recorded as a run event with its reason. Failures
  from the sender are reported to the policy (for auto-degrade) and to
  observability; they never crash the agent (same EC03 skip-turn philosophy).
- **Kill-switch degrades, never stops.** Engaging it (TUI keybinding, or
  automatically after N consecutive send failures) flips policy state from
  live to shadow at the next decision. The agent keeps running and the
  operator keeps seeing would-be messages. Disengaging is an explicit operator
  action. There is no path where the kill-switch silently re-enables live.
- **Authorization is config + validation, twice.** New config block under
  `twitch` (send mode, allowed channels, caps, failure threshold). `--check`
  and startup fail when `live` is configured and the target channel is not in
  the allow-list, or the write token is missing. The policy re-checks the
  allow-list at send time (defense in depth).
- **Separate write credential.** The read path keeps `TWITCH_BOT_USERNAME` /
  `TWITCH_OAUTH_TOKEN` (read scope). Live sending requires a distinct
  environment variable holding a write-scope token for the dedicated bot
  account. A read-only setup physically lacks send capability. The token is
  covered by the existing redaction rules (prompt capture, dashboard, events).
- **Persona and disclosure.** Public messages use the existing
  `original_chat` style contract; the soul's "never reveal being an AI" rule
  stands. No disclosure tooling in this PRD (spec keeps FR27 as separate v2
  tooling; the framework stays neutral).
- **Human-likeness unchanged and mandatory in public.** Typing delay, dedup
  and `#end_conv` run before routing exactly as today. No immediate-send
  bypass for the public channel: instantaneous replies are the original's
  explicit anti-goal (EC06).
- **Self-echo handling.** Once Minnarone sends, the read connection will see
  his own messages as regular chat from the bot account. They stay in
  `perceptions.jsonl` (log fidelity, replay), but the Senser must never treat
  a perception whose speaker equals the bot's send-account username as a
  mention or trigger, and the prompt builder surfaces them through the
  existing "own recent messages" anti-repetition section, never as third-party
  chat. The filter keys on the send account's username; operators are advised
  to use one dedicated account for both connections.
- **Public persona is always the original-chat contract.** With the Twitch
  adapter and `mode: public`, the prompt uses the `original_chat` contract
  (`RE:`/`MSG:`, `#end_conv`) unconditionally — it is literally the original
  public behavior. The `commentator` block remains a private-mode concept; no
  new style combinations are introduced.
- **Internal-state bookkeeping per outcome.** A `shadow` decision updates all
  internal state exactly as a real send (own-message history for dedup,
  conversation-window continuation, budget) so rehearsals predict live
  behavior faithfully. A `drop` decision updates nothing: the turn is skipped
  (EC03 style). A sender failure after a `live` decision consumes budget, is
  recorded as `failed`, and updates state as if sent (conservative).
- **No outbound content filter; live is attended-only.** Faithful to the
  original: no moderation module, no blocklist. In exchange, operator docs
  prescribe that `live` runs are always attended with the kill-switch at hand.
  The sender refuses only protocol violations (newlines/control characters,
  oversized messages). Automated moderation for unattended use is a possible
  future PRD.
- **Live sessions start in shadow; promotion is manual.** `mode: live` in
  config *arms* the capability but every session begins in shadow. The
  operator promotes to live with a dedicated TUI keybinding once the context
  is warm (solves cold-start, EC13) — the same mechanism as the kill-switch in
  the opposite direction, and equally recorded as a run event. Consequence:
  live is reachable only through the `--tui` runtime; the plain console
  runtime tops out at shadow by construction.
- **No bandwagon here.** Bandwagon (UC05, no-LLM pile-on) is a separate future
  PRD layered on this send channel.

## Step-by-Step Implementation Plan

1. **Add the send configuration type and validation.**
   - What: a `twitch.send` config block — `mode` (`off`/`shadow`/`live`,
     default `off`), `allowed_channels` (list, default empty),
     `max_per_minute`, `max_per_hour`, `failure_threshold` — parsed and
     validated like the existing config dataclasses, with the established
     error style. `--check` fails for `live` without allow-list membership of
     `twitch.channel` or without the write-token env var.
   - Why first: every later slice reads this surface; validation-first is the
     repo's pattern (see the os-capture config slice).
   - Verify: unit tests for parse/validate; `--check` on example configs still
     passes (they default to `off`).
   - Pitfall: do not require the write token when mode is `off`/`shadow`.

2. **Build `PublicSendPolicy` as a pure module.**
   - What: the decision module described above, with injectable clock, budget
     sliding windows, kill-switch state (engage/disengage), allow-list check,
     and failure counting (auto-engage after threshold).
   - Why now: it is the safety core; everything else composes around it. Pure
     modules land with exhaustive tests before any I/O exists.
   - Verify: unit tests cover every action/reason combination, budget window
     edges, auto-degrade, and that shadow consumes budget.
   - Pitfall: no `time.time()` inside — the clock is injected, like the
     injected sleep in the Reactor.

3. **Route `PUBLIC` through a shadow-only router (tracer bullet).**
   - What: `TwitchPublicOutputRouter` without any sender yet — it can only
     shadow or drop. Wire it in the app's router selection when adapter is
     Twitch, mode is `public`, and send mode is `shadow`. Record every
     decision as a run event with reason; mirror messages to console/TUI with
     `[SHADOW]` marker.
   - Why now: the full end-to-end path (trigger → LLM → human-likeness →
     policy → display + events) becomes real and observable with zero network
     risk.
   - Verify: app-level test in the style of the existing "reacts to console
     without sending chat" runtime tests, asserting shadow events and no
     network component involved.
   - Pitfall: keep `off` behavior byte-identical to today (console router).

4. **Show send state in observability.**
   - What: TUI/status-bar surface for send mode, budget remaining, last
     decision and reason, consecutive failures; shadow/sent markers in the
     `MINNARONE` panel; a `send` source health label following the existing
     ok/idle/busy/failed vocabulary.
   - Why now: shadow rehearsals are only useful if the operator can see and
     trust them before live ever exists.
   - Verify: dashboard snapshot/unit tests like the existing panel tests;
     replay still renders runs containing send events.
   - Pitfall: never render the write token or PRIVMSG raw lines with
     credentials; extend the existing redaction tests.

5. **Implement `TwitchChatSender` against the IRC stream abstraction.**
   - What: the write-connection owner — login with the write token, JOIN,
     PING/PONG, `send(text)` as `PRIVMSG #channel :text`, length-limit
     refusal, typed errors, reconnect with bounded backoff, clean stop.
   - Why now: the network edge arrives only after the policy and shadow path
     are proven.
   - Verify: unit tests with a fake IRC stream (same pattern as the chat
     reader tests): login sequence, send framing, PONG, reconnect, oversized
     refusal. No real network in tests.
   - Pitfall: this class must be the only code that writes `PRIVMSG`; keep the
     read adapter untouched.

6. **Filter self-echo in the Senser.**
   - What: perceptions whose speaker equals the bot's send-account username
     are never mention/trigger candidates; the prompt builder routes them into
     the existing own-messages anti-repetition section instead of third-party
     recent chat. They remain in the store untouched.
   - Why now: it must exist before any live send, or Minnarone's first public
     message can trigger a self-reply loop through the read connection.
   - Verify: unit tests — a stored chat perception from the bot account
     produces no trigger even with a fuzzy name match, and appears only in the
     own-messages prompt section.
   - Pitfall: key the filter on the send account's username, not on the read
     login; they can differ.

7. **Enable `live` mode end-to-end behind all gates.**
   - What: compose the sender into the router; `live` requires config
     validation passed + allow-list + write token; failures feed the policy
     (auto-degrade) and observability. Sessions arm in shadow: the policy
     starts every run in shadow state even with `mode: live`.
   - Why now: every safety layer below it already exists and is tested.
   - Verify: app-level tests with a fake sender: live sends, budget drops,
     failure auto-degrade flips to shadow events, session starts shadowed
     until promoted.
   - Pitfall: a sender failure must skip the message (never queue-and-burst
     later) — stale public messages are worse than silence (EC03).

8. **Add the promotion and kill-switch keybindings.**
   - What: two TUI keybindings on the same policy state — promote (shadow →
     live, only when config arms live) and kill-switch (live → shadow) — with
     unmistakable status-bar feedback; both transitions recorded as run
     events.
   - Why now: they need the live path and the observability surface to exist.
   - Verify: TUI tests — promote flips the next decision to `send`; kill
     flips it back to `shadow` with the kill-switch reason; promote is
     rejected when config does not arm live.
   - Pitfall: promotion and disengage must be deliberate (distinct keys or
     confirmation), never a toggle you can fat-finger twice.

9. **Operator docs.**
   - What: extend the Twitch operator guide — dedicated bot account setup,
     write-scope token generation into the new env var, allow-list workflow
     (streamer authorization), shadow rehearsal workflow, live enablement
     checklist (attended-only, TUI-only, manual promotion), kill-switch use,
     and updated safety summary (the "no send path" claim becomes "send only
     via gated sender").
   - Why now: the HITL slices depend on a documented workflow.
   - Verify: docs tests if present (the repo tests operator docs), plus a dry
     read-through.
   - Pitfall: update every doc sentence that currently promises "no PRIVMSG
     write path exists" — they become false the moment slice 5 lands.

10. **HITL: bounded shadow acceptance run.**
   - What: a full live-perception run in `shadow` on any live channel;
     operator validates pacing (typing delay, budget), message quality against
     the original persona, and the completeness of send events.
   - Why now: rehearsal gate before any public exposure.
   - Verify: acceptance criteria on events (shadow decisions with reasons,
     budget accounting) and operator judgment.
   - Pitfall: do not shortcut to live because shadow "looks fine" after two
     minutes; the run must be a real bounded session.

11. **HITL: bounded live acceptance run on an authorized channel.**
    - What: with the streamer's explicit authorization, a short bounded `live`
      run via the TUI: session starts in shadow, operator promotes manually
      once context is warm, watches every message with the kill-switch at
      hand; afterwards, audit events vs actual chat.
    - Why last: it is the only slice with public consequences.
    - Verify: all acceptance criteria of the PRD, including at least one
      mention-reply and at most the configured proactive rate, zero
      over-budget sends, no self-triggered replies to Minnarone's own echoed
      messages, kill-switch tested at least once during the run.
    - Pitfall: never run it on a channel outside the allow-list "just to
      try"; that violates the core authorization decision of this PRD.

## Testing Decisions

- Good tests assert external behavior through the module's public interface:
  decisions returned, events recorded, lines written to a fake stream — never
  internal counters or private state.
- `PublicSendPolicy` gets the densest unit suite (pure, injectable clock):
  every `{mode, kill-switch, allow-list, budget}` combination and reason
  string, window-edge cases, auto-degrade threshold, shadow budget
  consumption. Prior art: the `HumanLikeness` and Senser unit tests.
- `TwitchChatSender` is tested against a fake IRC stream (login, framing,
  PONG, reconnect, refusal of oversized messages). Prior art: the existing
  Twitch chat reader tests with their fake stream.
- `TwitchPublicOutputRouter` is tested with a fake policy and fake sender.
  Prior art: `FakeOutputRouter` usage in reactor/app tests.
- App-level runtime tests extend the existing "runtime reacts without sending
  chat" family: `off` behaves exactly as today; `shadow` produces shadow
  events and never touches a sender; `live` with a fake sender sends and
  degrades on failures.
- TUI/dashboard tests follow the existing snapshot/panel test style for the
  new send status surface; redaction tests extend the existing secret
  patterns to the write token.
- HITL slices (9, 10) are documented acceptance runs, not automated tests —
  the same pattern as the perception and TUI acceptance issues.

## Out of Scope

- Bandwagon (UC05) — separate PRD on top of this send channel.
- Whisper/private Twitch messages, TTS voice output, structured actions
  (FR19/FR20).
- Helix API integration, EventSub platform events (FR04), moderation-API
  awareness.
- Disclosure tooling (FR27) beyond keeping the current soul behavior; the
  Twitch-profile bio choice is an operator matter, not code.
- Auto-memory updates from public conversations (FR13).
- Multi-channel simultaneous sending; one channel per running agent stays the
  model.
- Any change to the perception pipeline, the prompt contract, or
  `HumanLikeness` behavior.

## Further Notes

- The dedicated bot account (its Twitch profile, its authorization
  conversations with streamers) is an operational prerequisite handled by the
  operator, not by code; the code enforces only the allow-list and the token
  boundary.
- Twitch's practical IRC limit (~20 messages/30 s for regular users, stricter
  perception for chats where the account is not a moderator) is a platform
  behavior, not a contract; defaults must stay far below it. The original
  Minnarone's cadence (idle ~150 s, mention replies) is naturally far below
  any platform limit — the caps exist for failure modes, not normal
  operation.
- Once slice 5 lands, the repository-wide safety claim changes from "no send
  path exists" to "sending exists behind shadow-default, allow-list, budget,
  kill-switch and a separate credential". The docs slice (8) owns that
  rewrite; reviewers of future PRs should treat any new direct IRC write
  outside `TwitchChatSender` as a defect.
- A natural follow-up after acceptance: promote shadow-run transcripts into
  tuning material for proactive-comment frequency, which this PRD deliberately
  ships conservative.
