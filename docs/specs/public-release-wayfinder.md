# Passaggio del repo a pubblico

## Type

Wayfinding spec

## Status

Active

## Destination

Il repository `minnarone` è pubblico su GitHub, con licenza chiara (MIT), nessun
segreto o contenuto sensibile nei file tracciati né nella history, e un percorso
operativo verificato per due pubblici:

1. una persona può passare dal clone a una prova Twitch `shadow` chat-only e,
   opzionalmente, alla pipeline audio/video completa senza dipendere dallo stato
   nascosto della macchina dell'autore;
2. un code agent trova confini, comandi, architettura, workflow prompt e criteri
   di sicurezza sufficienti per contribuire senza inventare persona, facts o
   configurazione.

Il README resta la landing page, ma porta rapidamente a golden path brevi e
progressivi invece di chiedere al nuovo utente di ricostruire il flusso da una
guida operatore molto lunga.

## Decisions So Far

- **Licenza MIT** — decisa dall'utente (sessione 2026-07-17). `LICENSE` creato e
  `pyproject.toml` aggiornato (`license = { text = "MIT" }`) sulla branch
  `chore/public-release-prep` (non ancora committato/mergiato).
- **Docs interni restano** — issue/ticket/prds/specs/adrs in `docs/` (96+ file)
  si pubblicano così come sono: mostrano il processo di sviluppo, nessun
  problema di sicurezza rilevato. Decisione utente.
- **Rimuovere solo la skill personale** — `.agents/skills/project-designer/SKILL.md`
  è tracciata per errore e va tolta dal repo. Decisione utente.
- **README verificato accurato** (sessione 2026-07-17): flag CLI (`--check`,
  `--tui`, `--replay`), extra pip, script console, link a docs/examples — tutto
  combacia col codice su `main` (la feature branch llamacpp è mergiata, diff
  contenuti vuoto).
- **Nessun segreto nella history**: `.env` mai committato (verificato con
  `git log --all -- .env`); grep di pattern segreti sui file tracciati trova
  solo placeholder (`oauth:dry_run`). Solo `.env.example` (template vuoto) è
  tracciato.
- **Screenshot: si tengono tutti** (grilling 02, 2026-07-17). Revisione
  assistita dei 10 PNG: nessun segreto/credenziale visibile; contengono volti
  (enkk) e username Twitch di terzi già pubblici nel video di origine. Il
  "match binario" del grep era un falso positivo (pagina OpenRouter). Uso
  documentale con credito prominente nel README.
- **Enkk non è stato interpellato: rischio accettato** (grilling 02,
  2026-07-17). Assunzione registrata: il video di origine è pubblico, il
  credito è prominente nel README, l'idea è generalizzata in codice originale.
  Se enkk dovesse obiettare dopo il flip, si rimuove il materiale su richiesta.
- **README pubblico in inglese + README.it.md** (grilling 03, 2026-07-17):
  README principale tradotto in inglese per il pubblico globale, versione
  italiana conservata come `README.it.md` con link incrociati. → ticket 08.
- **Pre-flight sicurezza pulito** (ticket 04, 2026-07-17): gitleaks 8.30.1 su
  tutta la history (`git --log-opts=--all`) → **"no leaks found"**, 96 commit,
  3.11 MB scansionati. Review `git ls-files`: nessun `.log`/`.env`/`.key`/dump
  tracciato (solo `.env.example`). Rimosso `skills-lock.json` (artefatto orfano
  di Claude Code che puntava alla skill `project-designer` già rimossa nel
  ticket 01) e aggiunto a `.gitignore`.
- **Extra utente (2026-07-17)**: hero image dalla copertina del video di enkk
  (`docs/source/minnarone-cover.jpg`) in cima ai due README; sezione "offrimi
  un caffè" con link PayPal (`https://paypal.me/CarloSergi`). Entrambi committati
  sulla branch/PR del ticket 08.
- **Prep pubblicazione 01–04, 06–08 completata** (2026-07-17): licenza e pulizia,
  review screenshot, decisione lingua, secret scan history, suite verde,
  fresh-install e README bilingue risultano chiusi nei ticket sotto `done/`.
  Il ticket 05 (flip) resta intenzionalmente aperto.
- **Progressive enablement, shadow-first** (sessione operatore reale
  2026-07-18): il percorso affidabile è chat-only → raw audio/video smoke →
  ASR/VAD/speaker/VLM → shadow → config `live` separata → promozione TUI con
  doppio `p`; `k` torna immediatamente in shadow. Saltare direttamente alla
  configurazione completa nasconde troppi punti di guasto.
