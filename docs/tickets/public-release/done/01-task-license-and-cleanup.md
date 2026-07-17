# Finalizzare licenza MIT e pulizia file tracciati

## Parent Spec

[public-release-wayfinder.md](../../specs/public-release-wayfinder.md)

## Type

task

## Outcome

`main` contiene LICENSE MIT, `pyproject.toml` con `license = MIT`, README con
menzione della licenza, nessuna skill personale tracciata, e `.gitignore`
aggiornato per `wiki/` e `.tokensave/`.

## Acceptance Criteria

- [ ] `LICENSE` (MIT, copyright 2026 carlitose) presente in root.
- [ ] `pyproject.toml` dichiara `license = { text = "MIT" }`.
- [ ] README ha una sezione/riga "Licenza" che punta a LICENSE.
- [ ] `.agents/skills/project-designer/SKILL.md` rimosso dal tracking
      (`git rm`), e `.agents/` gitignorato per evitare ricadute.
- [ ] `wiki/` e `.tokensave/` aggiunti a `.gitignore` (o gestiti diversamente
      con motivazione registrata).
- [ ] PR verso `main` creata e mergiata.

## Blocked By

- None - can start immediately.

## Frontier

È il primo blocco concreto: senza licenza su main il repo non può diventare
pubblico. Lavoro già parzialmente svolto sulla branch
`chore/public-release-prep` (LICENSE creato, pyproject aggiornato, non
committato).

## Work Plan

1. Riprendere la branch `chore/public-release-prep` (già creata da main).
2. Verificare LICENSE e pyproject già modificati; aggiungere la riga licenza
   nel README.
3. `git rm .agents/skills/project-designer/SKILL.md`; aggiungere `.agents/`,
   `wiki/`, `.tokensave/` a `.gitignore`.
4. Commit, push, PR su `main`, merge.

## Evidence to Capture

- Hash del commit/PR di merge.
- Output `git ls-files .agents wiki .tokensave` vuoto dopo il merge.

## Out of Scope

- Revisione screenshot (ticket 02) e lingua README (ticket 03).
- Qualsiasi modifica ai docs interni.

---

## Esito (2026-07-17) — CHIUSO

Tutti i criteri soddisfatti: LICENSE MIT in root, pyproject `license = MIT`,
sezione Licenza nel README, `.agents/` untracked e gitignorato insieme a
`wiki/`/`.tokensave/`/`.ruff_cache/`. PR #26 mergiata su main (merge commit
`974f327`). `git ls-files .agents wiki .tokensave` vuoto.
