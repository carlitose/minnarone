## Parent PRD

[original-minnarone-chat-dry-run.md](../../prds/original-minnarone-chat-dry-run.md)

## What to build

When original-chat dry-run is selected, render a prompt shaped like the
original Minnarone screenshots. The prompt should ask the LLM to behave as a
Twitch chat user named Minnarone and produce an Italian chat-style answer using
the `RE`/`MSG` format.

This slice should build the prompt contract and verify section order,
cacheability, and key instructions. It does not need to fully split every
dynamic perception channel yet; that is covered by the next context slice.

## Step-by-step implementation plan

1. Define the prompt style boundary.
   - What to change: make prompt building choose between the existing
     operator-facing stance and the original-chat stance based on the selected
     style.
   - Why this step comes first: the same prompt builder must support both
     behaviors without forking the whole runtime.
   - Affects: prompt builder interface and prompt tests.
   - Verify: default style still produces the current prompt; original-chat
     style produces a distinct prompt.
   - Pitfalls: do not branch in the TUI; this is model-input behavior.

2. Build the stable original-chat prefix.
   - What to change: add the screenshot-derived stable rules: Minnarone is a
     Twitch chat user, writes one Italian chat message, uses informal lowercase
     Twitch language, avoids assistant tone, keeps continuity, does not reveal
     bot/AI status, handles name misspellings, and uses Twitch emotes
     sparingly.
   - Why this comes early: the prefix is the cacheable part and should be
     deliberate before adding dynamic content.
   - Affects: prompt stable prefix and prompt caching behavior.
   - Verify: repeated builds with the same stable memory and style have the
     same prefix bytes.
   - Pitfalls: do not include timestamps, trigger text, recent messages, or
     summary in the stable prefix.

3. Add permanent memory sections.
   - What to change: render `soul` and `facts` as permanent memory in the
     original-chat prompt.
   - Why this follows the stable rules: memory is still stable input and belongs
     near the top for cacheability.
   - Affects: memory-to-prompt integration.
   - Verify: fake `soul` and `facts` appear in the expected permanent memory
     section.
   - Pitfalls: missing memory should remain allowed and degrade to empty
     sections or clear placeholders, not crash.

4. Add the response format contract.
   - What to change: include the exact two-line response requirement:

```text
RE: <what Minnarone is responding to, 3-6 words>
MSG: <the chat message> or #end_conv
```

   - Why this comes before output normalization: the LLM must be instructed
     before the normalizer can rely on the shape.
   - Affects: prompt dynamic or stable instructions, later output parser tests.
   - Verify: original-chat prompts include the `RE` and `MSG` contract.
   - Pitfalls: do not ask for extra explanation or markdown around the answer.

5. Keep trigger-specific situation at the bottom.
   - What to change: render a final situation section that differs for idle,
     streamer mention/continuation, and chat mention/continuation.
   - Why this comes last in the prompt: the original prompt intentionally puts
     the immediate trigger at the bottom for salience.
   - Affects: trigger-to-prompt rendering.
   - Verify: tests assert that the final situation appears after memory and
     recent context sections.
   - Pitfalls: do not duplicate the trigger in multiple places in ways that
     confuse the model.

6. Preserve anti-injection fencing.
   - What to change: keep perceived chat/audio/video content inside the existing
     untrusted data fence or an equivalent protected representation.
   - Why this comes with prompt rendering: the original prompt structure should
     not remove current safety properties.
   - Affects: prompt formatting helpers.
   - Verify: injected fake headers inside chat/audio text cannot become
     top-level prompt sections.
   - Pitfalls: do not over-redact normal chat content; the prompt must remain
     useful.

## Acceptance criteria

- [ ] Original-chat style produces a distinct prompt from operator-commentary style.
- [ ] The prompt includes screenshot-derived Twitch chat behavior rules.
- [ ] Permanent `soul` and `facts` memory are included.
- [ ] The prompt requires exactly the `RE`/`MSG` response contract.
- [ ] The trigger-specific situation is rendered at the bottom.
- [ ] The stable prefix remains byte-identical across turns with the same stable inputs.
- [ ] Perceived content remains protected as untrusted data.
- [ ] Existing operator-commentary prompt tests still pass.

## Blocked by

- Blocked by [01-opt-in-original-chat-style-skeleton.md](./01-opt-in-original-chat-style-skeleton.md)

## User stories addressed

- User story 7
- User story 8
- User story 14
- User story 15
- User story 16
- User story 17
- User story 18
- User story 19
- User story 22
- User story 23
- User story 24
- User story 25
- User story 29
