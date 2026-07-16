# LLM locale via llama.cpp (Gemma) per il provider di reazione

## Type

Wayfinding spec

## Status

Active — MVP costruito (ticket 05 chiuso il 2026-07-16): l'evoluzione
multimodale (VLM su llama.cpp) è la prossima mappa, da aprire come spec
separata.

## Destination

Poter far girare il LLM di reazione di minnarone **in locale** (modello Gemma in
formato GGUF servito da `llama-server` di llama.cpp), selezionabile da config
(es. `llm_provider: llamacpp`), senza `OPENROUTER_API_KEY`. Il riferimento
architetturale è `../translate-lector`, che già gestisce `llama-server` con
endpoint OpenAI-compatibile. La soluzione deve convivere con il captioner VLM
(Qwen2-VL via torch) **sulla stessa GPU** senza esaurire la VRAM.

## Decisions So Far

Evidenza raccolta leggendo il codice (nessuna decisione di prodotto ancora presa):

- **Punto di aggancio pulito in minnarone**: `LLMProvider` è una ABC con un solo
  metodo `complete(prompt) -> LLMResult` (`src/minnarone/llm.py:33`). L'unica
  implementazione reale è `OpenRouterProvider` (`src/minnarone/openrouter.py:128`),
  già OpenAI-Chat-Completions-compatibile con transport iniettabile (urllib,
  zero dipendenze). La whitelist provider vive in `build_provider`
  (`openrouter.py:253`, `_DEFAULT_MODELS = {grok, deepseek}`); il wiring è in
  `app.py:805`. Un provider locale è quindi una variante con `base_url` locale
  e senza Bearer token — il grosso del codice HTTP/parsing è riusabile.
- **Config**: `llm_provider` è una stringa libera validata solo come non-vuota
  (`config.py:804`); i valori ammessi sono decisi da `build_provider`. Aggiungere
  un valore nuovo non tocca lo schema.
- **Contratto errori**: gli errori provider sono eccezioni (`LLMError`/`LLMTimeout`)
  che il Reactor traduce in salta-turno (EC03). Il provider locale deve rispettare
  lo stesso contratto (mai risultati parziali).
- **Caching del prompt**: il PromptBuilder garantisce un prefisso stabile
  byte-identico e il provider passa il prompt verbatim. Va preservato anche col
  provider locale (llama.cpp ha il proprio prompt caching).
- **Pattern di riferimento translate-lector** (`../translate-lector/src-tauri/src/sidecar.rs`):
  - `llama-server` espone `POST /v1/chat/completions` OpenAI-compatibile su
    `http://127.0.0.1:<porta>`.
  - Spawn **on-demand** alla prima richiesta, kill deterministico all'uscita,
    PID file + reap all'avvio per gli orfani da crash; su Windows Job Object
    con `KILL_ON_JOB_CLOSE` (crate `command-group`).
  - Readiness via `GET /health` → 200 solo a **modello caricato** (non basta il
    socket: `/v1/models` risponde mentre `chat/completions` dà ancora 503).
  - Argomenti pinnati: `-m <model> --port <p> -ngl 99 -c <ctx> --reasoning off
    --parallel 1`.
  - Distinzione tra provider **app-managed** (llamaserver con `binary_path`) e
    provider locali lanciati dall'utente (Ollama/LM Studio: mai spawnati
    dall'app).
