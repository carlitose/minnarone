## Parent PRD

[minnarone-mvp.md](../../prds/minnarone-mvp.md)

## What to build

La **dashboard di osservabilità (TUI)** che mostra in tempo reale, in sola lettura, lo stato del sistema: le percezioni in arrivo (chat/audio/video), gli eventi/trigger prodotti dal Senser, le finestre di conversazione attive (streamer/chat) e i messaggi inviati dall'agente. È lo strumento di debug e tuning dell'operatore.

Demo: lancio la TUI durante una sessione e vedo scorrere percezioni, trigger, finestre e messaggi.

Riferimenti PRD: *Step-by-Step* 14; FR28; NFR09; US28.

## Step-by-step implementation plan

1. **Implementa la TUI (Textual)** che legge lo stato già prodotto (PerceptionStore, stato finestre del Senser, messaggi dell'OutputRouter). Perché ora: ultimo, perché consuma stato esistente senza produrne. Trappola: deve essere sola lettura, non deve interferire col loop.
2. **Mostra le sezioni**: percezioni recenti, eventi/trigger, finestre di conversazione attive, messaggi inviati. Verifica: i dati riflettono lo stato reale in tempo reale.
3. **Aggiornamento fluido** senza bloccare i loop principali. Verifica: la TUI regge un flusso sostenuto di percezioni senza degradare la reattività dell'agente.

## Acceptance criteria

- [ ] La TUI mostra percezioni, trigger/eventi, finestre di conversazione e messaggi inviati in tempo reale.
- [ ] È in sola lettura e non interferisce con il loop del Reactor.
- [ ] Regge un flusso sostenuto senza degradare la reattività.
- [ ] Smoke test: la TUI rende lo stato senza crash.

## Blocked by

- Blocked by [01-walking-skeleton.md](./01-walking-skeleton.md)

## User stories addressed

- User story 28
