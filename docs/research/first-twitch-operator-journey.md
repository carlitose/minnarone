# Primo percorso operatore Twitch reale

## Domanda di ricerca

Quali gap repository-backed incontra un primo operatore Twitch dal discovery
alla promozione live, e quale ticket o decisione esplicita deve possedere ogni
gap prima del rilascio pubblico?

## Risposta

La sessione AiRwayTV dimostra che il runtime multimodale e i gate shadow/live
funzionano, ma non dimostra ancora un onboarding ripetibile da clone pulito. I
blocchi da risolvere prima del pubblico sono di priorità **P1**: percorso
task-first e intervista persona, acquisizione/configurazione portabile dei
modelli, e allineamento fra smoke, guida, examples e runtime. Nell'ambito
tecnico di questo inventario non emerge un P0 autonomo; la decisione di safety
pubblica resta al [ticket 14](../tickets/public-release/done/14-research-public-twitch-safety.md).

La progressione osservata resta la golden path corretta: chat-only, smoke raw
audio/video, ASR/VAD/speaker/VLM, shadow, config `live` separata, doppio `p` in
TUI; `k` riporta subito in shadow. I gap sotto non richiedono di indebolire
questi gate.

## Matrice del percorso e delle evidenze

Legenda: **P1** = fix prima del pubblico; **D** = comportamento intenzionale da
conservare/documentare. Non sono emersi gap da rinviare come semplice follow-up
P2.

