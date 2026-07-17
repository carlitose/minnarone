# 06 — Task: extra `vlm` opzionale (footprint leggero per il captioner llama.cpp)

## Parent Spec

[vlm-llamacpp-multimodal-wayfinder.md](../../specs/vlm-llamacpp-multimodal-wayfinder.md)

## What to Build

Separare il packaging in `pyproject.toml` così che un utente che usa **solo** il
captioner llama.cpp (`vlm.backend: llamacpp`) possa installare minnarone **senza**
lo stack pesante torch/transformers, che serve solo al backend Qwen2-VL.

Oggi l'extra `vlm` (`pyproject.toml`, righe 57-63) tira dentro `accelerate`,
`bitsandbytes`, `pillow`, `torch`, `torchvision`, `transformers` — diversi GB
(su Windows torch/torchvision arrivano dall'indice CUDA `pytorch-cu126`). Il
`LlamaCppCaptioner` del ticket 05 necessita invece solo di `pillow` (downscale +
JPEG) e `urllib` (stdlib): nessuna dipendenza ML.

Copre la **decisione 3 del grilling** (ticket 03): "opzionalità dell'extra `vlm`
diventa ticket 06 condizionale". È **puro packaging**: nessun cambiamento di
comportamento a runtime; entrambi i backend restano funzionanti.

## Acceptance Criteria

- [ ] Nuovo extra leggero (es. `vlm-llamacpp = ["pillow>=10"]`) che copre il
      footprint del backend llama.cpp senza torch/transformers.
- [ ] L'extra `vlm` esistente resta invariato per il backend Qwen2-VL torch.
- [ ] `import minnarone` e la costruzione di `LlamaCppCaptioner` funzionano in un
      ambiente con il solo extra leggero installato (niente torch/transformers).
- [ ] `Qwen2VlCaptioner` continua a funzionare con l'extra `vlm` pesante.
- [ ] `deptry` non segnala regressioni (nuove dipendenze non dichiarate o
      inutilizzate); aggiornare `per_rule_ignores`/mappe se serve.
- [ ] README/docs: la sezione VLM indica quale extra installare per ciascun
      backend (`vlm-llamacpp` leggero vs `vlm` torch).

## Blocked By

- [05-task-implement-llamacpp-captioner.md](./05-task-implement-llamacpp-captioner.md)

## Frontier

Bloccato dal ticket 05: il `LlamaCppCaptioner` deve esistere e avere il suo
footprint reale (solo `pillow`) prima di poter definire l'extra leggero in modo
verificabile. Puramente AFK una volta sbloccato.

## Step-by-Step Implementation Plan

1. **Verificare il footprint reale del backend llama.cpp** (dopo 05): confermare
   che `minnarone.vlm` / il nuovo modulo del captioner llama.cpp importi solo
   `pillow` + stdlib e non trascini transformers/torch a import-time (import
   lazy del backend torch). Verifica: `python -c "import minnarone"` in un venv
   senza torch non deve fallire.
2. **Aggiungere l'extra leggero** in `[project.optional-dependencies]`:
   `vlm-llamacpp = ["pillow>=10"]`. Perché ora: è il contratto di installazione
   minimo del backend llama.cpp. Superficie: `pyproject.toml`.
3. **Lasciare `vlm` invariato** (torch/torchvision/transformers/accelerate/
   bitsandbytes + pillow) per il backend Qwen2-VL. Non spostare `pillow` fuori
   da `vlm`: entrambi gli extra lo condividono legittimamente.
4. **Verificare `deptry`**: `pillow` è già mappato (`pillow = ["PIL"]` in
   `package_module_name_map`). Assicurarsi che il nuovo extra non introduca
   DEP002 (dichiarata-non-usata) o DEP001 (usata-non-dichiarata). Aggiornare
   `per_rule_ignores` solo se strettamente necessario e con commento.
5. **Aggiornare README/docs**: nella sezione VLM/LLM locale, indicare
   `pip install 'minnarone[vlm-llamacpp]'` per il captioner locale e
   `[vlm]` per il backend torch. Comune pitfall: non promettere che l'extra
   leggero abiliti il backend torch.
6. **Verifica finale**: creare (o simulare) un ambiente con il solo extra
   leggero e confermare che il percorso `vlm.backend: llamacpp` + `--check`
   passi; e che l'ambiente con `vlm` pesante continui a costruire
   `Qwen2VlCaptioner`.

## Testing Plan

- Test/asserzione che l'import di `minnarone` e la costruzione del captioner
  llama.cpp non richiedano torch/transformers (es. test che fallisce se il
  modulo del captioner llama.cpp importa `torch` a livello di modulo).
- `deptry` pulito sul progetto.
- Suite esistente verde (nessuna regressione sui test del backend torch e del
  captioner llama.cpp del ticket 05).
- Verifica manuale: installazione con solo `vlm-llamacpp` → `--check` di una
  config `vlm.backend: llamacpp` passa senza torch installato.

## Out of Scope

- Rimuovere o deprecare il backend Qwen2-VL torch (decisione 03: si mantengono
  entrambi).
- Cambiare il comportamento a runtime dei captioner.
- Ristrutturare gli altri extra (`audio`, `video`, `os-capture`, ecc.).

---

## Risultati (2026-07-17)

Cambiamento di solo packaging + docs; nessuna logica runtime toccata.

- **`pyproject.toml`**: aggiunto l'extra leggero `vlm-llamacpp = ["pillow>=10"]`
  per il backend `vlm.backend: llamacpp` (solo Pillow; il trasporto è urllib
  stdlib, niente torch/transformers). L'extra `vlm` pesante
  (accelerate/bitsandbytes/pillow/torch/torchvision/transformers) resta
  **invariato** per il backend `qwen`.
- **README.md**: riga install aggiornata (`[vlm]` per `qwen`, `[vlm-llamacpp]`
  per `llamacpp`); descrizione del canale video riscritta per citare i due
  backend e i rispettivi extra; nota nella sezione captioning llama.cpp
  sull'installazione leggera.

### Verifica

- Extra risolve: `vlm-llamacpp` → `['pillow>=10']`; `vlm` invariato (contiene
  ancora torch). Confermato via `tomllib`.
- `deptry .` → **Success! No dependency issues found** (nessuna regressione).
- `tests/test_vlm_llamacpp.py` 27 passed, incluso
  `test_llamacpp_captioner_module_imports_without_torch` (il path llamacpp non
  importa torch a import-time → l'extra leggero è sufficiente).
- Test docs: solo il failure pre-esistente `test_readme_private_commentator_...`
  (drift del refresh README precedente, già rosso su HEAD), indipendente da
  questo diff.

### Criteri di accettazione

- [x] Nuovo extra leggero `vlm-llamacpp = ["pillow>=10"]`.
- [x] Extra `vlm` invariato per il backend Qwen2-VL torch.
- [x] `import minnarone` + `LlamaCppCaptioner` senza torch/transformers (test).
- [x] `Qwen2VlCaptioner` continua a funzionare con l'extra `vlm` (invariato).
- [x] `deptry` senza regressioni.
- [x] README/docs indicano quale extra per ciascun backend.
