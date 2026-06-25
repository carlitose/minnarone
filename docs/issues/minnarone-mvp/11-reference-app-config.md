## Parent PRD

[minnarone-mvp.md](../../prds/minnarone-mvp.md)

## What to build

L'**app di riferimento "Minnarone"** che impacchetta l'SDK nello scenario streamer pubblico, avviabile da un **file di configurazione** (soul, facts, adapter, provider, cadenze, modalità). Cabla lo **switch modalità pubblica/privata** (privata inerte in MVP, ma il percorso esiste) e rende esplicitamente presenti — ma inerti — i **punti di estensione v2**: hook disclosure/retention e auto-aggiornamento memoria.

Demo: `run` con un file di config → l'agente parte in modalità pubblica usando il provider e i file indicati; cambiando `mode` la struttura accetta "private" anche se l'output privato non è ancora implementato.

Riferimenti PRD: *Step-by-Step* 15; FR21; *Implementation Decisions* (configurazione); US4, US6, US29–32.

## Step-by-step implementation plan

1. **Implementa il caricamento del file di config** secondo lo schema dello slice 00. Perché ora: serve tutto il core già pronto. Verifica: un config d'esempio avvia l'agente; config invalido dà errore chiaro.
2. **Cabla l'app di riferimento** che compone i moduli SDK (Perceptor, Senser, Summarizer, Memory, PromptBuilder, LLMProvider, HumanLikeness, OutputRouter, Reactor, TUI) secondo la config. Verifica end-to-end: scenario streamer pubblico funzionante da config.
3. **Implementa lo switch `mode`**: pubblica operativa; privata accettata ma instradata a un OutputRouter che segnala "non implementato in MVP". Trappola: lo stesso motore, non due codebase — la modalità è solo configurazione/instradamento.
4. **Rendi presenti ma inerti i punti v2**: `disclosure`, `retention`, hook auto-memory. Verifica: presenti nello schema, non alterano il comportamento.
5. **Documenta l'avvio** (permessi macOS audio/schermo, chiavi provider) nel README.

## Acceptance criteria

- [ ] L'agente si avvia in modalità pubblica da un file di configurazione, senza scrivere codice.
- [ ] Il provider LLM e i file soul/facts sono selezionati da config.
- [ ] Lo switch `mode` accetta public/private (private inerte ma instradata, non un crash).
- [ ] I punti v2 (disclosure, retention, auto-memory) sono presenti nello schema ma inerti.
- [ ] Test: avvio da config valido; errore chiaro su config invalido; smoke end-to-end dello scenario streamer.

## Blocked by

- Blocked by [02-llm-provider-caching.md](./02-llm-provider-caching.md)
- Blocked by [03-long-term-memory.md](./03-long-term-memory.md)
- Blocked by [07-conversation-windows-idle.md](./07-conversation-windows-idle.md)
- Blocked by [08-human-likeness.md](./08-human-likeness.md)

## User stories addressed

- User story 4
- User story 6
- User story 29
- User story 30
- User story 31
- User story 32
