# 05 — Task: migrare il prompt del summarizer nei file

## Parent Spec

[prompt-externalization-wayfinder.md](../../specs/prompt-externalization-wayfinder.md)

## Type

task

## Outcome

Il testo tunabile del Summarizer vive in file esterni via il loader: l'istruzione
`_PROMPT_INSTRUCTION`, il placeholder `_EMPTY_SUMMARY_PLACEHOLDER` e le etichette
`_SOURCE_GROUPS` (STREAMER/SCHERMO/CHAT). Le costanti hard-coded sono rimosse.

## Acceptance Criteria

- [ ] `_PROMPT_INSTRUCTION`, `_EMPTY_SUMMARY_PLACEHOLDER`, etichette
      `_SOURCE_GROUPS` servite da file; costanti rimosse.
- [ ] La mappatura fonte→etichetta resta corretta (audio→STREAMER, video→SCHERMO,
      chat→CHAT) anche se le etichette vengono dal file.
- [ ] Robustezza preservata: store vuoto → nessuna chiamata LLM; `LLMError` →
      riassunto precedente conservato.
- [ ] Test del summarizer aggiornati per asserire contro i default caricati;
      suite intera verde.

## Blocked By

- Blocked by [03-task-prompt-source-loader.md](./03-task-prompt-source-loader.md)

## Frontier

Contenuto ben isolato nel Summarizer; dipende solo dal loader.

## Work Plan

1. Creare i file di prompt del summarizer (default) col testo attuale.
2. Sostituire le costanti con letture dal loader; mantenere la mappa fonte→gruppo.
3. Aggiornare i test del summarizer.

## Evidence to Capture

- Diff `summarizer.py` + nuovi file.
- Test verdi; prompt summarizer identico a prima (default).

## Out of Scope

- Original-chat (04) e altri stili (06).
