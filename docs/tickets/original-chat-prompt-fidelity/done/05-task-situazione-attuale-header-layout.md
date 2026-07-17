# 05 — Task: header `SITUAZIONE ATTUALE` + layout sezioni (divergenza F)

## Parent Spec

[original-chat-prompt-fidelity-wayfinder.md](../../specs/original-chat-prompt-fidelity-wayfinder.md)

## Type

task

## Outcome

Il prompt original-chat apre e si struttura come l'originale: intestazione
`====== SITUAZIONE ATTUALE ======` e riga `Ti trovi nel canale di enkk`, con
l'ordine e le etichette delle sezioni (`[MEMORIA]`, `[CHAT RECENTE]`, `[I TUOI
ULTIMI MESSAGGI]`, `[FORMATO RISPOSTA]`, `[SITUAZIONE]`) allineati al layout
originale trascritto nel ticket 01.

## Acceptance Criteria

- [ ] Aggiunta l'apertura `====== SITUAZIONE ATTUALE ======` + `Ti trovi nel
      canale di enkk` (testo esatto da ticket 01) dove l'originale la colloca.
- [ ] Ordine ed etichette delle sezioni dinamiche coincidenti con l'originale.
- [ ] La riga del canale non è hard-coded su "enkk" se il canale è configurabile:
      usare il canale dalla config; "enkk" solo se è il default reale.
- [ ] Prefisso STABILE resta byte-invariante (l'apertura dinamica non entra nel
      blocco cacheable).
- [ ] Coordinato col ticket 02 sui nomi-sezione citati nei testi SITUAZIONE.
- [ ] Test di ordine sezioni aggiornati in `tests/test_prompt_builder.py`.

## Blocked By

- Blocked by [01-research-transcribe-screenshots.md](./01-research-transcribe-screenshots.md)
  (layout e testo esatto dell'header).

## Frontier

Ridà al prompt la "cornice" dell'originale. Interagisce con 02 (nomi citati) e 06
(la sezione `[MEMORIA]` è riempita dal summarizer): va tenuto coerente con
entrambi.

## Work Plan

1. Inserire l'apertura `SITUAZIONE ATTUALE` + riga canale nel percorso dinamico
   original-chat (non nel prefisso stabile).
2. Riordinare/rietichettare le sezioni secondo la trascrizione del ticket 01.
3. Verificare la byte-invarianza del prefisso stabile con i test esistenti.
4. Allineare i test di ordine sezioni.

## Evidence to Capture

- Diff di `prompt.py`.
- Test ordine sezioni verdi; test di invarianza prefisso stabile verdi.

## Out of Scope

- Contenuto/strategia del riassunto dentro `[MEMORIA]` (ticket 06).
- Formato delle righe (ticket 03/04).
