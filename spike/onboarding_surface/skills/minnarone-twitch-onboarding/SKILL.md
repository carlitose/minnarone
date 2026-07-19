---
name: minnarone-twitch-onboarding
description: Create or update Minnarone Twitch soul, facts and shadow configuration through a confirmation-gated interview. Use for new-channel onboarding, persona/channel edits, or preparing a safe shadow run; use minnarone-prompts only for prompt-template overrides.
---

# Minnarone Twitch onboarding prototype

Use this skill only for onboarding a Twitch channel. Use `minnarone-prompts`
instead when the user explicitly wants to validate, edit, translate or preview
prompt-template overrides.

## Hard gate before writes

Do not create or modify `soul.md`, facts or config until the operator has seen
and explicitly confirmed the exact Markdown preview and each field's origin.

Ask for:

- persona name/nickname, role, tone, two to five traits or opinions,
  behavioural limits and typical message length;
- optional age, bio, team and interests;
- channel name, content and relationship to the persona;
- language (default from `commentator.language`, confirm ambiguity);
- whether a clearly labelled `## Contesto corrente` should persist;
- dedicated bot account, broadcaster-consent status, disclosure choice and
  acknowledgement of retained artifacts/manual deletion.

Twitch metadata may prefill only verifiable name/category/title/live state.
Inferences must be labelled and confirmed. Never treat an allow-list as proof
of broadcaster permission.

## Preview and apply

1. Default to `.local/<channel>/` and one facts file per entity.
2. Keep persona/tone in `soul.md`, channel knowledge in `facts/*.md`, and shared
   format/security in prompt templates.
3. Show exact file contents plus origin labels. For existing files show a
   minimal diff and never overwrite silently.
4. Write only after exact confirmation. Current context needs separate opt-in
   and a warning that it persists into future sessions. On the next session,
   force the operator to replace, remove or reconfirm that section.
5. Run `minnarone validate-prompts --config <config>` and
   `minnarone <config> --check`; keep the diff on failure and propose a fix.
6. Stop at shadow. Never start runtime or promote live during onboarding.

The disposable test driver is `../../onboarding.py`; canonical input contracts
are the ticket 13 decision and `../../../../docs/prototypes/agent-human-onboarding.md`.
It is not a production command.
