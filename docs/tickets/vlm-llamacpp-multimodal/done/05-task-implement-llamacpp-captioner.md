# 05 — Task: implementare `LlamaCppCaptioner` + config `vlm.backend` + test

## Parent Spec

[vlm-llamacpp-multimodal-wayfinder.md](../../specs/vlm-llamacpp-multimodal-wayfinder.md)

## Type

task

## Outcome

Il canale video di minnarone può produrre caption via `llama-server`
multimodale locale, selezionabile da config (es. `vlm.backend: llamacpp`),
rispettando il Protocol `video.Captioner` e riusando preprocessing e trasporto
esistenti. I frame vengono descritti dall'istanza multimodale locale senza
transformers/torch.

## Acceptance Criteria

- [ ] Nuovo `LlamaCppCaptioner` che implementa `caption(frame) -> str`: downscale
      del frame (riusando la logica di `vlm.py`), encoding JPEG base64,
      POST `/v1/chat/completions` con content-part `image_url`, taglio a
      `max_caption_chars`, mapping degli errori a caption vuota/eccezione
      coerente col contratto attuale del captioner.
- [ ] `build_captioner` (`app.py`) instrada in base a `vlm.backend`; il backend
      Qwen2-VL torch resta invariato per chi lo seleziona.
- [ ] Config: `vlm.backend` + `base_url` (condiviso con `llamacpp` o dedicato,
      secondo la decisione 03) validati al `--check` con errori chiari;
      `prompt`/`language`/`max_new_tokens`/downscale riusati dal blocco `vlm:`.
- [ ] Nessuna dipendenza runtime nuova (trasporto urllib condiviso con
      `llamacpp.py`).
- [ ] Unit test con transport fake: caption ok, risposta malformata → vuota/errore,
      timeout, taglio a max_chars, backend selezionato da config.
- [ ] `--check` passa senza rete; README/docs aggiornati (comando `--mmproj`,
      esempio config, nota su parallel).
- [ ] Il backend torch continua a funzionare (test esistenti verdi).

## Blocked By

- 03 (config/perimetro), 04 (verdetto spike).

## Frontier

Build ticket finale del percorso captioning locale. La deprecazione/opzionalità
di torch è fuori (ticket 06, se deciso in 03).

## Work Plan

1. Estrarre l'helper di downscale di `vlm.py` in forma condivisibile (o riusarlo)
   senza rompere `Qwen2VlCaptioner`.
2. Implementare `LlamaCppCaptioner` riusando `_open_request` + opener locale.
3. Estendere `build_captioner` + config schema + validazione `--check`.
4. Test unitari (pattern fake-transport già usato per il provider llamacpp).
5. Prova manuale contro l'istanza multimodale (setup del ticket 04).
6. Aggiornare README/docs e il map; chiudere il ticket.

## Evidence to Capture

- Output test suite e `--check`.
- Un run locale reale con caption da llama-server.

## Out of Scope

- Rendere opzionale l'extra `vlm` torch (ticket 06). Gestione del processo
  server (resta user-launched).

---

## Risultati (2026-07-16)

Implementato end-to-end con TDD (RED sui boundary pubblici → GREEN → refactor a
verde). Nessun server reale richiesto: tutti i test usano fake transport/probe.

### Cosa e' stato implementato

- **`LlamaCppCaptioner`** (nuovo modulo `src/minnarone/vlm_llamacpp.py`):
  implementa il Protocol `video.Captioner`. Path: `VideoFrame` →
  `frame_to_pil_image` → `downscale_image_for_vlm` (helper riusati da `vlm.py`)
  → JPEG base64 data-URI → `POST {base_url}/v1/chat/completions` con
  `content:[{type:text},{type:image_url}]` e `max_tokens` →
  `_normalize_caption`. Trasporto `_local_transport` (opener no-proxy/no-redirect
  di `llamacpp.py`), iniettabile. **Contratto errore best-effort**: ritorna `""`
  (con log) su `TransportError`/`TransportTimeout`/`OSError`, status != 200 o
  risposta malformata — diverge di proposito da `Qwen2VlCaptioner` che SOLLEVA.
  Modulo scelto separato da `vlm.py` per minimizzare l'accoppiamento e NON
  importare mai torch nel path llamacpp (prep. ticket 06); verificato con test
  in subprocess che blocca `torch`.
- **Config** (`vlm.py` + `config.py`): campo `vlm.backend` (`qwen|llamacpp`,
  default `qwen`), validato in `QwenVlConfig.__post_init__` (errore chiaro al
  `--check`), aggiunto agli `allowed` e al pass-through di `_vlm_config_from_dict`.
  Il backend llamacpp riusa `llamacpp.base_url` (nessun `vlm.base_url`);
  prompt/language/token/downscale/max_caption_chars restano in `vlm:`.
- **Routing** (`app.py`): `_build_default_video_perceiver`/`build_agent`
  instradano su `config.vlm.backend` — `qwen` → `Qwen2VlCaptioner` (invariato),
  `llamacpp` → `LlamaCppCaptioner(base_url=config.llamacpp.base_url,
  config=config.vlm)`. Aggiunto `llamacpp_captioner_factory` iniettabile.
