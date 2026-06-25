# Specifica di Progetto — Framework per Agenti Percettivi Multimodali Real-Time

> **Nome di lavoro:** *Minnarone Framework* (impl. di riferimento: **Minnarone**)
> **Versione documento:** 1.0
> **Data:** 2026-06-25
> **Tipo:** Framework riusabile (SDK + app di riferimento)

---

## 1. Executive Summary

Un **framework riusabile** per costruire agenti AI che **percepiscono un contesto live multimodale** (audio, video/schermo, chat, eventi di piattaforma), lo convertono in testo, e **reagiscono proattivamente** — sia come **partecipante pubblico** (co-host streamer, commentatore in un gruppo) sia come **assistente privato** (suggerimenti riservati a venditori in call, presentatori).

L'idea nasce da **Minnarone**, un bot che ascoltava e guardava live stream Twitch e interagiva in chat in modo indistinguibile da un umano. Questo documento **generalizza** quell'architettura in un framework, mantenendo Minnarone come implementazione di riferimento per l'MVP.

**Principio guida architetturale:** la pipeline di **percezione** è condivisa tra tutti gli scenari; cambia solo il **loop di reazione** e il **canale di output**. Modalità privata e pubblica sono lo **stesso motore con una configurazione** diversa.

---

## 2. Utenti Target

| ID | Utente | Modalità prevalente |
|----|--------|---------------------|
| U01 | Venditore in video-call | Privata (suggerimenti) |
| U02 | Presentatore online | Privata (suggerimenti) |
| U03 | Streamer / co-host | Pubblica (partecipa) |
| U04 | Gruppo in video-call | Pubblica (commenta) |
| U05 | Sviluppatore che costruisce sul framework | Build (SDK) |

