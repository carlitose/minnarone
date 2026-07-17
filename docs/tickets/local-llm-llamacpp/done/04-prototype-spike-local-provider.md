# 04 — Prototype: spike prompt reale minnarone → llama-server (+ VLM caricato)

## Parent Spec

[local-llm-llamacpp-wayfinder.md](../../specs/local-llm-llamacpp-wayfinder.md)

## Type

prototype

## Outcome

Prova usa-e-getta che un prompt **reale** di minnarone (preso da un run/replay
esistente) ottiene una risposta valida dal modello scelto in 01 via
`llama-server`, con latenza compatibile col contratto salta-turno del Reactor,
**mentre** il carico VLM previsto dalla policy di 02 è attivo sulla GPU.

## Acceptance Criteria

- [x] Script/spike (fuori da `src/`, es. in `examples/` o scratch) che invia un
      prompt reale a `llama-server` lanciato a mano e stampa risposta, latenza
      end-to-end e token usage.
- [x] Almeno 5 richieste consecutive con prefisso stabile: verificato l'effetto
      del prompt caching sulla latenza (confronto 1ª vs successive).
- [x] Scenario GPU della policy scelta in 02 riprodotto (es. Qwen2-VL caricato
      in parallelo, o unico server multimodale): niente OOM, latenze registrate.
- [x] Verdetto esplicito: il contratto di 03 regge? La latenza sta nel timeout
      (default 30 s) e nella cadenza del Reactor? Cosa cambia per 05?
- [x] Esiti riportati nel wayfinder; lo spike resta throwaway (non mergiato in
      `src/`).

## Blocked By

- 01 (modello scelto), 02 (policy GPU da riprodurre), 03 (contratto da
  esercitare).

## Frontier

Ultimo bordo prima di scrivere codice di produzione: se lo spike fallisce
(OOM, latenze fuori scala, mismatch contratto) si torna a 01/02 senza aver
toccato `src/`.

## Work Plan

