# Speaker diarization over-segmentation nella pipeline audio Twitch

## Type

Diagnostic spec

## Status

Accepted (diagnosi confermata, triangolata 3/3 ad alta confidenza)

## Problem / Context

Durante un run live Twitch (talk stream italiano, ~4 parlanti reali) il pannello
TRASCRIZIONE mostra molti più speaker di quelli reali: in ~42 secondi compaiono
`speaker_1, speaker_5, speaker_7, speaker_8, speaker_9, speaker_10`, più il
label `streamer` e una riga con speaker letterale `?`. L'over-segmentation
confonde chi parla e degrada il contesto che il PromptBuilder passa all'LLM
(attribuzioni sbagliate nel prompt).

Config del run: sherpa-onnx CAM++ 192-dim
`3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx` su CPU;
`speaker_clustering: threshold 0.6, warmup_seconds 60.0, min_update_seconds 1.0`;
VAD webrtc `padding_ms=300`, frame 30ms; ASR faster-whisper large-v3-turbo
CPU int8 lingua it; `audio_chunk_seconds: 1.0`.

La diagnosi è stata triangolata con 3 subagenti indipendenti (lenti:
repro-first, data-flow, environment/config). Tutti e tre hanno costruito un
harness deterministico contro il clusterer di produzione e sono convergiuti
sullo stesso meccanismo con confidenza alta.

## Goals

- Spiegare il meccanismo che produce l'esplosione di `speaker_N`.
- Spiegare i label `?` e `streamer`.
- Definire la mitigazione operativa immediata e i fix duraturi.

## Non-Goals

- Implementare i fix (elencati come follow-up, non eseguiti qui).
- Cambiare il design del freeze `streamer` o del gate `?` (funzionano come
  specificato; eventuali modifiche sono decisioni di prodotto separate).

## Evidence

Tre harness indipendenti (scratch, fuori repo) hanno pilotato il
`OnlineSpeakerClusterer` di produzione con embedding sintetici 192-dim a
similarità intra-speaker controllata:

- **Riproduzione quantitativa dell'esplosione**: con similarità coseno
  stesso-parlante ≈ 0.50 (regime realistico per segmenti corti + modello
  zh-cn su italiano), `threshold 0.6` produce 16–35 cluster per 4 parlanti
  (harness diversi, stessa forma del sintomo: `speaker_10+` in ~42s). Con
  `threshold 0.4` lo **stesso stream di embedding produce esattamente 4
  cluster**. Con similarità ≥ 0.62 anche 0.6 dà 4 cluster: il codice è
  internamente coerente, la soglia è solo sopra la qualità che i segmenti
  reali consegnano.
- **Semantica della soglia** (`src/minnarone/speaker.py`, `assign`):
  `similarity < threshold → nuovo cluster`. `threshold` è un *pavimento di
  similarità coseno per unirsi* a un cluster esistente (dot di vettori
  normalizzati): più alto = più splitting. Non esiste merge né tetto ai
  cluster; `_next_label_id` è monotono (i buchi speaker_2/3/4/6 sono cluster
  nati su righe fuori dalla finestra visibile o promossi a `streamer`).
- **Perché la similarità reale sta sotto 0.6**: (a) il VAD chiude le utterance
  dopo ~270-300ms di silenzio → segmenti da 1–3s con ~300ms di pre-roll e coda
  non-target, regime in cui gli embedding CAM++ sono rumorosi; (b) il modello è
  addestrato sul mandarino (`zh-cn`) e gira su parlato italiano, il che
  deprime la similarità intra-speaker (~0.45–0.55).
- **`?` è by design**: utterance con durata `< min_update_seconds` (1.0s)
  ritornano `UNKNOWN_SPEAKER = "?"` senza essere clusterizzate
  (`speaker.py` gate di durata; costante in `audio.py`). Il `?: Sì` del run è
  un "Sì" sotto il secondo. Verificato in harness (0.9s → `?`, 1.1s →
  `speaker_N`). La dashboard stampa lo speaker verbatim: nessun artefatto di
  rendering.
- **`streamer` è by design**: raggiunti 60s cumulativi di parlato
  clusterizzato (`warmup_seconds`), il cluster col massimo tempo di parola
  viene congelato permanentemente come `streamer`
  (`_freeze_streamer_if_ready`). Nota: con l'over-segmentation il freeze si
  degrada — la "corona" va al frammento più grande e gli altri frammenti
  dello stesso streamer continuano a generare `speaker_N`.
- **Docs invertiti** (scoperta della lente environment):
  `docs/twitch-operator.md` consiglia "alza `speaker_clustering.threshold`
  verso 0.65/0.7" per l'over-segmentation — la direzione **sbagliata** rispetto
  alla semantica del codice (verificato: a similarità ≈0.50, threshold 0.7 →
  40 cluster; 0.5 → 6-7; 0.4 → 4). Il consiglio è scritto come se threshold
  fosse una distanza.
- **Nessun bug di boundary**: campionamento forzato mono 16kHz da ffmpeg
  (`twitch_audio.py`), assert 16kHz in VAD e backend sherpa, scaling PCM
  `/32768.0` corretto (`asr.py`), media dei centroidi corretta
  (running mean + renormalize), il VAD accumula frame attraverso i chunk da
  1s (le utterance sono intere). `tests/test_speaker.py` passa: i test
  coprono solo il regime a similarità alta, mai quello basso.
