# Contributing to Minnarone

Start with the task-first [README](README.md), then use the architecture and
quality rules in [AGENTS.md](AGENTS.md) whether you are a human contributor or
a code agent. The [specification](docs/SPECIFICATION.md) describes product
intent; the [Twitch operator guide](docs/twitch-operator.md) and
[meeting-assistant guide](docs/meeting-assistant-operator.md) describe supported
operations.

## Development loop

Create a Python 3.11+ environment, install the development dependencies, and
make a focused change with an executable regression test:

```bash
uv sync
uv run pytest tests/path_to_relevant_test.py
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Keep public examples sanitized and shadow-first. Never commit `.env`, tokens,
absolute personal paths, captured chat, or local model weights. Prompt safety
changes must use the `minnarone-prompts` workflow and preserve disclosure,
secret-redaction, and public-send boundaries.

Before handing off, inspect the dirty worktree, leave unrelated user changes
untouched, list the checks you ran, and call out unverified hardware or network
behavior. Do not describe an optional retention field, lazy `--check`, or a
shadow rehearsal as stronger evidence than it is.

## Skill routing for code agents

- [.agents/skills/minnarone-prompts/SKILL.md](.agents/skills/minnarone-prompts/SKILL.md): prompt overrides and validation.
- [.agents/skills/minnarone-twitch-onboarding/SKILL.md](.agents/skills/minnarone-twitch-onboarding/SKILL.md): confirmation-gated Twitch shadow onboarding.
- [.agents/skills/minnarone-runtime-doctor/SKILL.md](.agents/skills/minnarone-runtime-doctor/SKILL.md): read-only runtime readiness diagnosis.

The portable canonical copies live under `.agents/skills/`. Relative aliases
under `.claude/skills/` are optional on symlink-capable checkouts. With
`core.symlinks=false`, a checked-out alias can be a plain file containing its
target; do not treat that file as a skill and load the canonical `.agents`
copy instead.
