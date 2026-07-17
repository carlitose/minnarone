# 02 — Task: allineare i riferimenti di sezione nel testo SITUAZIONE (divergenza D)

## Parent Spec

[original-chat-prompt-fidelity-wayfinder.md](../../specs/original-chat-prompt-fidelity-wayfinder.md)

## Type

task

## Outcome

Il testo delle situazioni original-chat cita le sezioni con gli **stessi nomi
dell'originale**: `[I TUOI ULTIMI MESSAGGI]` e `[MEMORIA]` dove il codice oggi
scrive `[CONVERSAZIONE RECENTE]`. Riferimenti interni coerenti con gli header
effettivamente resi nel prompt.

## Acceptance Criteria

- [ ] `_original_chat_situation` (streamer→TE) cita `[I TUOI ULTIMI MESSAGGI]` e
      `[MEMORIA]` come nell'originale (oggi: nessun riferimento).
- [ ] Variante continuation streamer: `[CONVERSAZIONE RECENTE]` → riferimento
      dell'originale (`[I TUOI ULTIMI MESSAGGI]`) come da trascrizione ticket 01.
- [ ] I nomi citati nel testo corrispondono agli header realmente prodotti dal
      builder (nessun riferimento a una sezione inesistente).
- [ ] Test in `tests/test_prompt_builder.py` aggiornati/aggiunti per asserire i
      nuovi riferimenti.
- [ ] Blocchi già coincidenti non toccati.

## Blocked By

- Blocked by [01-research-transcribe-screenshots.md](./01-research-transcribe-screenshots.md)
  (servono i nomi-sezione esatti + eventuale rinomina header decisa in 01/05).

## Frontier

Divergenza a basso sforzo e basso rischio: buon primo passo implementativo una
volta fissato il testo di riferimento.

## Work Plan

1. Applicare i riferimenti esatti dal ticket 01 in `_original_chat_situation`
   (`prompt.py:423-475`).
2. Coordinarsi col ticket 05 (F) se gli header vengono rinominati, per non citare
   nomi che poi cambiano.
3. Aggiornare i test del prompt builder.

## Evidence to Capture

- Diff di `prompt.py`.
- Output test prompt builder verde.

## Out of Scope

- Cambiare il formato delle righe (ticket 03/04) o il layout delle sezioni
  (ticket 05).
