## Parent PRD

[minnarone-mvp.md](../../prds/minnarone-mvp.md)

## What to build

Lo **scheletro che cammina**: il percorso end-to-end più sottile possibile che attraversa *tutti* i layer. Un messaggio di chat (da una sorgente finta/semplice) entra nel `PerceptionStore`, il `Senser` rileva una menzione base, il `PromptBuilder` assembla un prompt, un **fake `LLMProvider`** restituisce un messaggio, e l'`OutputRouter` lo stampa su un canale pubblico (console). Stabilisce il `Reactor` come orchestratore e il `PerceptionStore` come spina dorsale. Tutte le parti "intelligenti" (LLM reale, audio, video, memoria) restano stub/fake: verranno ispessite negli slice successivi.

Demo: digito in chat un messaggio che nomina l'agente → vedo stampato un messaggio generato.

Riferimenti PRD: *Step-by-Step* 1–2, 8, 9 (fake), 11–13.

## Step-by-step implementation plan

1. **Implementa `PerceptionStore`** su `perceptions.jsonl` (`append`, `read_since`, `tail`). Perché ora: è il giunto centrale; tutto il loop vi legge/scrive. Verifica: N append riletti mantengono l'ordine per `ts`; `read_since` filtra. Trappola: append durevole e atomico per riga, niente buffering che faccia perdere righe al tail.
2. **Implementa un `ChatPerceiver` minimo** che trasforma un input testuale (anche da stdin/file) in `Perception(source=chat)` nello store. Perché ora: dà percezioni reali senza dipendere dai modelli ML.
3. **Implementa un `Senser` minimo** che a ogni tick legge le percezioni recenti e produce un `Trigger` se il nome dell'agente compare in un messaggio. Perché ora: serve un trigger per far girare il Reactor. Verifica: messaggio con nome → trigger; senza → nessun trigger.
4. **Implementa un `PromptBuilder` minimo** che assembla prefisso stabile + ultimi messaggi + sezione situazione/trigger in coda. Verifica: ordine sezioni corretto; il prefisso stabile è identico tra due build con stesso contesto stabile. Trappola: niente dati dinamici (timestamp ecc.) nel prefisso.
5. **Usa il fake `LLMProvider`** (da slice 00) per trasformare prompt → messaggio deterministico.
6. **Implementa `OutputRouter` (canale console pubblico)** che stampa il messaggio.
7. **Implementa il `Reactor`** che lega Senser → PromptBuilder → LLMProvider → OutputRouter in un loop asincrono. Verifica end-to-end: un messaggio-menzione produce un output. Trappola: il tick del Senser deve restare veloce e idempotente.

## Acceptance criteria

- [ ] Un messaggio di chat che nomina l'agente produce, end-to-end, un messaggio stampato sul canale pubblico.
- [ ] Le percezioni transitano realmente per `perceptions.jsonl` (la reazione legge dallo store, non riceve il dato direttamente).
- [ ] Il `Reactor` gira in loop e reagisce solo quando il `Senser` emette un trigger.
- [ ] Il prefisso stabile del prompt è invariante tra build con stesso contesto stabile.
- [ ] Tutti i moduli toccati hanno test (PerceptionStore, ChatPerceiver, Senser base, PromptBuilder, OutputRouter, Reactor con fake LLM).

## Blocked by

- Blocked by [00-foundational-contracts.md](./00-foundational-contracts.md)

## User stories addressed

- User story 3
- User story 10
- User story 11
- User story 14
- User story 16
