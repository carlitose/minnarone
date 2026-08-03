---
ticket_schema: 1
ticket_id: "06"
execution_mode: AFK
blocked_by:
  - "03"
  - "04"
---

# Portare la safety policy pubblica in shadow su YouTube

## Parent Spec

[youtube-live-wayfinder.md](../../specs/youtube-live-wayfinder.md)

## Question / Outcome

Come può YouTube riusare la safety floor di Twitch senza dipendere da
`TwitchSendConfig`, username Twitch o normalizzazione canale IRC, e senza
rendere più permissivo il percorso Twitch?

Output atteso: policy/config/router pubblici profondi e piattaforma-neutrali o
una composizione equivalente, cablati a YouTube in shadow con TUI/run events e
zero sender di rete.

## What to Build

Refactor comportamentale-preservante della policy pubblica: target allow-list
tipizzato, `off`/`shadow`/`live-armed`, budget, failure state, promozione,
kill-switch, snapshot e reason codes. Aggiungere la superficie YouTube shadow
e mantenere byte/behavior compatibility dove i test Twitch lo richiedono.

Sezioni coperte: safety reuse e output pubblico della `Frontier`; prepara il
sender 07 senza autorizzarlo.

## Evidence Required

- Characterization test del comportamento Twitch prima del refactor.
- Matrice dei target identifier Twitch/YouTube e del punto che valida
  allow-list/self identity.
- Test che `live` configurato parte sempre shadow e che nessun sender viene
  costruito senza capability/transport esplicito.

## Acceptance Criteria

- [ ] I tipi neutrali non importano config, normalizzatori, sender o errori
  Twitch; gli adapter di piattaforma traducono al bordo.
- [ ] Twitch conserva reason/action, budget, kill-switch, auto-degrade,
  TUI/run events e fail-closed esistenti.
- [ ] YouTube `off` droppa, `shadow` registra/mostra e `live` resta non promoted
  finché la TUI non conferma; shadow consuma i budget di prodotto.
- [ ] Allow-list usa l'identificatore stabile scelto in 03 e una destinazione
  non normalizzabile/non autorizzata non può inviare.
- [ ] Il router non cattura eccezioni generiche come sender failure e non fa
  retry/queue di messaggi stale.
- [ ] Test dimostra che il ticket non contiene alcuna chiamata all'endpoint di
  insert né lettura di token write.
- [ ] Suite e quality checks passano.

## Frontier

Dependency-blocked by 03 and 04. Può procedere in parallelo al media ticket 05;
sblocca il solo bordo live 07.

## Step-by-Step Implementation Plan

1. Congelare con test pubblici le combinazioni e transizioni della policy Twitch.
2. Disegnare target/config neutrali minimi e adapter Twitch compatibile.
3. Refactorizzare policy, router e snapshot mantenendo reason codes e TUI.
4. Aggiungere config e wiring YouTube shadow/live-armed senza sender.
5. Aggiungere test cross-platform che provino isolamento e nessuna escalation
   di capability; aggiornare guide shadow.

## Testing Plan

Characterization + unit test puri con clock iniettato; router fake; app/TUI/run
event regression Twitch; app-level YouTube shadow; secret-access sentinel;
quality suite completa.

## Out of Scope

- Client OAuth, refresh/revoca o endpoint di insert.
- Self-echo dopo un send reale.
- Modifiche a prompt, human-likeness o rate ufficiali della piattaforma.
- Esecuzione live o creazione di credenziali.