- **`soul`, `facts` e prompt template sono confini diversi** (sessione
  2026-07-18): `soul.md` è identità/opinioni/stile, `facts/*.md` è conoscenza del
  canale/sessione, `src/minnarone/prompts/*.md` è il contratto comportamentale e
  di formato byte-stabile. Un assistente non deve dedurre e scrivere identità o
  descrizioni del canale senza un checkpoint umano; nella prova reale è stato
  necessario correggere una persona inventata.
- **La personalizzazione sicura resta locale**: la prova reale ha usato
  config, soul e facts sotto `.local/` (gitignored) e artifact sotto `.smoke/`.
  I default prompt impacchettati sono rimasti invariati.
- **Pipeline completa provata su una live reale** (2026-07-18): Streamlink ha
  reso disponibili più profili di qualità; uno smoke conservativo ha prodotto
  31 chunk audio, 5 utterance VAD e 6 frame video senza failure media. La chat
  quieta (0 eventi) ha però reso l'intero smoke non-zero: utile evidenza di una
  semantica di successo troppo rigida.
- **Setup completo ancora dipendente dalla macchina**: la prova ha riusato
  modelli locali già presenti (faster-whisper, speaker ONNX, Qwen2-VL) e path
  assoluti personali. Questo dimostra il runtime, non un onboarding ripetibile
  per un visitatore esterno.
- **Priorità skill chiarita dall'utente (2026-07-18)**: il bisogno non è creare
  altri file di prompt, ma offrire più skill repo-local per i code agent. Prima
  si rinomina la skill generica `prompts`; solo dopo si definisce e documenta
  il catalogo completo nei README.
- **Stato skill corrente**: il solo pacchetto skill realmente versionato è
  `.agents/skills/minnarone-prompts/`, esposto a Claude Code dal symlink
  `.claude/skills/minnarone-prompts`. Il README cita solo questa skill. Il
  vecchio alias `prompts` e il symlink personale rotto `project-designer` sono
  stati rimossi.
- **Nome skill prompt confermato dall'utente (2026-07-18)**:
  `minnarone-prompts` ha sostituito il nome generico `prompts` nel ticket 11.
- **Migrazione skill confermata dall'utente (2026-07-18)**: rename netto
  applicato, senza alias `prompts`; rimosso anche il symlink personale rotto
  `.claude/skills/project-designer`.
- **Catalogo skill confermato dall'utente (ticket 10, 2026-07-18)**:
  `minnarone-prompts` gestisce prompt-set; `minnarone-twitch-onboarding` guida
  intervista soul/facts, config e shadow/live; `minnarone-runtime-doctor`
  verifica dipendenze, modelli e smoke. I confini di dettaglio saranno provati
  nel ticket 16, ma i nomi sono stabili.
- **Contratto onboarding soul/facts confermato (ticket 13, 2026-07-18)**: hard
  gate prima della scrittura; preview Markdown esatta con origine dei dati;
  diff minimo per file esistenti; default sotto `.local/<canale>/`; soul e facts
  separati dai prompt template; metadata solo verificabili; eventuale
  `## Contesto corrente` persistente solo con opt-in e revisione alla live
  successiva; validazione automatica senza avvio runtime. Nessuna modifica al
  runtime, limite dimensionale o guardrail segreti aggiuntivo.
- **Ticket 12 — primo percorso operatore Twitch inventariato** (2026-07-18):
  la sessione reale conferma la golden path progressiva chat-only → smoke
  media → modelli → shadow → config live separata → doppio `p`, con `k` come
  kill-switch; non dimostra ancora onboarding ripetibile da clone pulito.
- **Priorità risultante dal ticket 12**: P1 prima del pubblico per drift
  runtime/docs (`commentator.enabled`, token shadow, dotenv smoke, chat quieta,
  Grok 4.3/`thinking`) nel ticket 18 e per profili/acquisizione/path modelli nel
  ticket 15; intervista persona e golden path passano dai ticket 13, 16 e 17.
  I gate shadow/live sono intenzionali e restano soggetti alla decisione safety
  del ticket 14.
- **Policy Twitch pubblica verificata (ticket 14, 2026-07-18)**: il primo
  golden path può restare IRC e shadow-first. IRC richiede User Access Token
  `chat:read`/`chat:edit` e `NICK` uguale al login dell'account autorizzante; il
  Chat Bot Badge richiederebbe invece Send Chat Message API, App Access Token,
  `user:write:chat`, `user:bot` e `channel:bot` (o stato moderatore); il bot non
  può essere il broadcaster del canale. I budget
  Minnarone `1/min` e `20/ora` restano scelte conservative sotto i limiti
  ufficiali.
