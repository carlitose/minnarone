## Parent PRD

[minnarone-mvp.md](../../prds/minnarone-mvp.md)

## What to build

La **memoria a breve termine**: il `Summarizer` osserva periodicamente le percezioni e produce, via LLM, un blocchetto di riassunto di cosa è successo finora nella sessione (stream, conversazioni con lo streamer, conversazioni in chat). Il riassunto viene iniettato nella sezione dinamica del prompt, così l'agente fa riferimenti coerenti a eventi precedenti senza dover rileggere tutto.

Demo: dopo un po' di sessione, l'agente cita qualcosa accaduto prima (es. "il boss di prima").

Riferimenti PRD: *Step-by-Step* 11; *Implementation Decisions* (Summarizer, struttura prompt §3); FR11.

## Step-by-step implementation plan

1. **Implementa `Summarizer.summarize(perceptions) -> summary_text`** che chiama l'`LLMProvider` su cadenza periodica. Perché ora: richiede l'LLM reale (slice 02). Verifica: il summary si aggiorna nel tempo e tollera input rumoroso (trascrizioni imperfette).
2. **Inietta il summary nella sezione dinamica del prompt** (prima degli ultimi messaggi). Trappola: è dinamico → fuori dal prefisso cacheable.
3. **Gestisci la cadenza** in modo che non si sovrapponga né accumuli chiamate. Verifica: nessun pile-up di chiamate al Summarizer sotto carico.
4. **Verifica end-to-end:** l'agente produce un messaggio che fa riferimento a un evento precedente della sessione.

## Acceptance criteria

- [ ] Esiste una memoria a breve termine aggiornata periodicamente dal `Summarizer`.
- [ ] Il riassunto viene iniettato nella sezione dinamica del prompt.
- [ ] L'agente fa riferimenti coerenti a eventi precedenti della sessione.
- [ ] Il Summarizer tollera trascrizioni rumorose senza rompersi.
- [ ] Test di contratto su `Summarizer` con fake LLM.

## Blocked by

- Blocked by [02-llm-provider-caching.md](./02-llm-provider-caching.md)

## User stories addressed

- User story 19
