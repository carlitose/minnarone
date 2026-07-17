# Esternalizzazione dei prompt (SOUL.md & co.)

## Type

Wayfinding spec

## Status

Active

## Destination

Spostare tutto il testo di prompt **tunabile** fuori da `prompt.py` e
`summarizer.py`, in **file esterni** (SOUL.md e file di prompt companion),
caricati e **validati** all'avvio, estendendo il pattern già esistente
`FileMemory` + path da config. Obiettivo: poter modificare persona, stile,
formato, testi di situazione e istruzione del summarizer **senza editare codice
Python**, mantenendo però:

1. le **regole di sicurezza** (anti-injection + disclosure) **cablate nel
   codice** — un file editabile non deve poter indebolire la protezione;
2. la **byte-invarianza del prefisso stabile** (per il prompt caching);
3. le **garanzie dei test** sul contenuto del prompt (nessuna regressione muta).

Beneficio abilitante (operatore, 2026-07-17): **l'esternalizzazione È la
soluzione multilingua/multi-canale.** Una volta che i prompt sono in file, chi
vuole un canale non italiano semplicemente **riscrive i file nella sua lingua** e
Minnarone funziona — nessun motore i18n, nessuna traduzione "fornita" dal
progetto. L'unico requisito infrastrutturale che ne consegue: (a) **niente
italiano cablato** nelle parti tunabili, e (b) i file di prompt stanno in un
**percorso configurabile** (lo stesso pattern di `soul_path`/`facts_dir` di oggi).
Nota: se l'intero prompt è già nella lingua scelta dall'operatore, il placeholder
`{language}` diventa quasi ridondante — da valutare se tenerlo o lasciar fare al
testo del file.

## Decisions So Far

- **Confine di sicurezza** (operatore, 2026-07-17): esternalizzare tutto TRANNE le
  regole anti-injection (`_ROBUSTNESS_RULES`) e la stance di disclosure
  (`_DISCLOSURE_HIDE/_ANNOUNCE`), che restano hard-coded. Anche la meccanica del
  fence (`_UNTRUSTED_OPEN/CLOSE`, `_DATA_LINE_PREFIX`) resta nel codice.
- **Pattern di estensione già esistente**: `FileMemory(soul_path, facts_dir)`
  (`memory.py`) carica `soul.md` + `facts/*.md` da path in `config`
  (`config.py:836-837`). File reali in `.local/` e
  `examples/original-chat-memory/`. La nuova infrastruttura di prompt-loading
  deve riusare/estendere questo approccio, non inventarne uno parallelo.
- **Prior art**: i ticket done `meeting-synthesizer-prompt-template` e
  `suggester-prompt-template` hanno prodotto *template hard-coded* (con
  `{language}`), non file esterni — quindi il lavoro qui li supera esternalizzandoli.

## Cosa si esternalizza (tunabile) vs cosa resta cablato (sicurezza)

**Esterno** (in file):
- `_ORIGINAL_CHAT_RULES` — persona Minnarone, stile, lista emote.
- `_COMMENTATOR_/_MEETING_/_SUGGESTER_RULES_TEMPLATE` — con placeholder `{language}`.
- `[FORMATO RISPOSTA]` — testo del contratto RE/MSG.
- Testi `_original_chat_situation` (idle, chat mention/continuation, streamer
  mention/continuation) — variantati per tipo di trigger.
- `_ORIGINAL_CHAT_INTRO` (banner `SITUAZIONE ATTUALE`) + **canale** (oggi "enkk"
  hard-coded).
- `summarizer._PROMPT_INSTRUCTION`, `_EMPTY_SUMMARY_PLACEHOLDER`, etichette
  `_SOURCE_GROUPS`.
- (Da decidere) le etichette di sezione (`[MEMORIA]`, `[CHAT RECENTE]`,
  `[I TUOI ULTIMI MESSAGGI]`, ...).

**Cablato** (resta in codice, sicurezza/struttura):
- `_ROBUSTNESS_RULES`, `_DISCLOSURE_HIDE/_ANNOUNCE`.
- Fence: `_UNTRUSTED_OPEN/CLOSE`, `_DATA_LINE_PREFIX`, `_fence()`.

- **Inventario fatto (ticket 01, 2026-07-17)**: lista completa in
  `docs/tickets/prompt-externalization/done/01-research-inventory-prompts.md`.
  Esiti chiave: (a) prompt confinati in `prompt.py` + `summarizer.py` (il RE/MSG di
  `original_chat_output.py` è output, non prompt); (b) **base = branch
  `autopilot/original-chat-prompt-fidelity` / PR #32** — l'esternalizzazione va
  rebasata lì o su `main` dopo il merge; (c) canale "enkk" cablato in 2 punti, da
  unificare; (d) `[FORMATO RISPOSTA]` è esterno ma accoppiato al parser (validazione
  forte); (e) token di controllo `#end_conv`/`#nothing`/`RE:`/`MSG:` devono
  sopravvivere; (f) le 6 varianti situazione + 3 etichette summarizer + 3 template
  `{language}` sono le voci "a varianti chiave" che guidano il formato.

## Not Yet Specified

