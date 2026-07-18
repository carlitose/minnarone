---
name: minnarone-prompts
description: Safely manage minnarone's externalized prompts. Use when asked to change/edit the prompts, translate the prompt-set into another language, validate an override or a prompts_dir, add/rename section headers, or preview the effect of a prompt change before committing. Three modes - validate, edit, try.
---

# Skill `minnarone-prompts` — validate, edit and preview the externalized prompts

One skill with three modes (**validate** / **edit** / **try**) because the three
flows share the same file map, the same constraints and the same warnings — and
in practice they always chain: edit → validate → try.

## System map (where things live)

- **Source of truth for constraints**: `src/minnarone/prompt_source.py` — the
  `PromptSpec`/`KeySpec` definitions (`FORMAT_SPEC`, `RULES_SPEC`, `INTRO_SPEC`,
  `SITUATIONS_SPEC`, `HEADERS_SPEC`, `OPERATOR_RULES_SPEC`,
  `MEETING_SYNTHESIZER_RULES_SPEC`, `SUGGESTER_RULES_SPEC`, `SUMMARIZER_SPEC`)
  declare, per file, the allowed/required placeholders, control tokens and
  required sections. **When in doubt or on any divergence, read the specs in the
  code: the table below is a summary, not the source.**
- **Packaged defaults**: `src/minnarone/prompts/*.md` (9 files, Italian).
- **Override**: a directory named by `prompts_dir` in the config YAML (resolved
  relative to the config file). **Per-file** precedence: a file present in the
  override wins; the others fall back to the packaged default.
- **Language swap** = rewrite the `.md` files and point `prompts_dir` at them.
  Commented partial example: `examples/prompts-en/` (read its README).

## ⚠️ Security boundary (what is deliberately NOT in the files)

The anti-injection / anti-disclosure rules and the untrusted-data fence
(`DATI_PERCEPITI`, `| ` line prefix) are **hard-coded in
`src/minnarone/prompt.py`** and do NOT appear in the editable `.md` files. An
override can change persona, language and labels but cannot weaken the
protection: the security text is always prepended under the `regole` label,
whatever the label says. **Do not try to "externalize" these parts or replicate
them in the files: it is a recorded design decision, not an oversight.**

## ⚠️ Byte-invariance (why the defaults are not edited casually)

The stable prefix of the prompt is cached on the LLM side: with the packaged
defaults it must stay **byte-identical** across builds. The tests
(`tests/test_prompt_fresh_install.py`, `tests/test_prompt_builder.py`) pin the
content of the defaults: touching `src/minnarone/prompts/*.md` makes them fail
until you update them consciously. **The safe path to experiment or customize is
an override via `prompts_dir`**, never editing the defaults — change the defaults
only when the change is intended for everyone and you update the tests
accordingly.

## File / constraint table (summary derived from the PromptSpecs — verify in code)

| File | Keyed? | Required placeholders | Required control tokens | Notes |
|------|--------|-----------------------|-------------------------|-------|
| `format.md` | no | — | `RE:`, `MSG:`, `#end_conv` | Output-parser contract |
| `rules.md` | no | `{{channel}}` | — | Persona, in the stable prefix |
| `intro.md` | no | `{{channel}}` | — | Dynamic banner |
| `situations.md` | yes (6 sections) | per-section, see below | `#end_conv` in `idle`, `chat-mention`, `chat-continuation`, `streamer-continuation` | PER-SECTION constraints in `SITUATIONS_SPEC.key_specs` |
| `headers.md` | yes (17 keys) | `{{channel}}` only in `cosa_sai` | — | No `{{header_*}}` allowed here (no recursion) |
| `operator.md` | no | `{{language}}` | — | Operator style |
| `meeting_synthesizer.md` | no | `{{language}}` | — | Meeting style |
| `suggester.md` | no | `{{language}}` | `#nothing` | "nothing to suggest" sentinel |
| `summarizer.md` | yes (8 keys) | NO placeholders allowed | — | Separate set (`SUMMARIZER_SET`) |

