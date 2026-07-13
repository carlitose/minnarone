## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Add two new values to the `CommentatorStyle` enum: `MEETING_SYNTHESIZER` and
`SUGGESTER`. Introduce per-style profile config dataclasses that will later be
used by `CommentatorConfig.profiles`.

This is a purely additive slice: no existing behavior changes, no consumers are
updated yet. The goal is to establish the type contracts that all subsequent
slices depend on.

## Step-by-step implementation plan

1. **Add enum values to `CommentatorStyle`.**
   Add `MEETING_SYNTHESIZER = "meeting_synthesizer"` and
   `SUGGESTER = "suggester"` to the `CommentatorStyle` enum in the output
   module. The enum already uses `str, Enum` so the new values follow the same
   pattern as `OPERATOR` and `ORIGINAL_CHAT`.
   *Verify:* the new values are importable and behave correctly with
   `_coerce_enum`.
   *Pitfall:* do not remove or rename the existing values.

2. **Create per-style ProfileConfig dataclasses.**
   In the config module, introduce frozen dataclasses for each style's
   profile-specific settings:
   - `OperatorProfileConfig(idle_interval: float | None = None)`
   - `OriginalChatProfileConfig(idle_interval: float | None = None)`
   - `MeetingSynthesizerProfileConfig(interval_s: float = 180.0)`
   - `SuggesterProfileConfig()` (no style-specific fields yet)
   Each should validate its fields in `__post_init__` (e.g. `interval_s` must
   be positive, `idle_interval` must be positive when set).
   *Verify:* dataclasses instantiate with defaults, reject invalid values with
   `ConfigError`.
   *Pitfall:* these are NOT yet wired into `CommentatorConfig` — that happens
   in slice 02. Do not modify `CommentatorConfig` here.

3. **Write tests.**
   - New enum values coerce correctly from strings.
   - Each ProfileConfig instantiates with defaults.
   - Each ProfileConfig rejects invalid values (negative interval, zero
     interval, etc.).
   Prior art: existing `CommentatorStyle` coercion tests in `test_config.py`.

## Acceptance criteria

- [ ] `CommentatorStyle.MEETING_SYNTHESIZER` and `CommentatorStyle.SUGGESTER` are importable
- [ ] `_coerce_enum` converts `"meeting_synthesizer"` and `"suggester"` to the correct enum values
- [ ] All four ProfileConfig dataclasses instantiate with defaults and reject invalid values
- [ ] Existing tests remain green — no behavior change

## Blocked by

None — can start immediately.

## User stories addressed

- User story 12
