## Parent Spec

[speaker-diarization-over-segmentation.md](../../specs/speaker-diarization-over-segmentation.md)

## What to Build

> **OPZIONALE / DEPRIORITIZZATO** — rivalutare dopo il ticket 03. Con il
> collasso `[ALTRO]` (01) e il marking manuale dello streamer (03),
> l'over-segmentation interna dei non-streamer non impatta più né il display né
> l'identificazione dello streamer. Questo ticket ha senso solo se, dopo 01/03,
> restano casi in cui la crescita illimitata dei cluster crea problemi (memoria,
> diagnostica, o streamer-id automatico ancora fragile).

Rendere il clusterer robusto alla crescita illimitata dei cluster indipendente-
mente dalla soglia: merge periodico dei centroidi la cui similarità reciproca
supera la soglia, e/o un tetto al numero di cluster con fallback
all'assegnazione al più vicino, e/o conferma su seconda utterance prima di
creare un nuovo cluster. Vedi Follow-Up 3 e la sezione Options Considered
(Opzione B) dello spec.

## Acceptance Criteria

- [ ] Nel regime a bassa similarità intra-speaker (0.45–0.55), il numero di
      cluster interni non cresce senza limite per una singola voce ripetuta.
- [ ] Il merge (se implementato) fonde cluster con centroidi troppo simili senza
      corrompere l'identificazione dello streamer.
- [ ] Nessuna regressione sul comportamento a similarità alta (i test esistenti
      restano verdi).
- [ ] Politica di relabel documentata se il merge tocca cluster già etichettati.

## Blocked By

- [01-collasso-altro.md](./01-collasso-altro.md)

## Frontier

Bloccato dal ticket 01. **Bassa priorità**: potenzialmente superato dal ticket
03. Non iniziare prima di aver valutato dal vivo (ticket 05) se il problema
residuo esiste ancora.

## Step-by-Step Implementation Plan

1. Dopo 01/03, valutare dal run live se la crescita dei cluster interni è ancora
   un problema reale (memoria/diagnostica/streamer-id). Se non lo è, chiudere
   questo ticket senza implementare.
2. Se serve, aggiungere al clusterer una passata di merge periodico: fondere
   coppie di cluster con similarità centroide > soglia (media pesata dei
   centroidi, somma dei talk_time). TDD sul regime a bassa similarità che i test
   attuali non coprono.
3. In alternativa/aggiunta: tetto ai cluster con fallback al più vicino, oppure
   conferma su seconda utterance prima di coniare un nuovo cluster.
4. Definire la politica di relabel: fondere solo in avanti o rietichettare lo
   storico nel perception store (vedi Open Question dello spec).

Pitfall: il merge retroattivo cambia identità già emesse — scegliere una
politica esplicita. Non reintrodurre `speaker_N` esposti (restano `altro`).

## Testing Plan

- Nuovi test in `tests/test_speaker.py` nel regime a bassa similarità: il numero
  di cluster interni resta limitato; il merge fonde correttamente; lo streamer
  resta identificato.
- I test esistenti a similarità alta restano verdi.

## Out of Scope

- Collasso `[ALTRO]` (01) e marking manuale (03) — prerequisiti/alternative.
- Scelta del modello embedding (ticket 02).
