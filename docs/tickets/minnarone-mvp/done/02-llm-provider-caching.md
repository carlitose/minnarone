## Parent PRD

[minnarone-mvp.md](../../prds/minnarone-mvp.md)

## What to build

Sostituisce il fake `LLMProvider` con un'implementazione **reale via OpenRouter** verso **Grok 4.3** e **DeepSeek V4 Flash**, selezionabili da configurazione, e attiva il **prompt caching** assicurando che il prefisso stabile sia in testa e byte-identico tra chiamate. Dopo questo slice, l'agente genera messaggi reali; lo switch di provider è una riga di config.

Demo: stesso messaggio-menzione dello slice 01, ma la risposta arriva da un modello reale; cambiando `llm_provider` cambia il modello senza toccare codice.

Riferimenti PRD: *Step-by-Step* 9; *Implementation Decisions* (LLMProvider, struttura prompt, configurazione); QR03/QR04.

## Step-by-step implementation plan

1. **Implementa `LLMProvider` reale** dietro l'interfaccia astratta dello slice 00, chiamando OpenRouter. Perché ora: il core già funziona col fake; qui si innesta la dipendenza reale senza cambiare il Reactor. Verifica: con un fake HTTP il modulo costruisce la richiesta corretta; con credenziali reali ritorna un messaggio.
2. **Esponi la selezione del modello da config** (`llm_provider` + parametri, thinking basso). Verifica: cambiando config si passa Grok↔DeepSeek senza modifiche al codice.
3. **Gestisci timeout/errore** restituendo il segnale distinto definito in slice 00 (lo userà lo slice 09 per il salto-turno). Verifica: una risposta lenta/errata non blocca il Reactor.
4. **Verifica il prompt caching:** conferma che il prefisso stabile è in testa e invariante; misura/registra la quota di token in cache. Trappola: qualsiasi variazione (anche un timestamp) nel prefisso azzera il risparmio da caching.

## Acceptance criteria

- [ ] L'agente genera messaggi reali da Grok e da DeepSeek.
- [ ] Il provider/modello si seleziona da configurazione, senza modifiche al codice.
- [ ] Timeout/errore del provider producono un segnale gestibile, senza bloccare il loop.
- [ ] Il prefisso stabile è in testa e invariante tra chiamate (prompt caching attivo).
- [ ] Test di contratto su `LLMProvider` (fake HTTP) e test sull'invarianza del prefisso.

## Blocked by

- Blocked by [01-walking-skeleton.md](./01-walking-skeleton.md)

## User stories addressed

- User story 5
- User story 26
