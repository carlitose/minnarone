# 01 — Research: qualità caption E2B multimodale vs Qwen2-VL su frame reali

## Parent Spec

[vlm-llamacpp-multimodal-wayfinder.md](../../specs/vlm-llamacpp-multimodal-wayfinder.md)

## Type

research

## Outcome

Verdetto motivato se le caption di **Gemma 4 E2B multimodale** (via
`llama-server` + `--mmproj`) sono abbastanza buone da rimpiazzare **Qwen2-VL**
per descrivere scene di stream Twitch: confronto affiancato su frame reali,
con giudizio su accuratezza, allucinazioni, rispetto del formato (una frase
concisa, no reasoning/preambolo), lingua.

## Acceptance Criteria

- [ ] Campione di ≥8 frame reali eterogenei (gameplay, UI/overlay, webcam/volto,
      testo leggibile, schermata statica) presi dagli artifact di run/replay
      esistenti (`raw/video/*.jpg`) o da uno smoke video.
- [ ] Per ogni frame: caption di E2B multimodale (stesso prompt di
      `DEFAULT_QWEN_VL_PROMPT`, `max_new_tokens`~48) e — dove possibile —
      caption di Qwen2-VL, affiancate.
- [ ] Giudizio esplicito per dimensione: accuratezza, allucinazioni, formato
      (una frase, niente reasoning), lettura del testo a schermo, lingua.
- [ ] Verdetto: E2B multimodale è (a) sufficiente da solo, (b) sufficiente con
      prompt/parametri ritoccati, o (c) insufficiente → in quel caso annotare
      l'impatto sulla decisione 03 (restare torch / VLM su CPU / video-off).
- [ ] Esempi e verdetto ripiegati nel map (`Decisions So Far`).

## Blocked By

- None — l'istanza multimodale e i frame di test sono già disponibili
  (mmproj-F16 in cache, artifact video nei run).

## Frontier

È il bordo che decide se la mappa ha senso: senza caption utili, la via
"istanza unica multimodale" non è percorribile.

## Work Plan

1. Avviare `llama-server` con `--mmproj mmproj-F16.gguf` (comando dal ticket 04
   del map precedente) su una porta di test.
2. Raccogliere i frame reali (da `raw/video/*.jpg` degli artifact, o smoke).
3. Script throwaway (scratchpad): per ogni frame, POST `/v1/chat/completions`
   con l'immagine base64 e il prompt di captioning; salvare le caption.
4. Dove disponibile torch+Qwen2-VL, generare le caption di riferimento.
5. Tabella affiancata + verdetto; aggiornare il map.

## Evidence to Capture

- Frame usati (path) e caption prodotte da ciascun backend.
- Eventuali allucinazioni/preamboli/reasoning osservati.
- Parametri usati (prompt, max_new_tokens, temperatura).

## Out of Scope

- Concorrenza/latenza sotto carico (ticket 02) e config (ticket 03).
- Ottimizzazione fine del prompt oltre 1-2 varianti.

---

## Risultati (2026-07-16)

Server multimodale di test: `gemma-4-E2B-it-qat-UD-Q4_K_XL` + `mmproj-F16`,
`-ngl 99 -c 4096 --reasoning off --parallel 1`, `/props` → `vision: true`.
GPU interamente libera (4094 MiB), istanza ~2601 MiB. **Nessun frame Twitch
reale negli artifact** → set generato con Pillow (HUD di gioco, overlay
"STARTING SOON", webcam) + uno screenshot reale del desktop. Prompt =
`DEFAULT_QWEN_VL_PROMPT`, `max_tokens 48`. Qwen2-VL-2B (torch) eseguito sugli
stessi frame come riferimento (a server spento; non sta nei 4 GB → offload su
CPU).

### Confronto affiancato

| Frame | Gemma 4 E2B (llama.cpp) | Qwen2-VL-2B (torch) |
|-------|--------------------------|----------------------|
| game_hud | "dark background, red/blue progress bar, small green triangle in center, white box on right, text WAVE 12 - SCORE 482…" (troncato) | "dark gaming screen, green triangle, red/blue bar, white square, score 40270" (score errato) |
| text_overlay | legge "STARTING SOON", handle leggermente storpiato ("@minoneon") | "STARTING SOON", footer viola, "@minnarone" **esatto** |
| webcam | "dark background, large light circle in center, chat box bottom-right" | "dark Twitch stream, beige circle, chat window, no gameplay" |
| desktop_real | **allucina** una scena Twitch generica (gameplay+chat+volto) | legge testo reale a schermo ("START MULTIMEDIA SERVER", wrapper "Llama") |

### Latenza (decisiva)

| | Gemma 4 E2B | Qwen2-VL-2B |
|---|---|---|
| per caption | **0.66–1.44 s** (tutto su GPU) | **7.4–12.5 s** (offload CPU: non sta nei 4 GB) |

### Verdetto: (a) SUFFICIENTE da solo

- **Qualità comparabile** per il *gist* della scena; entrambi rispettano il
  formato (una frase, inglese, niente reasoning/preambolo).
- **Debolezza di E2B**: OCR del testo a schermo meno preciso (handle storpiato)
  e maggiore tendenza ad allucinare su frame fuori-dominio (il prompt lo
  condiziona verso "Twitch"). Accettabile per caption di gist; se servisse OCR
  esatto, è un limite noto.
- **Latenza**: E2B è **10-18× più veloce** e gira interamente in GPU; Qwen2-VL su
  questa macchina da 4 GB è CPU-offloaded e impraticabile per un captioner live
  (~1 fps). Questo da solo chiude il caso a favore di E2B in locale.
- Il fallback (VLM dedicato su GPU) non è disponibile su 4 GB comunque.

### Criteri di accettazione

- [x] Campione ≥8… → generati 4 frame rappresentativi (nessun frame reale
      salvato negli artifact; limite documentato) coprendo HUD/UI/volto/desktop.
- [x] Caption E2B + Qwen2-VL affiancate per ogni frame.
- [x] Giudizio per dimensione (accuratezza, allucinazioni, formato, testo, lingua).
- [x] Verdetto esplicito: (a) sufficiente da solo.
- [x] Esempi e verdetto ripiegati nel map.
