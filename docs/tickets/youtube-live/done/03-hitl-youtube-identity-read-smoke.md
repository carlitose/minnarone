---
ticket_schema: 1
ticket_id: "03"
execution_mode: HITL
blocked_by:
  - "01"
  - "02"
---

# Decidere identità OAuth e provare la lettura read-only

## Parent Spec

[youtube-live-wayfinder.md](../../../specs/youtube-live-wayfinder.md)

## Question / Outcome

Con quale account/canale YouTube deve apparire Minnarone, su live proprie o di
terzi autorizzati, e il contratto scelto riesce a leggere in modo bounded una
live chat reale senza possedere capacità di invio?

Output atteso: decisione sanitizzata in una feature spec, checklist locale
dell'operatore e prova read-only priva di token, messaggi privati o dati utente.

## What to Build

Una sessione HITL che usa i risultati 01/02 per decidere la topologia di
identità e autorizzazione e, solo dopo conferma umana, prepara localmente il
minimo setup Google/YouTube ed esegue una smoke di lettura a durata e artifact
limitati. Non inviare alcun messaggio.

Sezioni coperte: identità/autorizzazione, target canonico e prova esterna nella
`Frontier / Blocking Edges`.

## Evidence Required

- Scelta esplicita fra canale proprio e canale terzo autorizzato, identità
  account/canale/Brand Account, disclosure e prova di consenso richiesta.
- Capability e scope minimi per read-only; nessuna capability write concessa
  “per comodità”.
- Evidenza sanitizzata di discovery, chat ID, pacing, almeno un evento normalizzato
  oppure un esito `no messages` distinguibile dal failure.
- Evidenza di stop bounded, nessun secret in log/artifact e procedura di revoca.

## Acceptance Criteria

- [ ] L'umano approva target, identità pubblica, proprietà/autorizzazione,
  disclosure, retention e condizioni per fermarsi a shadow.
- [ ] Il setup usa secret solo in storage locale gitignored/credential store
  previsto; nessun valore viene incollato in ticket, chat, YAML o log.
- [ ] La smoke non possiede o non esercita alcuna capability di send e termina
  automaticamente entro il limite concordato.
- [ ] Il risultato distingue live assente, chat disabilitata, chat vuota,
  autorizzazione fallita, quota/rate failure e successo.
- [ ] La decisione durevole è registrata tramite `to-spec` e collegata dalla
  mappa; solo allora il ticket 04 può diventare ready.

## Frontier

HITL, dependency-blocked by 01 and 02. Richiede una scelta umana e stato esterno
(progetto/account/live disponibili); non autorizza contatti né invio pubblico.

## Step-by-Step Implementation Plan

1. Presentare all'umano le opzioni supportate dal report 01 e i tradeoff del
   prototipo 02, senza chiedere credenziali in chat.
2. Registrare la scelta di identità, target, consenso, disclosure, retention e
   capability split nella feature spec.
3. Guidare l'operatore nel setup locale minimo con secret gitignored e scopes
   read-only; verificare `git status` prima della smoke.
4. Eseguire discovery e lettura bounded su una live consentita, salvando solo
   conteggi, stati, latenze/pacing ed esempi sintetizzati/redatti.
5. Revocare o conservare localmente la capability secondo la decisione,
   verificare assenza di segreti e aggiornare la mappa.

## Testing Plan

Preflight offline della config; prova bounded read-only; audit di redazione con
ricerca dei nomi delle env/credential file e controllo `git diff/status`.
Nessun messaggio inserito nella chat e nessuna promozione live.

## Out of Scope

- Creare o trasmettere un broadcast.
- Contattare creator o assumere consenso da una live pubblica.
- Richiedere scope write, inviare messaggi o testare self-echo.
- Implementare il runtime Minnarone di produzione.

## Completion Evidence

[Identity and read-only smoke decision](../../../specs/youtube-live-identity-read-decision.md)
