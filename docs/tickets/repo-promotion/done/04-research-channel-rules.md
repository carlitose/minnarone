# 04 — Research: mappa canali, regole di self-promotion, formati vincenti

## Parent Spec

[repo-promotion-wayfinder.md](../../specs/repo-promotion-wayfinder.md)

## Type

research

## Outcome

Una tabella canale → regole di self-promotion → formato consigliato → timing,
con fonti citate, per i canali candidati: Hacker News (Show HN), Reddit
(subreddit da individuare: es. r/LocalLLaMA, r/MachineLearning, r/Python,
r/Twitch, r/ItalyInformatica), lobste.rs, X, LinkedIn, community italiane
(Discord/Telegram tech).

## Acceptance Criteria

- [x] Per ogni canale: regole ufficiali di self-promo citate (link), formato
      del post che funziona (titolo, demo, testo), e rischi (ban, shadowban,
      cooldown tra post).
- [x] Almeno 2-3 esempi di lanci riusciti di progetti simili (framework AI/
      agent open source) con cosa hanno fatto bene.
- [x] Raccomandazione di calendario: ordine dei canali e spaziatura (non tutto
      lo stesso giorno), giorno/ora per HN.
- [x] Nota esplicita su come citare l'ispirazione a Enkk in ogni canale senza
      violare il vincolo di non-affiliazione.

## Esito (2026-07-21)

Ricerca completata con fonti primarie (regole lette dai canali il 2026-07-21).
Deliverable: [repo-promotion-channels.md](../../specs/repo-promotion-channels.md).
Punti chiave: Show HN domenica mattina UTC col post all'inizio della finestra
di presidio; r/LocalLLaMA canale Reddit primario (autorìa dichiarata, testo
non generato da LLM); **r/Python vietato per showcase AI** (solo thread
mensile); **r/Twitch solo previa modmail**; su X e LinkedIn video nativo
prima, link nel secondo post/primo commento; mai sollecitare voti.

## Blocked By

- None — può partire subito, in parallelo a 01-03.

## Frontier

Scrivere testi (05) senza conoscere le regole dei canali rischia rimozioni e
brucia il lancio: questa ricerca è l'ultimo prerequisito del launch kit.

## Work Plan

1. Ricerca web sulle regole di self-promotion di ciascun canale candidato
   (guidelines ufficiali di Show HN, wiki/rules dei subreddit, lobste.rs tags).
2. Cercare post-mortem/case study di lanci open source riusciti su HN/Reddit
   (es. "Show HN launch lessons") e distillare i pattern.
3. Compilare la tabella e la raccomandazione di calendario.
4. Salvare l'output in `docs/specs/repo-promotion-channels.md` (o in coda a
   questo ticket) e linkarlo dalla mappa.

## Evidence to Capture

- URL delle regole ufficiali e degli esempi citati.

## Out of Scope

- Scrittura dei testi (ticket 05); creazione di account nuovi.
