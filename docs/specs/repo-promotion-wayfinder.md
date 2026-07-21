# Promozione pubblica del repo Minnarone

## Type

Wayfinding spec

## Status

Active

## Destination

Minnarone è conosciuto nelle comunità rilevanti (dev AI/agenti, streaming/Twitch,
tech italiana): il repo ha una vetrina GitHub curata, un asset demo che mostra il
progetto in 30 secondi, ed è stato lanciato sui canali scelti con messaggi adatti a
ciascuno. Il successo è misurato con le metriche decise nel grilling 01 (es. stelle,
clone, issue/PR esterne) — non "viralità" generica.

## Decisions So Far

- **Repo pubblico** — verificato 2026-07-21 (`gh repo view`: visibility PUBLIC,
  1 stella). Il flip del piano [public-release](public-release-wayfinder.md)
  è avvenuto; il ticket 05 di quella mappa risulta però ancora tra gli aperti
  (da riconciliare, vedi Next Review).
- **Disclaimer di non-affiliazione con Enkk** — richiesto esplicitamente da
  Enrico Mensa (chat LinkedIn 2026-07-21) e aggiunto lo stesso giorno in coda
  alla sezione "Origin and credits" di `README.md` e `README.it.md`. **Vincolo
  duro per la promozione**: ogni messaggio pubblico può citare l'ispirazione
  ("inspired by Enkk's video") ma non deve mai suggerire affiliazione,
  endorsement o coinvolgimento suo; Enkk non vuole ricevere mail o contatti
  in merito al progetto.
- **README in inglese + README.it.md** — già fatto (public-release ticket 08).
  Il materiale di lancio internazionale può linkare direttamente il README.
- **Licenza MIT, gitleaks pulito, pytest verde su main** — prerequisiti di
  credibilità già chiusi dal piano public-release.
- **Link "Buy me a coffee" (PayPal)** già nel README — la monetizzazione soft
  esiste, non serve deciderla ora.
- **Obiettivo: utenti reali** (grilling 01, 2026-07-21) — successo a 30 giorni
  = persone che installano il framework e aprono issue/domande, non stelle.
- **Pubblico primario: dev AI/agenti** (grilling 01, 2026-07-21) — pitch
  tecnico "framework per agenti con percezione multimodale live, tutto in
  locale (anche su GPU da 4 GB)". Streamer e community italiana restano
  pubblici secondari.
- **Canali: HN (Show HN), Reddit, X/LinkedIn** (grilling 01, 2026-07-21) —
  lobste.rs e community italiane dedicate non selezionati.
- **Tempo di presidio: ~1h/giorno nelle 72h post-lancio** (grilling 01,
  2026-07-21). Implicazione: Show HN senza presidio real-time è rischioso —
  il research 04 deve raccomandare giorno/ora compatibili (es. weekend) e il
  launch kit deve includere risposte-tipo pronte per le domande prevedibili.
