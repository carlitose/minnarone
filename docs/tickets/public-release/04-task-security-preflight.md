# Pre-flight di sicurezza sulla history e sui file tracciati

## Parent Spec

[public-release-wayfinder.md](../../specs/public-release-wayfinder.md)

## Type

task

## Outcome

Conferma con tool dedicato che l'intera history git e i file tracciati non
contengono segreti, come rete di sicurezza finale prima del flip. I check
manuali della sessione 2026-07-17 (`.env` mai committato, grep pattern puliti)
vengono ri-verificati in modo sistematico.

## Acceptance Criteria

- [ ] Scan completo della history con gitleaks (o trufflehog) eseguito:
      `gitleaks detect --source . --log-opts="--all"`.
- [ ] Eventuali finding triaged: veri positivi risolti (rotazione credenziale +
      decisione su riscrittura history), falsi positivi documentati.
- [ ] `git ls-files` rivisto per artifact residui (log, dump, output di run,
      file IDE/personali).
- [ ] Esito riassunto nella mappa.

## Blocked By

- [01-task-license-and-cleanup.md](01-task-license-and-cleanup.md) — lo scan
  finale va fatto sullo stato di main post-pulizia.

## Frontier

Ultimo gate tecnico prima del flip: il flip rende pubblica tutta la history,
irreversibilmente (i fork/mirror nascono subito). Un tool dedicato copre
pattern che i grep manuali non coprono.

## Work Plan

1. Installare/eseguire gitleaks sull'intero repo, tutta la history.
2. Triage dei finding; documentare i falsi positivi.
3. Rivedere `git ls-files` completo per file fuori posto.
4. Riportare l'esito nella mappa.

## Evidence to Capture

- Output (o riassunto) del report gitleaks.
- Elenco finding con triage.

## Out of Scope

- Riscrittura della history (solo se un vero positivo la rende necessaria —
  in quel caso diventa un ticket dedicato).
