# YouTube Live per Minnarone

## Type

Wayfinding spec

## Status

Active

## Destination

Portare su YouTube Live il percorso progressivo già disponibile per Twitch:

1. chat-only in `shadow`, senza invio pubblico;
2. percezione locale di chat, audio e video in full shadow;
3. invio nella live chat solo dopo autenticazione, autorizzazione, rehearsal,
   promozione manuale in TUI e con kill-switch immediato.

Assunzione di destinazione: Minnarone osserva una live YouTube e partecipa alla
sua chat come co-host. Non crea né trasmette una live via RTMP e non amministra
il broadcast dello streamer. Una sessione continua a osservare una sola
piattaforma e una sola live.

## Decisions So Far

- YouTube Live è una nuova verticale di piattaforma, non una variante
  configurativa di Twitch. Il core resta invariato dietro `SourceAdapter` e
  continua a ricevere soltanto `RawEvent` per `chat`, `audio`, `video` ed
  eventualmente `event` ([source.py](../../src/minnarone/source.py)).
- La parità desiderata è progressiva e shadow-first. I gate Twitch esistenti —
  allow-list, budget conservativi, sessione live inizialmente in shadow,
  promozione manuale, kill-switch, fail-closed sulle credenziali e niente retry
  di messaggi stale — sono il floor da preservare, non dettagli da copiare
  ciecamente.
- `MergingSourceAdapter`, perceiver, store, reactor, prompt construction e
  code limitate sono riusabili. Chat discovery/auth, lettura chat, cattura
  media e invio sono bordi di piattaforma separati.
- L'implementazione Twitch non è oggi una base neutra: config, normalizzazione
  canale, URL Streamlink, sender, router e policy pubblica dipendono
  esplicitamente da Twitch. Prima di riusare occorre scegliere un'interfaccia
  piattaforma-neutrale con un prototipo, evitando un secondo copia-incolla.
- La specifica corrente rende estendibili i connettori (`FR06`, `FR07`,
  `NFR08`) e condivide la pipeline di percezione, ma non nomina ancora YouTube.
  La decisione architetturale definitiva e l'aggiornamento della feature spec
  saranno registrati dopo ricerca e prototipo, non anticipati in questa mappa.
- La documentazione ufficiale corrente, risolta con Context7 come
  `/websites/developers_google_youtube`, conferma che la YouTube Live Streaming
  API appartiene alla YouTube Data API e governa risorse live. Il contratto
  verificato è registrato nel
  [report del ticket 01](../research/youtube-live-platform-contract.md).
- Il target canonico è un `video_id` esplicito. `activeLiveChatId` è effimero e
  viene risolto con `videos.list`; la discovery per channel/search non è il
  default e una pagina live persistente non può retargettare una sessione in
  silenzio.
- La lettura chat preferita è `liveChatMessages.streamList` con API key, resume
  token e identità stabile `(liveChatId, messageId, authorChannelId)`; REST
  `list` resta un fallback che deve rispettare `pollingIntervalMillis`.
- Il send richiede OAuth utente `youtube` o `youtube.force-ssl`. La capability
  di scrittura resta fisicamente separata e assente da read/shadow. L'identità
  pubblica scelta è un canale/Brand Account dedicato a Minnarone; l'effettiva
  selezione OAuth resta da osservare prima del sender live.
- Il ticket 03 ha registrato la
  [decisione identità + read smoke](youtube-live-identity-read-decision.md):
  target esplicito di terzo autorizzato, disclosure AI, retention aggregata,
  API key locale senza OAuth/write e permanenza in shadow. La smoke bounded ha
  osservato discovery, pacing, 72 eventi testuali e una normalizzazione in
  memoria senza conservare contenuti o identità della chat.
- Le quote correnti separano `search.list` (100 chiamate/giorno) dal bucket
  combinato predefinito (10.000 unità/giorno); `videos.list` costa 1. I costi
  numerici dei metodi live-chat non sono pubblicati e restano `unknown`.
