# PRD — Sintetizzatore di meeting e Suggeritore

> **Slug:** `meeting-synthesizer-and-suggester`
> **Data:** 2026-07-08
> **Riferimenti:** [SPECIFICATION.md](../SPECIFICATION.md) (US07, US09, UC11, U01, U02, roadmap v2) ·
> [PRD os-capture-teams-commentator](os-capture-teams-commentator.md)

## Problem Statement

Oggi Minnarone in modalità `PRIVATE` ha un unico stile utile per i meeting:
`OPERATOR`, che commenta ciò che accade come un osservatore. Ma l'operatore che
partecipa a un meeting ha due bisogni distinti non coperti:

1. **Non perdere il filo** — se si distrae o arriva in ritardo, non ha un
   riassunto strutturato di ciò che è stato detto. Il Summarizer interno produce
   riassunti ogni ~30s, ma li usa solo come contesto per il prompt dell'agente:
   non li mostra mai all'operatore.

2. **Sapere cosa dire o chiedere** — in una call con molti interlocutori e
   argomenti, l'operatore vuole suggerimenti contestuali: "chiedi a X del
   budget", "menziona che la deadline è venerdì", basati su ciò che viene detto
   in quel momento e sulla storia con quell'interlocutore (facts).

Questi due bisogni richiedono stili di reazione diversi (timer vs event-driven),
output diversi (riassunto strutturato vs notifica puntuale) e devono poter
girare **in parallelo** durante la stessa sessione.

## Solution

Aggiungere due nuovi `CommentatorStyle` al motore esistente:

- **`MEETING_SYNTHESIZER`** — ogni N secondi (configurabile, default 180s)
  prende il riassunto prodotto dal Summarizer esistente, lo formatta come note
  di meeting leggibili per l'operatore, e lo mostra in un pannello TUI dedicato.

- **`SUGGESTER`** — ogni volta che arriva una nuova percezione audio (speech),
  valuta se c'è qualcosa di utile da suggerire all'operatore (domande da fare,
  cose da ricordare/menzionare) basandosi sul contesto live e sui facts degli
  interlocutori. Se non c'è nulla, tace.

Entrambi girano come **Reactor indipendenti** con LLM call separate, prompt
dedicati, e pannelli TUI distinti. Condividono la pipeline di percezione e il
Summarizer con qualsiasi altro stile attivo.

Il config passa da `commentator.style` (singolo valore) a `commentator.profiles`
(dizionario di stili con config per-stile), permettendo profili multipli in
parallelo.

## User Stories

1. Come operatore in un meeting, voglio vedere un riassunto incrementale ogni
   ~3 minuti in un pannello dedicato, così che se mi distraggo posso riprendere
   il filo senza chiedere "cosa mi sono perso".
2. Come operatore, voglio che il riassunto sia formattato come note leggibili
   (non come contesto tecnico per un prompt LLM), così che possa leggerlo
   velocemente durante la call.
3. Come operatore, voglio configurare l'intervallo del sintetizzatore (es. 120s,
   180s, 300s), così da bilanciare frequenza e costo in token.
4. Come operatore, voglio ricevere suggerimenti contestuali quando qualcuno
   dice qualcosa di rilevante, così che possa fare la domanda giusta al momento
   giusto.
5. Come operatore, voglio che il suggeritore usi i miei facts sugli
   interlocutori (es. `facts/enkk.md`), così che i suggerimenti siano
   personalizzati ("ricorda a Enkk che ti deve quel documento").
6. Come operatore, voglio che il suggeritore taccia quando non ha nulla di
   utile da dire, così che non mi distragga con rumore.
7. Come operatore, voglio che sintetizzatore e suggeritore girino in parallelo
   nella stessa sessione, così da avere sia il riassunto sia i suggerimenti
   senza dover scegliere.
8. Come operatore, voglio vedere l'output del sintetizzatore e del suggeritore
   in pannelli TUI separati, così da non mescolare riassunti e suggerimenti.
9. Come operatore, voglio poter attivare solo il sintetizzatore, solo il
   suggeritore, o entrambi, così da personalizzare l'esperienza.
10. Come operatore, voglio poter combinare i nuovi stili con il commentatore
    OPERATOR, così da avere commenti + riassunti + suggerimenti se lo desidero.
11. Come operatore, voglio che i nuovi stili funzionino con `os_capture` per
    meeting Teams/Zoom/Meet, ma siano predisposti per altri adapter futuri.
12. Come sviluppatore, voglio che il config `commentator.profiles` sia
    estensibile: aggiungere un nuovo stile richiede solo un nuovo enum value e
    un blocco YAML, senza cambiare il parser.