- **Disclosure resta operator choice, con floor anti-inganno (ticket 14,
  2026-07-18)**: Twitch non impone un annuncio AI per messaggio, ma vieta
  bot/pratiche ingannevoli e richiede identità/scopo comprensibili. Il percorso
  pubblico `ORIGINAL_CHAT` ignora oggi `announce_ai` e forza non-disclosure; il
  golden path non deve descrivere il flag come efficace finché il gap non è
  corretto o documentato.
- **Token e retention non sono ancora production-safe (ticket 14,
  2026-07-18)**: Twitch richiede validazione token all'avvio e ogni ora e
  cancellazione/opt-out dei log chat conservati solo finché necessari. Il
  runtime controlla solo token non vuoti e `retention.perceptions_days` è
  inerte; tutorial e onboarding devono mostrare artifact/cancellazione manuale
  e fallire verso shadow/stop su credenziali invalide.
- **Permesso broadcaster obbligatorio per il live pubblico (ticket 14,
  2026-07-18)**: Minnarone usa un account bot dedicato e non coincide con
  l'installed chatbot che opera tramite l'account del broadcaster. Poiché l'IRC
  non esprime il grant per-canale richiesto dal modello cloud chatbot, il golden
  path richiede consenso out-of-band registrato prima del live; allow-list e
  token del bot non bastano. Senza consenso il percorso termina a shadow.
- **Ticket 15 — profili runtime definiti** (2026-07-18): sei profili
  progressivi separano chat-only, capture, CPU audio, Apple Silicon, CUDA e
  llama.cpp; ogni profilo dichiara extra, tool, modelli, budget e smoke.
- **Modelli ripetibili (ticket 15)**: ASR, CAM++ English 512, Qwen2-VL-2B e
  GGUF/mmproj hanno owner, licenza, revision e SHA-256; il vecchio CAM++ zh-cn
  192 non è più raccomandato per italiano. Il ticket 16 proverà docs + manifest
  + `minnarone-runtime-doctor`, senza download multi-GB impliciti.

## Evidence: First Real Twitch Operator Journey (2026-07-18)

- Il primo problema dell'utente è stato capire **che progetto fosse e come
  avviarlo**, non installare Python: il README contiene le risposte ma non offre
  una corsia task-first abbastanza visibile.
- `.env.example` → `.env` è semplice; la CLI principale carica `.env`, mentre
  `minnarone-twitch-smoke` richiede oggi variabili già esportate. La differenza
  non è evidente dal quickstart.
- Il default `llm_provider: grok` risolve ancora a `x-ai/grok-4.3`; la sessione
  ha richiesto `llm_params.model: x-ai/grok-4.5` e `reasoning_effort: low`.
  Gli example usano ancora `thinking: low`.
- La guida operatore contiene almeno due drift osservabili: usa ancora
  `commentator.enabled` in un esempio e afferma che anche `shadow` richiede
  `TWITCH_SEND_OAUTH_TOKEN`, mentre il runtime costruisce/legge il sender solo
  per `live`.
- L'assistente ha confuso inizialmente personalizzazione con generazione libera:
  ha scritto una bozza di soul/facts prima di intervistare l'operatore. Il
  prodotto/documentazione deve rendere il checkpoint esplicito, non affidarlo
  alla disciplina conversazionale del singolo agent.
- Shadow/live è tecnicamente ben protetto ma poco scopribile: `mode: live` arma
  soltanto; la sessione parte in shadow, doppio `p` promuove, `k` disarma. Una
  config live separata si è dimostrata più sicura di modificare quella shadow.

## Not Yet Specified

- Se l'onboarding pubblico debba restare docs/templates oppure includere un
  comando guidato (`minnarone init`/`doctor`) che crea config + soul + facts e
  verifica credenziali, dipendenze e modelli.
- Quale modello OpenRouter sia il default pubblico e come validare parametri
  model-specific (`thinking` vs `reasoning_effort`) senza inseguire slug
  hard-coded obsoleti.
- Set minimo di documenti per contributori e code agent (`AGENTS.md`,
  `CONTRIBUTING.md`, `SECURITY.md`, architettura rapida) prima del flip.

## Out of Scope

- Traduzione completa della documentazione operativa (`docs/*.md`) in inglese.
- Pulizia o riscrittura dei docs interni (issue/ticket/prds) — restano com'è.
- CI avanzata, benchmark multi-hardware e supporto garantito per ogni
  combinazione GPU/OS.