| Fase | Osservazione o gap | Evidenza primaria | Severità / owner | Decisione e assegnazione |
| --- | --- | --- | --- | --- |
| Discovery | Il README porta prima a un indice documentale e a una reference di installazione/configurazione; non offre ancora i due risultati progressivi chat-only e multimodale. | Sezioni `Documentation` e `Running the reference app` del [README](../../README.md); il frontier del [ticket 17](../tickets/public-release/17-task-readme-skill-catalog-onboarding.md) registra esplicitamente il carattere reference-first. | **P1** — docs/skill | Confrontare le superfici nel [ticket 16](../tickets/public-release/done/16-prototype-agent-and-human-onboarding.md), poi rendere README/AGENTS task-first nel ticket 17. |
| `.env` — CLI principale | Il contratto corrente è coerente: prima `.env` accanto al config, poi cwd, senza sovrascrivere l'ambiente. | [`README.md`](../../README.md), sezione `Secrets via .env`; `_load_env_files()` e `load_dotenv_file()` in [`src/minnarone/cli.py`](../../src/minnarone/cli.py); template [`.env.example`](../../.env.example). | **D** — CLI/docs | Conservare precedenza e redazione dei valori. Il ticket 18 deve portare lo smoke allo stesso contratto o documentare/testare esplicitamente la differenza. |
| `.env` — smoke | `minnarone-twitch-smoke` è un entry point separato e legge direttamente `os.environ`; non chiama il loader dotenv della CLI. Con le due variabili Twitch rimosse dall'ambiente, fallisce anche se il cwd contiene `.env`. | Entry point in [`pyproject.toml`](../../pyproject.toml); `main()` e `_missing_twitch_env()` in [`src/minnarone/twitch_smoke.py`](../../src/minnarone/twitch_smoke.py); comando di verifica sotto, exit `2`. | **P1** — runtime/CLI | [Ticket 18](../tickets/public-release/done/18-task-fix-operator-journey-drift.md): strategia dotenv condivisa oppure differenza esplicita e coperta da test. |
| Modello LLM | Default, examples e parametri possono divergere senza un contratto verificato: il codice fissa `x-ai/grok-4.3`, README/examples inviano `thinking: low` verbatim, mentre la config finale della sessione ha richiesto override del modello e `reasoning_effort`. La prima config locale conservava Grok 4.3 + `thinking`; il passaggio manuale dimostra drift, non una migrazione supportata. | `_DEFAULT_MODELS`, pass-through di `_params` e `build_provider()` in [`src/minnarone/openrouter.py`](../../src/minnarone/openrouter.py); `llm_params.thinking` in [README](../../README.md) ed [`examples/twitch.example.yaml`](../../examples/twitch.example.yaml); forma sanitizzata degli artifact locali gitignored `.local/twitch-commentator.local.yaml` e `.local/<channel>-shadow.yaml`. | **P1** — config/runtime/docs | [Ticket 18](../tickets/public-release/done/18-task-fix-operator-journey-drift.md): decidere slug/default/override e policy `thinking` vs `reasoning_effort`, poi coprirla con test. |
| `soul` / `facts` / prompt | I confini runtime sono distinti, ma la prima bozza della sessione ha trasformato inferenze in persona prima dell'intervista. `soul` e tutti i file di `facts_dir` sono memoria permanente; i prompt sono template comportamentali fail-fast separati. | `FileMemory` in [`src/minnarone/memory.py`](../../src/minnarone/memory.py); prefisso stabile in [`src/minnarone/prompt.py`](../../src/minnarone/prompt.py); contratto override/validazione in [`src/minnarone/prompt_source.py`](../../src/minnarone/prompt_source.py); decisione e scenario nel [ticket 13](../tickets/public-release/done/13-grilling-persona-facts-onboarding.md). | **P1** — skill/docs; decisione già presa | Applicare il gate di conferma del ticket 13 nel prototipo 16 e documentarlo nel ticket 17. Nessun cambio ai prompt default o al runtime è richiesto da questo gap. |
| Config commentator | La sezione `Full Commentator Run Workflow` usa ancora `commentator.enabled` e `idle_interval` piatti, mentre README, example e schema corrente richiedono `commentator.profiles.<style>`. La prima config locale ha inoltre aggiunto un campo `style` piatto nel tentativo di seguire quella forma stantia. | Blocco YAML nella [guida operatore](../twitch-operator.md), sezione `Full Commentator Run Workflow`; forma sanitizzata della prima config locale; contratto corrente nel [README](../../README.md) e in [`examples/twitch-commentator.example.yaml`](../../examples/twitch-commentator.example.yaml). | **P1** — docs | [Ticket 18](../tickets/public-release/done/18-task-fix-operator-journey-drift.md): sostituire lo schema stantio e aggiungere test docs mirato. |
| Installazione media e modelli | Gli extra installano runtime Python, non i pesi. Gli example lasciano `speaker_embedding.model_path` e `vlm.model` a `null`; la prova completa ha funzionato riusando tre path assoluti personali già presenti per ASR, speaker ONNX e Qwen2-VL. È prova del runtime, non della ripetibilità. | Extra `audio`, `video`, `vlm` in [`pyproject.toml`](../../pyproject.toml); commenti e valori `null` in [`examples/twitch.example.yaml`](../../examples/twitch.example.yaml); placeholder `/path/to/...` nella [guida operatore](../twitch-operator.md); ispezione sanitizzata di `.local/<channel>-shadow.yaml` (nessun valore di path riportato); regole di esclusione [`.gitignore`](../../.gitignore). | **P1** — docs/config/skill | [Ticket 15](../tickets/public-release/done/15-research-runtime-model-profiles.md) definisce profili, acquisizione e path portabili; ticket 16 prova la superficie; ticket 17 pubblica il golden path. |
| Smoke media | Lo smoke della sessione ha catturato media validi ma una chat quieta ha forzato exit non-zero: `chat=0`, `audio=31`, `vad=5`, `video=6`, `failures=[]`. `_smoke_failures()` considera zero chat un errore indipendentemente dal successo degli altri canali. | Artifact session-only `.smoke/<channel>-full/stats.json`, riassunto sotto; `_smoke_failures()` e `main()` in [`src/minnarone/twitch_smoke.py`](../../src/minnarone/twitch_smoke.py); test correnti in [`tests/test_twitch_smoke.py`](../../tests/test_twitch_smoke.py). | **P1** — runtime | [Ticket 18](../tickets/public-release/done/18-task-fix-operator-journey-drift.md): distinguere un canale quieto da un guasto media, lasciando un eventuale comportamento strict come opzione esplicita. |
| Shadow | Guida ed example dichiarano che il write token serve anche in shadow, ma runtime e test richiedono `TWITCH_SEND_OAUTH_TOKEN` solo per `live`; shadow non costruisce il sender. | `Public Chat Send` / `Write Token` nella [guida operatore](../twitch-operator.md); commento iniziale di [`examples/twitch.example.yaml`](../../examples/twitch.example.yaml); gate in [`src/minnarone/app.py`](../../src/minnarone/app.py); `test_cli_check_passes_for_shadow_send_without_write_token` in [`tests/test_cli.py`](../../tests/test_cli.py) e parametrizzazione off/shadow in [`tests/test_config.py`](../../tests/test_config.py). | **P1** — docs/examples | [Ticket 18](../tickets/public-release/done/18-task-fix-operator-journey-drift.md): documentare token di scrittura richiesto per `live`, non per shadow, senza cambiare il gate runtime. |
| Promozione live | Config `live`, allow-list, write token, avvio in shadow, doppio `p` e `k` sono gate coerenti e deliberati. | Validazione allow-list in [`src/minnarone/config.py`](../../src/minnarone/config.py); token/sender solo live in [`src/minnarone/app.py`](../../src/minnarone/app.py); binding e conferma in [`src/minnarone/dashboard_tui.py`](../../src/minnarone/dashboard_tui.py); transizioni in [`tests/test_tui_transitions.py`](../../tests/test_tui_transitions.py); procedura nella [guida operatore](../twitch-operator.md). | **D** — runtime/safety/docs | Conservare il comportamento. Il ticket 14 decide policy/guardrail pubblici; il ticket 17 espone il golden path attended-only dopo gli allineamenti del ticket 18. |