13. Come sviluppatore, voglio che ogni profilo abbia il suo Reactor
    indipendente, così che i test di uno stile non dipendano dagli altri.

## Implementation Decisions

### Nuovi enum values in `CommentatorStyle`

Si aggiungono `MEETING_SYNTHESIZER = "meeting_synthesizer"` e
`SUGGESTER = "suggester"` all'enum `CommentatorStyle` in `output.py`.

### Nuovo formato config: `commentator.profiles`

Il campo `commentator.style` (singolo) viene sostituito da
`commentator.profiles` (dizionario). Ogni chiave è un valore di
`CommentatorStyle`, ogni valore è la config specifica dello stile.

Struttura YAML:

```yaml
commentator:
  language: it                    # default condiviso
  profiles:
    operator:
      idle_interval: 30.0
    meeting_synthesizer:
      interval_s: 180
    suggester: {}
```

Il campo `commentator.enabled` diventa implicito: se `profiles` è non vuoto,
il commentatore è abilitato. Campi globali (`language`) restano a livello
`commentator` e ogni profilo li eredita.

`CommentatorConfig` viene rifattorizzato: il campo `style` sparisce, sostituito
da `profiles: dict[CommentatorStyle, ProfileConfig]`. Si introducono dataclass
per-stile:

- `OperatorProfileConfig(idle_interval: float | None)`
- `OriginalChatProfileConfig(idle_interval: float | None)`
- `MeetingSynthesizerProfileConfig(interval_s: float = 180.0)`
- `SuggesterProfileConfig()` (nessun parametro specifico per ora)

I campi `enabled` e `style` spariscono da `CommentatorConfig`. Il metodo
`prompt_style` viene sostituito da `active_styles() -> list[CommentatorStyle]`.

Tutti i config `.local` e `examples/` vengono aggiornati al nuovo formato.

### Trigger strategy per stile

Ogni profilo attivo produce il proprio Reactor con un Senser configurato
per il suo pattern di trigger:

| Stile | Trigger | Meccanismo |
|-------|---------|------------|
| `OPERATOR` | mention + continuation + idle | Senser esistente (invariato) |
| `ORIGINAL_CHAT` | mention + continuation + idle | Senser esistente (invariato) |
| `MEETING_SYNTHESIZER` | timer periodico | Nuovo trigger kind `synthesis_tick`: il Senser emette un trigger ogni `interval_s`, indipendente da menzioni/finestre/idle |
| `SUGGESTER` | ogni nuova percezione audio | Nuovo trigger kind `suggestion_eval`: il Senser emette un trigger per ogni nuova percezione speech, senza finestre di conversazione |

Il Senser acquisisce un parametro `trigger_mode` che determina quali trigger
kinds sono attivi. I modi esistenti (mention/continuation/idle) diventano il
modo `reactive` (default). Si aggiungono `periodic` (solo timer) e
`on_perception` (ogni percezione nuova).

### Prompt per stile

Il `PromptBuilder` acquisisce template per i nuovi stili:

- **MEETING_SYNTHESIZER**: riceve il summary corrente dal Summarizer e il
  contesto recente. Il prompt chiede di formattare un riassunto strutturato per
  l'operatore: argomenti discussi, chi ha detto cosa, eventuali decisioni o
  action items emersi. Lingua configurabile (default: italiano).

- **SUGGESTER**: riceve la percezione che ha triggerato, i facts
  dell'interlocutore (se presenti), il contesto recente e il summary. Il prompt
  chiede di valutare se c'è una domanda utile da fare o qualcosa da
  ricordare/menzionare. Se non c'è nulla, deve rispondere con un sentinel
  `#nothing` (analogo a `#end_conv`). Lingua configurabile.

### Reactor multipli in parallelo

`build_agent` in `app.py` istanzia un Reactor per ogni profilo attivo. Tutti
condividono:
- `PerceptionStore` (unico, append-only)
- `Summarizer` (unico, il suo summary è letto da tutti)
- `LLMProvider` (unico, le call sono serializzate internamente da OpenRouter)
- Facts e soul (caricati una volta)

Ogni Reactor ha il suo:
- `Senser` (configurato con il trigger_mode dello stile)
- `PromptBuilder` (configurato con il CommentatorStyle)
- `OutputRouter` (mappato a un canale TUI specifico)
- `CadenceLoop` (intervallo appropriato allo stile)

`Agent.run()` lancia N reactor loop (uno per profilo) + 1 summarizer + 1
perception pump, tutti come task concorrenti.

### Output: pannelli TUI separati

