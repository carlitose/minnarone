# Inventario del primo percorso operatore Twitch reale

## Parent Spec

[public-release-wayfinder.md](../../../specs/public-release-wayfinder.md)

## Type

research

## Outcome

Trasformare la sessione operatore reale in una matrice evidence-backed di gap, con
severità, owner (docs/config/runtime/skill) e decisione: fix prima del pubblico,
follow-up o comportamento intenzionale.

## Acceptance Criteria

- [x] La matrice copre discovery del progetto, `.env`, modello LLM,
      soul/facts/prompt, installazione media, smoke, shadow e promozione live.
- [x] Ogni gap cita file/codice/comando o artifact che lo dimostra.
- [x] Sono inclusi almeno: schema `commentator.enabled` stantio, requisito token
      shadow contraddittorio, smoke senza dotenv, chat quieta che rende non-zero
      media riusciti, Grok 4.3/`thinking` e path modello personali.
- [x] Ogni voce è assegnata a un ticket esistente o a una decisione esplicita.
- [x] Esito e priorità sono riportati nel parent spec.

## Blocked By

- None - può iniziare immediatamente.

## Frontier

La precedente fresh-install ha provato installabilità e `--help`; la sessione
reale ha attraversato decisioni semantiche e media live che quel test non
copriva. Senza una matrice si rischia di risolvere sintomi nel README e lasciare
il runtime incoerente.

## Work Plan

1. Ricostruire il percorso cronologico e i punti in cui l'utente ha chiesto
   spiegazioni o correzioni.
2. Verificare ogni osservazione contro codice, README, operator guide, example e
   artifact smoke.
3. Classificare severità e surface responsabile.
4. Collegare le correzioni ai ticket 13–18 o registrarne l'accettazione.
5. Aggiornare mappa e ticket dipendenti.

## Evidence to Capture

- Config/soul/facts locali solo come forma, senza segreti o path personali.
- `stats.json` dello smoke e comandi usati.
- Linee pertinenti di README, `docs/twitch-operator.md`, examples e runtime.

## Out of Scope

- Implementare i fix.
- Pubblicare artifact `.local` o `.smoke`.
- Giudicare la qualità dei messaggi Grok prodotti nella live.

## Progress

- 2026-07-18 — creata la matrice evidence-backed in
  [`docs/research/first-twitch-operator-journey.md`](../../../research/first-twitch-operator-journey.md).
- Coperti discovery, env, LLM, memoria/prompt, modelli, smoke, shadow e live;
  ogni voce ha evidenza e destinazione nei ticket 13–18 o decisione esplicita.
- Verificato lo smoke dotenv senza rete e riassunto l'artifact della sessione senza
  credenziali, contenuti raw o path personali.
- Esito e priorità sono stati riportati nel parent spec; il ticket è pronto per
  lo spostamento in `done/` dopo review e QA.

## Status

Done — review indipendenti e QA documentale completati.
