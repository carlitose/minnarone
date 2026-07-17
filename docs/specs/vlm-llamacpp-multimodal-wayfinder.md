# Migrazione del captioning VLM su llama.cpp (multimodale)

## Type

Wayfinding spec

## Status

Completata (2026-07-17): tutti i ticket 01–06 chiusi. Il backend
`vlm.backend: llamacpp` è implementato, testato e documentato; l'installazione
leggera (`vlm-llamacpp`) è disponibile. Nessun edge aperto.

## Destination

Poter produrre le **caption dei frame video in locale via `llama-server`**
multimodale (Gemma 4 E2B + `--mmproj`), in alternativa al backend attuale
Qwen2-VL su transformers/torch (`vlm.py`). Obiettivo forte su GPU da 4 GB:
**una sola istanza `llama-server` multimodale serve sia le reazioni testo
(provider `llamacpp` del map precedente) sia il captioning**, eliminando la
doppia residenza in VRAM (torch-VLM + LLM) che il ticket 04 ha dimostrato
non sostenibile su 4 GB.

È la mappa di follow-up esplicitamente rinviata dal
[map del provider LLM locale](local-llm-llamacpp-wayfinder.md) (decisione del
grilling 02: MVP solo testo; migrazione VLM decisa dai numeri del ticket 04).

## Decisions So Far

- **Seam di aggancio pulito** (letto dal codice): il canale video dipende solo
  dal Protocol `video.Captioner` — `caption(frame: VideoFrame) -> str`
  (`src/minnarone/video.py:107`). L'unica implementazione concreta è
  `Qwen2VlCaptioner` (`src/minnarone/vlm.py:136`), costruita in
  `app.py:715` `build_captioner()` e **già iniettabile** via
  `qwen_captioner_factory`. Un captioner llama.cpp è quindi un nuovo
  `Captioner` che invia il frame come immagine e ritorna una stringa: il
  `VideoPerceiver` non cambia.
- **Preprocessing frame già presente** in `Qwen2VlConfig`/`vlm.py`: downscaling
  (`max_image_edge: 768`, `max_image_pixels: 500_000`), `max_new_tokens`,
  `max_caption_chars`, prompt e lingua. Riusabile: il nuovo backend deve solo
  cambiare il *trasporto* (HTTP verso llama-server con immagine base64 in un
  content-part `image_url`) invece del runtime torch locale.
- **Contratto llama-server multimodale** (misurato nel ticket 04 del map
  precedente): istanza Q4_K_XL + `mmproj-F16` con `-ngl 99 -c 4096` carica in
  ~4 s, **+2408 MiB VRAM**; `/props` → `vision: true`; captioning JPEG 720p
  **1.26 s a freddo, 0.44 s a caldo** (~256 token immagine). L'endpoint è lo
  stesso `POST /v1/chat/completions` OpenAI-compatibile, con l'immagine come
  data-URI base64 in `messages[].content` (parte `image_url`).
- **Vincolo VRAM (4 GB)**: l'istanza multimodale da sola occupa ~2.4 GB; **due**
  istanze `llama-server` (una testo + una multimodale) NON coesistono. Quindi
  se si vuole sia LLM testo sia VLM in locale, la via obbligata è **un'unica
  istanza multimodale che serve entrambi** (le reazioni testo funzionano
  comunque su un server multimodale: il campo immagine è opzionale).
- **Trasporto riusabile**: il provider `llamacpp` (map precedente) ha già
  `_open_request` + opener locale no-proxy/no-redirect in
  `src/minnarone/llamacpp.py` e `openrouter.py`. Il captioner può riusare lo
  stesso trasporto stdlib (zero dipendenze nuove).
- **[Ticket 01, 2026-07-16] Qualità caption E2B multimodale: SUFFICIENTE.**
  Confronto su frame rappresentativi (HUD, overlay, webcam, desktop reale;
  nessun frame Twitch salvato negli artifact) vs Qwen2-VL-2B. Qualità del gist
  comparabile, formato rispettato (una frase, inglese, niente reasoning). E2B
  più debole sull'OCR del testo a schermo (handle storpiato) e più incline ad
  allucinare fuori-dominio. **Latenza decisiva**: E2B **0.66–1.44 s** (tutto in
  GPU) vs Qwen2-VL **7.4–12.5 s** (su 4 GB va in offload CPU → impraticabile per
  un captioner live). E2B in locale vince nettamente. Dettagli:
  `docs/tickets/vlm-llamacpp-multimodal/done/01-…`.
- **[Ticket 02, 2026-07-16] Istanza unica condivisa: praticabile.** Reazione
  testo e caption sulla stessa istanza multimodale: con `--parallel 1` la wall
  concorrente resta ~0.74 s (entrambe sub-secondo, accodamento trascurabile);
  con `--parallel 2` ~0.54 s (vera concorrenza) a costo **+10 MiB VRAM** (2611
  vs 2601 MiB su 4094). Ai ritmi reali (`video_fps` 1.0 + dedup) le collisioni
  sono rare. **Raccomandazione: `--parallel 2`**. Dettagli:
  `docs/tickets/vlm-llamacpp-multimodal/done/02-…`.
