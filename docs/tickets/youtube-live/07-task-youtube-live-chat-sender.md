---
ticket_schema: 1
ticket_id: "07"
execution_mode: AFK
blocked_by:
  - "06"
---

# Implementare il sender YouTube Live dietro tutti i gate

## Parent Spec

[youtube-live-wayfinder.md](../../specs/youtube-live-wayfinder.md)

## Question / Outcome

Minnarone può inserire un messaggio nella live chat come identità autorizzata,
validando e revocando la capability in modo fail-closed, senza self-loop, retry
stale o contaminazione di segreti?

Output atteso: sender e token/capability guard YouTube testati solo con fake,
integrati nel router pubblico ma non esercitati su rete da questo ticket.

## What to Build

Implementare il transport `liveChatMessages.insert` o contratto ufficiale
selezionato dal report 01, OAuth refresh/validation/revocation handling,
classificazione errori, sender single-attempt, self-echo per identità stabile e
integrazione con policy/TUI/run events. La sessione resta shadow fino a
promozione manuale.

Sezioni coperte: `Destination` punto 3 e `Sender live` nella frontiera.

## Evidence Required

- Request/response fake fedeli alle fonti 01 per successo, auth revocata,
  scope/identity mismatch, chat terminata/disabilitata, quota/rate e failure
  transitorio.
- Prova di capability split: off/shadow non caricano refresh/access token con
  write scope e `--check` non apre browser/rete.
- Test redazione su config errors, logs, TUI, run events e exception chains.

## Acceptance Criteria

- [ ] Una sola classe/porta possiede l'operazione di insert; nessun altro
  modulo può pubblicare direttamente.
- [ ] Live richiede target allow-listed, identità approvata, scope/capability
  validi, token non scaduto/revocato e promozione TUI esplicita.
- [ ] Revoca, `401`/equivalente, scope o identity mismatch disarmano il live per
  la sessione; quota/rate/chat-ended producono reason distinti e mai fallback
  best-effort.
- [ ] Ogni candidato è single-attempt: nessuna coda o retry successivo può
  pubblicare un messaggio divenuto stale.
- [ ] Self-echo resta nel perception log ma non genera trigger e viene trattato
  come own-message usando l'identità YouTube stabile, non il display name.
- [ ] Token, client secret, auth code e payload sensibili non compaiono in
  errori, log, prompt, eventi, artifact o test fixture.
- [ ] Tutta la suite, lint e format passano con fake; nessuna rete reale in CI.

## Frontier

Dependency-blocked by 06. AFK autorizza implementazione e test fake soltanto;
non autorizza una chiamata reale o la creazione/uso di credenziali.

## Step-by-Step Implementation Plan

1. Aggiungere protocolli transport/credential store e test failing dalle
   risposte ufficiali sanitizzate.
2. Implementare guard di capability e lifecycle OAuth con clock/transport
   iniettati e redazione centralizzata.
3. Implementare sender con validazione messaggio e singola insert, errori
   tipizzati e cleanup.
4. Collegare router/policy/TUI mantenendo startup shadow e kill-switch.
5. Aggiungere self-echo filter e prompt own-message con ID stabile.
6. Aggiornare guida live come procedura attended-only e verificare regressioni.

## Testing Plan

Unit test transport/guard/sender con fake e clock; app/router/TUI integration;
self-echo; redaction; auth expiry/revocation; quota/rate; no-retry; regression
Twitch; quality suite completa.

## Out of Scope

- Chiamate API reali e bounded live acceptance.
- Creazione di client OAuth o acquisizione token.
- Moderazione, ban, Super Chat, analytics o broadcast management.
- Operazione unattended o multi-live.