- **Health-check vision** (`llamacpp.py`): `check_vision_ready` +
  `_urllib_vision_probe` (probe iniettabile, come `check_server_ready`) verifica
  `modalities.vision == true` via `GET /props`; `ensure_llamacpp_ready` esteso
  per lanciarlo quando `vlm.backend == "llamacpp"` (indipendente da
  `llm_provider`, gira anche con LLM cloud). Errore azionabile in italiano che
  ricorda `--mmproj` (`LLAMA_SERVER_MULTIMODAL_COMMAND`, `--parallel 2`). Solo
  percorso live, mai `--check`.
- **Docs**: README (blocco `vlm:` con `backend`, nuova sezione "Captioning video
  locale via llama.cpp" con comando `--mmproj`, esempio `vlm.backend: llamacpp`,
  nota `--parallel 2` e istanza condivisa) e `examples/llamacpp-local.example.yaml`
  (blocco commentato per abilitare il captioner multimodale).
- **Nessuna dipendenza runtime nuova** (trasporto stdlib urllib condiviso).

### File toccati

- Nuovi: `src/minnarone/vlm_llamacpp.py`, `tests/test_vlm_llamacpp.py`.
- Modificati: `src/minnarone/vlm.py`, `src/minnarone/config.py`,
  `src/minnarone/app.py`, `src/minnarone/llamacpp.py`, `README.md`,
  `examples/llamacpp-local.example.yaml`.

### Esito test/lint

- `pytest tests/test_vlm_llamacpp.py` → 26 passed (caption ok+shape,
  malformata/non-json/HTTP!=200/transport/timeout/OSError → "", troncamento
  max_caption_chars, import senza torch, config backend, routing, vision ok/ko,
  `--check` senza rete, live vision-ko → errore chiaro).
- `pytest tests/test_vlm.py tests/test_llamacpp_provider.py tests/test_config.py`
  → tutti verdi (backend qwen invariato).
- `ruff check src/minnarone/ tests/test_vlm_llamacpp.py` → All checks passed.
- 4 fallimenti nella suite completa sono PRE-ESISTENTI e non correlati
  (verificato con le modifiche in stash): `test_cli` live-send token,
  `test_twitch_audio` kill-process, `test_twitch_operator_docs` README wording,
  e un test audio-clustering flaky per ordine (verde in isolamento).

### Criteri di accettazione

- [x] `LlamaCppCaptioner` con downscale riusato, JPEG base64, content-part
  `image_url`, taglio `max_caption_chars`, contratto errore best-effort "".
- [x] `build_captioner` instrada su `vlm.backend`; backend qwen invariato.
- [x] Config `vlm.backend` validato al `--check`; riuso di `llamacpp.base_url`.
- [x] Nessuna dipendenza runtime nuova.
- [x] Unit test fake-transport completi; backend qwen resta verde.
- [x] `--check` senza rete; README/docs aggiornati (`--mmproj`, esempio,
  `--parallel 2`).

## Review + QA (2026-07-16, super-autopilote)

Code-review adversariale del diff. Verifica manuale delle aree a rischio (wiring
health-check, gating video, contratto errore, import torch-free): nessun bug
strutturale. Un rilievo di correttezza confermato e **corretto**:

- **`http.client.HTTPException` non catturata** (`vlm_llamacpp.py`,
  `LlamaCppCaptioner.caption`): `caption()` catturava solo `(TransportError,
  OSError)`, ma `_open_request` può propagare `http.client.IncompleteRead`/
  `BadStatusLine` (server che chiude a metà risposta) — NON sottoclasse di
  OSError, non incapsulata da urllib. Le funzioni sorelle dello stesso modulo
  (`check_server_ready`/`check_vision_ready`) la catturano di proposito. Ora
  `caption()` cattura `(TransportError, OSError, http.client.HTTPException)`,
  onorando il contratto best-effort "" su errore di trasporto/HTTP. +1 test.

Rilievo **non** applicato (deciso): errori di *preprocessing* (frame malformato →
`QwenVlCaptionError`/`TypeError`) restano fuori dal catch — sono fuori dal
contratto "trasporto/HTTP" e devono emergere come frame `failed` nelle stats
(la pompa `perception_queue` cattura comunque per-evento, il canale non muore),
non essere inghiottiti in "" per sempre mascherando bug di wiring.

**Test**: `tests/test_vlm_llamacpp.py` 27 passed (+1 regressione HTTPException);
suite affette (vlm/llamacpp/config) verdi; ruff pulito sui file toccati.
**QA end-to-end**: spike ticket 04 contro server reale (caption via path di
produzione); `--check` offline su config `llm_provider: llamacpp` ok;
validazione backend in-process (qwen default, llamacpp ok, bogus rifiutato,
`LlamaCppCaptioner` costruito con `llamacpp.base_url` senza model). 3 failure
pre-esistenti nel repo (flake audio Twitch, drift wording README) verificati
indipendenti dal diff via git stash.
