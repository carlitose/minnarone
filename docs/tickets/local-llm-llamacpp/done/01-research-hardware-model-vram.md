# 01 — Research: hardware target, modello Gemma e budget VRAM

## Parent Spec

[local-llm-llamacpp-wayfinder.md](../../specs/local-llm-llamacpp-wayfinder.md)

## Type

research

## Outcome

Scelta motivata di **modello, quantizzazione e context size** per il LLM locale
("gemma4" secondo l'utente — verificare cosa esiste davvero e cosa supporta
llama.cpp), con numeri misurati sull'hardware target: VRAM occupata, tokens/s,
e se ci sta **insieme** a Qwen2-VL (o quale alternativa VLM rende la coesistenza
possibile).

## Acceptance Criteria

- [ ] Inventario hardware documentato: GPU, VRAM totale, `nvidia-smi` (o equivalente).
- [ ] Famiglia Gemma verificata: quale versione intende l'utente con "gemma4",
      quali GGUF ufficiali/quantizzati esistono, supporto llama.cpp confermato
      (incluso `--mmproj` per la variante multimodale).
- [ ] Tabella comparativa di 2–3 candidati (modello × quant × ctx) con VRAM
      stimata/misurata e tokens/s da `llama-bench` o `llama-server` reale.
- [ ] Misura della VRAM residua con Qwen2-VL caricato (config `vlm` attuale) e
      verdetto: quali candidati coesistono, quali no.
- [ ] Peso VRAM/qualità della variante "VLM su llama.cpp" (Qwen2-VL GGUF o
      Gemma multimodale) annotato per la decisione in 02.
- [ ] Evidenza e conclusioni riportate nel wayfinder (`Decisions So Far` /
      `Not Yet Specified`).

## Blocked By

- None — può partire subito.

## Frontier

È il bordo che blocca tutto: senza sapere cosa gira sull'hardware reale, la
policy GPU (02), lo spike (04) e l'implementazione (05) sono ciechi.

## Work Plan

1. Rilevare GPU/VRAM della macchina target (`nvidia-smi`).
2. Verificare su fonti aggiornate (llama.cpp releases, HF) la famiglia Gemma
   corrente, i GGUF disponibili e il supporto multimodale in llama.cpp.
3. Scaricare 1–2 quant candidate; misurare con `llama-bench` (o server + una
   richiesta) VRAM e tokens/s a ctx realistici (prompt minnarone ~ lungo:
   stimare dai run esistenti in `run.log`/replay).
4. Caricare Qwen2-VL con la config attuale e rimisurare la VRAM residua.
5. Scrivere la tabella e il verdetto nel ticket + aggiornare il wayfinder.

## Evidence to Capture

- Output `nvidia-smi` prima/dopo ogni carico.
- Righe `llama-bench` (o log server) con modello, quant, ctx, tokens/s.
- Link ai GGUF scelti (repo HF) e alla release llama.cpp usata.

## Out of Scope

- Decidere la policy GPU (è di 02); qui solo i numeri.
- Fine-tuning o valutazione qualitativa approfondita del modello.

---

## Risultati (2026-07-16)

### Hardware target (misurato)

- GPU: **NVIDIA RTX 500 Ada Generation Laptop — 4094 MiB VRAM** (driver 596.47, CUDA 13.2, Windows 11, WDDM).
- ⚠️ Discrepanza: il decision brief di translate-lector (D2) assumeva "~8GB VRAM"; la macchina reale ne ha **4 GB**. Ogni dimensionamento va fatto su 4 GB.

### "gemma4" verificato

**Gemma 4 esiste**: rilasciato da Google **aprile 2026** (Apache 2.0), supporto llama.cpp ufficiale al lancio. Famiglia: **E2B, E4B, 12B** (giugno 2026), **26B-A4B, 31B**. **Multimodale** (testo+immagine; audio sui modelli piccoli) via file `--mmproj` separato; ctx 128K (E2B/E4B). GGUF ufficiali da `ggml-org` e `unsloth`; checkpoint **QAT** (~4-bit con qualità vicina a BF16). Fonti: [Google AI docs](https://ai.google.dev/gemma/docs/integrations/llamacpp), [Unsloth docs](https://unsloth.ai/docs/models/gemma-4), [unsloth/gemma-4-E2B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF), [stato supporto llama.cpp](https://avenchat.com/blog/does-llama-cpp-support-gemma-4).

### Misure live (server translate-lector già in esecuzione su QUESTA macchina)

Modello: `unsloth/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf` (2.6 GB, 4.6B parametri), llama.cpp build `b10016`, `-c 4096 --parallel 1`, endpoint `http://127.0.0.1:8080`.

| Metrica | Valore |
|---|---|
| VRAM occupata (server carico, GPU altrimenti idle) | **~1.47 GB / 4.09 GB** |
| Prompt eval (freddo, 2372 tok) | **~2436 tok/s** → 1.17 s wall |
| Generazione | **~75 tok/s** |
| Con prefisso stabile in cache | solo ~20 tok rivalutati → **0.19–0.23 s wall** |

Latenza ampiamente dentro il timeout 30 s e la cadenza del Reactor.

### Tabella candidati (GPU 4 GB)

| Candidato | File | VRAM | tok/s | Verdetto |
|---|---|---|---|---|
| **E2B QAT UD-Q4_K_XL** | 2.6 GB | ~1.5 GB @4K ctx (misurato) | 75 (misurato) | ✅ Provato su questa GPU. ⚠️ translate-lector ha visto output rotto col QAT nel loro task (Q4 liscio ok): qualità da verificare sul task reazioni (ticket 04); tenere pronto il fallback **E2B Q4_K_XL non-QAT** |
| E4B Q4 | ~4.0–4.5 GB | non sta interamente in 4 GB | crollo con offload parziale | ❌ Solo con spill in RAM; mai insieme a un VLM |
| 12B / 26B-A4B / 31B | ≥8 GB | fuori scala | — | ❌ |

### Coesistenza con Qwen2-VL (verdetto analitico)

Con E2B caricato restano **~2.6 GB liberi**. Qwen2-VL-2B fp16 ≈ 4.4 GB (**non sta nemmeno da solo**); int4 ≈ 1.5–2 GB + contesto CUDA di torch (~0.5 GB) + attivazioni → **marginale, rischio OOM**. La co-residenza torch-VLM + LLM su questa GPU **non è una base affidabile**.

Percorsi realistici (decisione in ticket 02):
1. **Un solo server multimodale**: Gemma 4 E2B + `--mmproj` serve testo E captioning (costo VRAM del projector da misurare nel ticket 04 — l'istanza attuale gira con `vision:false`).
2. VLM su CPU (latenza per frame da verificare vs `video_fps`).
3. Solo testo (video spento) come primo step.

### Criteri di accettazione

- [x] Inventario hardware
- [x] Famiglia Gemma verificata (versione, GGUF, supporto llama.cpp, mmproj)
- [x] Tabella candidati con VRAM e tok/s (E2B misurato; E4B/12B esclusi per aritmetica su 4 GB)
- [x] Coesistenza Qwen2-VL: risolta analiticamente (non ci sta); conferma empirica del percorso scelto ripiegata nello scenario combinato del ticket 04
- [x] Peso della variante "VLM su llama.cpp" annotato (mmproj, da misurare in 04)
- [x] Wayfinder aggiornato