- **[Correzione 2026-07-17] `--parallel 2` dimezza il contesto per-richiesta.**
  Scoperto in un run reale "tutto attivo" (chat+audio+video): `llama-server`
  divide `-c` tra gli slot (`n_ctx_slot = n_ctx / n_slots`), quindi
  `-c 4096 --parallel 2` dà solo **2048 token/slot**. Un prompt `original_chat`
  multi-canale arriva a 2500–3000+ token → il server risponde **400 "exceeds the
  available context size"**. Il ticket 02 aveva misurato la concorrenza con
  prompt corti e non aveva colto questa divisione. **Fix**: con `--parallel 2`
  usare `-c 16384` (→ 8192/slot); costo VRAM trascurabile (+~80 MiB, la KV cache
  di E2B è piccola: misurato 2611→2689 MiB da 4096→16384). Aggiornati i comandi
  consigliati in `llamacpp.py` (`LLAMA_SERVER_*COMMAND`), README ed esempio.

## Not Yet Specified

Nessuna incognita bloccante per 04/05: fattibilità risolta da 01/02, decisioni
di prodotto dal grilling 03 (sotto). Da confermare in 05 (non bloccanti): il
comportamento attuale di `Qwen2VlCaptioner` su fallimento inferenza, e la
coerenza `llm_provider` cloud + `vlm.backend: llamacpp` (il VLM usa
`llamacpp.base_url` anche con testo cloud).

## Out of Scope

- Gestione del processo `llama-server` da parte di minnarone (resta
  user-launched, come deciso nel map precedente).
- Bundling di binari o download automatico di modelli/mmproj.
- Cambiare il Protocol `Captioner` o la pipeline `VideoPerceiver`.
- Captioning multi-immagine o video nativo (una frame → una caption, come oggi).
- Audio multimodale di Gemma 4 (fuori tema: qui solo visione).

## Frontier / Blocking Edges

- **[Ticket 05, 2026-07-16] Build completato.** `LlamaCppCaptioner`
  (`src/minnarone/vlm_llamacpp.py`, torch-free) + `vlm.backend: llamacpp|qwen`
  (default `qwen`) + routing in `app.py` (`build_captioner`) + health-check
  vision (`check_vision_ready`/`GET /props` in `llamacpp.py`, agganciato al
  percorso live di `cli.py` via `ensure_llamacpp_ready`) + contratto errore ""
  best-effort. README/example aggiornati (`--mmproj`, `--parallel 2`, istanza
  condivisa). 27 unit test fake-transport verdi, backend qwen invariato, nessuna
  dipendenza nuova. Code-review: corretto un gap nel contratto errore
  (`caption()` ora cattura anche `http.client.HTTPException`, come le funzioni
  sorelle). Dettagli: `docs/tickets/vlm-llamacpp-multimodal/done/05-…`.

- **Frontiera residua — solo ticket 06 (condizionale, NON attivato)**: rendere
  opzionale l'extra `vlm` torch / docs per l'installazione solo-llama.cpp. Si
  attiva solo se si decide di alleggerire quel setup; il path llamacpp e' gia'
  torch-free (verificato in 05), quindi 06 e' puramente di packaging/docs.

- **[Ticket 04, 2026-07-16] Spike production-shaped: contratto pronto.** Il path
  VideoFrame → `downscale_image_for_vlm` → JPEG base64 → `/v1/chat/completions`
  (`image_url`) → `_normalize_caption` regge riusando gli helper reali di
  `vlm.py` e il trasporto di `llamacpp.py` (`_open_request`/`_local_opener`).
  Caption 0.6–1.2 s (dentro i ritmi video); errore trasporto → `""` pulito
  (cattura `TransportError`/`TransportTimeout`/`OSError`); concorrenza
  `--parallel 2` wall 0.90 s, nessun OOM. 05 deve solo comporre
  `LlamaCppCaptioner`. Dettagli: `docs/tickets/vlm-llamacpp-multimodal/done/04-…`.

## Decisioni del grilling (2026-07-16, ticket 03)

1. **Config**: `vlm.backend: llamacpp | qwen` (default `qwen`); il backend
   llamacpp riusa `llamacpp.base_url`; prompt/language/token restano in `vlm:`.
2. **Istanza unica** multimodale (E2B + `--mmproj`) per testo+visione,
   `--parallel 2`.
3. **Due backend affiancati**, nessuna rimozione di torch; ticket 06
   (extra `vlm` opzionale) **non attivato**.
4. **Health-check**: con `vlm.backend: llamacpp`, verifica `vision: true` via
   `/props` all'avvio live, errore azionabile se manca `--mmproj`.
5. **Contratto errore runtime**: caption `""` su errore trasporto/HTTP (best-effort,
   salta il frame), con log; diverge dal salta-turno del provider LLM.

## Ticket Plan

| # | Tipo | Titolo | Stato |
|---|------|--------|-------|
| 01 | research | Qualità caption E2B multimodale vs Qwen2-VL | ✅ done (2026-07-16) |
| 02 | research | Concorrenza istanza condivisa: `--parallel`, VRAM | ✅ done (2026-07-16) |
| 03 | grilling | Decisioni: single vs separate, config, futuro backend torch | ✅ done (2026-07-16) |
| 04 | prototype | Spike `LlamaCppCaptioner` end-to-end + reazioni in concorrenza | ✅ done (2026-07-16) |
| 05 | task | Implementare `LlamaCppCaptioner` + config `vlm.backend` + test | ✅ done (2026-07-16) |
| 06 | task (condizionale) | Rendere opzionale l'extra `vlm` torch / docs | ✅ done (2026-07-17) |

## Next Review

Destinazione raggiunta: 01–05 done. Il captioning VLM locale via `llama-server`
multimodale e' in produzione (`vlm.backend: llamacpp`). Resta solo il ticket 06
(condizionale, packaging/docs per l'extra `vlm` torch opzionale), da attivare
solo se si vuole alleggerire l'installazione solo-llama.cpp.