Il `TuiPrivateOutputRouter` viene esteso per supportare canali di output
multipli. Ogni profilo scrive su un `MinnaroneOutputStream` dedicato,
identificato dal `CommentatorStyle`.

La TUI acquisisce due nuovi pannelli:
- **SINTETIZZATORE** — mostra i riassunti incrementali del meeting
- **SUGGERIMENTI** — mostra i suggerimenti contestuali

Il `DashboardState` acquisisce campi per gli output di ogni profilo, e
`render_panels()` produce i pannelli aggiuntivi.

Il layout della griglia TUI va adattato per accogliere i nuovi pannelli (da
3x3 a layout flessibile a seconda dei profili attivi).

### Gestione del silenzio del SUGGESTER

Il SUGGESTER può decidere di non suggerire nulla. Il Reactor per il SUGGESTER
riconosce il sentinel `#nothing` nella risposta LLM e non effettua routing
(nessun output nel pannello). Questo è analogo al pattern `#end_conv` già
esistente.

### Adapter-agnostic

Entrambi gli stili funzionano con qualsiasi `SourceAdapter`. Nessun vincolo
sul campo `adapter` nel config. La combinazione tipica sarà
`adapter: os_capture` + `mode: private` + profili sintetizzatore/suggeritore,
ma il codice non lo impone.

## Step-by-Step Implementation Plan

L'ordine segue il principio tracer-bullet: prima i contratti, poi la logica
interna, poi il wiring, infine la UI. Ogni passo è verificabile
indipendentemente.

1. **Aggiungere i nuovi enum values a `CommentatorStyle`.**
   Aggiungere `MEETING_SYNTHESIZER = "meeting_synthesizer"` e
   `SUGGESTER = "suggester"` all'enum in `output.py`. Nessun altro modulo
   cambia ancora: è un passo puramente additivo.
   *Verifica:* i test esistenti restano verdi; i nuovi valori sono importabili.
   *Trappola:* non rimuovere ancora `OPERATOR` e `ORIGINAL_CHAT` — servono.

2. **Rifattorizzare `CommentatorConfig` da `style` singolo a `profiles`.**
   Sostituire il campo `style: CommentatorStyle` con
   `profiles: dict[CommentatorStyle, ProfileConfig]`. Introdurre le dataclass
   per-profilo (`OperatorProfileConfig`, `OriginalChatProfileConfig`,
   `MeetingSynthesizerProfileConfig`, `SuggesterProfileConfig`). Rimuovere
   `enabled` (implicito da `len(profiles) > 0`). Mantenere `language` a livello
   `CommentatorConfig`. Aggiornare `_commentator_config_from_dict` per parsare
   il nuovo formato YAML. Aggiornare `validate_for_mode` per i nuovi vincoli
   (profili privati richiedono `mode: private`, ecc.).
   *Perché ora:* è il contratto che sblocca tutto il resto; senza questo nessun
   altro modulo può consumare i nuovi stili.
   *Verifica:* test di config con profili multipli, profili vuoti, campi
   sconosciuti rifiutati, vincoli di modo. I test esistenti vanno aggiornati per
   il nuovo formato.
   *Trappola:* aggiornare tutti i punti che leggono `commentator.style` o
   `commentator.enabled` — cercare con grep per trovarli tutti.

3. **Aggiornare tutti i config files (`.local` e `examples/`).**
   Convertire ogni file dal formato `commentator.style: X` al nuovo formato
   `commentator.profiles`. Includere: `teams-commentator.local.yaml`,
   `twitch-commentator.local.yaml`, `teams-commentator.audio.local.yaml`,
   `examples/teams-commentator.yaml`, `examples/twitch-commentator.example.yaml`,
   `examples/twitch-original-chat.example.yaml`. Aggiungere preset di esempio
   per i nuovi stili (es. `examples/teams-meeting-assistant.yaml` con
   sintetizzatore + suggeritore).
   *Perché ora:* i config devono essere coerenti con il nuovo parser prima di
   qualsiasi test end-to-end.
   *Verifica:* `python -m minnarone <config> --check` passa per ogni file.
   *Trappola:* non dimenticare i `.local` — non sono in git ma devono funzionare.

