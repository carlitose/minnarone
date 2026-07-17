# 02 — Task: validazione per-sezione / strict-set mode

## Parent Spec

[prompt-externalization-followups-wayfinder.md](../../specs/prompt-externalization-followups-wayfinder.md)

## Type

task

## Outcome

Un override malformato fallisce **all'avvio** con un messaggio chiaro, non a
runtime al primo trigger sfortunato. Oggi `required_tokens`/placeholder di un
file a chiavi (es. `situations.md`) sono validati sull'INTERO file: se un
override toglie `#end_conv` solo dalla sezione `streamer-mention`, l'avvio passa
e l'errore esplode live.

## Acceptance Criteria

- [ ] `PromptSpec` (o estensione) permette vincoli **per chiave**: token di
      controllo richiesti e placeholder ammessi/richiesti per singola sezione
      (es. `#end_conv` richiesto in OGNI variante situazione che lo usa;
      `{{user}}`/`{{mention}}` ammessi solo nelle sezioni chat).
- [ ] `situations.md` (e `summarizer.md` dove sensato) migrati ai vincoli
      per-sezione; i default passano invariati.
- [ ] Un override con una sezione rotta (token mancante / placeholder estraneo)
      fallisce al load con `PromptError` che indica FILE e SEZIONE.
- [ ] Messaggio d'errore utilizzabile da un agente/operatore (file, chiave,
      cosa manca).
- [ ] Valutato (e deciso nel ticket) lo "strict-set mode": nessun fallback
      per-file quando `prompts_dir` è impostato, per evitare mix silenzioso di
      lingue con override parziali. Se adottato: opt-in documentato; se
      scartato: motivazione scritta.
- [ ] Suite verde; test nuovi per ogni modo di rottura.

## Blocked By

- None — può partire subito.

## Frontier

Chiude la maglia larga della rete di sicurezza del loader; prerequisito logico
del ticket 03 (headers.md avrà anch'esso vincoli per chiave).

## Work Plan

1. RED: test che un `situations.md` senza `#end_conv` in UNA sezione fallisca al
   load nominando file+sezione.
2. Estendere la validazione in `prompt_source.py` (vincoli per chiave).
3. Migrare le spec esistenti; decidere e (eventualmente) implementare
   strict-set.
4. Aggiornare docs (README sezione override).

## Evidence to Capture

- Diff `prompt_source.py` + spec; messaggi d'errore d'esempio.
- Decisione strict-set registrata.

## Out of Scope

- Header (ticket 03) — ma il meccanismo qui costruito deve poterli coprire.