- **Formato dei file**: markdown per la prosa (SOUL.md), ma le parti
  parametrizzate (`{language}`, canale) e quelle **a varianti chiave** (situazioni
  per tipo di trigger, etichette gruppi summarizer) vogliono una struttura. Un
  file solo markdown non basta → decidere: markdown-con-`{placeholder}` +
  un file strutturato (YAML/TOML) per le varianti chiave e le etichette? O un
  unico YAML con blocchi multilinea? (prototype, ticket 02)
- **Meccanismo di templating/placeholder**: come iniettare `{language}`, canale e
  i punti dove entra il contenuto dinamico. `str.format` è fragile se il testo
  contiene `{`/`}`; serve un templater minimale e sicuro (il templating NON deve
  diventare un vettore di injection). (ticket 02/03)
- **Posizione e packaging dei file**: i default di prodotto devono essere
  **impacchettati** con l'app (fresh install funziona) ma **sovrascrivibili**
  dall'operatore (come oggi soul/facts puntano a `.local/`). Dove:
  `importlib.resources` su `resources/prompts/` + dir di override da config?
  (ticket 02/03)
- **Validazione**: fail-fast su file mancante/invalido vs degrado con grazia.
  Con le regole di sicurezza in codice, un persona-file mancante NON deve
  degradare a vuoto silenzioso. Definire la severità + il check dei placeholder
  richiesti. (ticket 02/03)
- **Relazione SOUL.md ↔ `soul` di memoria**: OGGI il `soul` (memoria) = "chi è
  l'agente (nome, età, gusti)" e finisce in `[MEMORIA PERMANENTE]`; le
  `_ORIGINAL_CHAT_RULES` = regole di comportamento in `[REGOLE]`. Sono blocchi
  DIVERSI. "SOUL.md" richiesto dall'utente potrebbe voler unificare i due concetti
  o restare separato. **Decisione da prendere nel prototype** (ticket 02): unire
  persona+regole in SOUL.md o tenere due file (memoria-soul vs regole-persona).
- **Multi-canale / multilingua**: risolto "gratis" dall'esternalizzazione (chi
  vuole un'altra lingua riscrive i file). Le uniche cose da decidere nel prototype:
  (1) i file di prompt stanno in una **directory configurabile** (come soul/facts)
  così un operatore punta al suo set senza toccare il codice — confermare che
  riusiamo quel pattern; (2) se tenere il placeholder `{language}` o lasciar
  dettare la lingua direttamente al testo del file. NIENTE motore i18n, niente
  fallback multi-set complicati.

## Out of Scope

- Esternalizzare/indebolire le regole anti-injection e di disclosure (decisione:
  restano cablate).
- Tuning dei prompt a runtime/hot-reload (i file si leggono all'avvio).
- Qualsiasi motore i18n: localizzare = riscrivere i file di prompt, cosa che
  l'esternalizzazione già permette. Il progetto non deve "fornire" set tradotti né
  gestire negoziazione lingua; deve solo non cablare l'italiano e leggere i file
  da un percorso configurabile.
- Riscrivere la logica di reazione/summarizer oltre quanto serve a spostare il
  testo.
- Cambiare il contenuto dei prompt (è un refactor: stesso testo, altra sede).

## Frontier / Blocking Edges

- **Edge #1 (blocca l'implementazione): formato + templating + packaging +
  validazione non decisi.** Senza un contratto di prompt-source provato, ogni
  migrazione rischia di essere rifatta. Lo risolve il **prototype (ticket 02)**,
  che deve anche sciogliere il nodo SOUL.md ↔ memoria-soul.
- ✅ **Edge #2 — inventario**: CHIUSO dal ticket 01 (lista completa + classificazione
  esterno/cablato + placeholder + voci a-varianti-chiave).

## Ticket Plan

| # | Tipo | Titolo | Output atteso |
|---|------|--------|---------------|
| 01 | research | Inventario dei prompt hard-coded | Tabella file:line di ogni stringa, classificata esterno/cablato, con placeholder richiesti |
| 02 | prototype | Formato + loader + packaging + validazione (spike) | Contratto prompt-source provato su 2 prompt rappresentativi; decisione SOUL.md↔memoria registrata |
| 03 | task | Modulo PromptSource (loader reale) | Loader con default impacchettati + override da config + validazione + placeholder; 1 prompt migrato come tracer + test |
| 04 | task | Migrare i prompt original-chat | persona/regole, [FORMATO RISPOSTA], situazioni, intro/canale in file |
| 05 | task | Migrare il prompt del summarizer | istruzione + placeholder + etichette gruppi in file |
| 06 | task | Migrare gli altri stili | operator/meeting/suggester rules in file (con {language}) |
| 07 | task | Test-strategy + docs + fresh-install | test allineati ai default impacchettati, byte-invarianza verificata, doc del meccanismo e del confine di sicurezza |

Dipendenze: 01 → 02 → 03 → {04, 05, 06} → 07. 04/05/06 condividono il loader (03),
quindi meglio sequenziali; ognuno porta i propri test (TDD).

## Next Review

Dopo 02: (1) confermare formato/packaging/validazione, la decisione SOUL.md↔
memoria-soul e il **layout dei prompt-set** (multi-canale/lingua); (2) ricalibrare
03-07 sul contratto scelto; (3) decidere se le etichette di sezione entrano
nell'esternalizzazione o restano cablate.
