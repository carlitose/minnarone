# 06 — Task: skill di repo `prompts` per il code agent

## Parent Spec

[prompt-externalization-followups-wayfinder.md](../../specs/prompt-externalization-followups-wayfinder.md)

## Type

task

## Outcome

Un code agent (Claude Code) che lavora su questo repo può gestire i prompt in
autonomia e in sicurezza tramite skill locali in `.claude/skills/`, senza dover
riscoprire ogni volta loader, vincoli e comandi. Copertura minima (assunzione
dalla mappa, da confermare in apertura ticket):

- **validate**: valida un set/override col comando del ticket 05 e riporta gli
  errori in forma azionabile.
- **edit**: flusso guidato di modifica — quali file esistono, quali placeholder
  e token NON vanno rimossi, modifica → `validate-prompts` → test mirati
  (`test_prompt_source.py`, `test_prompt_builder.py`, fresh-install) → diff.
- **try**: rende il prompt con un set (default o override) e lo mostra
  (es. via `PromptBuilder.build` con percezioni fake o lo smoke esistente),
  così l'agente vede l'effetto della modifica prima di committare.

## Acceptance Criteria

- [ ] Skill(s) in `.claude/skills/` (una `prompts` con sottocomandi o 2-3
      separate — scelta motivata nel ticket) con frontmatter e descrizioni che
      le fanno scattare sulle richieste giuste ("cambia i prompt", "traduci il
      set", "valida il mio override", ...).
- [ ] La skill di edit incorpora i vincoli non ovvi: token di controllo
      (`#end_conv`, `#nothing`, `RE:`, `MSG:`), placeholder richiesti
      (`{{channel}}`, `{{language}}`), sezioni richieste, confine di sicurezza
      (cosa NON è nei file e perché), byte-invarianza per i default.
- [ ] Ogni skill usa comandi reali e verificati (validate-prompts del 05, pytest
      mirati, eventuale smoke `/run`), non pseudo-procedure.
- [ ] Prova end-to-end documentata: un agente segue la skill per creare un
      override rotto → la skill lo porta a scoprire l'errore all'avvio e a
      correggerlo.
- [ ] README (sezione contributor/agent) menziona le skill.

## Blocked By

- Blocked by [05-task-vlm-skip-and-validate-cli.md](./05-task-vlm-skip-and-validate-cli.md)
  (serve il comando di validazione).

## Frontier

Trasforma l'infrastruttura dei prompt in un flusso operabile da agenti: è il
"manuale eseguibile" che evita regressioni da editing manuale.

## Work Plan

1. Decidere la granularità (1 skill con modalità vs 2-3 skill) e scriverle.
2. Includere la mappa dei file/vincoli (generata dai `PromptSpec`, non duplicata
   a mano dove possibile).
3. Prova end-to-end con override rotto e correzione guidata.
4. README + eventuale nota in CLAUDE.md del repo.

## Evidence to Capture

- Trascrizione della prova end-to-end.
- Le skill stesse.

## Out of Scope

- Skill per aspetti non-prompt (build, deploy, ecc.).
- Automazioni via hook (solo skill invocabili).
