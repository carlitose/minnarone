## Parent PRD

[twitch-public-chat-output.md](../../prds/twitch-public-chat-output.md)

## What to build

The shadow dress rehearsal: a bounded live-perception TUI session (any live
channel — shadow needs no authorization since nothing is sent) with
`twitch.send.mode: shadow`, judged by the operator. This is a HITL slice: it
requires live credentials, models, and qualitative judgment of message
quality and pacing.

The expected outcome is confidence that the live slice will behave: shadow
messages read like the original Minnarone, arrive at human pace after typing
delay, respect budget, and every decision is auditable in events and replay.

## Step-by-step implementation plan

1. Prepare a bounded run.
   - What: shadow config on a currently live channel (chat+audio+video as
     validated in the perception acceptance run), 15–30 minute timebox.
   - Why now: rehearsal gate before any public exposure.
   - Affects: operator workflow.
   - Verify: `--check` passes; docs workflow (slice 09) is followed as
     written.
   - Pitfall: never paste secrets into notes or artifacts.

2. Observe the session.
   - What: watch `[SHADOW]` messages in the `MINNARONE` panel, send state in
     the status bar, budget consumption, dedup/`#end_conv` skips, and at
     least one mention-style interaction if chat provides one.
   - Why now: live tuning judgment needs live inputs.
   - Affects: qualitative acceptance.
   - Verify: at least one shadow message clearly references live context; no
     decision without a recorded reason.
   - Pitfall: judge persona fidelity against the original-chat contract, not
     against the operator commentator style.

3. Audit artifacts and replay.
   - What: after the run, verify send events (actions, reasons, budget
     drops if any) in the run directory and replay the session offline.
   - Why now: the audit trail is an acceptance target itself.
   - Affects: acceptance criteria.
   - Verify: replay shows the same shadow decisions and transitions.
   - Pitfall: do not mark accepted if events and displayed messages disagree.

4. Record results and tuning follow-ups.
   - What: notes on message quality, pacing, budget adequacy, proactive
     frequency, and any needed prompt/caps tuning before live.
   - Why now: the live run (slice 11) inherits these settings.
   - Affects: follow-up planning.
   - Verify: notes are actionable and secret-free.
   - Pitfall: do not proceed to live acceptance with unresolved quality
     concerns — shadow is the cheap place to fix them.

## Acceptance criteria

- [ ] A bounded shadow session ran on a live channel with full perception.
- [ ] Shadow messages are visibly marked and read in-character (original-chat persona).
- [ ] Typing delay and dedup demonstrably applied; `#end_conv` produced skip decisions when it occurred.
- [ ] Budget accounting observed (counters move; caps respected).
- [ ] Every send decision has a recorded reason; replay reproduces the session.
- [ ] Zero network sends occurred (no sender constructed in shadow).
- [ ] Tuning follow-ups recorded before live.

## Blocked by

- Blocked by [04-send-observability.md](./04-send-observability.md)
- Blocked by [09-operator-docs-public-send.md](./09-operator-docs-public-send.md)

## User stories addressed

- User story 1
- User story 2
- User story 28
- User story 30
