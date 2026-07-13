## Parent Spec

[speaker-diarization-over-segmentation.md](../../specs/speaker-diarization-over-segmentation.md)

## What to Build

Correggere la documentazione operatore che oggi dà un consiglio **invertito**
sulla soglia di clustering e non spiega la scelta del modello embedding. Vedi
la sezione Evidence (docs inversion) e i Follow-Up 1 e 4 dello spec.

Tre correzioni: (a) dichiarare che `speaker_clustering.threshold` è un
*pavimento di similarità coseno per unirsi* a un cluster (più alto = più
splitting); (b) invertire l'advice di troubleshooting (over-segmentation →
**abbassa** la soglia verso 0.4–0.5; under-segmentation → alza); (c) aggiungere
una guida alla scelta del modello embedding (sconsigliare il modello
`..._zh-cn_16k-common` per stream non mandarini; preferire un modello
language-matched/multilingue per l'italiano).

## Acceptance Criteria

- [ ] `docs/twitch-operator.md` non contiene più il consiglio "alza il
      threshold" per risolvere l'over-segmentation (né nel troubleshooting né
      nella sezione smoke).
- [ ] La semantica della soglia (join floor di similarità coseno) è dichiarata
      esplicitamente.
- [ ] Esiste una nota sulla scelta del modello embedding (evitare zh-cn per
      italiano).
- [ ] Se il default della soglia in `config.py`/`examples/*.yaml` viene
      cambiato, il valore è coerente con i docs; altrimenti i docs indicano il
      valore consigliato (0.4–0.45) come punto di partenza, non universale.
- [ ] Eventuali test sui docs (se presenti) restano verdi.

## Blocked By

- None - can start immediately.

## Frontier

Pronto ora. Indipendente dal ticket 01 (tocca solo docs/esempi/eventuale default
di config, non la logica del clusterer). Nota: il valore *esatto* della soglia
si conferma solo nel run live (ticket 05), quindi qui documentare 0.4–0.45 come
default ragionevole, non come verità assoluta.

## Step-by-Step Implementation Plan

1. Trovare in `docs/twitch-operator.md` i punti che consigliano di alzare la
   soglia per l'over-segmentation (troubleshooting e sezione smoke) e riscriverli
   con la direzione corretta e la semantica del parametro.
2. Aggiungere una breve nota sulla scelta del modello embedding: il modello deve
   essere adatto alla lingua/dominio dello stream; il `zh-cn` è mandarino e
   deprime la similarità intra-speaker sull'italiano.
3. Decidere se abbassare il default in `config.py` e negli `examples/*.yaml`
   (commenti inclusi) a ~0.45. Se sì, aggiornarli e mantenerli coerenti coi
   docs; se no, lasciare il default e documentare 0.45 come valore consigliato.
4. Verificare che eventuali test sui docs (`tests/test_twitch_operator_docs.py`)
   passino ancora e, se necessario, aggiornarli.

Pitfall: mantenere la precisione per-modalità nei docs (i runtime off/shadow/
private continuano a non inviare — non toccare quelle affermazioni). Non
promettere una soglia universale: dipende da modello/lingua/rumore.

## Testing Plan

- `uv run pytest tests/test_twitch_operator_docs.py -q` (se copre queste
  sezioni) verde.
- Ricerca repo-wide: il vecchio consiglio "raise threshold to fix
  over-segmentation" non compare più al di fuori di documenti storici
  (spec/issue/PRD, che sono registri, non promesse).

## Out of Scope

- La logica del collasso `[ALTRO]` (ticket 01).
- Marking manuale (ticket 03) e hardening (ticket 04).
