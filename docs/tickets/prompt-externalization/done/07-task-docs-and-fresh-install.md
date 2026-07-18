# 07 — Task: docs, verifica fresh-install e canale non italiano

## Parent Spec

[prompt-externalization-wayfinder.md](../../specs/prompt-externalization-wayfinder.md)

## Type

task

## Outcome

Documentazione del nuovo meccanismo di prompt esterni e verifica che (a) un fresh
install funzioni coi default impacchettati e (b) un operatore possa puntare a un
proprio set di prompt (anche in un'altra lingua) senza toccare il codice. Chiude
il confine di sicurezza a livello di docs (quali file NON sono editabili perché la
sicurezza resta nel codice).

## Acceptance Criteria

- [ ] README/docs operatore aggiornati: dove stanno i file di prompt, come
      sovrascriverli (percorso in config), quali placeholder esistono.
- [ ] Documentato il caso **canale non italiano**: basta riscrivere i file di
      prompt nella propria lingua (nessun motore i18n), con un esempio minimo.
- [ ] Documentato il **confine di sicurezza**: le regole anti-injection e di
      disclosure restano nel codice e NON sono nei file editabili — motivazione.
- [ ] Verifica fresh-install: da clone pulito, senza override, i default
      impacchettati si risolvono e il prompt si costruisce (test o smoke).
- [ ] Verifica override: puntando la config a un set alternativo, il prompt usa
      quel set.
- [ ] Suite intera verde; nessun prompt tunabile più hard-coded (grep di verifica).

## Blocked By

- Blocked by [04-task-migrate-original-chat.md](./04-task-migrate-original-chat.md)
- Blocked by [05-task-migrate-summarizer.md](./05-task-migrate-summarizer.md)
- Blocked by [06-task-migrate-other-styles.md](./06-task-migrate-other-styles.md)

## Frontier

Passo di chiusura: senza docs + verifica fresh-install/override, la feature è
implementata ma non usabile né dimostrata dall'operatore.

## Work Plan

1. Scrivere la sezione docs (file, override, placeholder, canale non italiano,
   confine di sicurezza).
2. Aggiungere una verifica fresh-install (default impacchettati) e una di override.
3. Grep di verifica che non restino prompt tunabili hard-coded.

## Evidence to Capture

- Diff docs.
- Output verifica fresh-install + override.
- Grep pulito sui prompt tunabili residui.

## Out of Scope

- Fornire set tradotti pronti (è contenuto, non infrastruttura).
- Hot-reload a runtime.