- Le API ufficiali non espongono PCM/frame del playback. La sorgente media
  scelta è quindi il player Chrome visibile gestito dall'operatore: il blocco
  top-level `os_capture` cattura l'audio di sistema tramite `soundcard` e il
  monitor selezionato tramite `mss`. Non servono Streamlink, yt-dlp, manifest,
  FFmpeg/PyAV, estensioni Chrome, CDP o `tabCapture`. La
  [decisione Chrome + OS capture](youtube-live-chrome-os-capture-decision.md)
  sostituisce il precedente gate sulla selezione della sorgente media senza
  formulare affermazioni legali o di approvazione della piattaforma.
- Il [prototipo offline del ticket 02](../prototypes/youtube-live-adapter-boundary.md)
  conferma che `SourceAdapter`, `MergingSourceAdapter`, `AudioChunk`,
  `VideoFrame`, perceiver e code restano invariati. YouTube discovery/chat
  restano specifici. La sua
  [decisione adapter/media](youtube-live-adapter-media-decision.md) rimane
  evidenza storica e continua a escludere URL arbitrari, shell string e
  generalizzazione nominale di config/classi Twitch; la scelta successiva
  Chrome + OS capture evita di introdurre un nuovo downloader media.
- Nel repository non esistono ancora config, adapter, test, esempi o guide
  YouTube Live. Il worktree era pulito all'inizio di questa mappatura.

## Not Yet Specified

- Selezione effettiva del canale/Brand Account dedicato durante OAuth e identità
  stabile per il self-echo filter; l'API insert non permette di scegliere
  l'autore nel body e la smoke API-key del ticket 03 non esercita OAuth.
- Costo numerico corrente di `liveChatMessages.list`, `streamList` e `insert`,
  limite numerico del testo e durata dei cursor, che le pagine ufficiali non
  stabiliscono.
- Interpretazione di compliance per output LLM derivato dalla chat e livello di
  consenso espresso richiesto prima di ogni insert; la promozione TUI di
  sessione non è ancora prova sufficiente.
- Precisione operativa della cattura full-monitor e scelta concreta di monitor,
  permesso Screen Recording e routing audio/BlackHole sulla macchina di
  acceptance; se il monitor intero non basta, `tabCapture` richiederà un
  prototipo separato.
- Contratto YouTube-specifico per sender, `PublicSendPolicy`, router, stato TUI,
  run events e token guard; il ticket 02 ha escluso una generalizzazione
  preventiva insieme al media.
- Disclosure, consenso, retention e cancellazione applicabili alla live target;
  nessun campo inerte deve essere presentato come protezione attiva.

## Out of Scope

- Creazione, scheduling, transizione o ingest RTMP di broadcast YouTube, salvo
  la sola discovery read-only necessaria a trovare la live chat attiva.
- Upload VOD, analytics, monetizzazione, moderazione, ban, Super Chat,
  membership, sottotitoli, traduzione o EventSub-equivalenti non necessari al
  primo tracer bullet.
- Bypass di DRM, paywall, live private/unlisted non autorizzate, membership,
  age gate o restrizioni geografiche.
- Cross-posting Twitch↔YouTube, aggregazione multi-chat o una singola sessione
  Minnarone attiva contemporaneamente su più piattaforme/live.
- Invio pubblico senza consenso/autorità adeguata, operazione unattended o
  allentamento di shadow default, allow-list, code limitate, redazione segreti,
  limiti artifact, anti-injection e kill-switch.
- Implementazione runtime in questo passaggio Wayfinder.

## Frontier / Blocking Edges

- **Contratto piattaforma — evidence complete:** ticket 01 ha prodotto il
  [report ufficiale e datato](../research/youtube-live-platform-contract.md).
  Le conclusioni su chat restano correnti; la sezione media è evidenza storica
  precedente alla scelta Chrome + OS capture.
