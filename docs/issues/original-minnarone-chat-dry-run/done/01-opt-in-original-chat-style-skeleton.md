## Parent PRD

[original-minnarone-chat-dry-run.md](../../prds/original-minnarone-chat-dry-run.md)

## What to build

Add the smallest end-to-end switch for the original Minnarone chat dry-run
style. The operator should be able to opt into an `original_chat` commentator
style without changing the existing operator-facing commentator behavior.

This slice is the tracer bullet for the whole feature: configuration accepts the
style, the app wiring carries it to the reaction/prompt boundary, and tests
prove that the dry-run remains private/local-only. It does not need to implement
the full screenshot-faithful prompt or `RE`/`MSG` normalization yet.

## Step-by-step implementation plan

1. Extend the commentator configuration contract.
   - What to change: add a style field for commentator mode with at least the
     existing operator-facing value and the new original-chat dry-run value.
   - Why this step comes first: every later slice needs a stable opt-in switch.
   - Affects: config schema, validation, examples, app wiring tests.
   - Verify: old configs without the field still load and behave as before.
   - Pitfalls: do not make `commentator.enabled: true` automatically select the
     new behavior.

2. Validate style values clearly.
   - What to change: reject unknown style values with a targeted config error.
   - Why this comes now: bad config should fail before runtime or model setup.
   - Affects: config parsing and CLI `--check` behavior.
   - Verify: a config with an invalid style fails with a message naming the bad
     field and accepted values.
   - Pitfalls: avoid silently falling back to the default; that would make live
     debugging confusing.

3. Enforce local-only safety for the new style.
   - What to change: ensure original-chat dry-run is valid only in the existing
     private/local commentator path and never creates a Twitch send path.
   - Why this comes before prompt work: safety is the first invariant of this
     PRD.
   - Affects: config validation, app assembly, output routing tests.
   - Verify: enabling original-chat dry-run in a public mode is rejected or
     otherwise cannot route to public Twitch output.
   - Pitfalls: do not require Twitch write scopes or public output credentials.

4. Carry the style to the reaction boundary.
   - What to change: make the selected style visible where prompt building and
     reaction finalization will need it.
   - Why this comes after validation: downstream modules should consume a valid
     normalized style, not raw config.
   - Affects: app assembly and prompt builder construction.
   - Verify: a fake app wiring test can observe that original-chat mode reaches
     the prompt/reaction path without live Twitch or OpenRouter calls.
   - Pitfalls: avoid passing ad hoc booleans through many layers if a small enum
     or value object makes the contract clearer.

5. Preserve the current operator-commentary behavior.
   - What to change: add regression tests that current commentator configs still
     produce the existing operator-facing prompt stance and local output.
   - Why this comes last: the new style must be additive.
   - Affects: prompt builder tests and app wiring tests.
   - Verify: existing tests pass without changing their expected output.
   - Pitfalls: do not rename or reinterpret current config values in a way that
     breaks local workflows.

## Acceptance criteria

- [ ] Existing commentator configs load without specifying a style.
- [ ] `commentator.style: original_chat` is accepted when the runtime is local/private.
- [ ] Invalid style values fail with a clear config error.
- [ ] Original-chat dry-run cannot create or use a public Twitch send path.
- [ ] The selected style reaches the prompt/reaction boundary in app wiring.
- [ ] Existing operator-commentary behavior remains unchanged.

## Blocked by

None - can start immediately

## User stories addressed

- User story 2
- User story 3
- User story 27
- User story 28
- User story 34
- User story 36
