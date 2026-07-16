# 03 — Research: contratto llama-server (parametri, caching, errori)

## Parent Spec

[local-llm-llamacpp-wayfinder.md](../../specs/local-llm-llamacpp-wayfinder.md)

## Type

research

## Outcome

Mapping documentato tra il contratto attuale del provider minnarone
(`OpenRouterProvider` + `llm_params`) e `POST /v1/chat/completions` di
`llama-server`: quali parametri passano invariati, quali vanno tradotti o
droppati, come funzionano prompt caching, readiness e gli stati d'errore da
tradurre in `LLMError`/`LLMTimeout`.

## Acceptance Criteria

- [ ] Tabella `llm_params` → llama-server: `temperature`, `max_tokens`,
      `timeout`, `thinking` (OpenRouter/Grok-specific: come si spegne il
      reasoning per Gemma — `--reasoning off` server-side vs campo
      per-richiesta), altri parametri presenti negli esempi YAML del repo.
- [ ] Comportamento del prompt caching di llama.cpp verificato rispetto al
      prefisso stabile del PromptBuilder (`cache_prompt`: default, granularità,
      effetto con `--parallel 1`).
- [ ] Semantica `/health` e `/v1/models` documentata (readiness a modello
      caricato vs socket aperto — cfr. fix ticket-08 di translate-lector).
- [ ] Catalogo errori: 503 in caricamento, timeout, connessione rifiutata,
      risposta malformata → mappa verso `LLMError`/`LLMTimeout` (salta-turno).
- [ ] Differenze note tra risposta llama-server e schema OpenAI usato da
      `_parse_response`/`_extract_meta` (campi `usage`, `cost` assente, ecc.).

## Blocked By

- None — indipendente dall'hardware, può correre in parallelo a 01.

## Frontier

È il contratto che 04 (spike) esercita e 05 implementa; farlo prima evita di
scoprire i mismatch dentro il codice.

## Work Plan

1. Leggere la doc llama.cpp aggiornata (`examples/server/README`) per gli
   endpoint e i parametri correnti della versione che si userà.
2. Confrontare con `openrouter.py` (`_build_request`, `_parse_response`,
   `_extract_meta`) e con gli `llm_params` usati negli `examples/*.yaml`.
3. Riusare le evidenze di translate-lector (`sidecar.rs`, `llm.rs`,
   `docs/specs/` di quel repo) su readiness e porte.
4. Scrivere il mapping nel ticket e linkarlo dal wayfinder.

## Evidence to Capture

- Versione/commit llama.cpp di riferimento.
- Estratti della doc server per ogni parametro mappato.
- Esempio di body richiesta/risposta reale (può arrivare da 04).

## Out of Scope

- Benchmarks (01) e decisioni di policy (02).

---

## Risultati (2026-07-16)

Evidenza raccolta contro un `llama-server` reale (build `b10016-32b741c33`, Gemma 4 E2B, `--parallel 1`, `-c 4096`) su questa macchina.

### Compatibilità con il provider attuale

- **Shape risposta** (`/v1/chat/completions`, non-streaming): chiavi `choices, created, id, model, object, system_fingerprint, timings, usage`. `choices[0].message.content` presente → **`_parse_response` funziona invariato**.
- **Caching nei meta**: `usage.prompt_tokens_details.cached_tokens` è popolato (es. `2350/2370`) — **lo stesso campo che `_extract_meta` legge per OpenRouter**. Nessun campo `cost` (atteso: è gratis/locale); la dashboard deve tollerarne l'assenza (già opzionale).
- **Extra**: llama-server aggiunge `timings` (`prompt_per_second`, `predicted_per_second`) — meta gratuiti utili per la dashboard.

### Mapping `llm_params` → llama-server

| Param minnarone | llama-server | Azione |
|---|---|---|
| `thinking: low` (unico param usato negli examples) | **ignorato silenziosamente** (verificato) | Droppare nel provider locale; il reasoning si spegne **server-side** con `--reasoning off` (pattern D4 translate-lector; `/props` conferma `reasoning_format: none`) |
| `temperature`, `max_tokens`, `top_p`, `top_k`, … | supportati nel body | Pass-through invariato. Default server (da `/props`): temp 1.0, top_k 64, top_p 0.95, min_p 0.05 |
| `timeout` | client-side | Invariato (gestito dal provider, non dal server) |
| `model` | ignorato: un solo modello caricato per istanza | Il provider locale NON deve richiederlo; lo slug diventa informativo |

Parametri sconosciuti nel body **non causano errori** (verificato con `"thinking":"low"` → 200 OK).

### Prompt caching

- `cache_prompt` è **attivo di default** (provato empiricamente: prefisso stabile → ~20 token rivalutati, wall 0.19 s vs 1.17 s a freddo).
- Requisiti: prefisso byte-identico in testa (garantito dal PromptBuilder + pass-through verbatim) e slot singolo (`--parallel 1`). Il contratto attuale è **già compatibile**; nessuna modifica al prompt.

### Readiness ed errori → `LLMError`/`LLMTimeout`

| Condizione | Comportamento server | Mapping provider |
|---|---|---|
| Server giù | connection refused | `LLMError` (transport) → salta-turno |
| Modello in caricamento | `/health` → 503; `chat/completions` → 503 "Loading model" (evidenza ticket-08 translate-lector: `/v1/models` risponde GIÀ 200 → mai usare come readiness) | `LLMError`; readiness = `GET /health` → 200 |
| Richiesta malformata | HTTP 400, body `{"error":{"code":400,"message":"…","type":"invalid_request_error"}}` (verificato) | già coperto: status ≠ 200 → `LLMError` |
| Latenza oltre soglia | — | `LLMTimeout` client-side (invariato) |

### Note per il ticket 05

- Il provider locale è ~`OpenRouterProvider` con: `base_url` configurabile, **niente** header `Authorization`, `model` opzionale, drop di `thinking`. Transport urllib riusabile as-is.
- `system_fingerprint` contiene la build llama.cpp → utile nei meta per diagnosi.

### Criteri di accettazione

- [x] Tabella `llm_params` → llama-server (incluso `thinking`)
- [x] Prompt caching verificato rispetto al prefisso stabile del PromptBuilder
- [x] Semantica `/health` vs `/v1/models` documentata
- [x] Catalogo errori con mapping `LLMError`/`LLMTimeout`
- [x] Differenze di shape risposta vs schema OpenAI documentate (`cost` assente, `timings` extra, `cached_tokens` identico)