- **Tono: tecnico + gancio narrativo** (grilling 01, 2026-07-21) — una riga di
  apertura sulla storia ("nato generalizzando un bot che passava un Turing
  test nella chat di Twitch"), poi solo sostanza tecnica. Compatibile col
  vincolo di non-affiliazione.
- **Tutto il materiale pubblico sempre in inglese** (autore, 2026-07-21) —
  description, topics, post di lancio, risposte: inglese ovunque, anche su
  X/LinkedIn.
- **Demo e superficie runtime in inglese** (autore, 2026-07-21): la demo
  (ticket 03) e l'esperienza del nuovo utente devono essere in inglese.
  **Già soddisfatto**: il ticket
  [public-release/09](../tickets/public-release/done/09-task-localize-cli-messages.md)
  era già stato implementato e mergiato su main con la PR #43
  ("refactor: localize operator surfaces in English", 2026-07-19). Verifica
  2026-07-21 su origin/main: nessuna stringa italiana in print/raise/log
  user-facing; restano solo docstring e commenti interni in italiano (fuori
  scope). Resta da garantire che il *run* della demo percepisca contenuto in
  inglese e produca reazioni in inglese (config del run, ticket 03).
- **Description, topics e release GitHub applicati** (ticket 02, 2026-07-21):
  description "Framework for AI agents that perceive live multimodal context
  (audio, video, chat) and react in real time - fully local"; topics
  `ai-agents, multimodal, twitch, llm, llamacpp, speech-recognition,
  speaker-diarization, python`; release `v0.1.0` pubblicata. La social preview
  1280×640 in `docs/assets/minnarone-social-preview.jpg` è caricata e verificata
  dalla pagina pubblica tramite `og:image` (hash remoto uguale al locale).

- **Mappa canali completata** (research 04, 2026-07-21) →
  [repo-promotion-channels.md](repo-promotion-channels.md) con regole citate,
  formati e calendario raccomandato (Day 1 Show HN domenica mattina UTC + X;
  Day 2 r/LocalLLaMA + LinkedIn; Day 3 r/opensource o r/SideProject; week 2
  r/MachineLearning). r/Python e r/Twitch fuori dal lancio standard.
- **Asset demo completato** (ticket 03, 2026-07-21) → GIF inglese di 30 secondi
  in [`docs/assets/minnarone-tui-demo.gif`](../assets/minnarone-tui-demo.gif),
  0,98 MB, inserita sotto la hero del README. Mostra chat, trascrizione, video e
  memoria che portano a una nuova reazione shadow; il pannello della reazione è
  evidenziato per quattro secondi. L'autore ha accettato esplicitamente gli
  handle e i messaggi provenienti dalla chat Twitch pubblica mostrata nel run.
- **Launch kit approvato** (ticket 05, 2026-07-21) →
  [repo-promotion-launch-kit.md](repo-promotion-launch-kit.md) contiene copy
  inglese approvato per Show HN, X, LinkedIn e r/SideProject, risposte FAQ e
  calendario 25–28 luglio. r/LocalLLaMA resta opzionale perché richiede copy
  scritto personalmente dall'autore.
- **Lancio preparato** (ticket 06, 2026-07-21) →
  [repo-promotion-launch-log.md](repo-promotion-launch-log.md) registra baseline
  pre-lancio, gate Day 0, URL dei post, presidio e metriche. Il ticket resta
  aperto fino alle pubblicazioni e ai checkpoint a 72 ore e 30 giorni.

## Not Yet Specified

- Nessuna decisione di lancio residua: asset, canali, copy e timing sono
  approvati. Restano esecuzione e misurazione del ticket 06.

## Out of Scope

- Contattare Enkk o chiedergli condivisioni/endorsement (esplicitamente
  escluso da sua richiesta).
- Paid advertising di qualsiasi tipo.
- Rebranding, rinomina del progetto, sito dedicato.
- Traduzione dei docs operativi in inglese (resta fuori come nel piano
  public-release).

## Frontier / Blocking Edges

- ~~**Vetrina GitHub spoglia**~~: risolto — description, topics, release e
  social preview pubblica sono presenti e verificati (ticket 02 chiuso
  2026-07-21).
- ~~Obiettivi/pubblico/canali non decisi~~: risolto (grilling 01 chiuso,
  2026-07-21 — vedi Decisions So Far).
- ~~Runtime/TUI in italiano~~: risolto — già mergiato su main con la PR #43
  (public-release/09, 2026-07-19); verificato su origin/main il 2026-07-21.
- ~~**Nessun asset demo**~~: risolto — GIF inglese di 30 secondi sotto la hero
  del README, con percezioni multimodali e reazione shadow evidenziata (ticket
  03 chiuso 2026-07-21).
- ~~Regole di self-promotion dei canali non verificate~~: risolto (research
  04 chiuso 2026-07-21) → [repo-promotion-channels.md](repo-promotion-channels.md).
  Vincoli emersi: r/Python vietato per showcase AI (solo thread mensile),
  r/Twitch solo previa modmail, Show HN domenica mattina UTC all'inizio della
  finestra di presidio.

## Ticket Plan

- 01 — grilling — Obiettivi, pubblico primario, canali, tono e budget di tempo
  → decisioni registrate nella mappa.
- 02 — task — Vetrina GitHub: description, topics, About, social preview image,
  eventuale release taggata v0.x → completato; repo presentabile da link nudo.
- 03 — task — Asset demo (GIF/clip del TUI o replay, screenshot curati) →
  completato; asset riusabile nel README e nei post di lancio.
- 04 — research — Mappa canali: regole di self-promotion, formato vincente ed
  esempi riusciti per HN/Reddit/lobste.rs/X/LinkedIn/community italiane, con
  fonti citate → tabella canale→regole→formato→giorno/ora consigliati.
- 05 — task — Launch kit: testo per ciascun canale scelto (Show HN, post
  Reddit, thread X/LinkedIn, post community IT), coerente col vincolo
  non-affiliazione → completato; testi e calendario approvati dall'autore.
- 06 — task — Lancio coordinato e presidio: pubblicazione secondo il
  calendario, risposta a commenti/issue nelle prime 48-72h → lancio eseguito,
  esiti registrati nella mappa.
- 07 — task (opzionale, post-lancio) — Contenuto di follow-up: blog post o
  video tecnico su un aspetto distintivo (es. diarization streamer/altro,
  llama.cpp multimodale su GPU piccole) → contenuto pubblicato.

## Next Review

Eseguire il gate Day 0 del ticket 06 sabato 2026-07-25 alle 18:00 CEST. Se
account, composer e disponibilità sono confermati, pubblicare Show HN e X
domenica 26, LinkedIn lunedì 27 e r/SideProject martedì 28, registrando subito
gli URL nel launch log. Prossime review metriche: 72 ore il 29 luglio,
preservation snapshot l'11 agosto e verdetto a 30 giorni il 25 agosto.

Housekeeping non bloccante: riconciliare
`docs/tickets/public-release/05-task-flip-visibility.md` (il flip è avvenuto —
spostarlo in done/ dopo la verifica post-flip descritta lì).
