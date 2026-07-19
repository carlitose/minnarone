# Working on Minnarone

Read `README.md`, `docs/SPECIFICATION.md`, and the relevant operator guide
before changing behavior. The runtime lives in `src/minnarone/`; executable
contracts live in `tests/`; sanitized examples live in `examples/`. Research
records evidence, while current runtime and tests remain authoritative when an
older document disagrees.

## Architecture and quality

Keep adapters, perception, prompt construction, output routing, and safety
gates separated along the existing module boundaries. Prefer the narrowest
test first, then run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Do not weaken shadow/live gates, secret redaction, bounded queues, or artifact
limits to make a test pass.

## Prompt safety

Built-in templates are in `src/minnarone/prompts/`; operator overrides belong
in an explicit `prompts_dir`. Preserve the disclosure and public-send safety
floor, never put credentials or private chat data in prompts/examples, and use
the prompt skill for override changes. Config, soul, and facts are not prompt
templates.

## Dirty worktree

Assume pre-existing modifications and untracked files belong to the human.
Inspect status and diffs before editing, preserve unrelated work, and never use
destructive reset/checkout commands. Report what you changed separately.

## Skill routing

Treat `.agents/skills/` as the portable canonical catalog. Use a
`.claude/skills/` alias only when it is a symlink that resolves to that catalog;
a `core.symlinks=false` plain-file checkout is not a valid skill.

- Prompt overrides, translation, validation, or previews:
  [minnarone-prompts](.agents/skills/minnarone-prompts/SKILL.md).
- New channel config, soul, facts, and shadow workspace:
  [minnarone-twitch-onboarding](.agents/skills/minnarone-twitch-onboarding/SKILL.md).
- Read-only P0-P5 tool/model/config readiness:
  [minnarone-runtime-doctor](.agents/skills/minnarone-runtime-doctor/SKILL.md).

Load the matching `SKILL.md` before acting. Keep its stated boundary; route a
mixed request between skills instead of expanding one skill silently.
