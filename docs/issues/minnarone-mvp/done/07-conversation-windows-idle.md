## Parent PRD

[minnarone-mvp.md](../../prds/minnarone-mvp.md)

## What to build

Il comportamento conversazionale ricco del `Senser`, oltre alla menzione base dello slice 01: **finestre di conversazione** per interlocutore (streamer e chat, anche sovrapposte), **idle loop** (~150s) per il commento proattivo in assenza di trigger, **continuazione** (l'interlocutore parla poco dopo un messaggio dell'agente → continua lo scambio), e **risposta multi-party** (legge più messaggi recenti e risponde alla persona giusta). Predispone l'hook *bandwagon* (FR24, v2) senza implementarlo.

Demo: l'agente entra, resta in silenzio, poi commenta spontaneamente; quando lo streamer gli risponde, si apre una finestra e i due continuano a chiacchierare; in chat affollata risponde alla persona corretta.

Riferimenti PRD: *Step-by-Step* 12; UC01, UC02, UC03, UC04; EC09, EC10, EC11; FR09, FR10.

## Step-by-step implementation plan

1. **Aggiungi lo stato finestre al `Senser`**: apri/aggiorna/chiudi una finestra per interlocutore quando viene rilevata interazione. Perché ora: il loop base esiste (01); qui si arricchisce la logica pura. Verifica: una menzione apre la finestra streamer; finestre streamer+chat possono coesistere (EC10).
2. **Implementa l'idle loop** (~150s configurabile): in assenza di trigger, emetti un trigger "commento proattivo" sul contesto corrente. Verifica: senza attività, parte un commento entro l'intervallo (EC11/UC01).
3. **Implementa la continuazione** (UC03): se l'interlocutore parla poco dopo un messaggio dell'agente dentro una finestra aperta, genera un trigger di continuazione.
4. **Implementa il match menzioni robusto** (EC09): riconosci anche il nome storpiato (fuzzy/fonetico). Verifica: variazioni del nome aprono comunque la finestra.
5. **Abilita la risposta multi-party** (UC04): il PromptBuilder riceve gli ultimi ~15 messaggi così l'LLM può rispondere alla persona giusta. Verifica: in chat affollata la risposta è indirizzata correttamente.
6. **Predisponi l'hook bandwagon** (no-op documentato, v2). Trappola: il tick a 0.5s deve restare veloce e idempotente anche con più finestre attive.

## Acceptance criteria

- [ ] In assenza di trigger, l'agente emette un commento proattivo entro l'intervallo idle.
- [ ] Una menzione (anche con nome storpiato) apre una finestra di conversazione.
- [ ] L'agente continua lo scambio se l'interlocutore parla subito dopo un suo messaggio.
- [ ] Finestre streamer e chat possono coesistere senza conflitti.
- [ ] In chat multi-utente l'agente risponde alla persona corretta.
- [ ] L'hook bandwagon esiste come no-op (v2).
- [ ] Test unit sul `Senser`: trigger menzione/idle/continuazione, match storpiato, gestione finestre sovrapposte.

## Blocked by

- Blocked by [01-walking-skeleton.md](./01-walking-skeleton.md)

## User stories addressed

- User story 13
- User story 14
- User story 15
- User story 17
- User story 21
