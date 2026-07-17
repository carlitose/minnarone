# 03 — Task: formato riga percezione con timestamp e brackets (divergenza B)

## Parent Spec

[original-chat-prompt-fidelity-wayfinder.md](../../specs/original-chat-prompt-fidelity-wayfinder.md)

## Type

task

## Outcome

Le righe di percezione rese nella sezione dinamica del prompt original-chat
appaiono come nell'originale: `-23s <leo95nf>: KEKW` — timestamp relativo (quanti
secondi fa rispetto a "adesso") + username tra `< >`. Oggi il codice rende
`leo95nf: KEKW`.

## Acceptance Criteria

- [ ] Le righe in `[CHAT RECENTE]` (e sezioni sorella) mostrano prefisso `-Ns` e
      username tra `< >` come da trascrizione ticket 01.
- [ ] Il "now" di riferimento è iniettato secondo il meccanismo deciso nel ticket
      01, senza intaccare la byte-invarianza del prefisso STABILE (i timestamp
      vivono solo nella sezione dinamica).
- [ ] Verdetto ticket 01 su `format_perception_line` rispettato: se resta
      condivisa, il Summarizer continua a funzionare; se si separa, esiste un
      renderer dedicato alla recent-context.
- [ ] Il fence resta: le righe timestamp+brackets restano dentro `DATI_PERCEPITI`
      con il prefisso di riga `| `.
- [ ] Test aggiornati in `tests/test_prompt_builder.py` (e, se toccato,
      summarizer) con un "now" deterministico (nessun `Date.now()` reale nei test).

## Blocked By

- Blocked by [01-research-transcribe-screenshots.md](./01-research-transcribe-screenshots.md)
  (formato esatto + nodi timestamp/formatter).

## Frontier

È il nodo tecnico centrale: introduce il concetto di tempo relativo nel rendering
e tocca il formatter condiviso. Va fatto prima di C (04) e A (06), che ne
riusano il meccanismo.

## Work Plan

1. Introdurre il riferimento temporale nel percorso di build (parametro esplicito,
   testabile, deterministico).
2. Rendere le righe con `-Ns <user>: testo` secondo il verdetto su
   `format_perception_line`.
3. Verificare che il fence e il prefisso `| ` restino intatti attorno alle nuove
   righe.
4. Aggiornare i test con timestamp fissi.

## Evidence to Capture

- Diff di `perception.py` / `prompt.py` (+ `summarizer.py` se condiviso).
- Test verdi con "now" deterministico.

## Out of Scope

- Formato dei messaggi propri (ticket 04) — riusa questo meccanismo ma è separato.
- Layout/header (ticket 05).
