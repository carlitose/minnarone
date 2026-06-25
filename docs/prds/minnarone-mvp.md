# PRD — Minnarone Framework (MVP + scaffolding v2)

> **Fonte:** [`docs/SPECIFICATION.md`](../SPECIFICATION.md)
> **Scope:** MVP (scenario pubblico streamer/co-host) + interfacce astratte predisposte per v2 (non implementate)
> **Stato:** Design → pronto per implementazione
> **Linguaggio core:** Python (percezione + reactor) · TypeScript/Node (UI/overlay, futuro)

---

## Glossario (termini usati nel PRD)

- **Percezione (Perception):** un singolo evento osservato, normalizzato in testo e con timestamp. È l'unità di dato che attraversa tutto il sistema.
- **Perception store:** il log append-only (`perceptions.jsonl`) dove confluiscono tutte le percezioni; spina dorsale del sistema.
- **Adapter sorgente:** componente che si aggancia a una fonte (cattura SO, Twitch, Zoom…) e produce stream grezzi da dare alle pipeline di percezione.
- **Pipeline di percezione:** trasforma uno stream grezzo (audio/video/chat) in percezioni testuali.
- **VAD (Voice Activity Detection):** rileva *quando* c'è parlato nell'audio, per non lanciare l'ASR sul silenzio.
- **ASR (Automatic Speech Recognition):** trascrizione audio → testo.
- **Diarizzazione / speaker tagging:** capire *chi* sta parlando (es. distinguere lo streamer dall'audio di un video riprodotto).
- **VLM (Vision-Language Model):** modello che genera una didascalia testuale di un fotogramma.
- **Trigger:** segnale prodotto dal Senser che dice "è successo qualcosa di rilevante, considera una reazione", con allegato il contesto della situazione.
- **Finestra di conversazione:** stato che tiene traccia di uno scambio in corso con un interlocutore (streamer o chat), così l'agente sa di essere "in conversazione".
- **Idle loop:** timer che, in assenza di trigger, fa intervenire l'agente proattivamente (~150s) per non sparire.
- **Bandwagon:** accodamento a emote/messaggi simili senza interpellare l'LLM.
- **Prefisso stabile (cacheable):** la parte iniziale del prompt che non cambia tra chiamate, posta in testa per sfruttare il prompt caching del provider LLM.
- **Modalità privata/pubblica:** dove va l'output — *whisper* solo all'operatore (privata) vs messaggio visibile a tutti (pubblica). Stesso motore, configurazione diversa.
- **Deep module:** modulo che incapsula molta logica dietro un'interfaccia piccola e stabile, testabile in isolamento.

---

## Problem Statement

Chi gestisce un'interazione live — uno streamer durante una diretta, ma in prospettiva anche un venditore in call o un presentatore — non ha un "compagno" software che **percepisca davvero il contesto in tempo reale** (cosa si dice a voce, cosa si vede a schermo, cosa scorre in chat) e **reagisca in modo pertinente e naturale**. Gli strumenti esistenti riassumono *a posteriori*; non partecipano *nel momento*.

Costruire un agente così è difficile: enormi quantità di dati multimodali in tempo reale, vincoli stringenti di latenza e di costo (deve girare per ore senza costare un patrimonio), un linguaggio (chat/parlato live) diverso da quello tipico degli LLM, e un'interazione in **broadcast** (uno parla, molti possono rispondere) anziché uno-a-uno. Il problema centrale è la **memoria**: un LLM non ricorda nulla tra una chiamata e l'altra, mentre un partecipante umano ricorda tutta la sessione.

L'esperimento **Minnarone** ha dimostrato che è fattibile e a costi irrisori (ordine di cent/ora). Manca però una **base riusabile**: oggi quel valore è bloccato in un prototipo non rilasciato e legato a Twitch.

## Solution

Un **framework** (SDK Python + app di riferimento "Minnarone") che separa nettamente due macro-blocchi:

1. **Percezione (locale):** adapter sorgente → pipeline audio/video/chat → percezioni testuali in un log append-only `perceptions.jsonl`. Gira con modelli leggeri on-device.
2. **Reazione (LLM in cloud):** un Senser osserva continuamente le percezioni e decide quando reagire; un Prompt Builder assembla un prompt cache-friendly con memoria a breve e lungo termine; un LLM genera il messaggio; un layer di "human-likeness" lo rende credibile (ritardo di battitura, dedup, possibilità di chiudere la conversazione); un Output Router lo consegna al canale giusto.

Per l'MVP il framework realizza lo **scenario pubblico streamer** (riferimento Minnarone) con l'adapter di **cattura a livello di sistema operativo**. Tutte le interfacce chiave (adapter sorgente, provider LLM, canale di output) nascono **astratte** così che gli scenari v2 (connettori per-piattaforma, modalità privata/whisper, auto-memoria, RAG, TTS) si innestino senza riscrivere il core. La differenza privata/pubblica è **una configurazione**, non due codebase.

---

## User Stories

### Setup e configurazione (sviluppatore/operatore)
1. Come sviluppatore, voglio definire l'identità dell'agente in un file `soul`, così che l'agente sappia chi è (nome, età, gusti, background).
2. Come sviluppatore, voglio definire fatti su interlocutori/canale in file `facts`, così che l'agente risponda a "chi sono io / chi sei tu / cosa hai studiato".
3. Come sviluppatore, voglio comporre un agente importando i moduli dell'SDK, così da costruire varianti personalizzate.
4. Come operatore, voglio avviare l'app di riferimento con un file di configurazione (soul, facts, modalità, adapter, provider), così da partire senza scrivere codice.
5. Come sviluppatore, voglio selezionare il provider LLM (Grok / DeepSeek / altro) da configurazione, così da bilanciare costo/latenza/qualità.
6. Come operatore, voglio impostare la modalità (pubblica/privata) da configurazione, così che lo stesso motore serva scenari diversi.

### Percezione
7. Come operatore, voglio che l'agente trascriva l'audio in tempo reale, così che "senta" cosa viene detto.
8. Come operatore, voglio che la trascrizione indichi chi parla (es. `streamer` vs audio di un video), così che l'agente non confonda le fonti.
9. Come operatore, voglio che l'agente descriva cosa appare a schermo, così che possa commentare ciò che vede (es. riconoscere un oggetto mostrato).
10. Come operatore, voglio che i messaggi di chat entrino nel flusso delle percezioni, così che l'agente reagisca anche al testo.
11. Come operatore, voglio che tutte le percezioni finiscano in un unico log temporizzato, così da poter ispezionare e debuggare cosa "ha percepito" l'agente.
12. Come operatore, voglio che la percezione giri in locale, così che i costi restino bassi e la latenza contenuta.

### Reazione e conversazione
13. Come streamer, voglio che l'agente commenti spontaneamente ogni tanto, così che la chat resti viva nei momenti morti.
14. Come streamer, voglio che l'agente risponda quando lo nomino o mi rivolgo a lui, così che sembri un partecipante reale.
15. Come streamer, voglio che l'agente continui lo scambio se parlo subito dopo un suo messaggio, così che la conversazione sia fluida.
16. Come viewer, voglio che l'agente conversi anche con gli utenti della chat, così che l'interazione sia broadcast-naturale.
17. Come operatore, voglio che l'agente legga più messaggi recenti e risponda alla persona giusta, così che la risposta sia pertinente in un contesto multi-utente.
18. Come operatore, voglio che l'agente integri ciò che vede a schermo nel messaggio, così che le risposte siano contestualmente ricche.
19. Come operatore, voglio che l'agente ricordi cosa è successo prima nella sessione, così che possa fare riferimenti coerenti.
20. Come operatore, voglio che l'agente risponda a domande sulla sua identità e sui fatti noti, attingendo alla memoria a lungo termine.
21. Come operatore, voglio che l'agente possa decidere di chiudere la conversazione quando non ha più nulla di utile da dire, così da non risultare insistente.

### Naturalezza (human-likeness)
22. Come operatore, voglio che l'agente impieghi un tempo plausibile a "scrivere" un messaggio, così da evitare risposte istantanee innaturali.
23. Come operatore, voglio che l'agente non invii messaggi quasi-identici tra loro, così da non sembrare ripetitivo.
24. Come operatore, voglio che l'agente eviti di fissarsi sullo stesso tema, vedendo i propri ultimi messaggi.
25. Come operatore, voglio che l'agente resista ai tentativi di prompt injection restando in personaggio.

### Costo, latenza, osservabilità
26. Come operatore, voglio che il prefisso stabile del prompt sia in testa, così da sfruttare il prompt caching e risparmiare.
27. Come operatore, voglio che, in caso di latenza anomala del provider, il turno venga saltato anziché inviare un messaggio stale.
28. Come operatore, voglio una dashboard che mostri percezioni, eventi/trigger, finestre di conversazione e messaggi inviati, così da monitorare e fare tuning.

### Scaffolding v2 (predisposizione, non implementazione)
29. Come sviluppatore, voglio che l'interfaccia adapter sorgente sia astratta, così da poter aggiungere connettori per-piattaforma (Twitch ricco, Zoom, Meet) senza toccare il core.
30. Come sviluppatore, voglio che il canale di output sia astratto, così da aggiungere whisper privato, TTS e azioni strutturate in seguito.
31. Come sviluppatore, voglio che la memoria esponga un punto di estensione per l'auto-aggiornamento cross-sessione, così da abilitarlo in v2.
32. Come operatore, voglio che esista un punto di configurazione per disclosure AI e retention dati, così da attivare il tooling privacy in v2.

---

## Implementation Decisions

### Architettura generale
- **Due macro-blocchi disaccoppiati** dal `perceptions.jsonl`: la percezione *scrive*, la reazione *legge in tail*. Questo disaccoppiamento è una decisione architetturale: i due lati non si chiamano direttamente.
- **Concorrenza:** loop asincroni indipendenti (`asyncio`) a cadenze diverse — Perceptor continuo, Senser ~0.5s, Summarizer periodico, Reactor su trigger. Coordinamento via il log + stato finestre in memoria.
- **Local-first per la percezione, cloud solo per l'LLM di reazione.** Ogni componente resta sostituibile.

### Contratto dati: `Perception`
Forma canonica di una percezione (una riga JSON nel log):
```json
{ "ts": 1781057651.73, "source": "audio", "type": "speech", "speaker": "streamer", "text": "..." }
```
- `source ∈ {chat, audio, video, event}`
- `type` dipende da source (es. `msg`, `speech`, `caption`, `join`)
- `speaker` opzionale (presente per chat/audio diarizzato)
- `ts` epoch secondi (float)

Questo contratto è il **giunto centrale** del sistema; va fissato per primo perché tutti i moduli ci dipendono.

### Moduli (deep modules) e interfacce
> Interfacce descritte come *contratto*, non come codice. Niente path/snippet che invecchiano.

- **PerceptionStore** — `append(perception)`, `read_since(ts) -> [Perception]`, `tail() -> iterator`. Append-only, ordinato per `ts`. Deep module su I/O semplice.
- **SourceAdapter (astratto)** — `start() -> stream handles per canale`, `stop()`. Impl. MVP: **OSCaptureAdapter** (mic + audio di sistema + screen). v2: connettori per-piattaforma.
- **AudioPerceiver** — consuma audio grezzo, produce `Perception(source=audio)`. Pipeline interna: VAD → ASR → speaker tagging. L'interfaccia esterna è solo "audio in → percezioni out".
- **VideoPerceiver** — consuma frame, produce `Perception(source=video, type=caption)`. Pipeline: sampling → hashing (salta frame ~uguali) → VLM caption.
- **ChatPerceiver** — consuma eventi chat, produce `Perception(source=chat)`.
- **Senser** — `evaluate(perceptions_recenti, window_state, now) -> Trigger | None`. Logica pura e deterministica: rileva menzioni (anche con nome storpiato → match fuzzy/fonetico), apre/aggiorna/chiude finestre di conversazione, gestisce idle timer e bandwagon. **Cuore del comportamento.**
- **Summarizer** — `summarize(perceptions) -> summary_text` via LLM, su cadenza periodica. Produce la memoria a breve termine.
- **Memory** — `load() -> {soul, facts}`; carica `soul`/`facts` da file e li rende come blocchi di prompt. Espone un hook `update(facts_delta)` **predisposto** per l'auto-memoria v2 (no-op in MVP).
- **PromptBuilder** — `build(stable_ctx, memory, summary, recent_msgs, perceptions, self_msgs, trigger) -> prompt`. Deterministico. Ordine: **prefisso stabile (cacheable)** → memoria permanente → situazione dinamica → **sezione trigger in coda** (massima salienza).
- **LLMProvider (astratto)** — `complete(prompt) -> message`. Impl.: OpenRouter verso Grok 4.3 e DeepSeek V4 Flash. Iperparametri (thinking basso) da config.
- **HumanLikeness** — `process(message, recent_self_msgs) -> {message, send_after_delay, drop?}`. Pura: stima typing delay, scarta duplicati/quasi-duplicati, interpreta `#end_conv`.
- **OutputRouter** — `route(message, mode) -> channel`. MVP: canale pubblico (chat). Astratto per whisper/TTS/azioni in v2.
- **Reactor** — orchestratore: lega Senser → PromptBuilder → LLMProvider → HumanLikeness → OutputRouter. Gestisce il salto-turno su latenza anomala.
- **Observability TUI** — visualizza percezioni, trigger/eventi, finestre, messaggi inviati. Sola lettura sullo stato.

### Struttura del prompt (decisione precisa)
1. **SYSTEM (stabile, cacheable):** ruolo, tono, regole generali, contesto piattaforma (emote), regole anti-disclosure/continuità.
2. **MEMORIA PERMANENTE:** `soul` + `facts`.
3. **SITUAZIONE ATTUALE (dinamica):** riassunto (Summarizer) → ultimi ~15 messaggi chat (con timestamp) → percezioni recenti (voce + schermo) → ultimi messaggi propri (anti-ripetizione) → formato risposta (incl. opzione `#end_conv`) → **sezione SITUAZIONE/trigger in coda**.

### Configurazione
Un unico file di config dichiara: `mode` (public/private), percorsi `soul`/`facts`, `adapter`, `llm_provider` + parametri, cadenze (`senser_interval≈0.5s`, `idle_interval≈150s`), `recent_chat_window≈15`, e i punti di estensione v2 (`disclosure`, `retention`) presenti ma inerti.

---

## Step-by-Step Implementation Plan

> Sequenza pensata per un dev junior. Ogni passo dice *cosa*, *perché ora*, *cosa tocca*, *cosa verificare*, *trappole*.

1. **Definisci il contratto `Perception` e il `PerceptionStore`.**
   - *Cosa:* tipo dato `Perception` + store append-only su `perceptions.jsonl` con `append`/`read_since`/`tail`.
   - *Perché ora:* è il giunto centrale; tutto il resto vi dipende.
   - *Verifica:* scrivendo N percezioni e rileggendole si ottiene lo stesso ordine per `ts`; `read_since` filtra correttamente.
   - *Trappola:* non bufferizzare in modo che il tail perda righe; ogni `append` deve essere durevole e atomico per riga.

2. **Implementa lo scaffolding delle interfacce astratte** (`SourceAdapter`, `LLMProvider`, `OutputRouter`, hook `Memory.update`).
   - *Perché ora:* fissare i contratti prima delle implementazioni evita riscritture e abilita i fake nei test.
   - *Verifica:* esistono implementazioni "null/fake" usabili nei test.
   - *Trappola:* non far trapelare dettagli di Twitch/SO nelle interfacce astratte (devono restare neutre per v2).

3. **Implementa `OSCaptureAdapter`** (mic + audio di sistema + screen).
   - *Perché ora:* è l'unica sorgente dell'MVP; sblocca le pipeline.
   - *Tocca:* `SourceAdapter`.
   - *Verifica:* produce stream audio e frame video grezzi su una macchina reale.
   - *Trappola:* permessi macOS per cattura schermo/audio di sistema; documentarli nel README.

4. **Implementa `ChatPerceiver`** (il più semplice: testo già pronto).
   - *Perché ora:* dà subito percezioni reali allo store senza dipendere dai modelli ML.
   - *Verifica:* eventi chat finti diventano `Perception(source=chat)` corrette nello store.

5. **Implementa `AudioPerceiver`** (VAD → ASR → speaker tagging).
   - *Perché ora:* è la fonte a più alto valore (il parlato).
   - *Verifica:* su una clip nota produce trascrizioni plausibili con `speaker` valorizzato; il VAD evita di trascrivere il silenzio.
   - *Trappola:* mis-tagging tra streamer e audio di un video (EC02) — la pipeline deve almeno distinguere la sorgente "operatore" dal resto.

6. **Implementa `VideoPerceiver`** (sampling → hashing → VLM caption).
   - *Perché ora:* completa la percezione multimodale.
   - *Verifica:* frame quasi identici vengono saltati (hashing); i frame nuovi producono caption sensate.
   - *Trappola:* non caption-are ad ogni frame (costo/latenza) — campionare.

7. **Implementa `Memory`** (load `soul`/`facts`; `update` come no-op).
   - *Perché ora:* serve al PromptBuilder; semplice e isolato.
   - *Verifica:* i file diventano blocchi di prompt; `update` non fa nulla ma esiste (hook v2).

8. **Implementa `PromptBuilder`.**
   - *Perché ora:* il Reactor non può funzionare senza; è deterministico, quindi facile da testare prima dell'integrazione.
   - *Verifica:* dato un set fisso di input, l'output ha l'ordine corretto e il prefisso stabile è byte-identico tra due build con stesso contesto stabile (requisito per il caching).
   - *Trappola:* qualsiasi variazione nel prefisso (anche un timestamp) rompe il prompt caching — tenere il dinamico fuori dalla testa.

9. **Implementa `LLMProvider`** (OpenRouter → Grok/DeepSeek).
   - *Perché ora:* trasforma il prompt in un messaggio.
   - *Verifica:* con un fake il Reactor funziona; con il provider reale ritorna un messaggio; thinking basso configurabile.
   - *Trappola:* gestire timeout/errore restituendo un segnale che il Reactor sa tradurre in "salta turno".

10. **Implementa `HumanLikeness`** (typing delay, dedup, `#end_conv`).
    - *Perché ora:* filtro finale prima dell'output; isolabile e puro.
    - *Verifica:* messaggi quasi-identici vengono scartati; il delay cresce con la lunghezza; `#end_conv` chiude la finestra.

11. **Implementa `OutputRouter`** (canale pubblico) e `Summarizer`.
    - *Perché ora:* chiudono il ciclo dati; il Summarizer popola la memoria a breve termine.
    - *Verifica:* il messaggio raggiunge il canale pubblico; il summary si aggiorna periodicamente.

12. **Implementa `Senser`** (trigger, finestre, idle, bandwagon).
    - *Perché ora:* è il cervello; va costruito quando tutti gli ingredienti che usa esistono, ma la sua logica è pura e testabile a parte.
    - *Verifica:* menzione (anche storpiata) → trigger; nessun trigger per X → idle trigger; molti messaggi simili → bandwagon senza LLM; finestre sovrapposte gestite.
    - *Trappola:* la cadenza 0.5s non deve accumulare lavoro; ogni tick deve essere veloce e idempotente.

13. **Implementa il `Reactor`** (orchestrazione + salto-turno).
    - *Perché ora:* unisce tutto.
    - *Verifica:* end-to-end con fake LLM su percezioni registrate; in caso di latenza simulata, il turno viene saltato (EC03).

14. **Implementa la `Observability TUI`.**
    - *Perché ora:* ultimo; legge stato già prodotto.
    - *Verifica:* mostra percezioni/trigger/finestre/messaggi in tempo reale.

15. **App di riferimento + file di config.**
    - *Perché ora:* impacchetta l'SDK nello scenario streamer pubblico.
    - *Verifica:* avvio da config; modalità pubblica funzionante; i punti v2 presenti ma inerti.

---

## Testing Decisions

**Cosa rende buono un test:** verifica il **comportamento esterno** osservabile dall'interfaccia del modulo, non i dettagli interni. I deep module qui sono pensati per essere testati dal loro contratto (input → output), così i test sopravvivono ai refactor interni (es. cambiare modello ASR non deve rompere i test del PerceptionStore o del Senser). Per i moduli che dipendono da modelli/servizi esterni si usano **fake/contract test**: si verifica che il modulo *usi* la dipendenza secondo il contratto, non l'output del modello reale.

Test richiesti **per tutti i moduli**:

| Modulo | Tipo | Cosa verifica (comportamento esterno) |
|---|---|---|
| PerceptionStore | unit | append/read_since/tail, ordinamento per ts, durabilità per riga |
| SourceAdapter / OSCaptureAdapter | contract | produce stream audio+video; `stop()` rilascia risorse (fake device dove possibile) |
| AudioPerceiver | contract (fake VAD/ASR) | audio→Perception, VAD salta il silenzio, `speaker` valorizzato |
| VideoPerceiver | contract (fake VLM) | hashing salta frame simili; frame nuovo→caption |
| ChatPerceiver | unit | evento chat→Perception corretta |
| Senser | unit | menzione (incl. storpiata)→trigger; idle→trigger; bandwagon senza LLM; gestione finestre sovrapposte |
| Summarizer | contract (fake LLM) | aggiorna il summary su cadenza; tollera input rumoroso |
| Memory | unit | load soul/facts→blocchi prompt; `update` no-op presente |
| PromptBuilder | unit | ordine sezioni corretto; prefisso stabile invariante (caching) |
| LLMProvider | contract (fake HTTP) | prompt→messaggio; timeout/errore→segnale "salta turno" |
| HumanLikeness | unit | dedup quasi-duplicati; delay ∝ lunghezza; `#end_conv` chiude |
| OutputRouter | unit | instrada al canale per `mode` |
| Reactor | integrazione (fake LLM) | ciclo end-to-end su percezioni registrate; salto-turno su latenza |
| Observability TUI | smoke | rende lo stato senza crash |

**Prior art:** nessuno (repo greenfield). I test del Reactor useranno un dataset di `perceptions.jsonl` registrato come fixture deterministica.

---

## Out of Scope

- **Connettori per-piattaforma** (Twitch ricco/IRC, Zoom, Meet, Teams) — solo l'interfaccia astratta, non le implementazioni (v2).
- **Modalità privata operativa** (whisper panel/overlay) — l'`OutputRouter` è astratto ma l'MVP implementa solo il canale pubblico (v2).
- **Voce / TTS** (v3) e **azioni/eventi strutturati** in output oltre al testo (v2).
- **Auto-aggiornamento agentico della memoria** — solo hook `Memory.update` inerte (v2).
- **RAG / knowledge base esterna** (v3).
- **Tooling privacy operativo** (disclosure/retention attivi) — solo punti di configurazione presenti (v2).
- **Eventi strutturati di piattaforma** come canale di percezione (v2).
- **UI web/overlay TS/Node** — l'MVP usa la TUI Python; il web arriva con la modalità privata (v2).

## Further Notes

- **Etica/disclosure:** il framework resta neutro ma deve esporre fin da subito i *punti* di configurazione (disclosure/retention) per non doverli retrofittare. Vedi SPECIFICATION §11.
- **"Gusto" dell'LLM:** dall'esperienza Minnarone, la struttura del prompt va curata a mano e iterata; il `PromptBuilder` è un modulo di prima classe e i suoi test sull'invarianza del prefisso stabile proteggono il risparmio da caching.
- **Tolleranza all'imperfezione:** trascrizioni rumorose e mis-tagging sono attesi (EC01/EC02); i moduli a valle devono degradare con grazia, non rompersi.
- **Target di qualità** (da SPECIFICATION §8): senser ~0.5s, idle ~150s, finestra chat ~15 msg, costo ~0.30 €/h (Grok) / ~0.03 €/h (DeepSeek), cache hit ~40%.
