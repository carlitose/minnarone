# 06 — Task: Summarizer rolling incrementale + `[MEMORIA]` strutturata (divergenza A)

## Parent Spec

[original-chat-prompt-fidelity-wayfinder.md](../../specs/original-chat-prompt-fidelity-wayfinder.md)

## Type

task

## Outcome

Il `Summarizer` produce una memoria a breve termine **incrementale** come
l'originale: reinietta il riassunto precedente ("Riassunto attuale: …"), integra
gli "Eventi recenti" raggruppati in **STREAMER / SCHERMO / CHAT**, e chiude con
"Aggiorna il riassunto". Il risultato è reso nel prompt come `[MEMORIA]` con le
sotto-sezioni **STREAM / CONVERSAZIONI CON LO STREAMER / CONVERSAZIONI IN CHAT**.
Oggi il codice fa un riassunto *from-scratch* piatto (`## EVENTI`).

## Acceptance Criteria

- [ ] Prompt del summarizer riscritto secondo la trascrizione del ticket 01:
      istruzione "sintetizzatore", `Riassunto attuale:` + riassunto precedente,
      `Eventi recenti:` raggruppati per STREAMER/SCHERMO/CHAT, `Aggiorna il
      riassunto.`
- [ ] Il riassunto precedente è reinniettato ad ogni giro (esiste già
      `Summarizer._summary`): il summarizer aggiorna invece di rifare da zero.
- [ ] Gli eventi sono raggruppati per fonte (audio→STREAMER, video→SCHERMO,
      chat→CHAT) invece della lista piatta.
- [ ] Store vuoto → nessuna chiamata LLM sprecata; `LLMError` → si conserva il
      riassunto precedente (comportamento robusto attuale preservato).
- [ ] Il testo prodotto è reso nel prompt sotto `[MEMORIA]` con le sotto-sezioni
      attese (coordinato col ticket 05 per la collocazione).
- [ ] Test aggiornati in `tests/` (summarizer) con LLM fake; nessuna chiamata LLM
      reale in CI.

## Blocked By

- Blocked by [01-research-transcribe-screenshots.md](./01-research-transcribe-screenshots.md)
  (testo esatto del prompt sintetizzatore e struttura `[MEMORIA]`).

## Frontier

È la divergenza più grande — quasi una feature a sé (memoria rolling strutturata).
Va affrontata per ultima, quando formato riga (03) e layout (05) sono stabili.
Se in fase di 01 emerge complessità (persistenza, formato output vincolato),
valutare di promuoverla a un `to-spec`/PRD dedicato invece di un singolo task.

## Work Plan

1. Riscrivere `_build_prompt`/`_PROMPT_HEADER` (`summarizer.py:34-69`) al prompt
   incrementale con riassunto precedente + eventi raggruppati.
2. Raggruppare le percezioni per fonte prima del rendering.
3. Rendere l'output sotto `[MEMORIA]` nel prompt (coordinato col ticket 05).
4. Preservare i comportamenti robusti (store vuoto, swallow LLMError).
5. Aggiornare i test del summarizer con LLM fake.

## Evidence to Capture

- Diff di `summarizer.py` (+ punto di rendering in `prompt.py`).
- Test summarizer verdi con fake LLM.
- Se promosso a spec: link al nuovo `to-spec`/PRD.

## Out of Scope

- Auto-facts / memoria a lungo termine (resta OOS dal PRD padre).
- Formato delle righe evento (ereditato dal ticket 03).
