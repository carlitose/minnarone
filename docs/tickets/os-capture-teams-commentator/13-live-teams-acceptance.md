## Parent PRD

[os-capture-teams-commentator.md](../../prds/os-capture-teams-commentator.md)

## What to build

Acceptance **manuale live** (HITL): eseguire il commentatore locale su un meeting
Teams reale e registrare l'esito, sullo stesso modello delle issue di acceptance
Twitch/TUI esistenti. Non automatizzabile: dipende da un meeting reale, hardware
e permessi. Vedi *Step-by-Step → step 8* e user story 2/3/4 nel PRD.

## Step-by-step implementation plan

1. Preparare l'ambiente: installare l'extra `[os-capture]`, impostare l'uscita
   audio di default sul dispositivo del meeting, concedere i permessi di cattura
   schermo, scegliere il monitor. *Perché ora:* richiede tutti i backend (07/08),
   il preset (11) e la guida (12).
2. Entrare in un meeting Teams reale col client. Avviare Minnarone con
   `examples/teams-commentator.yaml`.
3. Osservare che: (a) il parlato degli altri partecipanti diventa percezioni
   audio→ASR; (b) lo schermo condiviso diventa caption video→VLM; (c) il
   commentatore stampa interventi `[PRIVATE]` in console; (d) **nulla** viene
   inviato dentro il meeting; (e) sotto carico i drop sono osservabili (policy
   ADR) invece di accumulare backlog.
4. Registrare l'esito (successo/limiti/bug) nel file dell'issue, come le
   acceptance run esistenti. In caso di bug, aprire follow-up.

Trappole: verificare esplicitamente l'assenza di output pubblico verso Teams;
annotare qualità di trascrizione/caption e latenza per il tuning futuro.

## Acceptance criteria

- [ ] Meeting Teams reale osservato: audio→ASR e schermo→VLM producono percezioni.
- [ ] Il commentatore stampa `[PRIVATE]` in console; nessun output verso Teams.
- [ ] Comportamento sotto carico coerente con la policy di backpressure (drop
      osservabili).
- [ ] Esito registrato nel file dell'issue; eventuali bug tracciati come follow-up.

## Blocked by

- Blocked by [06-app-wiring-oscapture.md](./06-app-wiring-oscapture.md)
- Blocked by [08-screen-device-backend.md](./08-screen-device-backend.md)
- Blocked by [11-teams-preset.md](./11-teams-preset.md)
- Blocked by [12-operator-docs.md](./12-operator-docs.md)

## User stories addressed

- User story 2
- User story 3
- User story 4
