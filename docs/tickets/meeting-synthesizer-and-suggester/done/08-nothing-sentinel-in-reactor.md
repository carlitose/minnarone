## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Add `#nothing` sentinel handling to the Reactor. When the LLM responds with
`#nothing` (the SUGGESTER's "I have nothing to suggest"), the Reactor skips
routing — no output is produced. This is analogous to the existing `#end_conv`
sentinel pattern.

## Step-by-step implementation plan

1. **Add `#nothing` detection to the Reactor's `_react` method.**
   After receiving the LLM response, check if the response (stripped of
   whitespace) equals `#nothing` or contains `#nothing` as the only
   meaningful content. If so, skip routing entirely — do not call
   `router.route()`.
   *Verify:* a response of `"#nothing"` produces zero routed messages.
   *Pitfall:* the LLM may produce `#nothing` with leading/trailing whitespace,
   or preceded by thinking text like "There's nothing to suggest. #nothing".
   The detection should be tolerant: if `#nothing` appears anywhere in the
   response, treat it as silence. This matches how `#end_conv` is handled.

2. **Scope to SUGGESTER style only (optional guard).**
   Consider whether `#nothing` should be recognized only when the Reactor's
   style is `SUGGESTER`, or for all styles. The PRD specifies it for
   SUGGESTER, but making it universal is simpler and harmless (no other
   style's LLM would produce `#nothing` unprompted).
   Recommendation: recognize it universally like `#end_conv`, but only the
   SUGGESTER prompt instructs the LLM to use it.
   *Verify:* OPERATOR style with a response containing `#nothing` also
   suppresses output (harmless edge case).

3. **Write tests.**
   - Response `"#nothing"` → no routing.
   - Response `"  #nothing  "` → no routing.
   - Response `"No suggestion needed. #nothing"` → no routing.
   - Response `"Here is my suggestion: do X"` → normal routing.
   - Response `"#nothing and also #end_conv"` → no routing (nothing takes
     precedence, or both suppress — either way, no output).
   Prior art: `#end_conv` tests in `test_reactor.py`.

## Acceptance criteria

- [ ] `#nothing` in LLM response suppresses routing (zero output)
- [ ] Detection tolerates whitespace and preceding text
- [ ] Normal responses (without `#nothing`) route as before
- [ ] Existing `#end_conv` behavior unchanged

## Blocked by

None — the Reactor change is independent of the new styles.

## User stories addressed

- User story 6
