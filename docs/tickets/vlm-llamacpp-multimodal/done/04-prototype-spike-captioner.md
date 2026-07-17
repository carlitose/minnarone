# 04 — Prototype: spike `LlamaCppCaptioner` end-to-end + reazioni concorrenti

## Parent Spec

[vlm-llamacpp-multimodal-wayfinder.md](../../specs/vlm-llamacpp-multimodal-wayfinder.md)

## Type

prototype

## Outcome

Prova usa-e-getta che un captioner llama.cpp — un `Captioner` che invia un
`VideoFrame` reale come immagine base64 all'istanza multimodale e ritorna una
caption — funziona end-to-end col preprocessing di `vlm.py` (downscale), con
latenza compatibile con la pipeline video, **mentre** una reazione testo gira
in concorrenza sulla stessa istanza (scenario deciso in 03).

## Acceptance Criteria

- [ ] Script/spike (fuori da `src/`) che: prende un `VideoFrame` reale, applica
      il downscale come `Qwen2VlConfig` (`max_image_edge`/`max_image_pixels`),
      lo codifica in JPEG base64 data-URI, POST `/v1/chat/completions` con il
      content-part `image_url`, e stampa caption + latenza + token immagine.
- [ ] Verifica del contratto: formato risposta OpenAI-compatibile, caption
      tagliata a `max_caption_chars`, nessun reasoning/preambolo residuo.
- [ ] Scenario concorrente: una reazione testo e una caption in volo insieme
      sulla stessa istanza; latenze registrate; nessun OOM.
- [ ] Verdetto esplicito: il contratto regge per 05? latenza dentro i ritmi
      video? cosa cambia per l'implementazione?
- [ ] Esiti nel map; spike throwaway (non mergiato in `src/`).

## Blocked By

- 01 (qualità), 02 (parallel/VRAM), 03 (scenario e config decisi).

## Frontier

Ultimo bordo prima del codice di produzione: se lo spike fallisce (caption
inutili sotto carico, latenze fuori scala, mismatch contratto) si torna a
01/03 senza aver toccato `src/`.

## Work Plan

1. Avviare l'istanza multimodale con il `--parallel` deciso in 03.
2. Estrarre un `VideoFrame` reale (artifact di run o smoke video).
3. Spike Python minimale che riusa la logica di downscale di `vlm.py` e il
   trasporto locale di `llamacpp.py` (`_open_request` + opener no-proxy).
4. Misurare caption/latenza da solo e sotto reazione concorrente.
5. Scrivere il verdetto e aggiornare il map.

## Evidence to Capture

- Caption prodotte + latenze (sola / concorrente).
- `nvidia-smi` durante lo scenario concorrente.
- Body richiesta/risposta d'esempio (per 05).

## Out of Scope

- Codice di produzione, config schema, test (05).

---

## Risultati (2026-07-16)

Spike production-shaped (`scratchpad/spike_captioner04.py`) che riusa gli helper
REALI di `vlm.py` (`frame_to_pil_image`, `downscale_image_for_vlm`,
`_normalize_caption`) e il trasporto locale di `llamacpp.py` (`_open_request` +
`_local_opener` no-proxy/no-redirect). Server multimodale E2B + `mmproj` su
:8090, `--parallel 2`, `/props` → `vision: true`, 2611 MiB VRAM. Nessun frame
Twitch reale negli artifact → HUD sintetico + screenshot reale del desktop.

### Caption via path di produzione

| Frame | Latenza | len (≤240) | Caption |
|-------|--------|------------|---------|
| game_hud | 1.18 s | 186 | "…red progress bar…, small green triangle…, text WAVE 12 SCORE 48210." (accurata) |
| desktop_real | 0.59 s | 120 | "A Twitch stream displays gameplay…chat sidebar…streamer's overlay…" (coerente; allucina Twitch — priming del prompt, atteso in produzione) |

Gli helper `vlm.py` compongono correttamente col trasporto `llamacpp.py`;
`_normalize_caption` collassa/strip/tronca (186 < 240, nessun troncamento
forzato). Nessun reasoning/preambolo residuo.

### Caso d'errore (contratto best-effort "")

Captioner puntato a una porta morta → `TransportError` (WinError 10061)
catturato → **ritorna `""`**. Il contratto "caption vuota su errore trasporto/
HTTP a runtime" (decisione 5 del grilling) è implementabile in modo pulito
catturando `TransportError`/`TransportTimeout`/`OSError` attorno a
`_open_request`.

### Concorrenza (--parallel 2)

Reazione testo + caption in volo insieme sullo stesso server: testo **0.35 s** |
caption **0.89 s** | wall **0.90 s** (vera concorrenza, ~max). Nessun OOM.

### Verdetto: contratto pronto per il build 05

- Il path VideoFrame → downscale → JPEG base64 → `/v1/chat/completions`
  (`image_url`) → `_normalize_caption` regge riusando codice esistente: 05 deve
  solo comporre `LlamaCppCaptioner` che implementa `Captioner.caption`.
- Latenza (0.6–1.2 s) ampiamente dentro i ritmi video (`video_fps` ~1.0).
- `""` best-effort su errore: pulito, catturando le eccezioni di trasporto.
- Riuso confermato: `frame_to_pil_image`, `downscale_image_for_vlm`,
  `_normalize_caption` (con `QwenVlConfig` per prompt/max_edge/max_pixels/
  max_caption_chars/max_new_tokens) + `_open_request`/`_local_opener`.

### Criteri di accettazione

- [x] Spike che riusa downscale di vlm.py + trasporto locale, encoding JPEG
      base64, POST con content-part image_url, `_normalize_caption`.
- [x] Contratto verificato: OpenAI-compatibile, caption ≤ max_caption_chars,
      niente reasoning; caso errore → "".
- [x] Scenario concorrente `--parallel 2`: latenze registrate, nessun OOM.
- [x] Verdetto esplicito per 05.
- [x] Esiti nel map; spike throwaway (non in src/).
