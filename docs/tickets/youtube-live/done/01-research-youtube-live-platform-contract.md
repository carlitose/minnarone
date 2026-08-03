---
ticket_schema: 1
ticket_id: "01"
execution_mode: AFK
blocked_by: []
---

# Ricercare il contratto corrente di YouTube Live

## Parent Spec

[youtube-live-wayfinder.md](../../../specs/youtube-live-wayfinder.md)

## Question / Outcome

Qual è il contratto ufficiale e corrente che Minnarone deve rispettare per
scoprire una live YouTube, leggerne la chat, ottenere legalmente il media e,
in seguito, pubblicare in chat con un'identità autorizzata e quote prevedibili?

Output atteso: `docs/research/youtube-live-platform-contract.md`, datato, con
fonti primarie, matrice requisito piattaforma/scelta progetto, decisioni
supportate ed unknowns residui.

## What to Build

Una ricerca read-only che copra la destinazione e tutti i blocking edge del
parent spec. Usare Context7 prima delle fonti ufficiali Google/YouTube e la
documentazione corrente dei tool media candidati. Non scrivere runtime e non
aprire un flusso OAuth reale.

Sezioni coperte: `Destination`, `Not Yet Specified` e primo edge della
`Frontier / Blocking Edges`.

## Evidence Required

- Discovery da URL/video ID/channel ID fino a broadcast e live chat attivi,
  inclusi stati scheduled/live/complete e assenza o sostituzione della chat.
- Contratto live chat read: endpoint corrente, cursori/page token o stream,
  pacing indicato dal server, ordinamento, dedup, delete/retract, errori e retry.
- Contratto live chat write: endpoint, identità effettiva, scope OAuth,
  autorizzazione del canale, limiti testo, quota e failure semantics.
- OAuth: tipi client ammessi, browser/loopback flow locale, refresh, revoca,
  scadenza, storage, separazione capability read/send e indisponibilità dei
  service account dove applicabile.
- Costi quota ufficiali, quota giornaliera/default se documentata, backoff e
  comportamento richiesto quando quota o rate vengono esauriti.
- Policy e minimum functionality rilevanti a bot, disclosure, consenso,
  retention/cancellazione e contenuti chat; distinguere requisiti ufficiali da
  scelte conservative di Minnarone.
- Disponibilità o assenza del media playback nelle API Google e contratto
  corrente di Streamlink/altro tool per live pubbliche, senza bypass.

## Acceptance Criteria

- [ ] Ogni affermazione normativa o API ha una fonte ufficiale e una data di
  consultazione; fonti secondarie sono solo corroboranti.
- [ ] Il report separa con chiarezza Data/Live Streaming API, playback media e
  strumenti terzi, senza assumere che una singola API fornisca tutto.
- [ ] Sono registrati scope, quote/costi e pacing esatti oppure marcati
  `unknown` con la prova che la documentazione non li stabilisce.
- [ ] Il report propone un identificatore target canonico e una capability
  split read/shadow/live, motivandoli con evidenza.
- [ ] Sono evidenziati breaking external contracts, vincoli irreversibili e
  attività che richiedono credenziali o consenso umano.
- [ ] La mappa Wayfinder viene aggiornata con unknown risolti, nuove decisioni
  e stato del ticket 02; le decisioni durevoli vengono instradate a `to-spec`.

## Frontier

Ready. È l'unico ticket eseguibile senza dipendenze e sblocca 02 e 03.

## Step-by-Step Implementation Plan

1. Risolvere con Context7 la documentazione YouTube ufficiale usando la domanda
   completa; consultare poi solo le pagine primarie necessarie a colmare gap.
2. Costruire una matrice discovery/chat read/chat write/OAuth/quota/media/policy
   con fatto, fonte, impatto Minnarone e livello di certezza.
3. Confrontare il contratto con `SourceAdapter`, config, merge/backpressure,
   Twitch media, token guard, public send e operator workflow esistenti.
4. Scrivere il report, classificare le scelte reversibili e gli unknown e
   proporre i criteri che il prototipo 02 deve falsificare.
5. Aggiornare la mappa senza implementare codice o creare credenziali.

## Testing Plan

Verificare manualmente che ogni URL sia ufficiale e raggiungibile, che versioni
e date non siano contraddittorie e che tutte le righe della matrice abbiano
fonte o `unknown`. Rieseguire i link/check documentali disponibili nel repo.

## Out of Scope

- Codice di produzione o prototipo eseguibile.
- Creazione di un progetto Google Cloud, consent screen o token OAuth.
- Chiamate API reali, cattura media o invio in live chat.
- Progettazione di broadcast RTMP, upload, analytics o moderazione.

## Completion Evidence

[YouTube Live platform contract](../../../research/youtube-live-platform-contract.md)