1. Estrarre un prompt reale (da `--replay` o dagli artifact di run esistenti).
2. Avviare `llama-server` con gli argomenti decisi (cfr. D4 translate-lector:
   `-ngl`, `-c`, `--reasoning off`, `--parallel 1` — adattati all'esito di 01/02).
3. Spike Python minimale (urllib, come `openrouter.py`) → misure.
4. Attivare il carico VLM secondo policy e ripetere le misure.
5. Scrivere il verdetto e aggiornare il wayfinder.

## Evidence to Capture

- Log latenze (1ª richiesta a freddo, successive con cache).
- `nvidia-smi` durante lo scenario combinato.
- Body richiesta/risposta d'esempio (alimenta anche 03).

## Out of Scope

- Codice di produzione, test, config schema (05).
- Gestione lifecycle del server (06, se deciso).

## Risultati (2026-07-16)

Spike THROWAWAY eseguito contro il `llama-server` già attivo (build b10016
CUDA, `gemma-4-E2B-it-qat-UD-Q4_K_XL`, `-c 4096 --parallel 1`,
`http://127.0.0.1:8080`). Script nello scratchpad di sessione
(`spike_ticket04.py` + probe ad-hoc), nessun codice in `src/`. GPU: RTX 500
Ada Laptop, 4094 MiB VRAM.

### 1. Prompt reale

Prompt costruito col **PromptBuilder vero** (profilo `original_chat`):
soul/facts di `examples/original-chat-memory/`, storia = percezioni del run
reale `run-20260710T114611Z-a25a96fe` (763 percezioni: 466 caption video,
245 speech, 52 chat msg), finestra recente = 20 (il `recent_chat_window`
dell'esempio original-chat), riassunto di sessione + 3 `self_messages`,
trigger mention in stile live.

- Dimensione misurata via `usage.prompt_tokens`: **1689–1746 token**
  (~6.0 KB di testo) a regime con finestra 20.

### 2. Latenza e prompt caching sul prompt reale

Loop simulato come il Reactor: prefisso stabile + riassunto byte-identici,
3 nuove percezioni in coda per turno, trigger nuovo a ogni turno.

| Richiesta | wall | prompt_tokens | cached | rivalutati (`prompt_n`) | gen tok/s |
|---|---|---|---|---|---|
| 1ª (fredda) | 1.07 s | 1702 | 1 | 1701 | 72.3 |
| 2ª | 0.91 s | 1716 | 1 | 1715 | 74.8 |
| 3ª | 0.88 s | 1729 | 1 | 1728 | 74.5 |
| 4ª | 0.84 s | 1746 | 1 | 1745 | 67.1 |
| 5ª | 0.84 s | 1708 | 1 | 1707 | 71.2 |

**Scoperta chiave (limite iSWA di Gemma)**: il riuso della cache NON è
avvenuto quando la finestra di storia scorre. Misurato con probe controllati:
la cache sopravvive solo se la divergenza col prompt precedente sta negli
ultimi **~400–450 token** (350 dalla fine → riuso ok; ≥450 → rivalutazione
completa). È coerente con la sliding-window attention di Gemma (`n_swa`=512):
llama.cpp non può fare rollback del KV oltre la finestra. Conferme:

- Stesso prompt ripetuto → `cached=1549`, `prompt_n=1` (0.07 s): la cache
  funziona.
- Cambio del SOLO trigger in coda (finestra ferma) → `cached=1534`,
  `prompt_n=17`, **0.10 s**: riuso pieno.
- Scorrimento finestra di 3 percezioni (divergenza a ~620 token dalla fine,
  dentro `[PARLATO RECENTE]`) → `cached=1`, rivalutazione completa.

Costo della rivalutazione completa: **0.84–1.07 s** a ~1.7K token
(prompt eval ~2100–3400 tok/s), generazione ~65–75 tok/s. Nel flusso reale
di original_chat i turni saranno un mix: mention ravvicinate senza nuove
percezioni ≈ 0.3–0.5 s; turni con storia scorsa ≈ 0.8–1.1 s.

**Verdetto**: il contratto di 03 regge senza modifiche; anche il caso
peggiore sta **1–2 ordini di grandezza sotto il timeout di 30 s** ed è
compatibile con la cadenza del Reactor (`senser_interval` 0.5 s: la reazione
completa resta sotto ~1.5 s). Per 05 NON contare sul prompt caching come
requisito di latenza (con Gemma iSWA è quasi sempre freddo appena la storia
scorre); eventuale `--swa-full` server-side lo riabiliterebbe al costo di KV
cache più grande — scelta operatore, non del provider.

### 3. Qualità QAT sul task reazioni (contratto RE:/MSG:)

6 trigger diversi sulla stessa storia reale, output parsato con
`normalize_original_chat_response` (sampling di default del server:
temp 1.0, top_k 64, top_p 0.95):

| Caso | Formato 2 righe | Output (MSG) | Giudizio |
|---|---|---|---|
| chat ironica (@minnarone "sicuro sei un pro KEKW") | ✅ | "@skeith96 tranquillo, fammi vedere quando ho tempo." | in personaggio, naturale |
| domanda diretta (honor run) | ✅ | "a meno che non faccia il casino, si può fare. pog" | sensata, informale |
| "ma sei un bot?" | ✅ | "no, sul serio. sono minnarone." | disclosure rispettata |
| audio streamer (ridare l'oro a Gale?) | ✅ | "tieni pure, non ti preoccupare." | sensata, risponde al quesito |
| continuation noiosa (msg fuori tema) | ✅ | "boh, non lo so" (non `#end_conv`) | formato ok; ignora "a metà" |
| idle_comment | ✅ | "ok, tranquillo allora." | formato ok ma generico |

**Verdetto QAT: OK.** Nessun output rotto/garbled, formato `RE:`/`MSG:`
rispettato 6/6, italiano naturale e in-character. Il problema visto da
translate-lector sul QAT NON si manifesta sul task reazioni. **Fallback
E2B Q4_K_XL non-QAT: non necessario** (non scaricato). Debolezze minori di
tuning, non di quant: sul caso "da ignorare" risponde blando invece di
`#end_conv`; l'idle comment è poco ancorato al contesto.

### 4. Context size reale

`usage.prompt_tokens` al crescere della finestra di storia (stessi
soul/facts/summary/self_messages):

| Finestra percezioni | prompt_tokens |
|---|---|
| 20 (config esempio) | 1689 |
| 40 | 2166 |
| 80 | 3109 |

A regime con la config reale (finestra 20 + riassunto + self_messages) il
prompt sta a **~1.7–1.8K token**: `-c 4096` basta con ampio margine (>2K per
la generazione). Sotto i ~3.5K non si va mai col default; **serve `-c 8192`
solo se l'operatore alza `recent_chat_window` verso 80+ o con riassunti molto
lunghi** — da annotare nella doc operatore di 05, non serve cambiare default.

### 5. mmproj (dato per l'evoluzione post-MVP, non blocca 05)

Istanza PROPRIA di `llama-server` (b10016) su porta 8090:
`-m Q4_K_XL --mmproj mmproj-F16 -ngl 99 -c 4096 --reasoning off --parallel 1
--no-webui`, con l'istanza testo di translate-lector ancora attiva su 8080.

- **Load**: ok al primo colpo, `-ngl 99`, `/health` 200 in ~4 s. Nessun
  fallback (`-ngl` ridotto / Q2_K_XL) necessario.
- **VRAM**: 1469 → 3877 MiB ⇒ **delta +2408 MiB** (modello ~1.5 GB +
  mmproj F16 940 MB su disco + KV/encoder). Headroom residuo **~217 MiB**:
  due istanze convivono ma al limite — conferma la decisione 02 di puntare,
  post-MVP, a UNA istanza multimodale unica invece di due processi.
- **Modalità**: `/props` → `modalities: {vision: true, video: true,
  audio: true}`.
- **Captioning** (JPEG 1280×720 generato con Pillow, inviato come
  `image_url` data-URI base64): 1ª richiesta **1.26 s** end-to-end
  (286 prompt token, di cui ~256 dell'immagine), 2ª **0.44 s**; caption in
  inglese coerente col contenuto; gen ~75 tok/s. Nessun OOM durante
  l'inferenza (3849 MiB).
- Istanza propria terminata a fine misura (PID proprio; il server di
  translate-lector mai toccato, `/health` 8080 ok a fine spike).

### Cosa cambia per 05

Niente di bloccante. Da riportare in 05: (a) non promettere benefici dal
prompt caching con Gemma iSWA; (b) `-c 4096` ok come default documentato,
`-c 8192` consigliato solo per finestre di storia ≥40; (c) i default di
sampling del server vanno bene per original_chat (nessun `llm_params` da
tradurre oltre al drop di `thinking`).
