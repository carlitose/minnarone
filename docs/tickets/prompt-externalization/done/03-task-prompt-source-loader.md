# 03 — Task: modulo PromptSource (loader reale) + tracer

## Parent Spec

[prompt-externalization-wayfinder.md](../../specs/prompt-externalization-wayfinder.md)

## Type

task

## Outcome

Un modulo di caricamento prompt (`PromptSource` o simile) che implementa il
contratto deciso nel ticket 02: legge i file di prompt da default impacchettati
con override da percorso in config, sostituisce i placeholder in modo sicuro, e
valida (fail-fast o fallback secondo la decisione). Per de-rischiare, migra UN
solo prompt come tracer bullet end-to-end (dal file al prompt costruito),
lasciando gli altri hard-coded per i ticket 04-06.

## Acceptance Criteria

- [ ] Modulo di loading con: risoluzione default impacchettati (`importlib.resources`
      o equivalente) + override da config; sostituzione placeholder sicura;
      validazione secondo 02.
- [ ] Un prompt tracer (es. `[FORMATO RISPOSTA]` o la persona) è servito dal file,
      non più dalla costante; la costante hard-coded corrispondente è rimossa.
- [ ] Le regole di SICUREZZA (anti-injection, disclosure, fence) restano cablate e
      intatte.
- [ ] Byte-invarianza del prefisso stabile preservata (con file default fissi).
- [ ] Degrado/errore su file mancante conforme alla decisione 02 (niente vuoto
      silenzioso per contenuti obbligatori).
- [ ] Test del loader (default, override, placeholder, file mancante) + il prompt
      builder che consuma il tracer restano verdi; suite intera verde.

## Blocked By

- Blocked by [02-prototype-format-loader-packaging.md](./02-prototype-format-loader-packaging.md)

## Frontier

Trasforma il contratto provato (02) in infrastruttura stabile su cui poggiano le
migrazioni. Il tracer prova l'intero percorso file→prompt prima di spostare tutto.

## Work Plan

1. Implementare il modulo di loading secondo il contratto 02 (TDD).
2. Impacchettare i file default (build config: includere le risorse nel wheel).
3. Migrare 1 prompt tracer end-to-end; rimuovere la costante relativa.
4. Test loader + builder; verificare byte-invarianza e packaging (import da wheel/
   risorsa).

## Evidence to Capture

- Diff del nuovo modulo + config di build per le risorse.
- Test verdi; prova che la risorsa default si risolve senza override.

## Out of Scope

- Migrare gli altri prompt (04-06).
- Esternalizzare le regole di sicurezza.
