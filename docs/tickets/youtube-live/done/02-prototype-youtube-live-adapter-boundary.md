---
ticket_schema: 1
ticket_id: "02"
execution_mode: AFK
blocked_by:
  - "01"
---

# Prototipare il confine adapter e media YouTube

## Parent Spec

[youtube-live-wayfinder.md](../../../specs/youtube-live-wayfinder.md)

## Question / Outcome

Qual è la minima interfaccia che permette a YouTube Live di produrre gli stessi
`RawEvent` di Twitch riusando merge, backpressure e perceiver, senza rinominare
come “generici” contratti che restano specifici di Twitch?

Output atteso: prototipo usa-e-getta e
`docs/prototypes/youtube-live-adapter-boundary.md` con alternative, evidenza,
scelta candidata e conseguenze sui moduli di produzione.

## What to Build

Un prototipo non produttivo, interamente fake/non-networked, di chat, audio e
video YouTube dietro `SourceAdapter`. Confrontare almeno: adapter YouTube
composto da reader specifici; estrazione di un media source URL neutro riusato
dai reader; duplicazione deliberata al bordo quando la semantica differisce.

Sezioni coperte: decisione adapter/media nella `Frontier`, riuso architetturale
e unknown su generalizzazione di Twitch.

## Evidence Required

- Tracce sintetiche che producano `RawEvent(channel="chat"|"audio"|"video")`
  nelle shape già accettate dai perceiver.
- Confronto di lifecycle, stop, errori parziali, queue priority e stats contro
  `TwitchStreamAdapter`/`MergingSourceAdapter`.
- Impatto concreto su `twitch_media.py`, audio reader, video opener, config e
  injection seam dei test.
- Dimostrazione che la soluzione scelta non accetta URL arbitrari o shell
  strings non validati e non amplia il perimetro di cattura.

## Acceptance Criteria

- [ ] Il prototipo usa solo fake e fixture sintetiche; non apre rete, browser,
  processi media reali o credenziali.
- [ ] Almeno due alternative sono esercitate e confrontate su coesione,
  testabilità, sicurezza, cleanup e duplicazione.
- [ ] La scelta preserva il `SourceAdapter` neutro, code limitate, priorità chat
  e isolamento dei failure per canale.
- [ ] Sono elencati esattamente moduli/contratti da generalizzare, lasciare
  invariati o creare per YouTube.
- [ ] La decisione candidata viene registrata tramite `to-spec` se sufficientemente
  stabile; altrimenti il report formula un nuovo blocking edge verificabile.
- [ ] La mappa viene aggiornata e il ticket 03 passa a ready solo se il confine
  per una smoke read-only è definito.

## Frontier

Dependency-blocked by 01. Non deve scegliere una libreria o un URL contract
prima che il report piattaforma sia disponibile.

## Step-by-Step Implementation Plan

1. Leggere il report 01 e tradurre i contratti esterni in porte fakeabili.
2. Scrivere fixture minime per discovery/chat/media senza copiare risposte reali
   contenenti dati utente.
3. Implementare due piccoli prototipi fuori dai package di produzione e farli
   attraversare il merge fino ai perceiver fake/reali già testabili.
4. Forzare stop, canale vuoto, failure chat, failure media e queue piena.
5. Selezionare l'interfaccia più profonda e documentare migrazione e test seam;
   eliminare o marcare chiaramente come disposable il codice di spike.

## Testing Plan

Test sintetici del prototipo per shape eventi, idempotenza start/stop, cleanup,
failure parziali, priorità e drop bounded. Nessun test live e nessuna dipendenza
opzionale scaricata automaticamente.

## Out of Scope

- Modifiche a `src/minnarone/`, config pubblica o esempi operatore.
- Scelta dell'account Google/YouTube dell'operatore.
- Chiamate API, Streamlink/FFmpeg/PyAV reali o invio chat.
- Generalizzazione preventiva di LLM, prompt, reactor o perception store.

## Completion Evidence

- [Offline adapter prototype](../../../prototypes/youtube-live-adapter-boundary.md)
- [Adapter/media decision](../../../specs/youtube-live-adapter-media-decision.md)