- **Confine adapter/media — evidence complete:** ticket 02 ha confrontato i
  reader specifici con una sorgente tipizzata in un
  [prototipo solo fake](../prototypes/youtube-live-adapter-boundary.md) e ha
  registrato la [decisione allora candidata](youtube-live-adapter-media-decision.md).
  Il confine interno validato resta utile, mentre la sorgente concreta è ora
  definita dalla
  [decisione Chrome + OS capture](youtube-live-chrome-os-capture-decision.md).
- **Identità e prova reale read-only — evidence complete:** ticket 03 ha
  registrato la
  [decisione sanitizzata](youtube-live-identity-read-decision.md) e osservato
  una smoke API-key di 60 secondi senza send né raw artifact. L'identità OAuth
  effettiva resta un gate del sender, non del reader shadow.
- **Chat-only shadow — ready, prerequisites 01, 02 e 03 complete:** ticket 04 è
  il prossimo tracer bullet di produzione, osservabile e senza send.
- **Full multimodal shadow — blocked only by 04:** ticket 05 compone la chat API
  con audio di sistema e video del monitor catturati localmente dal player
  Chrome visibile; la verifica hardware reale resta nel ticket 08 HITL.
- **Safety output pubblico — blocked by 03 e 04:** ticket 06 porta la policy in
  shadow su YouTube senza una chiamata di send reale.
- **Sender live — blocked by 06:** ticket 07 aggiunge l'unico bordo che può
  pubblicare, dietro OAuth validato e tutti i gate.
- **Evidenza operativa — blocked by 05 e 07, HITL:** ticket 08 esegue prima
  shadow e poi, solo se autorizzato, una live bounded e attended.

## Ticket Plan

- **01 — research — AFK — evidence complete:** contratto ufficiale YouTube
  Live per discovery, chat, OAuth, quote, lifecycle, policy e media registrato
  in [`youtube-live-platform-contract.md`](../research/youtube-live-platform-contract.md).
- **02 — prototype — AFK — evidence complete:** confronto offline in
  [`youtube-live-adapter-boundary.md`](../prototypes/youtube-live-adapter-boundary.md)
  e decisione storica in
  [`youtube-live-adapter-media-decision.md`](youtube-live-adapter-media-decision.md),
  successivamente superata per la scelta della sorgente media dalla
  [decisione Chrome + OS capture](youtube-live-chrome-os-capture-decision.md).
- **03 — grilling/decision + smoke — HITL — evidence complete:** target di
  terzo autorizzato, identità dedicata, capability split e smoke bounded sono
  registrati nella
  [decisione identità + read smoke](youtube-live-identity-read-decision.md).
- **04 — task — AFK — ready, prerequisites 01, 02 e 03 complete:** implementare
  il golden path YouTube chat-only shadow con config, adapter, test, esempio e
  guida.
- **05 — task — AFK — blocked by 04:** implementare audio/video YouTube full
  shadow componendo chat API, audio di sistema e monitor del player Chrome
  visibile tramite l'`os_capture` esistente, senza duplicare i perceiver né
  introdurre download/decodifica diretta del media YouTube.
- **06 — task — AFK — blocked by 03 e 04:** rendere la safety policy pubblica
  riusabile e osservabile per YouTube, ancora senza send di rete.
- **07 — task — AFK — blocked by 06:** implementare sender live chat, OAuth
  lifecycle, self-echo e failure handling dietro fake di test e gate completi.
- **08 — task/acceptance — HITL — blocked by 05 e 07:** eseguire bounded shadow
  e una eventuale live autorizzata; produrre audit sanitizzato e decisione di
  avanzamento, revisione o stop.

## Next Review

Il prossimo edge è il ticket 04 AFK: implementare e testare l'adapter YouTube
chat-only shadow usando fake deterministici, poi usare la API key soltanto per
una smoke locale bounded e sanitizzata. Non includere media, OAuth write o send
nel ticket 04. Il ticket 05 resta dependency-blocked soltanto dal ticket 04;
l'osservazione di monitor e audio reali resta riservata all'acceptance HITL del
ticket 08.