4. **Aggiungere trigger modes al Senser.**
   Introdurre il concetto di `trigger_mode` nel Senser:
   - `reactive` (default): mention + continuation + idle — comportamento attuale
   - `periodic(interval_s)`: emette un trigger `synthesis_tick` ogni N secondi
   - `on_perception`: emette un trigger `suggestion_eval` per ogni nuova
     percezione speech (source=AUDIO, type=speech)
   Aggiungere i nuovi trigger kinds (`synthesis_tick`, `suggestion_eval`) al
   tipo `Trigger`. Il Senser in modo `periodic` non gestisce finestre di
   conversazione; in modo `on_perception` non gestisce idle.
   *Perché ora:* il Reactor dipende dal Senser per i trigger; questo passo
   sblocca i Reactor per-profilo.
   *Verifica:* test del Senser in ogni modo: `periodic` emette trigger a
   intervalli corretti; `on_perception` emette un trigger per ogni speech
   perception e ignora altre sorgenti; `reactive` resta invariato.
   *Trappola:* il Senser `periodic` deve usare il clock iniettabile (come
   `idle_comment`) per testabilità deterministica.

5. **Aggiungere prompt template per `MEETING_SYNTHESIZER` e `SUGGESTER`.**
   In `PromptBuilder`, aggiungere i rami per i nuovi stili nel metodo `build()`:
   - `MEETING_SYNTHESIZER`: prefisso stabile con regole del sintetizzatore +
     sezione dinamica con il summary corrente + contesto recente. Il prompt
     chiede di produrre note di meeting strutturate.
   - `SUGGESTER`: prefisso stabile con regole del suggeritore + facts
     dell'interlocutore + sezione dinamica con la percezione trigger + contesto
     recente + summary. Il prompt chiede di suggerire o rispondere `#nothing`.
   *Perché ora:* i prompt sono necessari prima di poter testare i Reactor.
   *Verifica:* test del PromptBuilder per ogni nuovo stile: verifica che le
   sezioni attese siano presenti, che i facts vengano iniettati, che il sentinel
   `#nothing` sia documentato nel prompt del suggeritore.
   *Trappola:* mantenere il prefisso stabile (cacheable) per entrambi gli stili
   — non includere dati dinamici nel prefisso.

6. **Supportare il sentinel `#nothing` nel Reactor.**
   Aggiungere al Reactor la gestione di `#nothing` per il SUGGESTER: se la
   risposta LLM contiene solo `#nothing`, non effettuare routing (nessun output).
   Analogo al pattern `#end_conv` già esistente.
   *Perché ora:* il Reactor deve sapere gestire il silenzio prima del wiring
   multiplo.
   *Verifica:* test del Reactor con SUGGESTER e risposta `#nothing`: nessun
   messaggio routato.
   *Trappola:* `#nothing` deve essere riconosciuto anche se circondato da
   whitespace o preceduto da testo LLM spurio.

7. **Wiring multi-Reactor in `app.py`.**
   Modificare `build_agent` per istanziare un Reactor per ogni profilo attivo
   in `commentator.profiles`. Ogni Reactor riceve il suo Senser (con
   `trigger_mode` appropriato), il suo PromptBuilder (con lo stile), e il suo
   OutputRouter. Tutti condividono store, summarizer, LLM, facts/soul.
   Modificare `Agent.run()` per lanciare N reactor loop come task concorrenti.
   *Perché ora:* questo è il passo di integrazione che collega config → senser →
   prompt → reactor → output.
   *Verifica:* test di wiring con un config multi-profilo e sorgenti fake:
   l'Agent produce output da ogni profilo attivo.
   *Trappola:* ogni Reactor deve avere un `CadenceLoop` con l'intervallo giusto:
   il MEETING_SYNTHESIZER non ha bisogno del senser tick ogni 0.5s ma il
   suggeritore sì (deve reagire velocemente).

8. **Aggiungere pannelli TUI per sintetizzatore e suggeritore.**
   Estendere `MinnaroneOutputStream` o creare stream separati per ogni profilo.
   Estendere `TuiPrivateOutputRouter` per routare a stream diversi in base allo
   stile. Aggiungere pannelli SINTETIZZATORE e SUGGERIMENTI al `DashboardState`
   e alla TUI Textual. Adattare il layout della griglia per accogliere i nuovi
   pannelli (mostrarli solo quando i profili corrispondenti sono attivi).
   *Perché ora:* ultimo passo funzionale; senza pannelli l'output finisce tutto
   nello stesso stream.
   *Verifica:* test del DashboardState con profili attivi: i pannelli
   corrispondenti appaiono; test della TUI: i pannelli renderizzano.
   *Trappola:* il layout deve degradare gracefully quando ci sono meno profili
   (es. solo sintetizzatore → nessun pannello suggerimenti).

9. **Aggiornare il `DashboardState.snapshot()` e la status bar.**
   `snapshot()` deve aggregare le diagnostiche di ogni Reactor attivo (non solo
   del primo). La status bar deve riflettere lo stato di tutti i profili.
   *Perché ora:* dipende dai passi 7 e 8.
   *Verifica:* test di snapshot con multi-reactor: le diagnostiche sono
   aggregate correttamente per ogni profilo.

