# Assistente Meeting — Guida Operatore

Questa guida copre i due nuovi profili commentatore per meeting via
`adapter: os_capture`: il **sintetizzatore** e il **suggeritore**. Entrambi
producono output PRIVATO per il solo operatore, visibile nella TUI o nella
console locale. Nessun messaggio viene inviato a Teams, Zoom o altre
piattaforme.

## Prerequisiti

- Python 3.11+, `uv`, extra `--extra tui` per la dashboard.
- `OPENROUTER_API_KEY` nell'ambiente (o la chiave del provider configurato).
- Audio di sistema e cattura schermo funzionanti (vedi `docs/twitch-operator.md`,
  sezione OS-capture, per setup audio loopback e permessi schermo).
- Opzionale: extra `--extra audio --extra vlm` per ASR locale e captioning video.

## Sintetizzatore di meeting (`meeting_synthesizer`)

### Cosa fa

Il sintetizzatore produce un riassunto strutturato del meeting a intervalli
regolari. Ogni `interval_s` secondi (default: 180, cioè 3 minuti), prende il
summary corrente dal Summarizer interno, lo formatta come note leggibili per
l'operatore, e lo mostra nel pannello TUI **SINTETIZZATORE**.

Il riassunto include: argomenti discussi, chi ha detto cosa (se la
diarizzazione speaker e' attiva), decisioni emerse, e action item identificati.

### Configurazione

```yaml
commentator:
  language: it
  profiles:
    meeting_synthesizer:
      interval_s: 180    # secondi tra un riassunto e l'altro
```

- `interval_s: 120` — riassunti ogni 2 minuti: piu' granulare ma piu' costoso.
- `interval_s: 180` — default: buon compromesso tra frequenza e costo.
- `interval_s: 300` — riassunti ogni 5 minuti: meno call LLM, ideale per
  meeting lunghi a basso ritmo.

### Trigger

Il sintetizzatore usa un trigger periodico (`synthesis_tick`): emette un
trigger ogni `interval_s` secondi, indipendente da menzioni, finestre di
conversazione, o idle. Non reagisce a eventi specifici.

## Suggeritore (`suggester`)

### Cosa fa

Il suggeritore valuta ogni nuova percezione audio (speech) e decide se c'e'
qualcosa di utile da suggerire all'operatore: domande da fare, cose da
ricordare, punti da menzionare. I suggerimenti appaiono nel pannello TUI
**SUGGERIMENTI**.

Se non c'e' nulla di utile, il suggeritore tace (risponde con il sentinel
`#nothing` internamente, che non produce output nel pannello).

### Come usa i facts

Il suggeritore e' tanto utile quanto lo sono i facts sugli interlocutori. Se
la cartella `facts_dir` contiene un file per un interlocutore riconosciuto via
diarizzazione speaker, il suggeritore usa quei fatti per personalizzare i
suggerimenti.

Esempio: se `facts/marco.md` contiene "deve consegnare il report entro
venerdi'" e Marco sta parlando di timeline, il suggeritore potrebbe suggerire
"ricorda a Marco la deadline del report di venerdi'".

### Configurazione

```yaml
commentator:
  language: it
  profiles:
    suggester: {}    # nessun parametro specifico per ora
```

Il suggeritore non ha parametri dedicati. La sua reattivita' dipende dal
`senser_interval` globale e dal ritmo delle percezioni audio.

### Trigger

Il suggeritore usa un trigger `on_perception`: emette un trigger per ogni
nuova percezione speech (audio riconosciuto come parlato). Non gestisce
finestre di conversazione o idle. La frequenza dei suggerimenti dipende
direttamente da quanto spesso il meeting produce parlato riconoscibile.

## Scrivere file di facts per gli interlocutori

I facts sono file Markdown nella cartella `facts_dir`, uno per interlocutore
o canale. Il nome del file (senza estensione) deve corrispondere al label
speaker assegnato dalla diarizzazione o al nome usato nel contesto.

### Struttura di un file facts

```markdown
# @nome_interlocutore

- Fatto 1 rilevante per il contesto dei meeting.
- Fatto 2 con informazioni che l'operatore vuole ricordare.
- Scadenze, impegni, preferenze, punti aperti.
```

### Esempio: `facts/marco.md`

```markdown
# @marco

- Marco e' il responsabile del progetto Alpha.
- Ha promesso la consegna del report per venerdi' 11 luglio.
- Preferisce comunicazioni scritte, non ama le call lunghe.
- Ha un budget di 50k EUR per il Q3.
```

### Esempio: `facts/team-backend.md`

```markdown
# @team-backend

- Sprint corrente: migrazione database a PostgreSQL.
- Blocco noto: il servizio auth non supporta ancora OAuth2 PKCE.
- Retrospettiva fissata per giovedi' 10 luglio.
```

### Buone pratiche

- **Fatti specifici e azionabili**: "deve consegnare X entro Y" e' utile;
  "e' una brava persona" non lo e'.
- **Brevita'**: facts troppo lunghi diluiscono il contesto nel prompt LLM.
  5-10 bullet per interlocutore sono un buon limite.
- **Aggiornamento manuale**: in questa versione i facts sono read-only. Non
  vengono aggiornati automaticamente durante il meeting. Aggiornali prima
  della sessione.

## Combinare profili

I profili si attivano in parallelo: ogni profilo ha il suo Reactor, il suo
Senser, e il suo prompt indipendente. Tutti condividono la pipeline di
percezione, il Summarizer, il provider LLM, e i facts/soul.

### Solo sintetizzatore

```yaml
commentator:
  language: it
  profiles:
    meeting_synthesizer:
      interval_s: 180
```

Pannelli TUI: i 9 base + SINTETIZZATORE.

### Solo suggeritore

```yaml
commentator:
  language: it
  profiles:
    suggester: {}
```

Pannelli TUI: i 9 base + SUGGERIMENTI.

### Sintetizzatore + suggeritore (assistente meeting)

```yaml
commentator:
  language: it
  profiles:
    meeting_synthesizer:
      interval_s: 180
    suggester: {}
```

Pannelli TUI: i 9 base + SINTETIZZATORE + SUGGERIMENTI.
Preset di esempio: `examples/teams-meeting-assistant.yaml`.

### Operator + sintetizzatore + suggeritore (completo)

```yaml
commentator:
  language: it
  profiles:
    operator:
      idle_interval: 30.0
    meeting_synthesizer:
      interval_s: 180
    suggester: {}
```

Pannelli TUI: i 9 base + SINTETIZZATORE + SUGGERIMENTI. Il profilo operator
produce output nel pannello MINNARONE (come nel preset
`teams-commentator.yaml`).
Preset di esempio: `examples/teams-meeting-full.yaml`.

## Layout pannelli TUI

I 9 pannelli base appaiono sempre:

| Pannello | Contenuto |
|----------|-----------|
| IDLE | Trigger idle-comment recenti |
| FINESTRA CHAT | Finestre di conversazione aperte |
| STREAMER | Finestra conversazione dello speaker dominante |
| CHAT | Percezioni chat recenti |
| EVENTI | Trigger Senser + eventi tecnici (errori, drop) |
| MINNARONE | Output del profilo operator (se attivo) |
| TRASCRIZIONE | Trascrizioni ASR con label speaker |
| VIDEO | Contatori frame e caption VLM recenti |
| MEMORIA | Summary corrente del Summarizer |

I pannelli condizionali appaiono solo quando il profilo corrispondente e'
attivo e ha prodotto output:

| Pannello | Profilo | Contenuto |
|----------|---------|-----------|
| SINTETIZZATORE | `meeting_synthesizer` | Riassunti incrementali del meeting |
| SUGGERIMENTI | `suggester` | Suggerimenti contestuali per l'operatore |

L'ordine nella TUI e': pannelli base, poi SINTETIZZATORE, poi SUGGERIMENTI
(dopo MEMORIA). I pannelli condizionali non appaiono finche' il profilo
corrispondente non produce il primo output.

## Stime di costo

Ogni profilo fa call LLM indipendenti. Su un meeting di 1 ora con il provider
Grok via OpenRouter:

| Profilo | Frequenza call | Call/ora stimate | Costo stimato/ora |
|---------|----------------|------------------|-------------------|
| `meeting_synthesizer` (180s) | 1 ogni 180s | ~20 | ~$0.20 |
| `suggester` | 1 per percezione speech | ~50-100 | ~$0.25-$0.50 |
| `operator` (idle 30s) | reattivo + idle | variabile | ~$0.10-$0.30 |

**Totale con 3 profili attivi**: ~$0.55-$1.00/ora. Su un meeting di 2 ore
con tutti i profili, aspettarsi ~$1.00-$2.00 totali.

Il costo del suggeritore scala con il ritmo del parlato. Meeting molto attivi
(molti interlocutori, parlato continuo) producono piu' call. Il sentinel
`#nothing` non riduce il costo della call (la call LLM avviene comunque), ma
riduce il rumore nell'output.

Per ridurre i costi:

- Aumentare `interval_s` del sintetizzatore (es. 300s invece di 180s).
- Attivare solo i profili che servono (es. solo sintetizzatore senza
  suggeritore).
- Usare un provider LLM con costi per-token piu' bassi.

## Avvio rapido

1. Copiare il preset:

   ```bash
   cp examples/teams-meeting-assistant.yaml meeting.local.yaml
   ```

2. Opzionale: modificare `interval_s`, `llm_provider`, `os_capture.monitor`.

3. Esportare la API key:

   ```bash
   read -r -s -p "OPENROUTER_API_KEY: " OPENROUTER_API_KEY; echo; export OPENROUTER_API_KEY
   ```

4. Validare il config:

   ```bash
   uv run python -m minnarone meeting.local.yaml --check
   ```

5. Avviare con la TUI:

   ```bash
   uv run python -m minnarone meeting.local.yaml --tui
   ```

## Troubleshooting

### Il suggeritore e' troppo rumoroso

Sintomo: il pannello SUGGERIMENTI si riempie di suggerimenti poco utili o
ripetitivi.

Rimedi:

- **Accorciare i facts**: facts troppo generici portano il suggeritore a
  trovare connessioni ovunque. Rendere i facts piu' specifici e azionabili.
- **Ridurre il ritmo delle percezioni speech**: aumentare
  `os_capture.audio_chunk_seconds` (es. da 1.0 a 2.0) per ridurre la
  frequenza delle percezioni audio.
- **Ridurre la sensibilita' VAD**: se il VAD segmenta troppo aggressivamente,
  il suggeritore riceve molte percezioni brevi. Regolare i parametri VAD.

### Il sintetizzatore e' troppo frequente

Sintomo: i riassunti si ripetono o aggiungono poco valore tra un intervallo
e l'altro.

Rimedio: aumentare `interval_s`. Per meeting a ritmo lento, `300` (5 minuti)
e' un buon valore. Per meeting molto attivi, `120` (2 minuti) puo' valere il
costo aggiuntivo.

### Il tasso di silenzio (`#nothing`) del suggeritore e' troppo basso

Sintomo: il suggeritore produce quasi sempre un suggerimento, anche quando
non ce n'e' bisogno.

Rimedi:

- **Rendere i facts piu' specifici**: facts vaghi ("Marco lavora sul
  progetto") danno al suggeritore troppo margine di manovra. Facts precisi
  ("Marco deve consegnare il report Alpha entro venerdi' 11") producono
  suggerimenti solo quando il contesto e' rilevante.
- **Ridurre il numero di facts per interlocutore**: meno fatti = meno spunti
  per suggerire.

### I riassunti sono vuoti o dicono "(nessuna memoria)"

Il sintetizzatore dipende dal Summarizer interno. Se il Summarizer non ha
ancora prodotto un summary (nei primi `summarizer_interval` secondi della
sessione), il sintetizzatore non ha materiale da formattare. Attendere almeno
un ciclo del Summarizer (`summarizer_interval`, default 30s) prima di
aspettarsi il primo riassunto.

### I suggerimenti non menzionano fatti degli interlocutori

Verificare che:

1. `facts_dir` nel config punti alla cartella corretta.
2. Il file facts esista con il nome corrispondente allo speaker label (es.
   `facts/marco.md` per lo speaker `marco`).
3. La diarizzazione speaker sia attiva e funzionante (richiede
   `speaker_embedding` e `speaker_clustering` configurati).

Senza diarizzazione, gli speaker appaiono come `speaker_N` o `?`, e il
suggeritore non puo' associarli ai facts nominali.

### Nessun output in nessun pannello

Verificare che:

1. `mode: private` sia impostato (obbligatorio per i profili commentatore).
2. Almeno un profilo sia configurato in `commentator.profiles`.
3. L'audio di sistema sia catturato (controllare il pannello TRASCRIZIONE).
4. `OPENROUTER_API_KEY` (o la chiave del provider) sia nell'ambiente.
