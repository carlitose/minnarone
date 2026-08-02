# 06 — Task: lancio coordinato e presidio post-lancio

## Parent Spec

[repo-promotion-wayfinder.md](../../specs/repo-promotion-wayfinder.md)

## Type

task

## Outcome

I post sono pubblicati secondo il calendario del ticket 05; commenti, domande
e issue delle prime 48-72h ricevono risposta; gli esiti (metriche, feedback
ricorrente) sono registrati nella mappa.

## Acceptance Criteria

- [x] Ogni post pubblicato dal canale/account dell'autore secondo calendario.
- [ ] Commenti e issue presidiate nelle prime 48-72h (budget di tempo dal
      grilling 01).
- [ ] Metriche registrate a 72h e a 30 giorni (stelle, traffico da Insights,
      issue/PR esterne) confrontate con l'obiettivo del grilling 01.
- [ ] Feedback ricorrente distillato in issue o nuovi ticket.

## Blocked By

- 02 (vetrina), 05 (testi approvati).

## Frontier

Il presidio post-pubblicazione è la parte che decide l'esito del lancio: un
post senza risposte dell'autore muore in poche ore.

## Work Plan

1. Pubblicare secondo calendario (l'autore posta di persona; l'agente può
   preparare risposte-tipo alle domande prevedibili: "come funziona la
   diarization?", "gira su GPU piccole?", "è legale su Twitch?").
2. Monitorare commenti/issue; rispondere nel tono deciso.
3. A 72h: snapshot metriche (stelle, GitHub Insights → Traffic) e primo
   bilancio nella mappa.
4. A 30 giorni: secondo snapshot e chiusura del ticket con verdetto contro
   l'obiettivo.

## Evidence to Capture

- Link ai post pubblicati; snapshot metriche a 72h e 30gg; temi ricorrenti.

## Progress (2026-07-21)

- Dipendenze 02 e 05 chiuse: vetrina GitHub verificata, copy e calendario
  approvati.
- Creato il [launch log](../../specs/repo-promotion-launch-log.md) con gate Day
  0, record URL, finestre di presidio, checkpoint e tabella feedback.
- Baseline pre-lancio registrata alle `2026-07-21T20:55:11Z`: 1 stella, 0
  fork, 0 issue/PR esterne; finestra Traffic mobile di 14 giorni con 80 view / 8
  unici e 74 clone / 25 unici. I valori non sono zero e non vanno attribuiti al
  lancio.
- Prossimo gate umano: sabato 2026-07-25 alle 18:00 CEST, verifica account e
  composer. Prima pubblicazione: Show HN domenica 2026-07-26 alle 17:00 CEST.
- Il ticket resta aperto: pubblicazioni, presidio 72h e misurazione a 30 giorni
  sono necessariamente futuri e richiedono gli account dell'autore.

## Progress (2026-07-28)

- Pubblicati tutti e quattro i post selezionati: Show HN, X, LinkedIn e
  [r/SideProject](https://www.reddit.com/r/SideProject/comments/1v8w477/minnarone_multimodal_agents_that_watch_listen_and/).
- Il presidio post-lancio resta attivo; checkpoint a 72 ore previsto per il
  2026-07-29 e verdetto a 30 giorni per il 2026-08-25.

## Progress (2026-08-02)

- Show HN e X sono stati pubblicati il 2026-07-26, LinkedIn il 2026-07-27 e
  r/SideProject il 2026-07-28. Tutti e quattro hanno URL canonici, timestamp e
  account dell'autore verificati nel
  [launch log](../../specs/repo-promotion-launch-log.md); non serve alcuna
  ripubblicazione.
- Il checkpoint delle 72 ore non è stato acquisito in orario. Una
  ricostruzione read-only ha salvato le righe Traffic ancora disponibili e ha
  verificato che le 4 stelle attualmente attive erano già state create entro
  il confine delle 72 ore. Al momento della ricostruzione: 0 fork e nessuna
  issue/PR esterna in alcuno stato.
- La finestra Traffic mobile osservata in ritardo riporta 175 view / 96 unici e
  136 clone / 72 unici. Le righe UTC 2026-07-26–28 sommano 116 view e 11 clone;
  il giorno del lancio include però 15h10m49s precedenti al primo post e gli
  unici giornalieri non sono persone de-duplicate.
- Alla verifica del 2026-08-02 LinkedIn riportava 1.006 impressioni, 3
  reazioni, 2 commenti e 1 repost; Reddit riportava 1 voto e 1 commento. Non è
  emerso feedback ricorrente da trasformare in nuovi ticket. Il ticket 06
  resta aperto per il preservation snapshot dell'11 agosto e il verdetto a 30
  giorni del 25 agosto.
## Out of Scope

- Contenuti di follow-up (ticket 07); rilanci ripetuti sugli stessi canali.