10. **Preset di esempio e documentazione operatore.**
    Creare `examples/teams-meeting-assistant.yaml` con sintetizzatore +
    suggeritore attivi. Aggiornare `docs/twitch-operator.md` (o creare
    `docs/meeting-operator.md`) con istruzioni per i nuovi stili.
    *Verifica:* `--check` sul preset passa; la documentazione è coerente col
    config reale.

## Testing Decisions

Un buon test qui verifica **comportamento esterno**: che trigger emette un
Senser in un dato modo, che prompt produce un PromptBuilder per un dato stile,
che output produce un Reactor con una data risposta LLM, che pannelli rende un
DashboardState con dati profili attivi. I test **non** verificano dettagli
interni (strutture dati intermedie, ordine di istruzioni nel prompt).

Moduli coperti da unit test:

- **`CommentatorConfig` (profiles)** — parsing YAML multi-profilo, vincoli di
  validazione, `active_styles()`. Prior art: test esistenti di
  `CommentatorConfig` in `test_config.py`.

- **Senser (trigger modes)** — `periodic` emette trigger a intervalli, ignora
  menzioni; `on_perception` emette trigger su speech, ignora idle; `reactive`
  invariato. Prior art: `test_senser.py`.

- **PromptBuilder (nuovi stili)** — sezioni presenti per MEETING_SYNTHESIZER e
  SUGGESTER, facts iniettati, sentinel documentato. Prior art:
  `test_prompt_builder.py`.

- **Reactor (`#nothing`)** — SUGGESTER con risposta `#nothing` non produce
  output. Prior art: test `#end_conv` in `test_reactor.py`.

- **Wiring multi-Reactor** — `build_agent` con config multi-profilo produce
  Reactor separati, ognuno con il suo stile e trigger mode. Prior art: test di
  wiring in `test_shadow_router.py` (sezione app wiring).

- **DashboardState/TUI (pannelli)** — pannelli dinamici in base ai profili
  attivi. Prior art: `test_dashboard.py`, `test_dashboard_tui.py`.

**Non** coperti da test automatici: acceptance live su meeting reale — resta
manuale (coerente con le issue di acceptance Twitch/TUI).

## Out of Scope

- **Output vocale (TTS)** — i nuovi stili producono solo testo. TTS è roadmap
  v3 (FR19).
- **RAG / knowledge base** — il suggeritore usa solo facts statici, non una
  knowledge base esterna (roadmap v3, FR14).
- **Auto-update dei facts** — i facts sono read-only in questa iterazione.
  L'aggiornamento automatico è roadmap v2 (FR13).
- **Chat scritta di Teams** — non disponibile via os_capture (vedi PRD
  os-capture-teams-commentator).
- **Suggerimenti basati su video/schermo** — il SUGGESTER triggera solo su
  percezioni audio (speech). Estendere a video è un'evoluzione futura.
- **UI web o mobile** — l'output è solo TUI Textual (terminale).
- **Retrocompatibilità** con il formato config `commentator.style` — il
  vecchio formato viene rimosso.

## Further Notes

- Questo PRD implementa parti della roadmap v2 della SPECIFICATION: US07
  (suggerimenti privati real-time per venditori), UC11 (suggerimento privato),
  e anticipa elementi di US09 (AI utile durante meeting).
- Il pattern multi-Reactor è progettato per essere estensibile: aggiungere un
  nuovo stile richiede solo: (1) enum value, (2) profile config dataclass,
  (3) prompt template, (4) trigger mode (se nuovo), (5) pannello TUI. Il
  wiring in `app.py` lo gestisce automaticamente iterando sui profili.
- Il MEETING_SYNTHESIZER fa una LLM call extra ogni ~180s. Su sessioni lunghe
  (~2h) questo aggiunge ~40 call. A ~$0.01/call (Grok 4.3 via OpenRouter) il
  costo aggiuntivo è ~$0.40/sessione — trascurabile.
- Il SUGGESTER fa una LLM call per ogni percezione speech. Con ~4 utterance/min
  su un meeting attivo, sono ~480 call in 2 ore. A ~$0.005/call (prompt corto)
  il costo è ~$2.40/sessione — accettabile per il valore che fornisce, ma da
  monitorare. Un'ottimizzazione futura potrebbe pre-filtrare le percezioni
  prima della LLM call (es. ignorare utterance troppo corte o ripetitive).
- Prossimo passo suggerito: spacchettare questo PRD in issue con la skill
  `prd-to-issues` (slice verticali tracciabili nell'ordine del piano sopra).
