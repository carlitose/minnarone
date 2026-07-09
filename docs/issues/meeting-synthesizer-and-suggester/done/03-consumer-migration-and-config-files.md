## Parent PRD

[meeting-synthesizer-and-suggester.md](../../prds/meeting-synthesizer-and-suggester.md)

## What to build

Update every module that reads `commentator.style`, `commentator.enabled`, or
`commentator.prompt_style` to use the new `profiles` API. Migrate all `.local`
and `examples/` config files to the new YAML format. At the end of this slice
the system works exactly as before (OPERATOR and ORIGINAL_CHAT) but configured
via profiles.

## Step-by-step implementation plan

1. **Find all consumers of the old API.**
   Grep the codebase for `commentator.style`, `commentator.enabled`,
   `prompt_style`, and `idle_interval_or`. These are the call sites to update.
   Key files: `app.py`, `prompt.py`, `reactor.py`, `dashboard.py`,
   `output_sink.py`, and their tests.
   *Pitfall:* don't miss test files — they construct `CommentatorConfig`
   directly.

2. **Update `app.py`.**
   `build_agent` currently reads `config.commentator.prompt_style` and
   `config.commentator.enabled`. Replace with iteration over
   `config.commentator.active_styles()` and profile lookups. For now, the
   wiring still produces a single Reactor (multi-Reactor comes in slice 11) —
   take the first profile if multiple exist, or handle only OPERATOR /
   ORIGINAL_CHAT and skip unknown styles with a warning.
   *Verify:* `build_agent` with an OPERATOR profile produces the same Agent as
   before.
   *Pitfall:* the automatic ORIGINAL_CHAT promotion for `twitch + public` must
   be preserved — translate it to a profile insertion.

3. **Update `prompt.py`.**
   `PromptBuilder` receives `commentator_style` in its constructor. This stays
   as a `CommentatorStyle | None` — it's per-Reactor, not per-config. No
   structural change needed, just verify it still works with the new enum
   values (even though the new prompt templates come in slices 06/07).
   *Verify:* OPERATOR and ORIGINAL_CHAT prompts build correctly.

4. **Update `reactor.py`.**
   The Reactor reads `prompt_builder.commentator_style`. Verify this path
   works with profiles-originated styles. No structural change yet.
   *Verify:* Reactor tests pass.

5. **Update `dashboard.py` and `output_sink.py`.**
   Dashboard reads commentator state for rendering. Update any references to
   `commentator.enabled` or `commentator.style`. The TUI output sink may
   reference `uses_local_output` — verify it works with the new API.
   *Verify:* dashboard tests pass.

6. **Migrate config files.**
   Convert every config from the old format to the new:
   - `.local/teams-commentator.local.yaml`
   - `.local/twitch-commentator.local.yaml`
   - `.local/teams-commentator.audio.local.yaml`
   - `examples/teams-commentator.yaml`
   - `examples/twitch-commentator.example.yaml`
   - `examples/twitch-original-chat.example.yaml`

   Old:
   ```yaml
   commentator:
     enabled: true
     style: operator
     language: it
     idle_interval: 30.0
   ```
   New:
   ```yaml
   commentator:
     language: it
     profiles:
       operator:
         idle_interval: 30.0
   ```

   Files without a `commentator` section (e.g. `minnarone.example.yaml`,
   `twitch.example.yaml`) need no changes.
   *Verify:* `python -m minnarone <config> --check` passes for every file.
   *Pitfall:* `.local` files are not in git — update them manually but
   document the format change.

7. **Update all test files.**
   Grep tests for `CommentatorConfig(` or `commentator` dict construction.
   Update to the new profiles format.
   *Verify:* full test suite green. `make quality` passes.

## Acceptance criteria

- [ ] No remaining references to `commentator.style`, `commentator.enabled`, or `prompt_style()` in the codebase
- [ ] All `.local` and `examples/` configs use the new `profiles` format
- [ ] `python -m minnarone <config> --check` passes for every config file
- [ ] OPERATOR and ORIGINAL_CHAT behavior is unchanged end-to-end
- [ ] Full test suite green

## Blocked by

- Blocked by [02-commentator-config-profiles-refactor.md](./02-commentator-config-profiles-refactor.md)

## User stories addressed

- User story 9
- User story 12