- **Conflitto GPU noto** (sollevato dall'utente): `vlm.py` carica Qwen2-VL via
  transformers/torch con `device: auto` (→ CUDA se disponibile), mentre il
  pattern translate-lector usa `-ngl 99` (offload totale). Sulla stessa GPU i
  due contendono la VRAM: serve una policy esplicita prima di implementare.
- **[Ticket 01, 2026-07-16] Hardware e modello verificati**: GPU = RTX 500 Ada
  Laptop, **4 GB VRAM** (non gli 8 GB assunti dal brief translate-lector).
  "Gemma 4" esiste (aprile 2026, Apache 2.0, multimodale via `--mmproj`,
  supporto llama.cpp ufficiale). **Misurato live** su questa macchina:
  `gemma-4-E2B-it-qat-UD-Q4_K_XL` occupa ~1.5 GB VRAM @4K ctx, genera a
  ~75 tok/s, e col prefisso in cache risponde in **0.2 s** (1.2 s a freddo su
  2372 token). E4B+ non stanno in 4 GB. **Qwen2-VL via torch NON coesiste** in
  modo affidabile (fp16 non sta nemmeno da solo; int4 marginale): le vie
  realistiche sono un solo server multimodale (mmproj), VLM su CPU, o solo
  testo. Dettagli: `docs/tickets/local-llm-llamacpp/done/01-…`.
- **[Ticket 03, 2026-07-16] Contratto llama-server compatibile**: shape
  risposta OpenAI-compatibile (`_parse_response` invariato),
  `usage.prompt_tokens_details.cached_tokens` popolato (stesso campo di
  OpenRouter → `_extract_meta` invariato), `cache_prompt` attivo di default e
  il prefisso stabile del PromptBuilder viene riusato (~20 token rivalutati).
  `thinking: low` è ignorato senza errori → si droppa e si usa `--reasoning
  off` server-side. Readiness solo via `/health` (mai `/v1/models`). Errori →
  `LLMError`/`LLMTimeout` già coperti. Dettagli:
  `docs/tickets/local-llm-llamacpp/done/03-…`.
- **[Ticket 04, 2026-07-16] Spike col prompt reale: verdetto positivo su tutta
  la linea.** Prompt vero del PromptBuilder (profilo original_chat, storia da
  run reale, finestra 20) = **~1.7K token**; 1ª richiesta fredda 1.07 s,
  turni successivi 0.3–1.1 s, generazione ~65–75 tok/s → **1–2 ordini di
  grandezza sotto il timeout 30 s**, cadenza Reactor ok. Il contratto di 03
  regge senza modifiche.
  - **Qualità quant QAT: OK** — 6/6 trigger con formato `RE:`/`MSG:`
    rispettato, italiano naturale e in-character, nessun output rotto. Il
    fallback su E2B Q4_K_XL non-QAT NON serve.
  - **Ctx reale: `-c 4096` basta** — a regime (finestra 20 + riassunto +
    self_messages) il prompt sta a ~1.7–1.8K token; finestra 40 → 2.2K,
    80 → 3.1K. `-c 8192` solo se l'operatore alza `recent_chat_window` a 80+.
  - **Limite iSWA sul prompt caching** (misurato): con Gemma (n_swa 512) la
    cache è riusata solo se la divergenza sta negli ultimi ~400–450 token;
    appena la finestra di storia scorre si rivaluta tutto (~0.8–1.1 s a 1.7K
    token, comunque trascurabile). In 05 non contare sul caching; eventuale
    `--swa-full` è una scelta operatore.
  - **mmproj misurato** (dato per l'evoluzione post-MVP): istanza propria
    Q4_K_XL + `mmproj-F16` con `-ngl 99 -c 4096` carica in ~4 s, **+2408 MiB
    VRAM**; con l'istanza testo di translate-lector attiva restano ~217 MiB
    liberi (convivenza possibile ma al limite → conferma la via "istanza
    multimodale unica"). `/props` → `vision: true`; captioning JPEG 720p:
    1.26 s a freddo, 0.44 s a caldo (~256 token immagine).
  Dettagli: `docs/tickets/local-llm-llamacpp/done/04-…`.

## Not Yet Specified

Nessuna incognita bloccante per il ticket 05: le voci precedenti sono state
risolte da 01/03/04 (vedi `Decisions So Far`) e dal grilling 02 (lifecycle →
utente avvia a mano; motore custom → archiviato; mapping `llm_params` →
ticket 03). Resta aperta, per la mappa FUTURA di migrazione del VLM, la scelta
tra istanza multimodale unica e istanze separate (i numeri di 04 escludono la
coesistenza di due istanze su 4 GB).

## Out of Scope

- Bundling dei binari llama.cpp nel repo o download automatico dei modelli.
- Cambiare il contratto del prompt (PromptBuilder) o il protocollo dei profili
  commentatore.
- Refactor dei provider cloud oltre al minimo per introdurre la factory.
- Supporto multi-GPU o inference distribuita.

## Frontier / Blocking Edges

Mappa completata (MVP): nessun edge aperto. Il ticket 05 è chiuso
(`docs/tickets/local-llm-llamacpp/done/05-…`); la migrazione multimodale del
VLM (istanza unica E2B + `--mmproj`) è la prossima mappa, fuori da questa spec.

## Decisioni del grilling (2026-07-16, ticket 02)

1. **MVP solo testo**: in locale il canale video resta spento; l'evoluzione
   designata è il server multimodale unico (E2B + `--mmproj` al posto di
   `vlm.py`), decisa dai numeri di 04.
2. **Lifecycle**: server avviato a mano dall'utente; minnarone fa solo
   health-check su `/health` con errore chiaro. Ticket 06 non attivato.
3. **Motore di inferenza da zero**: archiviato; si riapre solo se llama.cpp
   diventa un limite reale. Interesse didattico → spec separata.
4. **Config**: `llm_provider: llamacpp` + blocco `llamacpp:` con `base_url`
   (default `http://127.0.0.1:8080`); niente `model` in config.

## Ticket Plan

| # | Tipo | Titolo | Stato |
|---|------|--------|-------|
| 01 | research | Hardware, modello Gemma e budget VRAM | ✅ done (2026-07-16) |
| 03 | research | Contratto llama-server: parametri, caching, errori | ✅ done (2026-07-16) |
| 02 | grilling | Decisioni: lifecycle server, policy GPU, futuro del VLM | ✅ done (2026-07-16) |
| 04 | prototype | Spike: prompt reale minnarone → llama-server nello scenario deciso | ✅ done (2026-07-16) |
| 05 | task | Implementare `LlamaCppProvider` + config + test | ✅ done (2026-07-16) |
| 06 | task (condizionale) | Lifecycle app-managed del server | NON attivato (decisione 02) |

## Next Review

Dopo 05: valutare se aprire la mappa di migrazione del VLM (istanza
multimodale unica E2B + mmproj: i numeri di 04 — +2408 MiB VRAM, captioning
0.4–1.3 s — dicono che è fattibile ma NON in coesistenza con una seconda
istanza testo sulla stessa GPU da 4 GB).
