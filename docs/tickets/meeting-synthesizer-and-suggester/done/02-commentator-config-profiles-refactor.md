## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Replace the single `style` and `enabled` fields in `CommentatorConfig` with a
`profiles` dictionary that maps `CommentatorStyle` to its `ProfileConfig`. This
is the core config contract change that all subsequent slices build on.

Only the config module and its tests change here. Consumers (app.py, prompt.py,
reactor.py, dashboard.py) are updated in slice 03.

## Step-by-step implementation plan

1. **Replace `style` and `enabled` with `profiles`.**
   In `CommentatorConfig`, remove the `enabled: bool` and
   `style: CommentatorStyle` fields. Add
   `profiles: dict[CommentatorStyle, ProfileConfig]` (default: empty dict).
   Keep `language: str = "it"` at the `CommentatorConfig` level (shared default
   inherited by all profiles).
   *Verify:* `CommentatorConfig()` creates an empty-profiles config.
   *Pitfall:* `enabled` becomes implicit — `len(profiles) > 0` means enabled.

2. **Add `active_styles()` and update helper methods.**
   Replace `prompt_style()` with `active_styles() -> list[CommentatorStyle]`
   that returns the keys of `profiles`. Update `uses_local_output(mode)` to
   check `len(profiles) > 0` instead of `enabled`. Update or remove
   `idle_interval_or(default)` — each profile now carries its own idle
   interval.
   *Verify:* `active_styles()` returns the correct list for various profile
   combinations.

3. **Update `validate_for_mode`.**
   Adapt the cross-field validation:
   - Any non-empty profiles require `mode: private` (same constraint as before).
   - `ORIGINAL_CHAT` in profiles still requires private mode.
   - New styles (`MEETING_SYNTHESIZER`, `SUGGESTER`) also require private mode.
   *Verify:* public mode + any profile raises `ConfigError`.

4. **Update `_commentator_config_from_dict`.**
   Parse the new YAML format:
   ```yaml
   commentator:
     language: it
     profiles:
       operator:
         idle_interval: 30.0
       meeting_synthesizer:
         interval_s: 180
       suggester: {}
   ```
   For each key in `profiles`, coerce the key to `CommentatorStyle` and
   construct the corresponding `ProfileConfig` dataclass. Reject unknown keys
   at both levels (commentator level and within each profile).
   *Verify:* parsing produces correct `CommentatorConfig` with typed profiles.
   *Pitfall:* an empty dict value (`suggester: {}`) must produce a valid
   `SuggesterProfileConfig()`, not an error.

5. **Write tests.**
   - Empty profiles → not enabled, `active_styles()` empty.
   - Single profile → enabled, `active_styles()` returns it.
   - Multiple profiles → all present in `active_styles()`.
   - Unknown profile key → `ConfigError`.
   - Unknown field within a profile → `ConfigError`.
   - Profile-specific validation (negative `interval_s` → error).
   - `validate_for_mode` with public mode + profiles → error.
   - Round-trip: construct from dict, check all fields.
   Prior art: existing `CommentatorConfig` tests in `test_config.py`.

## Acceptance criteria

- [ ] `CommentatorConfig` no longer has `style` or `enabled` fields
- [ ] `profiles` dict maps `CommentatorStyle` to typed `ProfileConfig` dataclasses
- [ ] `active_styles()` returns the correct list
- [ ] Parser handles new YAML format including empty profile dicts
- [ ] Unknown keys rejected at both levels
- [ ] `validate_for_mode` enforces private mode for all profile types
- [ ] Config module tests pass with the new format

## Blocked by

- Blocked by [01-enum-values-and-profile-config-types.md](./01-enum-values-and-profile-config-types.md)

## User stories addressed

- User story 9
- User story 12
