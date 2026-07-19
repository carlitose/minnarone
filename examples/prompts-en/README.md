# Example prompt override (English, partial)

This is a **minimal, illustrative** prompt-set override, not a maintained
translation. It exists to make the "non-Italian channel" story concrete: the
externalized prompts *are* the localization mechanism — there is no i18n engine.

## What it contains

- `rules.md` — Minnarone's persona/style rewritten in English. Keeps the one
  required placeholder `{{channel}}`.
- `intro.md` — the "current situation" banner in English. Also keeps
  `{{channel}}`.
- `headers.md` — the section headers and framing lines of the reaction prompt
  in English (`[RULES]`, `[MEMORY]`, `[SITUATION]`, `[RECENT CHAT]`, ...). The
  **keys** (`regole`, `memoria`, `situazione`, ...) are the contract and stay
  as they are; only the values are translated. `{{channel}}` stays in
  `cosa_sai`.
- `situations.md` — the 6 situation variants in English. Where a body cites a
  section header it uses a placeholder (`{{header_memoria}}`,
  `{{header_tuoi_ultimi_messaggi}}`, `{{header_conversazione_recente}}`)
  instead of the literal name: the reference is resolved from `headers.md`, so
  it always matches the actual section header — rename `[MEMORY]` in
  `headers.md` and every text citing it follows automatically.

## How to use it

Point `prompts_dir` at this folder in your config (path is resolved relative to
the config file, exactly like `soul_path` / `facts_dir`):

```yaml
prompts_dir: prompts-en   # e.g. when the config sits next to this examples/ dir
```

## Per-file precedence (important)

Overrides are resolved **per file**: for each prompt file, if it exists here it
wins; otherwise the packaged Italian default is used. This set does not
override `format.md`, the summarizer and the other per-style prompts, so those
still fall back to the packaged Italian defaults — you would see a partly
**mixed-language** prompt (`minnarone validate-prompts --prompts-dir ...`
prints a partial-override notice for exactly this reason).

To ship a fully English channel, copy the complete default set from
`src/minnarone/prompts/` and rewrite every `.md` in your language, keeping the
placeholders (`{{channel}}`, `{{language}}`, `{{user}}`, `{{mention}}`,
`{{reason}}`, `{{header_*}}`) and the control tokens (`#end_conv`, `#nothing`,
`RE:`, `MSG:`) intact. The loader is fail-fast: a missing placeholder, control
token or required section aborts startup rather than degrading silently.

## What you cannot override

The anti-injection and disclosure rules are **hard-coded** in `prompt.py` and are
intentionally NOT part of these editable files. A prompt override can change the
persona and language but can never weaken the security boundary: the untrusted
data fence (`DATI_PERCEPITI`, the `| ` line prefix) is always hard-coded, and
the configured disclosure stance is appended after tunable rules so an override
cannot become the last, contradictory instruction.
