## Parent Spec

[speaker-diarization-over-segmentation.md](../../specs/speaker-diarization-over-segmentation.md)

## What to Build

Allineare la diarizzazione all'originale Minnarone: le voci non-streamer non
devono più produrre etichette per-persona `speaker_1..speaker_N`, ma collassare
in un'unica etichetta `[ALTRO]`. Restano `STREAMER` (il cluster dominante
congelato dopo il warmup) e `?` (utterance sotto `min_update_seconds` o
sconosciute). Il clustering interno non cambia — `cluster_id`, centroidi e
`talk_time` servono ancora a *identificare* lo streamer; cambia solo l'etichetta
esposta. Vedi le sezioni Decision/Solution (step 1) e Testing dello spec.

## Acceptance Criteria

- [ ] Le voci non-streamer sono etichettate `altro` (mai `speaker_N`).
- [ ] Il cluster dominante congelato dopo il warmup resta etichettato `streamer`.
- [ ] Le utterance sotto `min_update_seconds` restano etichettate `?`.
- [ ] Due voci non-streamer distinte hanno lo stesso label `altro` ma
      `cluster_id` interni diversi (la distinzione interna sopravvive).
- [ ] Nessun campo/contatore morto residuo (`stable_label`, `_next_label_id`
      rimossi se non più referenziati).
- [ ] Il pannello TRASCRIZIONE e il prompt non mostrano più `speaker_N`.
- [ ] Suite verde; nessuna regressione in test_app/test_dashboard.

## Blocked By

- None - can start immediately.

## Frontier

Pronto ora. Nessun input umano necessario: è un cambiamento di comportamento
puro e ben definito, con test.

## Step-by-Step Implementation Plan

1. Aggiungere la costante etichetta in `src/minnarone/audio.py` accanto a
   `STREAMER` e `UNKNOWN_SPEAKER` (es. `OTHER = "altro"`). Perché prima: le altre
   modifiche la importano.
2. In `src/minnarone/speaker.py`, modificare `_label_for`: ritorna `STREAMER`
   per il cluster streamer congelato, altrimenti `OTHER` (non più
   `cluster.stable_label`). Verificare che `stats()`/`assign()` usino solo
   `_label_for` per l'etichetta esposta.
3. Rimuovere il campo `_Cluster.stable_label` e il contatore `_next_label_id`
   ora inutilizzati (confermare con una ricerca che non siano referenziati
   altrove prima di rimuoverli). Il `cluster_id` resta l'identità interna.
4. Aggiornare `tests/test_speaker.py`: le asserzioni che oggi si aspettano
   `speaker_1`/`speaker_2` diventano `altro`; aggiungere un test che due voci
   distinte danno `label == "altro"` ma `cluster_id` diversi; mantenere il test
   del freeze streamer.
5. Verificare il rendering: `dashboard.py` stampa `{speaker}: {text}` → mostrerà
   `altro:`/`streamer:`. Nel prompt (`prompt.py`) controllare che la frase con
   speaker `altro` resti sensata; correggerla SOLO se risulta sgrammaticata
   (es. "qualcosa di altro").
6. Eseguire la suite e il lint; poi segnare lo step 1 come fatto nello spec.

Pitfall: non toccare il meccanismo di clustering/freeze — solo l'etichetta
esposta. Non cambiare la soglia qui (è un altro ticket). Non introdurre la
cosmetica bracketed `[ALTRO]` maiuscola (fuori scope).

## Testing Plan

- `tests/test_speaker.py`: label `altro` per non-streamer, `streamer` per il
  dominante congelato, `?` per corti; distinzione interna via `cluster_id`.
- Suite ampia (`uv run pytest tests/` con i 3 flaky noti deselezionati): nessuna
  regressione, in particolare test_app/test_dashboard che potrebbero citare
  `speaker_N`.
- `uv run ruff check src/minnarone/`.
- Manuale (non automatizzabile): al prossimo run shadow il pannello mostra solo
  `streamer`/`altro`/`?` — verificato nel ticket 05.

## Out of Scope

- Marking manuale dello streamer (ticket 03).
- Hardening del clusterer (ticket 04).
- Cambio del default/esempi della soglia e correzione docs (ticket 02).
- Cosmetica display in stile originale (`[ALTRO]` maiuscolo/parentesi).
