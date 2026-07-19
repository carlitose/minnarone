# Guardrail per un bot Twitch pubblico

## Answer

**Domanda:** quali vincoli minimi servono per pubblicare il golden path Twitch
di Minnarone senza confondere requisiti tecnici, policy Twitch e scelte del
progetto?

**Data della ricerca:** 2026-07-18. Le fonti esterne sono documentazione e
termini ufficiali Twitch, risolti prima tramite Context7
(`/websites/dev_twitch_tv`) e poi verificati sulle pagine primarie indicate in
[Fonti](#fonti). Questo documento non è consulenza legale.

Il percorso `shadow` può restare il default pubblico. Il percorso `live` può
restare IRC e attended-only solo con permesso esplicito del broadcaster, perché
Minnarone usa un account bot dedicato in un canale di terzi: non coincide con
l'“installed chatbot” che opera usando l'account del broadcaster. IRC accetta
tecnicamente il User Access Token del bot senza codificare un grant per-canale,
ma questo non soddisfa da solo il modello di autorizzazione documentato per i
cloud chatbot. Il golden path deve quindi trattare il consenso out-of-band come
hard gate. Non è necessario migrare subito a EventSub/Send Chat Message API;
la migrazione diventerebbe necessaria per il Chat Bot Badge ufficiale e rende
l'autorizzazione del broadcaster verificabile tramite `channel:bot`.

La neutralità corrente sulla disclosure resta una scelta dell'operatore:
Twitch non impone un annuncio AI in ogni messaggio. Esiste però un limite di
policy: i bot non devono essere ingannevoli e il servizio deve rendere
comprensibili identità e scopo. Il prompt pubblico corrente forza la
non-disclosure anche quando `announce_ai: true`; non è quindi una
implementazione fedele della scelta dell'operatore e la negazione diretta di
essere un bot è un rischio di policy.

## Classificazione delle decisioni

| Area | Requisito tecnico Twitch | Policy di piattaforma | Scelta del progetto / esito |
|---|---|---|---|
| Trasporto | IRC richiede un User Access Token con `chat:read` e `chat:edit`; `NICK` deve essere il login lowercase dell'account che ha autorizzato il token. | Il bot resta soggetto a moderazione, blocco e richieste di interruzione. | IRC resta ammesso per il primo golden path; EventSub/API è un'evoluzione, non un blocker. |
| Account | Twitch permette a un cloud bot di agire con un account posseduto dal creatore; un account separato non è un obbligo tecnico generale. | Chiavi/account vanno protetti e le attività restano responsabilità del developer. | Conservare l'account bot dedicato già richiesto da `.env.example`; entrambi i token IRC devono corrispondere a `TWITCH_BOT_USERNAME`. |
| Autorizzazione canale | L'IRC corrente non richiede `channel:bot`, ma il modello Twitch per cloud chatbot richiede il permesso del broadcaster. Il badge/API con App Access Token richiede `user:write:chat` + `user:bot` del sender e `channel:bot` del broadcaster, salvo sender moderatore; il bot non può essere il broadcaster del canale. | Twitch distingue installed bot che opera con l'account del broadcaster e cloud bot che ottiene anche la sua autorizzazione; richiede inoltre di processare blocco/discontinue/opt-out. | Minnarone con account dedicato in un canale di terzi è trattato come cloud-like: l'allow-list non prova il permesso. Il live richiede consenso out-of-band registrato finché il trasporto IRC non esprime un grant per-canale; senza consenso il flusso termina a shadow. |
| Token | I token vanno validati all'avvio e ogni ora; un token invalido/revocato deve terminare le sessioni che lo usano. | Token, refresh token e client secret vanno trattati come password. | Mantenere token read/send separati in env e fail closed; la validazione attuale di sola non-vacuità non basta per dichiarare il live production-safe. |
| Rate | Account normale: 20 messaggi/30 s; 100/30 s se broadcaster/mod/VIP; inoltre 1 messaggio/s per canale se non broadcaster/mod/VIP. | Twitch vieta aggirare i limiti; al superamento può ignorare i messaggi per un'ora. | Conservare `1/min` e `20/ora`: sono limiti di prodotto più conservativi, non i limiti ufficiali Twitch. |
| Retention | Nessuna durata numerica universale è prescritta. | Log chat solo finché necessari; cancellazione su richiesta/revoca/riduzione scope; opt-out e privacy notice. | Non documentare `retention.perceptions_days` come funzionante: è inerte. Il tutorial deve mostrare artifact e cancellazione manuale finché manca enforcement. |
| Disclosure | Il Chat Bot Badge non compare con IRC/User Access Token; richiede Send Chat Message API + App Access Token e autorizzazioni specifiche. | Nessun obbligo trovato di annuncio AI per messaggio; sono vietati bot/pratiche ingannevoli e vanno chiariti identità e scopo del servizio. | Confermata neutralità/operator choice, con floor “non mentire”. L'operatore sceglie il meccanismo di disclosure; il flag deve però governare davvero il prompt pubblico. |

## Confronto con il repository

- `src/minnarone/config.py` offre `off`/`shadow`/`live`, allow-list,
  `1/min`, `20/ora`, soglia fallimenti 3 e token send separato. `live` richiede
  che il canale sia nell'allow-list.
- `src/minnarone/app.py` costruisce il sender e legge
  `TWITCH_SEND_OAUTH_TOKEN` solo in `live`; verifica però soltanto che il token
  non sia vuoto. Non verifica account, scope, scadenza o revoca all'avvio/ogni
  ora. `retention` è esplicitamente letto ma inerte.
- `src/minnarone/public_send.py` fa partire ogni sessione armata `live` in
  shadow, ricontrolla allow-list e budget, e degrada dopo fallimenti. I tentativi
  shadow consumano lo stesso budget: buona fedeltà della prova.
- `src/minnarone/live_tui.py` espone la superficie stretta di mutazione;
  `src/minnarone/dashboard_tui.py` richiede doppio `p` entro 3 secondi per
  promuovere e applica `k` immediatamente. Una nuova sessione riparte shadow.
- `.env.example` mantiene i segreti fuori dalla config e chiede
  `chat:read chat:edit`, coerente con l'IRC corrente. Il testo deve chiarire che
  username e token appartengono allo stesso account bot dedicato e aggiungere
  validazione/revoca; “read token” non significa che il runtime abbia già
  verificato lo scope.
- `src/minnarone/prompt.py` riceve `announce_ai`, ma il percorso
  `ORIGINAL_CHAT` usa sempre `_DISCLOSURE_HIDE`; `src/minnarone/prompts/rules.md`
  ripete “non rivelare bot/AI”. Poiché Twitch `public` usa `ORIGINAL_CHAT`, il
  flag non offre oggi la scelta dichiarata da README e
  `docs/SPECIFICATION.md`.
- `PerceptionStore` scrive un JSONL append-only. Le run conservano fino a 20
  directory completate e i prompt hanno retention count-based, ma non esiste
  enforcement di `perceptions_days`, richiesta di cancellazione o opt-out. Chat,
  prompt/eventi e riassunti possono duplicare gli stessi dati.
- `docs/SPECIFICATION.md` dichiara neutralità disclosure/privacy e controlli
  retention, ma questi ultimi sono v2; il golden path non deve presentarli come
  già operativi.

## Guardrail minimi per il golden path

### Account, autorizzazione e token

1. Usare un account Twitch dedicato al bot; non usare l'account personale
   dell'operatore. Verificare che `TWITCH_BOT_USERNAME` sia il login lowercase
   associato a entrambi i token IRC.
2. Chiedere solo gli scope richiesti dal trasporto corrente (`chat:read
   chat:edit` per l'IRC documentato) e non riutilizzare il token send in
   `off`/`shadow`.
3. Non salvare token in YAML, log, run artifact, screenshot o repository.
   Documentare rotazione e revoca.
4. Prima del live, validare almeno account, scope e scadenza; poi validare ogni
   ora. Su `401`, revoca, scope mancante o account mismatch: niente invio,
   degradare a shadow/stop e richiedere una nuova autorizzazione.
5. L'allow-list è difesa tecnica, non prova del permesso dello streamer. Per un
   account bot dedicato che opera in un canale di terzi, registrare il consenso
   out-of-band del broadcaster prima del live. Senza consenso il percorso
   termina a shadow. Il live resta attended-only e deve onorare immediatamente
   ban, block o richiesta di stop.

### Rate, shadow/live e kill-switch

1. Mantenere i default `1/min` e `20/ora`; distinguerli nei docs dai limiti
   Twitch. Non suggerire di “riempire” il bucket ufficiale.
2. Golden path progressivo: `off` -> shadow senza token send -> config live
   separata -> nuova sessione -> ispezione TUI -> doppio `p`.
3. `k` deve restare immediato, senza conferma; tornare live richiede sempre una
   nuova doppia conferma. Non promuovere via config, startup, reconnect o retry.
4. Conservare allow-list al config gate e al send gate, budget anche in shadow,
   nessuna coda/retry di messaggi stale e auto-degrado sui fallimenti.

### Retention

1. Dire chiaramente che shadow legge e conserva dati anche se non pubblica
   messaggi. Elencare `perceptions.jsonl`, prompt capture, run events e
   riassunti come artifact potenzialmente contenenti chat.
2. Non usare `perceptions_days: 7`/`null` come promessa: il campo è inerte.
   Documentare una durata scelta per lo scopo e una cancellazione manuale delle
   run fino a quando il runtime non la applica.
3. Offrire un percorso per delete/opt-out e cancellare copie derivate quando
   richiesto, quando l'autorizzazione viene revocata/ridotta o quando i dati non
   servono più. Non pubblicare database di log chat.

### Disclosure

1. L'operatore sceglie se e come dichiarare l'uso di AI; non serve un annuncio
   in ogni messaggio e il badge Twitch non è disponibile col trasporto attuale.
2. Qualunque scelta deve rendere comprensibili identità e scopo del servizio
   nel contesto (per esempio account/profilo bot, descrizione del canale o
   risposta esplicita) e non deve ordinare al modello di negare il vero quando
   viene chiesto direttamente.
3. Prima di descrivere `announce_ai` come guardrail, farlo valere anche per
   `ORIGINAL_CHAT` e rimuovere la regola duplicata che lo contraddice, oppure
   documentarlo onestamente come non supportato nel percorso pubblico.

## Impatto sui ticket 16–18

- **16:** il prototipo onboarding può arrivare a shadow; deve verificare account
  dedicato, identità token, consenso broadcaster, artifact/retention e scelta
  disclosure senza promuovere live.
- **17:** README/golden path devono essere shadow-first, distinguere limiti
  Twitch da budget Minnarone, non promettere badge o retention attiva e isolare
  il live in una checklist attended-only.
- **18:** riallineare `.env`/guida/runtime su token live, aggiungere o schedulare
  validazione token, correggere la semantica `announce_ai` per `ORIGINAL_CHAT` e
  rendere visibile l'inerzia della retention.

## Unknowns

- Twitch non definisce una formula unica per disclosure AI né chiarisce se una
  specifica risposta evasiva costituisca sempre “deceptive practice”; la
  valutazione dipende dal contesto. È però prudente non imporre una falsa
  negazione.
- Twitch non prescrive un numero di giorni per i log: deve derivare dallo scopo,
  dalla privacy notice e dalla normativa applicabile.
- Non è stata svolta un'analisi legale GDPR o per giurisdizione.

## Fonti

Tutte consultate il 2026-07-18.

- [Twitch Chat & Chatbots](https://dev.twitch.tv/docs/chat/) — definizione dei
  chatbot, interfacce preferite, rate limit, badge e identità chat.
- [Authenticating Chatbots](https://dev.twitch.tv/docs/chat/authenticating/) —
  User/App Access Token e scope `user:*`/`channel:bot`.
- [Send Chat Message API](https://dev.twitch.tv/docs/api/reference/#send-chat-message)
  — autorizzazione User/App token e vincoli sender/broadcaster.
- [Authenticating with the Twitch IRC server](https://dev.twitch.tv/docs/irc/authenticate-bot/)
  — `chat:read`, `chat:edit`, `PASS` e corrispondenza `NICK`/account.
- [Authentication](https://dev.twitch.tv/docs/authentication/) — trattamento
  dei token come password e cause di invalidazione.
- [Validating Tokens](https://dev.twitch.tv/docs/authentication/validate-tokens/)
  — obbligo di validazione all'avvio e ogni ora, `401` e terminazione sessione.
- [Revoking Access Tokens](https://dev.twitch.tv/docs/authentication/revoke-tokens/)
  — endpoint ufficiale di revoca.
- [Twitch CLI token command](https://dev.twitch.tv/docs/cli/token-command/) —
  generazione, scope e revoca tramite CLI.
- [Twitch Developer Services Agreement](https://legal.twitch.com/en/legal/developer-agreement/)
  — chiavi, sicurezza, data retention, cancellazione/opt-out, identità/scopo e
  divieto di bot ingannevoli. La pagina riporta “Last modified 12/04/2024”.

## Next Step

I ticket 16–18 possono procedere usando questa matrice. Per il trasporto IRC con
account bot dedicato, il consenso out-of-band del broadcaster è il hard gate
pubblico; un futuro percorso App Token/Send Chat Message API potrà renderlo
verificabile tramite `channel:bot`.