## Comandi e artifact verificati

Una ricostruzione plausibile del comando usato per lo smoke completo è:

```bash
uv run minnarone-twitch-smoke \
  --channel example-channel \
  --duration 30 \
  --output .smoke/example-channel-full \
  --quality 720p60 \
  --audio --video --vad-diagnostic \
  --video-fps 0.2
```

L'invocazione originale e i parametri non sono memorizzati nell'artifact;
questa ricostruzione deriva dalle note della sessione ed è coerente con i
conteggi registrati. `stats.json` contiene:

```text
chat_events=0
audio_events=31
audio_samples_saved=3
vad_utterances=5
video_events=6
video_frames_saved=3
failures=[]
```

Il contrasto dotenv è stato riprodotto senza rete con:

```bash
rtk proxy env -u TWITCH_BOT_USERNAME -u TWITCH_OAUTH_TOKEN \
  uv run minnarone-twitch-smoke \
  --channel example --duration 0.1 \
  --output /tmp/minnarone-ticket-12-smoke-env-check
```

Risultato: exit `2`, `credenziali Twitch mancanti`, nonostante un `.env` nel
cwd. Il comando termina prima di aprire una connessione.

Gli artifact `.local/` e `.smoke/` sono gitignored. Sono stati usati solo come
fonti della sessione e qui se ne pubblicano forma e conteggi, mai credenziali,
contenuti raw o valori di path personali.

## Evidenza consolidata

- Repository: README, guida, examples, schema, runtime e test citati riga per
  riga nella matrice.
- Sessione: forma sanitizzata delle due config locali e conteggi di
  `.smoke/<channel>-full/stats.json`.
- Comando: smoke con ambiente Twitch esplicitamente rimosso, che dimostra la
  differenza rispetto al loader dotenv della CLI principale.
- Decisioni: contratto persona/facts del ticket 13 e gate live già coperti dai
  test TUI.

## Unknowns

- L'invocazione originale dello smoke non è persistita; il comando sopra è una
  ricostruzione dichiarata, non un transcript.
- Slug/provider parameter correnti e supportati (`thinking` oppure
  `reasoning_effort`) vanno verificati e fissati nel ticket 18.
- Fonti, licenze, pinning, dimensioni e hardware dei modelli restano ricerca del
  ticket 15.
- Autorizzazione, disclosure, account bot e retention pubblica restano decisione
  del ticket 14.

## Next Step

Il report sblocca i ticket 15 e 17 come input; 18 deve assorbire i gap di drift.
Per il fold nel parent spec usare esattamente:

- **Ticket 12 — primo percorso operatore Twitch inventariato** (2026-07-18):
  la sessione AiRwayTV conferma la golden path progressiva chat-only → smoke
  media → modelli → shadow → config live separata → doppio `p`, con `k` come
  kill-switch; non dimostra ancora onboarding ripetibile da clone pulito.
- **Priorità risultante dal ticket 12**: P1 prima del pubblico per drift
  runtime/docs (`commentator.enabled`, token shadow, dotenv smoke, chat quieta,
  Grok 4.3/`thinking`) nel ticket 18 e per profili/acquisizione/path modelli nel
  ticket 15; intervista persona e golden path passano dai ticket 13, 16 e 17.
  I gate shadow/live sono intenzionali e restano soggetti alla decisione safety
  del ticket 14.