- Riscrittura della history git (i commit con email personale dell'autore sono
  accettati come normali).
- Auto-download immediato dei modelli multi-GB prima che profili, licenze,
  checksum e budget disco siano decisi.
- Modificare i nove prompt default byte-stabili solo per rendere più facile il
  quickstart: l'onboarding deve usare override/soul/facts, non indebolire il
  contratto impacchettato.
- Avviare o promuovere automaticamente un bot `live`; il passaggio resta
  attended-only e richiede un gesto umano esplicito.

## Frontier / Blocking Edges

- **Rename skill — risolto**: ticket 11 done; rename atomico
  `prompts` → `minnarone-prompts`, riferimenti aggiornati e symlink personale
  rimosso.
- **Inventario dell'esperienza reale — risolto**: ticket 12 done; la matrice
  assegna i gap P1 ai ticket 15, 16–18 e conserva i gate shadow/live.
- **Confine persona/facts — risolto**: ticket 13 done; contratto e due scenari
  di accettazione sono pronti come input del prototipo 16.
- **Policy pubblica — risolta per shadow e ticket dipendenti**: fonti, matrice
  e guardrail sono in `docs/research/public-twitch-bot-safety.md`; ticket 16–18
  possono procedere. Il consenso broadcaster out-of-band è hard gate per il
  live IRC raccomandato; senza consenso il percorso termina a shadow. → ticket
  14 done.
- **Runtime/model profiles — risolto per il prototipo**: ticket 15 done; sei
  profili e un manifest di artifact pinned sono pronti come input del ticket 16.
- **Onboarding guidato e nuove skill**: scegliere tramite prototipo minimo il
  confine tra skill repo-local, docs/templates e `init/doctor`; non costruire
  interfacce definitive prima delle decisioni 10, 13–15. → ticket 16.
- **README e code-agent surface**: golden path task-first, catalogo skill e
  istruzioni di repo dipendono dagli esiti precedenti. → ticket 17.
- **Attriti runtime noti**: smoke senza dotenv, chat quieta che invalida media
  riusciti, schema/commenti/token/model drift. → ticket 18.
- **Flip a pubblico**: il ticket 05 resta l'ultima azione, con conferma esplicita
  e dopo la chiusura dei nuovi blocker 10–18 (09 può restare polish separato).

## Ticket Plan

- 01–04 — done — licenza/pulizia, screenshot, lingua e security pre-flight.
- 05 — task — Flip visibilità GitHub a public + verifica post-flip (clone
  anonimo, link README funzionanti, pagina repo) → bloccato fino alla nuova
  frontiera.
- 06–08 — done — suite verde, fresh-install e README bilingue.
- 09 — task — localizzare CLI/example in inglese → polish, da riallineare dopo
  l'audit 10 per evitare doppio lavoro.
- 10 — done — nome, migrazione e catalogo skill repo-local decisi.
- 11 — done — skill `prompts` rinominata end-to-end in `minnarone-prompts`;
  directory, frontmatter, symlink, riferimenti/script/test aggiornati.
- 12 — done — inventario evidence-backed del primo percorso operatore reale;
  matrice gap/severità/owner riportata nella mappa.
- 13 — done — contratto guidato per persona, soul, facts e descrizione canale
  confermato; nessuna identità inventata, nessuna modifica runtime.
- 14 — done — policy Twitch/public bot verificata: IRC/auth, account/token,
  rate, disclosure, retention e shadow/live mappati; guardrail e gap consegnati
  ai ticket 16–18.
- 15 — done — profili runtime/modelli/hardware e acquisizione ripetibile;
  matrice, budget, licenze, revision e digest consegnati al prototipo 16.
- 16 — prototype — catalogo nuove skill + confronto skill/docs/templates vs
  `minnarone init/doctor` → prova reversibile e scelta dell'interfaccia minima
  per code agent e utente normale.
- 17 — task — README task-first, catalogo skill, tutorial Twitch progressivo,
  golden config sanitizzati e `AGENTS.md`/CONTRIBUTING pointers → percorso umano
  e code-agent ripetibile.
- 18 — task — correggere attriti e drift runtime/docs scoperti nella sessione →
  smoke/dotenv/quiet-chat, schema commentator, token shadow/live e modello/params.

## Next Review

Con 10–15 chiusi, prototipare il catalogo/onboarding nel 16,
poi rendere eseguibili 17–18 e decidere se il 09 va assorbito nel polish. Solo
quando la nuova frontiera è verde si riapre il ticket 05 con conferma esplicita
dell'utente e verifica anonima post-flip.
