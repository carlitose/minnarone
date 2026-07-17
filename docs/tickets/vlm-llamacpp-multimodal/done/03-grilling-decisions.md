# 03 — Grilling: single vs separate, config, futuro del backend torch

## Parent Spec

[vlm-llamacpp-multimodal-wayfinder.md](../../specs/vlm-llamacpp-multimodal-wayfinder.md)

## Type

grilling

## Outcome

Decisioni umane registrate su: (1) istanza multimodale unica (reazioni +
caption) vs backend separati; (2) modello della config (`vlm.backend`,
`base_url` condiviso o dedicato); (3) `--parallel` scelto (da 02); (4) destino
del backend torch `Qwen2VlCaptioner` e dell'extra `vlm`.

## Acceptance Criteria

- [ ] Ogni domanda ha risposta registrata (o assunzione esplicita con data) nel
      map (`Decisions So Far`).
- [ ] Le decisioni citano l'evidenza di 01 (qualità) e 02 (concorrenza/VRAM).
- [ ] L'esito determina il perimetro di 05 e se creare il ticket 06.

## Blocked By

- 01 (qualità caption), 02 (concorrenza/VRAM).

## Frontier

Le scelte cambiano cosa si implementa in 05; deciderle dopo lo spike sarebbe
rework, deciderle senza i numeri di 01/02 sarebbe indovinare.

## Work Plan

1. Presentare l'evidenza di 01+02 in forma compatta.
2. Porre le domande:
   - **Single vs separate**: confermiamo l'istanza multimodale unica che serve
     sia reazioni sia caption? (i numeri di 04 del map precedente escludono due
     istanze su 4 GB). Se la qualità di 01 è insufficiente, cosa si sceglie:
     restare su Qwen2-VL torch, VLM su CPU, o video-off in locale?
   - **Config**: `vlm.backend: llamacpp | qwen`? Il backend llamacpp riusa
     `llamacpp.base_url` (istanza unica) o ha un `vlm.base_url` proprio? Dove
     restano `prompt`/`language`/`max_new_tokens`/downscaling già in `vlm:`?
   - **Parallel**: adottiamo la raccomandazione di 02 (`--parallel 1` o `2`)?
     va nella doc operatore / comando di avvio?
   - **Backend torch**: manteniamo `Qwen2VlCaptioner` come opzione o lo
     deprechiamo? L'extra `vlm` (transformers+torch) diventa opzionale per gli
     utenti solo-llama.cpp?
3. Registrare risposte/assunzioni nel map e chiudere il ticket.

## Evidence to Capture

- Risposte testuali dell'utente (o assunzioni marcate come tali).
- Vincoli nuovi emersi.

## Out of Scope

- Implementare alcunché; solo decisioni.

---

## Risposte registrate (grilling 2026-07-16)

| # | Domanda | Decisione |
|---|---------|-----------|
| 1 | Config / selezione backend | `vlm.backend: llamacpp \| qwen` (default **qwen**, comportamento invariato); il backend llamacpp **riusa `llamacpp.base_url`** (istanza unica); prompt/language/max_new_tokens/downscale restano nel blocco `vlm:`. Nessun `vlm.base_url` finché non serve. |
| 2 | Single vs separate | Confermata l'**istanza multimodale unica** (E2B + `--mmproj`) per testo+visione, `--parallel 2` (dai numeri di 01/02). |
| 3 | Destino backend torch | **Entrambi affiancati**, `qwen` resta opzione per chi ha VRAM/vuole OCR migliore. Nessuna rimozione in 05. Opzionalità dell'extra `vlm` = ticket 06 condizionale, **non attivato** (creare solo se si vuole alleggerire l'installazione). |
| 4 | Health-check vision | Quando `vlm.backend: llamacpp`, all'avvio live verificare `modalities.vision == true` via `/props`; errore azionabile ("manca `--mmproj`"). Riusa/estende `ensure_llamacpp_ready`. Gira anche se `llm_provider` è cloud. |
| 5 | Contratto errore runtime | `LlamaCppCaptioner` ritorna `""` (salta il frame) su errori trasporto/HTTP a sessione avviata — coerente col Protocol `Captioner` best-effort; diverge di proposito dal salta-turno del provider LLM. Log dell'errore mantenuto. |

**Trade-off accettati**: OCR del testo a schermo di E2B più debole (ok per il gist); l'operatore avvia il server con `--mmproj`; canale video best-effort (caption perse ≠ crash).

**Assunzioni residue (da confermare in 05)**: comportamento attuale di `Qwen2VlCaptioner` su fallimento inferenza; coerenza `llm_provider` cloud + `vlm.backend: llamacpp` (il VLM usa `llamacpp.base_url` anche con testo cloud; l'health-check vision gira comunque).

### Criteri di accettazione

- [x] Ogni domanda ha risposta registrata.
- [x] Decisioni informate dall'evidenza di 01 (qualità/latenza) e 02 (concorrenza/VRAM).
- [x] Esito su 06 (non attivato) e perimetro di 05 (due backend, health-check vision, contratto "") determinati.
