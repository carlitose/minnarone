## Parent Spec

[workstream-untangle-wayfinder.md](../../specs/workstream-untangle-wayfinder.md)

## Type

grilling

## Outcome

Una decisione umana registrata (decision spec) sull'ordine di merge dei filoni
verso `main` e sulla strategia PR, dato che W3 (`profiles`) è la chiave di volta
e W2 è già pushato su schema vecchio. Senza questa decisione, la ricostruzione
della storia (ticket 03) non può partire.

## Acceptance Criteria

- [ ] Scelta registrata tra le opzioni di ordine di merge (vedi Work Plan) con
      motivazione.
- [ ] Deciso il destino del branch pushato `autopilot/twitch-public-chat-output`
      (schema vecchio): lo si migra a `profiles`, lo si supera, o lo si mergia
      prima e poi si migra?
- [ ] Deciso se W3 va su main come singolo commit "profiles refactor" o
      spacchettato per-ticket.
- [ ] Deciso se W1+W2 restano una PR impilata o separata, e dove va il `.env`.
- [ ] Decisione salvata come decision spec e linkata dallo spec wayfinder
      (`Decisions So Far`).

## Blocked By

- [01-research-dependency-map-and-snapshot-attribution.md](./01-research-dependency-map-and-snapshot-attribution.md)

## Frontier

È un gate umano: le opzioni hanno trade-off che solo l'utente può arbitrare
(quanto vale una storia git pulita vs il tempo di rifacimento; se il branch W2
pushato ha già occhi/CI sopra).

## Work Plan

Presentare all'utente le opzioni con trade-off:

1. **W3-fondazione-prima**: mergiare prima W1, poi W3 (`profiles`) come nuova
   base di schema, poi rifare/rebase W2 su `profiles` (portando i fix
   public-TUI dallo snapshot), infine W4. Pro: schema unico dall'inizio, W4 già
   pronto. Contro: il branch W2 pushato va rilavorato.
2. **W2-prima-poi-migrazione**: mergiare W1+W2 (schema vecchio, già pushato),
   poi W3 come PR che include la migrazione di schema + i fix public-TUI, poi
   W4. Pro: sfrutta il branch W2 già pushato. Contro: la PR W3 diventa grossa
   (refactor + migrazione dei consumer di W2).
3. **Ibrido**: W1 e `.env` come PR piccole subito; poi decidere W2/W3/W4.

Per ciascuna: elencare i punti di conflitto attesi su `config.py`/`app.py` e chi
li assorbe.

## Evidence to Capture

- La scelta e la motivazione dell'utente (o assunzione registrata se AFK).
- I punti di conflitto previsti per l'ordine scelto.

## Out of Scope

- Eseguire il merge o creare i branch (ticket 03).
