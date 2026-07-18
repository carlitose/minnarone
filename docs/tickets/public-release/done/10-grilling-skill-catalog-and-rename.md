# Decidere rinomina di `prompts` e catalogo skill pubblico

## Parent Spec

[public-release-wayfinder.md](../../../specs/public-release-wayfinder.md)

## Type

grilling

## Outcome

Registrare la decisione umana sul nuovo nome della skill `prompts`, sulla
compatibilità col vecchio nome e sul catalogo minimo di skill repo-local che il
progetto vuole offrire ai code agent.

## Acceptance Criteria

- [x] Il nuovo nome canonico di `prompts` è deciso e non collide con skill
      generiche fuori dal repo.
- [x] È deciso se mantenere temporaneamente un alias `prompts` o fare un rename
      netto.
- [x] È deciso il destino del symlink tracciato
      `.claude/skills/project-designer` verso tooling personale non versionato.
- [x] Esiste una shortlist con responsabilità non sovrapposte per le nuove
      skill pubbliche (prompt-set, onboarding/persona/Twitch, runtime doctor).
- [x] Le decisioni e le alternative scartate sono riportate nel Decision Log
      di questo ticket, così il record resta autosufficiente.

## Blocked By

- None.

## Frontier

Risolta: nome, migrazione e catalogo sono confermati; il rename atomico è
eseguibile dal ticket 11.

## Work Plan

1. Confrontare i nomi candidati.
2. Decidere rename netto vs alias deprecato.
3. Definire responsabilità non sovrapposte per le skill successive.
4. Classificare symlink/skill attuali come pubblici, personali o da rimuovere.
5. Aggiornare la mappa.

## Evidence to Capture

- Risposte dell'utente nella sessione 2026-07-18.
- `git ls-files .agents .claude` e struttura reale delle skill.
- Riferimenti attuali nei README e negli script della skill.

## Out of Scope

- Eseguire il rename (ticket 11).
- Scrivere le nuove skill (ticket 16 dopo il prototipo).
- Riscrivere il README (ticket 17).

## Decision Log

- 2026-07-18 — Nome canonico: `minnarone-prompts`.
- 2026-07-18 — Rename netto senza alias `prompts`.
- 2026-07-18 — Rimuovere il symlink personale `project-designer`.
- 2026-07-18 — Catalogo confermato:
  - `minnarone-prompts`: modifica, validazione e preview dei prompt-set;
  - `minnarone-twitch-onboarding`: intervista soul/facts, config e percorso
    Twitch shadow/live;
  - `minnarone-runtime-doctor`: dipendenze, modelli e smoke diagnostici.

## Status

Done — 2026-07-18.
