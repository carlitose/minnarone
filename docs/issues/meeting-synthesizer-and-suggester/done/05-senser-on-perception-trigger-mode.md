## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Add the `on_perception` trigger mode to the Senser. In this mode, the Senser
emits a `suggestion_eval` trigger for every new speech perception
(source=AUDIO, type=speech). This is the trigger strategy for the SUGGESTER
style.

## Step-by-step implementation plan

1. **Add `suggestion_eval` to trigger kinds.**
   Add `suggestion_eval` as a valid trigger kind. Unlike `synthesis_tick`,
   this trigger carries the perception that caused it (the speech utterance)
   and the interlocutor (the speaker).
   *Verify:* `Trigger(kind="suggestion_eval", perception=..., ...)` constructs
   correctly.

2. **Implement `on_perception` mode in the Senser.**
   In `on_perception` mode, `tick()` reads new perceptions from the store
   (using the existing cursor mechanism). For each perception with
   `source=AUDIO` and `type=speech`, emit a `suggestion_eval` trigger.
   Ignore perceptions from other sources (CHAT, VIDEO, EVENT).
   No conversation windows, no idle detection, no mention matching.
   *Verify:* a speech perception produces one trigger; a chat perception
   produces none.
   *Pitfall:* the self-echo filter (`bot_identity`) should still apply — don't
   trigger on the agent's own perceived output.

3. **Include interlocutor in the trigger.**
   The `suggestion_eval` trigger must carry the speaker from the perception
   so the PromptBuilder can look up facts for that interlocutor. Use the
   same interlocutor resolution logic as the existing `mention` trigger
   (speaker from the perception).
   *Verify:* trigger interlocutor matches the perception speaker.

4. **Write tests.**
   - `on_perception` mode: speech perception → `suggestion_eval` trigger.
   - `on_perception` mode: chat/video/event perception → no trigger.
   - `on_perception` mode: self-echo filtered out.
   - `on_perception` mode: no mention/continuation/idle triggers.
   - `on_perception` mode: multiple speech perceptions → one trigger each.
   Prior art: `test_senser.py`, mention detection tests.

## Acceptance criteria

- [ ] `on_perception` mode emits `suggestion_eval` for each speech perception
- [ ] Non-speech perceptions (CHAT, VIDEO, EVENT) produce no trigger
- [ ] Self-echo perceptions are filtered out
- [ ] Trigger carries the correct interlocutor (speaker)
- [ ] No mention/continuation/idle triggers in this mode

## Blocked by

- Blocked by [04-senser-periodic-trigger-mode.md](./04-senser-periodic-trigger-mode.md) (builds on the `trigger_mode` concept introduced there)

## User stories addressed

- User story 4
