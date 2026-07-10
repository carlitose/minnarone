## Parent Spec

[speaker-diarization-over-segmentation.md](../../specs/speaker-diarization-over-segmentation.md)

## What to Build

Il gate di accettazione: un run live bounded in cui l'operatore verifica che la
diarizzazione allineata all'originale funzioni su audio reale — solo le etichette
`streamer`/`altro`/`?`, il marking manuale dello streamer, e la soglia adeguata.
Questo run **risolve la Open Question** dello spec (la soglia esatta per il
modello zh-cn sull'italiano, l'unica quantità non misurata direttamente).

HITL per natura: richiede uno stream live, credenziali/modelli, e giudizio
qualitativo su chi-parla.

## Acceptance Criteria

- [ ] In un run live bounded, il pannello TRASCRIZIONE mostra solo `streamer` /
      `altro` / `?` — nessun `speaker_N`.
- [ ] Il marking manuale (ticket 03) funziona: marcata la voce dello streamer,
      le sue utterance successive risultano `streamer`; con più host, più
      streamer marcabili.
- [ ] Le attribuzioni sono ragionevoli per un umano che guarda (streamer vs
      altri), a parte errori occasionali `?` (accettabili, come nell'originale).
- [ ] La soglia usata è registrata come valore validato; se diversa da 0.45,
      aggiornare spec/docs/esempi di conseguenza.
- [ ] Osservazioni di qualità e follow-up annotati (senza segreti).

## Blocked By

- [01-collasso-altro.md](./01-collasso-altro.md)
- [03-marking-manuale-streamer-tui.md](./03-marking-manuale-streamer-tui.md)

## Frontier

Bloccato dai ticket 01 e 03, e da input umano (stream live + giudizio). Il
ticket 02 (docs) è consigliato ma non bloccante. Il ticket 04 è opzionale e non
richiesto per l'accettazione.

## Step-by-Step Implementation Plan

1. Preparare un run shadow bounded (15–30 min) su un canale live, con la config
   locale aggiornata (soglia di partenza 0.45). Validare con `--check`.
2. Osservare il pannello TRASCRIZIONE: confermare solo `streamer`/`altro`/`?`.
   Se lo streamer è mal identificato dall'auto-dominante, usare il marking
   manuale (ticket 03) e verificare l'effetto.
3. Se `altro` esplode o lo streamer è instabile, provare soglie 0.4 / 0.5 e
   annotare quale dà le attribuzioni migliori sul canale reale.
4. Registrare il valore di soglia validato e gli eventuali follow-up; aggiornare
   spec (Open Questions) e, se serve, i default via ticket 02.

Pitfall: non giudicare durante il warmup del VLM (~60s). Non incollare segreti
nelle note. Ricordare che qualche `?` occasionale è atteso, non un fallimento.

## Testing Plan

- Verifica manuale end-to-end sul run live (nessun automatismo può sostituirla).
- Confronto delle etichette osservate con la realtà (chi parla davvero).
- Conferma che il marking manuale registra transizioni con attore `operator`
  (visibili in replay).

## Out of Scope

- Implementazione del collasso (01), del marking (03), dell'hardening (04).
- Correzione docs (02) — indipendente, non bloccante per questo run.
