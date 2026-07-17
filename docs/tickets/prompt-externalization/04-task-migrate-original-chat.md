# 04 — Task: migrare i prompt original-chat nei file

## Parent Spec

[prompt-externalization-wayfinder.md](../../specs/prompt-externalization-wayfinder.md)

## Type

task

## Outcome

Tutto il testo tunabile della modalità original-chat vive in file esterni via il
loader del ticket 03: persona/regole (`_ORIGINAL_CHAT_RULES`) in SOUL.md (o file
persona secondo la decisione 02), `[FORMATO RISPOSTA]`, i testi `[SITUAZIONE]`
(tutte le varianti), e il banner/canale (`_ORIGINAL_CHAT_INTRO`). Le costanti
hard-coded corrispondenti sono rimosse.

## Acceptance Criteria

- [ ] `_ORIGINAL_CHAT_RULES`, `[FORMATO RISPOSTA]`, le varianti di
      `_original_chat_situation` e `_ORIGINAL_CHAT_INTRO` (incluso il canale) sono
      servite da file; costanti rimosse.
- [ ] Canale non più hard-coded "enkk": viene dal file/config.
- [ ] Regole di sicurezza (anti-injection/disclosure) ancora cablate.
- [ ] Byte-invarianza del prefisso stabile preservata (default fissi).
- [ ] I riferimenti di sezione (ticket D del lavoro precedente) restano coerenti
      con gli header resi.
- [ ] Test del prompt builder aggiornati: asseriscono contro i file default
      impacchettati e la struttura/placeholder, non più contro costanti inline;
      suite intera verde.

## Blocked By

- Blocked by [03-task-prompt-source-loader.md](./03-task-prompt-source-loader.md)

## Frontier

È la fetta di contenuto più grande e più visibile (la personalità di Minnarone):
va dopo che il loader è stabile.

## Work Plan

1. Creare i file di prompt original-chat (default impacchettati) col testo attuale.
2. Sostituire le costanti con letture dal loader; rimuovere le costanti.
3. Aggiornare i test per asserire contro i default caricati + placeholder.
4. Verificare byte-invarianza e coerenza dei riferimenti di sezione.

## Evidence to Capture

- Diff `prompt.py` + nuovi file di prompt.
- Test verdi; prompt renderizzato identico a prima (default).

## Out of Scope

- Summarizer (05) e altri stili (06).
- Cambiare il testo dei prompt (è un trasloco, non un riscrittura).
