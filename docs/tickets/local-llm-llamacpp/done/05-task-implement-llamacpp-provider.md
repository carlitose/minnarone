# 05 — Task: implementare il provider llama.cpp selezionabile da config

## Parent Spec

[local-llm-llamacpp-wayfinder.md](../../specs/local-llm-llamacpp-wayfinder.md)

## Type

task

## Outcome

`llm_provider: llamacpp` (naming da confermare in 02) funziona end-to-end: il
Reactor genera reazioni contro un `llama-server` locale, senza
`OPENROUTER_API_KEY`, rispettando il contratto `LLMProvider`
(`LLMError`/`LLMTimeout` → salta-turno) e il prompt verbatim.

## Acceptance Criteria

- [ ] Nuovo provider (modulo dedicato o generalizzazione di
      `OpenRouterProvider` con `base_url` iniettabile e auth opzionale) che
      implementa `complete(prompt)` contro `/v1/chat/completions` locale.
- [ ] `build_provider` (o factory equivalente) instrada in base a
      `llm_provider`; i provider cloud restano invariati.
- [ ] Config: chiavi nuove (es. `llamacpp.base_url`, modello, timeout) validate
      al `--check` con errori chiari; mapping `llm_params` secondo 03.
- [ ] Nessuna dipendenza runtime nuova (transport urllib come oggi).
- [ ] Unit test con transport fake: successo, 503 in caricamento, timeout,
      risposta malformata, parametri riservati non sovrascrivibili.
- [ ] `--check` passa senza rete; README/docs aggiornati (sezione provider).
- [ ] Meta popolato dove disponibile (token usage llama.cpp), senza rompere la
      dashboard/health che oggi legge i meta OpenRouter.

## Blocked By

- 02 (naming/perimetro), 03 (mapping parametri), 04 (verdetto spike).

## Frontier

È il build ticket finale del percorso testo-solo. L'eventuale migrazione del
VLM a llama.cpp o il lifecycle app-managed sono fuori da questo ticket.

## Work Plan

1. Generalizzare il transport/URL di `openrouter.py` o creare
   `llamacpp.py` accanto (decisione di design piccola, in PR).
2. Estendere `build_provider` + config schema + validazione `--check`.
3. Test unitari (pattern fake-transport già esistente nei test OpenRouter).
4. Prova manuale contro il server locale (riusa il setup di 04).
5. Aggiornare README e wayfinder; chiudere il ticket.

## Evidence to Capture

- Output test suite e `--check`.
- Un run locale reale (o shadow) con il provider nuovo.

## Out of Scope

- Spawn/kill del server (06). Migrazione VLM (spec/ticket separati se deciso
  in 02). Motore di inferenza custom (spec separata).

## Risultati (2026-07-16)

Implementato end-to-end con TDD stretto (RED → GREEN → refactor a verde per
comportamento).

### Cosa è stato implementato

- **`LlamaCppProvider`** (`src/minnarone/llamacpp.py`): specializza
  `OpenRouterProvider` su endpoint locale `{base_url}/v1/chat/completions`,
  header senza Bearer token e body senza `model` (il server serve il solo
  modello caricato); eredita invariati trasporto urllib, timeout client-side,
  parsing risposta, `_extract_meta` e mapping `LLMError`/`LLMTimeout`.
  Prompt passato verbatim (prefisso stabile intatto). `thinking` droppato dai
  params (reasoning spento server-side con `--reasoning off`); gli altri
  `llm_params` (temperature, max_tokens, timeout) passano come per i cloud.
- **Generalizzazione minima di `openrouter.py`**: endpoint (`self._url`) ed
  etichetta errori (`_LABEL`) parametrizzati; comportamento OpenRouter
  invariato (test esistenti verdi senza modifiche).
- **Factory**: `build_provider` instrada `llm_provider: llamacpp` →
  `LlamaCppProvider` (import locale, niente `OPENROUTER_API_KEY`);
  grok/deepseek invariati; messaggio "ammessi" aggiornato.
- **Config**: blocco top-level `llamacpp:` con sola `base_url`
  (default `http://127.0.0.1:8080`), validazione di sola forma al `--check`
  (URL http(s), host, porta esplicita richiesta con errore chiaro in
  italiano), rifiuto campi ignoti (`model` incluso).
- **Health-check all'avvio live** (`check_server_ready`/`ensure_llamacpp_ready`
  con probe iniettabile): `GET /health`, 200 = ok; 503 (modello in
  caricamento) e connection refused producono un errore azionabile che
  include il comando `llama-server -m <modello.gguf> --port <porta> -ngl 99
  -c 4096 --reasoning off --parallel 1`. Cablato in `cli.main` SOLO sul
  percorso live: `--check` resta dry-run senza rete.