**Scenario primario MVP:** **U03 — Streamer / co-host pubblico** (riuso massimo dell'architettura Minnarone, rischio minimo). Gli altri scenari sono pianificati in v2/v3.

---

## 3. Requisiti Funzionali (FR)

| ID | Requisito | Priorità |
|----|-----------|----------|
| FR01 | Percezione audio → testo (ASR) + diarizzazione (chi parla) | MVP |
| FR02 | Percezione video/schermo → captioning (VLM) | MVP |
| FR03 | Ingestione chat / messaggi testuali | MVP |
| FR04 | Ingestione eventi strutturati di piattaforma (join/leave, reaction, slide change, sub/follow) | v2 |
| FR05 | Store unificato delle percezioni (log temporizzato append-only, `perceptions.jsonl`) | MVP |
| FR06 | Astrazione adapter sorgenti + adapter di cattura a livello SO (mic + audio di sistema + screen) | MVP |
| FR07 | Connettori per-piattaforma (Twitch/Zoom/Meet/Teams) | v2+ |
| FR08 | Reactor loop a cadenza configurabile | MVP |
| FR09 | Senser: rilevamento trigger (menzioni, finestre, idle/proattivo ~150s) | MVP |
| FR10 | Finestre di conversazione per interlocutore (streamer/utente + chat/gruppo) | MVP |
| FR11 | Summarizer: memoria a breve termine (riassunto periodico della sessione) | MVP |
| FR12 | Memoria a lungo termine: `soul` (identità) + `facts` (inizializzabili a mano) | MVP |
| FR13 | Auto-aggiornamento agentico della memoria cross-sessione (stile auto-agent) | v2 |
| FR14 | RAG / knowledge base esterna (listino, slide, lore canale) | v3 |
| FR15 | Prompt builder: prefisso stabile cacheable + sezione "situazione" dinamica | MVP |
| FR16 | Generazione reazione via LLM (provider pluggable: Grok/DeepSeek/…) | MVP |
| FR17 | Output: messaggio testuale pubblico | MVP |
| FR18 | Output: whisper privato (pannello/overlay) | MVP |
| FR19 | Output: voce (TTS) | v3 |
| FR20 | Output: azioni/eventi strutturati (emote/bandwagon, highlight, trigger esterni) | v2 |
| FR21 | Switch modalità privata/pubblica via configurazione | MVP |
| FR22 | Human-likeness: stima del typing delay | MVP |
| FR23 | Dedup di messaggi troppo simili | MVP |
| FR24 | Bandwagon (accodamento a emote/messaggi simili, senza LLM) | v2 |
| FR25 | Auto-terminazione conversazione (`#end_conv`) | MVP |
| FR26 | Resistenza a prompt injection | MVP |
| FR27 | Tooling privacy: flag disclosure AI + controlli retention | v2 |
| FR28 | UI/TUI di monitoraggio (percezioni, eventi, finestre, messaggi inviati) | MVP |

---

## 4. Requisiti Non Funzionali (NFR)

| ID | Requisito |
|----|-----------|
| NFR01 | Bassa latenza / real-time (senser ~0.5s, reazione tempestiva) |
| NFR02 | Basso costo operativo (gira per ore; ordine di cent/h) |
| NFR03 | Prompt caching (prefisso stabile in testa al prompt) |
| NFR04 | Efficienza con flussi multimodali ad alto volume |
| NFR05 | Modularità / pluggability (ASR, VLM, LLM, adapter sostituibili) |
| NFR06 | Percezione local-first (modelli on-device) |
| NFR07 | Privacy / retention configurabili |
| NFR08 | Estensibilità (nuovi adapter e canali di output) |
| NFR09 | Osservabilità (dashboard operatore) |
| NFR10 | Configurabilità (soul/facts/modalità/tono) |

**Strategia locale vs cloud:** percezione **in locale** (modelli leggeri on-device), **solo l'LLM di reazione in cloud**. I singoli componenti restano sostituibili (anche LLM locale o percezione cloud, su scelta).

**Posizione su disclosure/privacy:** framework **neutro**: fornisce gli strumenti (flag "dichiara di essere AI", controlli di retention) e lascia la scelta all'utente, senza imporre un comportamento.

---

## 5. User Stories (US)

| ID | Come… | Voglio… | Così che… | Prio |
|----|-------|---------|-----------|------|
| US01 | sviluppatore | definire identità (`soul`) e `facts` via file di config | avvio rapido di un agente personalizzato | MVP |
| US02 | streamer | un co-host AI che commenta nei momenti naturali | la chat resta viva anche nei momenti morti | MVP |
| US03 | streamer | che l'agente risponda quando viene nominato/interpellato | sembra un partecipante reale | MVP |
| US04 | viewer/streamer | che l'agente conversi anche con gli utenti della chat | interazione broadcast naturale | MVP |
| US05 | sviluppatore | cambiare provider LLM (Grok/DeepSeek/locale) | bilanciare costo/latenza/qualità | MVP |
| US06 | operatore | vedere percezioni, trigger, finestre e messaggi in dashboard | debug e tuning | MVP |
| US07 | venditore | suggerimenti privati real-time durante la call | gestire meglio le obiezioni | v2 |
| US08 | presentatore | prompt privati basati su slide + reaction pubblico | migliorare la presentazione | v2 |
| US09 | partecipante gruppo | un'AI che commenta in modo utile (non solo riassume) | meeting più vivaci/utili | v3 |
| US10 | operatore | che l'agente sembri umano (typing delay, no duplicati, sa chiudere) | interazione autentica | MVP |
| US11 | operatore | impostare disclosure AI e retention dati | conformità al mio contesto | v2 |
| US12 | agente (sé) | aggiornare i propri `facts` cross-sessione | ricordare partecipanti nel tempo | v2 |
| US13 | sviluppatore | percezione locale, solo LLM reazione in cloud | basso costo e bassa latenza | MVP |
| US14 | venditore | collegare una knowledge base (listino) | suggerimenti accurati | v3 |

---

## 6. Use Cases (UC)

| ID | Use case | Riferimento Minnarone |
|----|----------|------------------------|
| UC01 | Commento proattivo idle (ogni ~150s) sul contesto corrente | idle loop |
| UC02 | Reazione a menzione/interpellanza → apre finestra conversazione → risponde | "Bravo Minnarone" |
| UC03 | Continuazione: interlocutore parla poco dopo un messaggio dell'agente | finestre |
| UC04 | Risposta multi-party: legge più messaggi recenti, risponde alla persona giusta | esempio Paolo/raid |
| UC05 | Bandwagon: molti messaggi/emote simili → si accoda senza LLM | feature bandwagon |
| UC06 | Integrazione visione: arricchisce il messaggio con caption dello schermo | "friggitrice Cosori" |
| UC07 | Recall breve termine: cita qualcosa di prima nella sessione | "il boss di prima" |
| UC08 | Recall lungo termine: risponde a "chi sei / chi sono / cosa hai studiato" | soul/facts |
| UC09 | Chiusura conversazione (`#end_conv`) quando non ha più nulla da dire | feature |
| UC10 | Resistenza prompt injection: devia/prende in giro, resta in personaggio | feature |
| UC11 | Suggerimento privato (venditore): rileva obiezione → whisper solo all'utente | v2 |
| UC12 | Switch provider/modello LLM da config | pluggability |
| UC13 | Auto-update memoria: a fine sessione scrive nuovi `facts` | v2 |

### Esempio di flusso — UC02 (Menzione → conversazione)
1. Il Perceptor scrive in `perceptions.jsonl` una percezione audio taggata `streamer`: *"Bravo Minnarone"*.
2. Il **Senser** (loop ~0.5s) rileva la menzione del nome → apre/aggiorna la **finestra di conversazione streamer**.
3. Genera un **trigger** che descrive la situazione ("lo streamer si è rivolto a te").
4. Il **Prompt Builder** assembla: prefisso stabile (cacheable) + memoria lunga (`soul`/`facts`) + memoria breve (summary) + ultimi ~15 messaggi + percezioni recenti + **sezione situazione** (in coda, dal trigger).
5. L'**LLM Provider** genera il messaggio.
6. **Human-likeness** applica typing delay e dedup; l'**Output Router** lo instrada al canale pubblico.

---

## 7. Edge Cases (EC)

| ID | Edge case | Mitigazione |
|----|-----------|-------------|
| EC01 | Trascrizione rumorosa/errata (voce sottovoce) | tollerare: basta "il senso", non rompere il flusso |
| EC02 | Mis-tagging speaker (streamer vs audio del video riprodotto) | diarizzazione + tag `streamer` esplicito |
| EC03 | Picco di latenza del provider LLM | saltare il turno invece di postare un messaggio stale |
| EC04 | Output duplicato/ripetitivo | modulo dedup messaggi |
| EC05 | Agente fissato su un tema | contesto "ultimi messaggi miei" anti-ripetizione |
| EC06 | Risposta lunga e istantanea (innaturale) | stima typing delay |
| EC07 | Costi fuori controllo su sessioni lunghe | prompt caching + percezione locale + rate limit |
| EC08 | Disclosure incoerente (rivela/nega di essere bot quando non dovrebbe) | flag disclosure + istruzioni di prompt |
| EC09 | Nome storpiato ("Minnarone" → "Merignnano") | rilevamento menzioni robusto (fuzzy/foneticо) |
| EC10 | Finestre conversazione sovrapposte (streamer + chat) | gestione multi-finestra con priorità |
| EC11 | Nessun trigger per molto tempo | idle loop mantiene la presenza |
| EC12 | Privacy: partecipante chiede cancellazione/non-consenso | controlli retention + opt-out |
| EC13 | Contesto vuoto/insufficiente a inizio sessione | gestione cold-start (attesa percezioni sufficienti) |

---

## 8. Quality Requirements (QR) — misurabili

| ID | Requisito di qualità | Target |
|----|----------------------|--------|
| QR01 | Cadenza senser | ~0.5s |
| QR02 | Latenza reazione end-to-end | ~tempi umani (pochi secondi) |
| QR03 | Costo orario (LLM cloud) | ~0.30 €/h (Grok 4.3) / ~0.03 €/h (DeepSeek V4 Flash) |
| QR04 | Cache hit sul prefisso stabile | ~40% token (come osservato) |
| QR05 | Intervallo commento idle | ~150s, configurabile |
| QR06 | Finestra chat recente nel prompt | ultimi ~15 messaggi |
| QR07 | Anti-duplicazione | nessun messaggio quasi-identico inviato |

---

## 9. System Design

### 9.1 Architettura di alto livello

```
┌─────────────────── PERCEPTION (locale) ──────────────────┐
│  Source Adapters (interfaccia astratta)                  │
│   ├─ OS Capture (mic + system audio + screen) ← MVP      │
│   └─ Platform connectors (Twitch/Zoom/Meet/Teams) ← v2+  │
│         │                                                │
│   ┌─────┴───── pipeline per canale ──────────────┐       │
│   │ Audio: VAD → ASR → speaker tagging            │       │
│   │ Video: sampling → hashing → VLM captioning    │       │
│   │ Chat:  ingest diretto                          │       │
│   │ Events: ingest strutturato                     │       │
│   └──────────────────┬────────────────────────────┘       │
│            scrive →  perceptions.jsonl  (append-only)     │
└──────────────────────┬───────────────────────────────────┘
                       │ tail / read
┌──────────────────────┴──── REACTION (cloud LLM) ─────────┐
│  Senser (loop ~0.5s): trigger + finestre conversazione   │
│     ├─ idle loop (~150s) → commento proattivo            │
│     ├─ menzioni / interpellanze → apre finestra          │
│     └─ bandwagon (no-LLM)                                │
│  Summarizer (loop periodico): memoria a breve termine    │
│  Memory: soul + facts (+ auto-update v2, + RAG v3)       │
│  Prompt Builder: [prefisso stabile cacheable] +          │
│                  [situazione dinamica]                   │
│  LLM Provider (pluggable: Grok / DeepSeek / …)           │
│  Output Router: pubblico | whisper privato | TTS | azioni│
│  Human-likeness: typing delay, dedup, #end_conv          │
└──────────────────────────────────────────────────────────┘
   Observability: TUI operatore + overlay web (whisper)
```

### 9.2 Componenti e responsabilità

| Componente | Responsabilità | Stack |
|------------|----------------|-------|
| Source Adapter (interface) | Astrazione fonti; impl. OS-capture per MVP | Python |
| Audio pipeline | VAD → ASR → diarizzazione | `webrtcvad`, `faster-whisper` (large-v3-turbo), `sherpa-onnx` (embeddings) |
| Video pipeline | Sampling → hashing → captioning | `PyAV`, VLM `Qwen2-VL` |
| Chat/Event ingest | Normalizzazione in percezioni | Python |
| Perception store | Log temporizzato append-only | `perceptions.jsonl` |
| Senser | Trigger, finestre, idle loop, bandwagon | Python (loop async) |
| Summarizer | Riassunto periodico (memoria breve) | Python + LLM |
| Memory | `soul.md`, `facts/*.md`; auto-update (v2); RAG (v3) | Python (+ vector store v3) |
| Prompt Builder | Assembla prompt cache-friendly | Python |
| LLM Provider | Interfaccia pluggable verso i modelli | Python (OpenRouter / Grok / DeepSeek SDK) |
| Output Router | Instrada l'output per modalità/canale | Python core + adapter |
| Human-likeness | typing delay, dedup, `#end_conv` | Python |
| Observability UI | Dashboard operatore + overlay whisper | TUI Python (Textual) + UI web TS/Node |

### 9.3 Modello di concorrenza

Loop asincroni indipendenti a cadenze diverse, coordinati tramite il log `perceptions.jsonl` e lo stato delle finestre:
- **Perceptor** — continuo (per canale).
- **Senser** — ~0.5s.
- **Summarizer** — periodico.
- **Reactor** — su trigger.

### 9.4 Strutture dati chiave

**`perceptions.jsonl`** (una riga per percezione, temporizzata):
```json
{"ts": 1781057640.78, "source": "chat",   "type": "msg",    "speaker": "mar31lly99K", "text": "..."}
{"ts": 1781057651.73, "source": "audio",  "type": "speech", "speaker": "streamer",    "text": "..."}
{"ts": 1781057657.73, "source": "video",  "type": "caption","text": "..."}
```

**Memoria a lungo termine:**
- `soul.md` — identità dell'agente (nome, età, gusti, background).
- `facts/<entità>.md` — fatti per interlocutore/canale (es. `facts/enkk.md`).

**Stato finestre di conversazione** — in memoria, una per interlocutore (streamer, chat), possibilmente sovrapposte (EC10).

### 9.5 Struttura del prompt (cache-friendly)

1. **PROMPT — SYSTEM (prefisso stabile, cacheable):** ruolo, tono, regole generali, contesto piattaforma (es. emote Twitch), regole anti-disclosure/continuità.
2. **MEMORIA PERMANENTE:** `soul` + `facts` (innestati direttamente).
3. **SITUAZIONE ATTUALE (dinamica, non cacheable):**
   - Riassunto (dal Summarizer): stream / conversazioni streamer / conversazioni chat.
   - Ultimi ~15 messaggi di chat (con timestamp).
   - Percezioni recenti (voce + schermo).
   - Ultimi messaggi inviati dall'agente (anti-ripetizione).
   - Formato risposta atteso (incl. opzione `#end_conv`).
   - **Sezione SITUAZIONE/trigger in coda** (massima salienza): cosa è appena successo e cosa fare.

> Nota di design osservata: la sezione "situazione" è collocata **in fondo** al prompt perché è quella che il modello pesa di più.

### 9.6 Tecnologie di default (tutte sostituibili — NFR05)

| Funzione | Default |
|----------|---------|
| Voice Activity Detection | `webrtcvad` |
| Speech recognition (ASR) | `faster-whisper` large-v3-turbo |
| Speaker tagging / diarizzazione | embeddings `sherpa-onnx` |
| Video sampling/decoding | `PyAV` + hashing |
| Vision captioning (VLM) | `Qwen2-VL` |
| LLM reazione | Grok 4.3 (qualità/latenza) · DeepSeek V4 Flash (costo) — via OpenRouter |
| Chat transport (Twitch) | IRC |
| UI operatore | Textual (TUI) |
| Overlay / connettori web | TypeScript / Node |

### 9.7 Distribuzione

- **SDK Python** (base): moduli componibili (`Perceptor`, `Reactor`, `Senser`, `Memory`, adapter…) per gli sviluppatori (U05).
- **App di riferimento "Minnarone"** costruita sopra l'SDK, configurabile via file (soul, facts, modalità, adapter).

---

## 10. Roadmap (per priorità)

### MVP — Minnarone pubblico (streamer)
Percezione (audio+video+chat) locale · `perceptions.jsonl` · OS-capture adapter · Senser (trigger/finestre/idle) · Summarizer · memoria `soul`/`facts` · Prompt Builder cache-friendly · LLM pluggable · output pubblico + whisper · human-likeness (typing delay, dedup, `#end_conv`) · anti prompt-injection · TUI di monitoraggio · SDK + app di riferimento.

### v2
Eventi strutturati di piattaforma · connettori per-piattaforma (Twitch ricco, poi Zoom/Meet) · auto-aggiornamento memoria cross-sessione · bandwagon · azioni/eventi strutturati in output · tooling privacy (disclosure + retention) · scenari privati (venditore/presentatore con whisper).

### v3
RAG / knowledge base esterna · output voce (TTS) · scenario gruppo in video-call.

---

## 11. Rischi e Note

- **Etica/percezione pubblica:** la capacità di indistinguibilità solleva temi etici (l'esperimento Minnarone si è chiuso con un monito). Il framework resta neutro ma espone strumenti di disclosure/consenso (FR27).
- **Qualità della percezione:** trascrizioni rumorose e mis-tagging speaker degradano la qualità (EC01/EC02); il sistema è progettato per tollerare l'imperfezione.
- **Dipendenza da provider LLM esterni:** latenza/costo variabili (EC03/EC07); mitigati da caching, percezione locale e provider sostituibili.
- **"Gusto" dell'LLM:** l'esperienza di sviluppo di Minnarone evidenzia che la struttura del prompt va curata a mano; il Prompt Builder è un componente di prima classe, non un dettaglio.

---

*Documento generato tramite il processo interattivo Project Designer (Phase 1 → 2 → 3, tutte confermate).*
