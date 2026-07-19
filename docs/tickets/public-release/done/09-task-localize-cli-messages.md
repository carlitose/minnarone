# (Follow-up, non bloccante) Localizzare i messaggi CLI runtime in inglese

## Parent Spec

[public-release-wayfinder.md](../../specs/public-release-wayfinder.md)

## Type

task

## Outcome

I messaggi a runtime rivolti all'utente (es. `errore di config: ...`,
`credenziali Twitch chat mancanti...`, `ok: agente ... costruito`) e i commenti
inline dei config-example sono in inglese, coerenti col README pubblico inglese.
Emerso dalla verifica fresh-install (ticket 07), severità "note".

## Acceptance Criteria

- [x] Le stringhe utente della CLI (`src/minnarone/cli.py`, errori di
      validazione config, messaggi di build/avvio) sono in inglese o gated su
      locale.
- [x] I commenti del blocco "Config example" nel README e/o i file
      `examples/*.yaml` sono coerenti con la lingua scelta.
- [x] Test aggiornati se asseriscono stringhe italiane.
- [x] `pytest` verde.

## Blocked By

- [12-research-first-operator-journey.md](done/12-research-first-operator-journey.md)
- [18-task-fix-operator-journey-drift.md](done/18-task-fix-operator-journey-drift.md) — done

Il ticket 18 è chiuso: questo follow-up è sbloccato e resta polish separato,
coordinabile col lavoro user-facing del ticket 17.

## Frontier

NON blocca il flip a pubblico (ticket 05): README inglese + runtime italiano è
funzionale e comune. È polish post-pubblicazione. Da valutare l'ampiezza:
tradurre tutte le stringhe CLI tocca molti file e molti test.

## Work Plan

1. Censire le stringhe user-facing (grep su `raise`, `print`, messaggi di
   errore config in `src/minnarone/`).
2. Decidere: traduzione secca vs i18n gated su locale.
3. Tradurre + aggiornare i test che le asseriscono.

## Evidence to Capture

- Elenco file/stringhe toccati; esito pytest.

## Out of Scope

- Traduzione dei docs operativi e dei docs interni (restano italiani).

## Completion Evidence (2026-07-19)

- Tradotte in inglese le superfici dei quattro comandi installati, gli errori
  runtime/config/provider/capture propagati alla CLI e tutta la copia pubblica
  dashboard/TUI; docstring, commenti interni e prompt/persona restano italiani.
- Tradotti i commenti fenced di `README.md` e dei cinque example YAML pubblici;
  `README.it.md`, valori come `language: it` e la semantica dei config restano
  invariati.
- Test aggiornati e rafforzati per help, errori, dashboard/TUI, commenti README,
  redazione dei segreti e contratti dei provider.
- Suite completa: `1287 passed`; `make quality`, `git diff --check` e tutti i
  comandi `--help` verdi.
- Tre iterazioni di review: verdetti finali code-review `Pass` e anti-pattern
  review `LGTM`, nessun finding residuo.
- QA offline: help, config valida/non valida, build failure, dipendenza TUI,
  dashboard vuota, cinque config example e redazione token/API key tutti verdi.
- Non eseguiti perché richiedono rete/account/hardware: capture Twitch, media
  OS e verifica visuale interattiva della TUI.
