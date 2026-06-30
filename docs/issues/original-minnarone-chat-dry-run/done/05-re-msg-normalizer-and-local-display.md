## Parent PRD

[original-minnarone-chat-dry-run.md](../../../prds/original-minnarone-chat-dry-run.md)

## What to build

Add a robust normalizer for original-chat LLM output and route the normalized
display text to local console/TUI. The TUI and console should show both lines:

```text
RE: <reason>
MSG: <message>
```

This slice does not handle the special `#end_conv` behavior yet beyond parsing
it as a recognizable message. The actual skip/close-window behavior is in the
next issue.

## Step-by-step implementation plan

1. Define a normalized response shape.
   - What to change: introduce a small contract with fields such as reason,
     message, end-conversation flag, raw text, and display text.
   - Why this comes first: tests and Reactor wiring need a stable interface.
   - Affects: output normalization module and tests.
   - Verify: constructing the normalized shape is possible without importing
     Twitch, Textual, or OpenRouter code.
   - Pitfalls: do not expose this as a public provider API unless needed.

2. Parse exact `RE`/`MSG` responses.
   - What to change: parse the ideal two-line format emitted by the prompt.
   - Why this is the simplest case and anchors the contract.
   - Affects: normalizer tests.
   - Verify: `RE: boss fight` and `MSG: bella giocata` become reason `boss
     fight` and message `bella giocata`.
   - Pitfalls: preserve the message text; do not over-normalize chat style.

3. Handle small LLM formatting deviations.
   - What to change: tolerate extra spaces, lowercase labels, blank lines,
     missing `RE`, missing `MSG`, and small preambles.
   - Why this comes before runtime wiring: LLM output is not guaranteed to be
     perfect even with strict prompts.
   - Affects: normalizer tests.
   - Verify: malformed-but-usable responses still produce stable display text.
   - Pitfalls: do not write a complex parser that tries to interpret arbitrary
     prose semantically; keep it predictable.

4. Build canonical display text.
   - What to change: expose display text that always uses `RE:` and `MSG:` lines
     for original-chat output.
   - Why this comes before routing: the router should receive already-normalized
     display text and should not parse raw model output.
   - Affects: output normalizer and dashboard expectations.
   - Verify: display text contains both labels even if the model omitted one.
   - Pitfalls: do not strip `RE`; the operator explicitly wants it visible.

5. Wire normalization into original-chat reactions.
   - What to change: after a reaction LLM call, normalize output only when the
     current style is original-chat, then route the display text locally.
   - Why this comes after the parser is tested: runtime changes should use a
     proven deep module.
   - Affects: Reactor finalization and output routing.
   - Verify: fake LLM output `RE/MSG` reaches the fake router in canonical
     display form.
   - Pitfalls: do not normalize summarizer output or operator-commentary output.

6. Preserve local TUI/console display.
   - What to change: ensure dashboard-visible output and non-TUI console output
     both show the normalized two-line text.
   - Why this comes last: display should consume the normalized output from the
     reaction path.
   - Affects: output sink, dashboard state, console tests.
   - Verify: the dashboard `MINNARONE` panel includes both `RE` and `MSG`.
   - Pitfalls: do not add `[PRIVATE]` inside the TUI panel; the existing console
     prefix behavior may remain for non-TUI output.

## Acceptance criteria

- [ ] Exact `RE`/`MSG` LLM output is parsed into a normalized response.
- [ ] Minor formatting deviations are tolerated.
- [ ] Display text always includes both `RE:` and `MSG:` lines.
- [ ] Normalization applies only to original-chat reaction output.
- [ ] Operator-commentary output remains unchanged.
- [ ] TUI/dashboard output shows both `RE` and `MSG`.
- [ ] Non-TUI local console output can show the same normalized content.

## Blocked by

- Blocked by [01-opt-in-original-chat-style-skeleton.md](./01-opt-in-original-chat-style-skeleton.md)

## User stories addressed

- User story 4
- User story 21
- User story 26
- User story 32