- **Meta**: `model` dallo slug della risposta, token usage e `cached_tokens`
  quando presenti; nessun `cost` (llama-server non lo espone, la dashboard
  tollera l'assenza).
- **Docs**: sezione README "LLM locale (llama.cpp)" con config e comando
  server; nuovo esempio minimale `examples/llamacpp-local.example.yaml`
  (valida a `--check` senza rete né modelli extra).

### File toccati

- `src/minnarone/llamacpp.py` (nuovo)
- `src/minnarone/openrouter.py` (generalizzazione `_url`/`_LABEL` + routing factory)
- `src/minnarone/config.py` (`LlamaCppConfig` + wiring in `Config`)
- `src/minnarone/cli.py` (health-check sul percorso live)
- `tests/test_llamacpp_provider.py` (nuovo, 32 test con transport/probe fake)
- `examples/llamacpp-local.example.yaml` (nuovo)
- `README.md` (sezione LLM locale + tabella env + commento provider)

### Esito test/lint

- `pytest` suite unit completa: tutti i test verdi tranne 4 failure
  PRE-ESISTENTI verificate anche sul baseline senza queste modifiche
  (`test_cli_check_fails_for_live_send_without_write_token` — flake da `.env`
  locale nel cwd; due flake di timing audio Twitch su Windows;
  `test_readme_private_commentator_wording_is_not_contradictory` — drift README
  del refresh precedente). I 32 test nuovi e tutti i test OpenRouter/config/cli
  passano (335 passed sulle suite impattate).
- `ruff check src tests`: nessun errore nuovo (35 pre-esistenti su file non
  toccati, invariati rispetto al baseline); i file toccati sono puliti.
- Verifica empirica contro il llama-server reale (gemma-4-E2B-it-qat
  Q4_K_XL): completion ok, meta con `model`/token/`cached_tokens`;
  health-check 200 → il loop parte; porta morta → errore azionabile, exit 1;
  `--check` dell'esempio → exit 0 offline.

## Review + QA (2026-07-16, super-autopilote)

Review a 8 angoli + audit di manutenibilità. Rilievi di correttezza confermati e **corretti**:

1. **base_url con path/query** (config): `http://127.0.0.1:8080/v1` (convenzione client OpenAI) passava `--check` e portava a `/v1/v1/chat/...` e `/v1/health` (404). Ora rifiutato al `--check` con messaggio chiaro. Anche `port == 0` (falsy ma non None) ora rifiutato.
2. **`http.client.HTTPException` non catturata** (llamacpp): una porta che punta a un servizio non-HTTP (`BadStatusLine`, non `OSError` né incapsulata in `URLError`) faceva crashare la CLI con traceback nudo invece dell'errore azionabile. Ora `check_server_ready` cattura `(OSError, http.client.HTTPException)`.
3. **Proxy aziendale + redirect asimmetrico** (llamacpp): la probe usava il default opener (onora `HTTP_PROXY`, segue i 3xx) mentre i completamenti usano `_no_redirect_opener`. Su macchina con proxy configurato e senza `127.0.0.1` in `NO_PROXY`, localhost veniva instradato al proxy. Ora probe **e** completamenti locali passano da un `_local_opener` dedicato (`ProxyHandler({})` + `_NoRedirect`); logica HTTP condivisa via `_open_request` estratto in openrouter.py (zero duplicazione). `HTTPError` della probe ora chiuso (niente socket dangling).
4. **run_session orfano** (cli): il fallimento dell'health-check in `--tui` faceva `return 1` senza `run_session.mark_completed()`, lasciando run "attive" mai potate. Ora marcato come nel percorso `build_agent`.

Pulizia applicata: default `base_url` non più triplicato (`from_dict` → `cls(**data)`). Doc coerenti: docstring `cli.py`, `.env.example`, README (`OPENROUTER_API_KEY` non serve con llamacpp; `model` non si applica a llamacpp).

Rilievi **non** applicati (annotati, non bloccanti per l'MVP): subclassing di `OpenRouterProvider` vs base comune neutro e provider-registry (altitudine — accettabili con 3 provider); duplicazioni nei test (`RecordingTransport`/`_ok_response`/scaffold YAML — funzionanti); `--parallel 1` vs chiamate concorrenti Reactor+Summarizer (latenze misurate in 04 lo rendono non-problema sull'HW target; da rivedere se si usa una GPU molto lenta); fallthrough di `build_provider` con `llm_params.model` su provider sconosciuto (pre-esistente).

**Test**: +3 regressioni (path/query rifiutato, port 0 rifiutato, HTTPException→errore azionabile). Suite llamacpp+openrouter verde; ruff pulito sui file toccati. 3 failure pre-esistenti nel repo (2 flake timing audio Twitch su Windows, 1 drift wording README dal refresh precedente) verificati indipendenti dal diff. Verifica end-to-end ripetuta contro il server reale dopo i fix: health-check OK, completion "ciao", meta popolati.
