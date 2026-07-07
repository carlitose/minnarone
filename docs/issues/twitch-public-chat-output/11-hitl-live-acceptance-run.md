## Parent PRD

[twitch-public-chat-output.md](../../prds/twitch-public-chat-output.md)

## What to build

The first real public words: a short, bounded, attended `live` run on a
channel whose streamer explicitly authorized the bot (allow-list). This is
the only slice with public consequences and the final acceptance gate of the
PRD. HITL by nature: authorization, credentials, judgment, and a hand on the
kill-switch.

## Step-by-step implementation plan

1. Secure authorization and prepare.
   - What: streamer's explicit ok recorded (privately), channel added to
     `allowed_channels`, write token for the dedicated bot account in the
     new env var, live config validated with `--check`, shadow acceptance
     (slice 10) completed with its tuning applied.
   - Why now: authorization is the PRD's hard precondition.
   - Affects: operator workflow.
   - Verify: `--check` passes in live mode; docs checklist satisfied.
   - Pitfall: never run on a non-allow-listed channel "just to try".

2. Run attended via the TUI.
   - What: start the session (it arms in shadow), watch context warm up,
     then manually promote to live; keep the run short (e.g. 10–20 minutes)
     and stay at the keyboard the whole time.
   - Why now: attended-only is the compensating control for having no
     content filter.
   - Affects: end-to-end live behavior.
   - Verify: promotion required confirmation; status bar shows `live`; sent
     messages appear both in the TUI (sent marker) and in the real Twitch
     chat.
   - Pitfall: if anything reads wrong, kill-switch first, diagnose second.

3. Exercise the safety controls deliberately.
   - What: during the run, trigger the kill-switch at least once and verify
     instant degrade to shadow (would-be messages keep appearing locally),
     then re-promote deliberately.
   - Why now: controls that were never used in anger are not accepted.
   - Affects: safety acceptance.
   - Verify: transitions recorded with actor and reason.
   - Pitfall: after re-promoting, confirm the budget did not burst-release
     queued messages (there must be no queue).

4. Audit and close.
   - What: compare run events against the actual channel chat log: every
     sent message present, no unsent message in chat, zero over-budget
     sends, no self-triggered replies to Minnarone's own echoed messages;
     record quality observations and follow-ups (e.g. bandwagon PRD input,
     proactive frequency tuning).
   - Why now: the audit is the acceptance.
   - Affects: PRD completion.
   - Verify: all PRD acceptance points hold; notes are secret-free.
   - Pitfall: do not mark done on a run where the kill-switch was never
     exercised or no mention-reply occurred — extend or repeat instead.

## Acceptance criteria

- [ ] Streamer authorization obtained; channel allow-listed; dedicated bot account used.
- [ ] Session started shadowed; live only after manual confirmed promotion.
- [ ] At least one mention-reply and at most the configured proactive rate; messages visible in real chat at human pace.
- [ ] Zero over-budget sends; zero messages outside the allow-listed channel.
- [ ] No self-triggered replies to the bot's own echoed messages.
- [ ] Kill-switch exercised live at least once: instant degrade, recorded transitions, deliberate re-promote.
- [ ] Events audit matches the real chat log exactly.
- [ ] Quality/tuning follow-ups recorded (input for the bandwagon PRD and frequency tuning).

## Blocked by

- Blocked by [07-live-mode-behind-gates.md](./07-live-mode-behind-gates.md)
- Blocked by [08-promotion-and-kill-switch-keys.md](./08-promotion-and-kill-switch-keys.md)
- Blocked by [09-operator-docs-public-send.md](./09-operator-docs-public-send.md)
- Blocked by [10-hitl-shadow-acceptance-run.md](./10-hitl-shadow-acceptance-run.md)

## User stories addressed

- User story 5
- User story 6
- User story 9
- User story 28
- User story 31
- User story 32
