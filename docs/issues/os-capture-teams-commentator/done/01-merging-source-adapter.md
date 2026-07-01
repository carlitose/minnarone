## Parent PRD

[os-capture-teams-commentator.md](../../prds/os-capture-teams-commentator.md)

## What to build

Un nuovo modulo profondo `MergingSourceAdapter`: il motore che compone più
`SourceAdapter` per-canale in un unico stream `RawEvent` bounded, con la stessa
policy di backpressure oggi implementata dentro `TwitchStreamAdapter` (coda
limitata; sotto pressione droppa preferendo mantenere la chat; conteggi
`produced`/`dropped`/`failures`; isolamento per-canale; arresto pulito).

In questo slice il modulo viene creato e testato **in isolamento** con reader
fake, ma **non è ancora usato** da `TwitchStreamAdapter` (l'adozione è lo slice
02). Vedi *Implementation Decisions → MergingSourceAdapter* nel PRD.

## Step-by-step implementation plan

1. Creare il nuovo modulo `MergingSourceAdapter` che implementa l'interfaccia
   `SourceAdapter` (`channels()`/`start()`/`stop()`/`events()`) più uno `stats()`
   diagnostico. Prende in costruzione una `Mapping[str, SourceAdapter]` di reader
   per-canale. *Perché prima:* è l'enabler condiviso Twitch/OS-capture; isolarlo
   permette di testarlo senza toccare Twitch.
2. Portare la logica di merge dal `TwitchStreamAdapter` esistente: task
   per-reader, coda `deque` bounded protetta da `asyncio.Condition`, pubblicazione
   con drop policy (quando la coda è piena, droppa un evento media per far posto
   alla chat), conteggi, e arresto pulito con cancellazione dei task e raccolta
   delle failure per-canale. *Verifica:* la logica deve essere neutra rispetto ai
   canali (nessun nome Twitch nel modulo).
3. Validare che ogni reader esponga solo il proprio canale (come fa oggi
   `_validate_reader_channels`).
4. Scrivere unit test con reader fake in-memory: merge di più canali, ordine e
   isolamento, comportamento sotto pressione (drop osservabili nei conteggi),
   propagazione delle failure, arresto pulito quando i reader si esauriscono o
   quando si chiama `stop()`. *Verifica:* `make quality` pulito e test verdi.

Trappole: non introdurre dipendenze da Twitch nel modulo; mantenere l'ordine dei
canali deterministico (i test lo osservano); non cambiare la semantica di drop
(sarà confrontata con Twitch nello slice 02).

## Acceptance criteria

- [ ] Esiste `MergingSourceAdapter` come `SourceAdapter` neutro, con `stats()`.
- [ ] Unit test coprono merge multi-canale, backpressure/drop, failure, shutdown.
- [ ] Nessun riferimento a Twitch nel nuovo modulo.
- [ ] `make quality` pulito (in particolare nessun `duplicate-code`/R0801 nuovo).

## Blocked by

None - can start immediately

## User stories addressed

- User story 11
