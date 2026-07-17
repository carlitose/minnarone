# 07 — Task: pre-commit tooling (stile ai-agent-python-api)

## Parent Spec

[prompt-externalization-followups-wayfinder.md](../../specs/prompt-externalization-followups-wayfinder.md)

## Type

task

## Outcome

Minnarone adotta un `.pre-commit-config.yaml` con hook locali via `uv run`,
sul modello di `../ai-agent-python-api` (richiesta operatore 2026-07-17):
ruff format, ruff check --fix, vulture, deptry, pylint duplicate-code. I check
girano automaticamente al commit, riconciliati col meccanismo `.githooks`
esistente.

## Stato attuale (verificato)

- `.githooks/pre-commit` esegue `make quality` (ruff check, vulture, deptry,
  pylint R0801); attivato con `git config core.hooksPath .githooks` (README).
- `pre-commit` NON è nelle dev deps.
- ⚠️ `ruff format --check`: **70 file da riformattare** (il repo non ha mai
  usato ruff format) → adottarlo implica un commit una-tantum di riformattazione.
- `check-layers` del progetto di riferimento NON si applica (minnarone non è
  esagonale) — escluso.

## Acceptance Criteria

- [ ] `.pre-commit-config.yaml` con hook locali `uv run`: ruff-format,
      ruff-check --fix, vulture, deptry, pylint duplicate-code (args coerenti
      col Makefile: `src tests`).
- [ ] `pre-commit` aggiunto alle dev deps (`pyproject.toml [dev]`).
- [ ] Riconciliazione con `.githooks`: UNA sola fonte di verità. Proposta
      raccomandata: `.githooks/pre-commit` diventa `uv run pre-commit run`
      (così `core.hooksPath` già documentato continua a funzionare e la config
      è nel file YAML); in alternativa migrare a `pre-commit install` e
      aggiornare README. Scelta motivata nel ticket.
- [ ] Riformattazione una-tantum dei 70 file in un **commit separato e
      behavior-neutral** ("style: ruff format (one-time)"), con suite completa
      verde prima e dopo (stesso numero di test passed).
- [ ] `uv run pre-commit run --all-files` verde a fine ticket.
- [ ] `make quality` resta funzionante (o viene aggiornato coerentemente).
- [ ] README (sezione Quality checks) aggiornato: setup con
      `uv run pre-commit install` o hooksPath, come da scelta.

## Blocked By

- None — può partire subito (dopo FU-04 il lint è già a zero).

## Frontier

Igiene di processo: automatizza al commit ciò che oggi è manuale, allineando
minnarone allo standard degli altri repo dell'operatore.

## Work Plan

1. Aggiungere `pre-commit` alle dev deps.
2. Scrivere `.pre-commit-config.yaml` (hook locali `uv run`, come il modello,
   senza check-layers).
3. Riconciliare `.githooks` ↔ pre-commit (scelta raccomandata sopra).
4. Commit una-tantum `ruff format` (separato); suite verde prima/dopo.
5. `pre-commit run --all-files` verde; README aggiornato.

## Evidence to Capture

- Output `pre-commit run --all-files`.
- Conteggio test passed prima/dopo la riformattazione.

## Out of Scope

- check-layers / architettura esagonale.
- Cambiare le regole ruff (`[tool.ruff]`) oltre l'aggiunta del formatter.
- CI remota (solo hook locali).
