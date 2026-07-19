---
name: minnarone-twitch-onboarding
description: Prepare a new Minnarone Twitch workspace through a confirmation-gated interview, sanitized soul and facts, a shadow-only configuration, and local validation. Use when a human or code agent asks to set up, configure, or onboard a Twitch channel; do not use for runtime diagnosis or prompt-template editing.
---

# Minnarone Twitch Onboarding

Build a reviewable local workspace that ends in `shadow`. Keep secrets out of
files and make no network calls, model downloads, or live-send changes.

## 1. Inspect the repository

Work from the repository root. Read these canonical sources before proposing
files:

- `README.md` or `README.it.md` for the current golden paths;
- `docs/twitch-operator.md` for commands and live-safety gates;
- `examples/onboarding/twitch-chat-shadow.it.yaml` and
  `examples/onboarding/twitch-full-shadow.it.yaml` for sanitized config shapes;
- `docs/runtime-model-manifest.json` only if media is requested.

If the request changes prompt templates or a `prompts_dir`, stop that part and
route it to `$minnarone-prompts`. Onboarding owns config, soul, and facts, not
prompt-template behavior.

## 2. Interview before writing

Collect only what is needed:

- Twitch channel login, agent name, language, tone, and explicit behavioral
  boundaries;
- stable channel facts and their source; label assumptions instead of inventing
  facts;
- chat-only or media intent, LLM provider, and whether local model artifacts
  already exist;
- disclosure choice, local artifact/retention choice, and an opt-out/delete
  contact;
- for any future live request: dedicated bot account, broadcaster consent, and
  attended operator. These are gates, not values to assume.

Never request or display OAuth tokens or API keys. Refer to environment
variable names only. Default the destination to
`.local/minnarone/onboarding/<channel>/` unless the user supplies another
gitignored path.

## 3. Preview and confirm

Show the exact proposed destination, source template, files, config values,
assumptions, and commands. Explain the distinct roles:

- YAML configuration selects adapters, models, modes, and cadences;
- `soul.md` defines identity, voice, and boundaries;
- `facts/` contains manually curated stable context;
- built-in prompt templates define runtime behavior, while `prompts_dir`
  explicitly overrides them.

Ask for explicit confirmation before the first write. If any destination file
exists, show a diff and ask for separate update approval; never overwrite it
silently.

## 4. Create the shadow workspace

After confirmation, create only the approved files. Use sanitized placeholders,
relative paths, `examplechannel`-style examples, and `twitch.send.mode: shadow`.
Do not enable `live`, populate `allowed_channels` as proof of consent, or write
secrets. For Italian/non-Mandarin speaker identification, use English VoxCeleb
CAM++ with dimension `512` and clustering threshold `0.5`; never recommend the
old `zh-cn` 192-dimension model.

Keep `retention.perceptions_days` honest: it is reserved and inert. State that
shadow still records local chat-bearing artifacts and provide the chosen manual
deletion and opt-out procedure.

## 5. Validate and hand off

Run the narrowest applicable local checks:

```bash
uv run python -m minnarone <config-path> --check
```

If a confirmed `prompts_dir` is present, also run:

```bash
uv run python -m minnarone validate-prompts --config <config-path>
```

Report created and unchanged files, validation results, unresolved requirements,
and the exact shadow command. Stop at shadow. A later live handoff must follow
the attended checklist in `docs/twitch-operator.md`; this skill never promotes
or sends a Twitch message.