- Storia git: `speaker.py` è invariato dal commit di nascita (a897e5a) —
  difetto di inception (default mai validato su modello non-mandarino con
  utterance corte), non una regressione.

## Decision / Solution

**Root cause**: clustering online greedy a soglia fissa senza merge
(`OnlineSpeakerClusterer.assign`): con `threshold 0.6` sopra la similarità
intra-speaker reale (~0.45–0.55, per segmenti VAD corti + modello CAM++
zh-cn su italiano), quasi ogni utterance manca il join e conia un nuovo
`speaker_N`, senza tetto né fusione. `?` (gate < 1.0s) e `streamer`
(freeze a 60s) sono meccanismi separati e funzionanti come da specifica.

**Mitigazione operatore (immediata, senza codice)**: abbassare
`speaker_clustering.threshold` a **0.4–0.45** nel config locale.

**Fix duraturi (in ordine di valore)**:
1. Correggere il consiglio invertito nei docs e dichiarare la semantica
   (join floor di similarità coseno: over-segmentation → *abbassa*).
2. Abbassare il default/esempi a ~0.4–0.45 per questo modello.
3. Robustezza del clusterer: merge periodico dei centroidi che superano la
   soglia tra loro e/o conferma su seconda utterance prima di assegnare un
   label / tetto ai cluster con fallback al più vicino.
4. Raccomandare un modello embedding language-matched o multilingue per
   stream non mandarini.

## Options Considered

### Opzione A: solo tuning del threshold (0.4–0.45)

- Cosa fa: mitigazione immediata a costo zero.
- Benefici: recupera esattamente 4 cluster negli harness; nessun codice.
- Svantaggi: fragile — la soglia giusta dipende da modello/lingua/rumore; il
  failure mode "un frammento per utterance, per sempre" resta possibile.

### Opzione B: robustezza del clusterer (merge + conferma/tetto)

- Cosa fa: rimuove la crescita monotona dei label indipendentemente dal tuning.
- Benefici: elimina il failure mode strutturale; tollerante ai modelli diversi.
- Svantaggi: più codice e test; il merge retroattivo cambia label già emessi
  (serve una politica di relabel o di sola fusione in avanti).

### Opzione C: modello embedding language-matched

- Cosa fa: alza la similarità intra-speaker alla fonte.
- Benefici: attacca la causa del regime basso.
- Svantaggi: dipendenza da un artefatto nuovo; da validare; non elimina il
  problema strutturale su segmenti molto corti.

Scelta: A subito (operatore), poi 1+2 (docs/default) e B come hardening;
C raccomandato nei docs.

## Implementation Plan

1. Config locale dell'operatore: `speaker_clustering.threshold: 0.45` (poi
   0.4 se ancora splitta). Verifica su run live: numero di speaker stabile
   vicino al reale.
2. `docs/twitch-operator.md`: invertire il consiglio di tuning nelle due
   sezioni (troubleshooting e smoke) e dichiarare la semantica della soglia.
   Aggiornare i valori consigliati negli esempi
   (`examples/twitch*.example.yaml`) e nel default di `config.py` se si
   decide di cambiarlo.
3. `src/minnarone/speaker.py`: hardening del clusterer (merge periodico e/o
   conferma nuova-cluster / tetto). TDD sul regime a similarità bassa che i
   test attuali non coprono (`tests/test_speaker.py` esercita solo vettori
   ben separati).
4. Docs: sezione sulla scelta del modello embedding (evitare `zh-cn` per
   stream non mandarini; indicare alternative multilingue).

## Testing Decisions

- Aggiungere a `tests/test_speaker.py` casi nel regime a similarità
  intra-speaker bassa (0.45–0.55): con la soglia di default corretta il
  numero di cluster non deve esplodere; con merge attivo i frammenti si
  fondono.
- Test del gate `?` (già implicito) e del freeze `streamer` esistono; non
  toccarli.
- Non testare i valori numerici interni dei centroidi (dettaglio di
  implementazione): testare il comportamento (numero di label emessi).
- Verifica manuale: run live bounded con threshold 0.45 e conteggio speaker
  osservato vs reale.

## Follow-Up Tickets

Lavoro eseguibile (non creati come file ticket su richiesta — restano qui):

1. Fix docs invertiti + semantica soglia + valori consigliati (AFK, piccolo).
2. Abbassare default/esempi threshold a 0.4–0.45 (AFK, piccolo, con test).
3. Hardening clusterer: merge periodico / conferma / tetto (AFK, medio, TDD
   sul regime a bassa similarità).
4. Guida alla scelta del modello embedding nei docs (AFK, piccolo).
5. (Opzionale, decisione di prodotto) attribuzione dei back-channel < 1s:
   assegnare senza aggiornare il centroide invece di `?`.

## Open Questions

- Quale threshold esatto per il modello zh-cn su italiano? 0.4–0.45 dagli
  harness sintetici; da confermare sul run live (unica quantità non misurata
  direttamente: la distribuzione reale di similarità del modello su audio
  Twitch italiano).
- Politica di relabel se si introduce il merge: fondere solo in avanti o
  rietichettare lo storico nel perception store?