Per-section details of `situations.md` (from `SITUATIONS_SPEC.key_specs`):
`{{user}}`/`{{mention}}` are allowed ONLY in `chat-mention` and
`chat-continuation`; `{{reason}}` ONLY in `generic`; the cross-references
`{{header_memoria}}`, `{{header_tuoi_ultimi_messaggi}}`,
`{{header_conversazione_recente}}` are allowed in EVERY section (resolved from
`headers.md`, so renaming a header propagates automatically). A placeholder in a
section whose render path does not supply it fails at startup.

Cross-cutting rules:

- Placeholders are EXACTLY `{{name}}`; single braces and `<...>` stay literal. A
  `{{x}}` outside the whitelist = error at load.
- Section **keys** (`## idle`, `## regole`, ...) are the contract: translate the
  BODIES, never the keys.
- Never leave a file or section empty: the loader is fail-fast, it does not
  degrade.

---

## VALIDATE mode

Validate both sets (original-chat + summarizer) with the real entry point:

```bash
# packaged defaults only
uv run python -m minnarone validate-prompts

# with an override directory
uv run python -m minnarone validate-prompts --prompts-dir PATH/TO/DIR

# reading prompts_dir from a config YAML (same relative resolution as the app)
uv run python -m minnarone validate-prompts --config PATH/TO/CONFIG.yaml
```

Exit codes: `0` = all valid; `1` = prompt errors (one line per problem on stderr,
with the file and — for keyed files — the offending SECTION); `2` = config
error. On exit 0 it prints each file's origin (`default`/`override`) and a
**partial-override notice** if only some files come from the override (possible
language mix: confirm it is intended).

Report the errors as-is: they are already actionable (e.g.
`token di controllo mancante in 'situations.md' sezione 'chat-mention': '#end_conv'`).

## EDIT mode

Guided flow to change or translate the prompts:

1. **Pick the target**: an override via `prompts_dir` (the normal case: trying,
   customizing, translating) or the packaged defaults (only if the change is for
   everyone — see byte-invariance above). For an override, start by copying the
   default file from `src/minnarone/prompts/`.
2. **Check the constraints** of the file you touch: the table above + the
   relevant `PromptSpec` in `src/minnarone/prompt_source.py`. NEVER remove
   required placeholders (`{{channel}}`, `{{language}}`), control tokens
   (`#end_conv`, `#nothing`, `RE:`, `MSG:`), required sections or keys.
3. **Edit** the `.md`.
4. **Validate**: `uv run python -m minnarone validate-prompts --prompts-dir DIR`
   (or without a flag if you touched the defaults). It must exit 0.
5. **Targeted tests** (mandatory if you touched the defaults, recommended
   always):

   ```bash
   uv run --extra dev python -m pytest -q tests/test_prompt_source.py tests/test_prompt_builder.py tests/test_prompt_fresh_install.py tests/test_cli.py
   ```

6. **Diff review**: `git diff` — check you did not touch section keys,
   placeholders or tokens by mistake; if you changed the defaults, verify every
   stable-prefix change is intended.
7. (Optional but recommended) **Preview the effect** with TRY mode.

## TRY mode

Two levels, from lightest to fullest:

1. **Render the prompt** with fake perceptions — shows the FULL prompt the LLM
   would receive, using the script bundled with the skill:

   ```bash
   # packaged defaults
   uv run python .claude/skills/minnarone-prompts/preview_prompt.py

   # with an override
   uv run python .claude/skills/minnarone-prompts/preview_prompt.py PATH/TO/DIR
   ```

   Fail-fast: if the set is broken the script dies with `PromptError` before
   rendering (same behavior as app startup). Useful for a before/after diff: save
   the default and override output and compare them.

2. **App smoke without network** — builds the full agent (prompt validation
   included) and exits:

   ```bash
   # baseline that passes with no extra setup
   uv run python -m minnarone examples/llamacpp-local.example.yaml --check

   # with YOUR config pointing at prompts_dir
   uv run python -m minnarone PATH/TO/CONFIG.yaml --check
   ```

   Exit 0 and `ok: agente '...' costruito (...)` = the prompts (and the rest of
   the config) survive a real startup.
