# 04 — Task: formato messaggi propri + header (divergenza C)

## Parent Spec

[original-chat-prompt-fidelity-wayfinder.md](../../specs/original-chat-prompt-fidelity-wayfinder.md)

## Type

task

## Outcome

La sezione dei messaggi propri del bot è resa come nell'originale: header
`[I TUOI ULTIMI MESSAGGI]` e righe nel formato
`-277s tu: "..." (rispondevi a: ...)` — timestamp relativo, `tu:`, messaggio tra
virgolette, e il contesto "(rispondevi a: …)". Oggi il codice rende
`minnarone: <msg>` sotto `[TUOI MESSAGGI RECENTI]`.

## Acceptance Criteria

- [ ] Header rinominato in `[I TUOI ULTIMI MESSAGGI]` (da `[TUOI MESSAGGI
      RECENTI]`).
- [ ] Righe nel formato `-Ns tu: "<msg>" (rispondevi a: <reason>)` come da
      trascrizione ticket 01.
- [ ] Il campo "(rispondevi a: …)" è alimentato da dati reali: i messaggi propri
      passati dal Reactor sono arricchiti con reason/target (oggi sono
      `Sequence[str]` nudi in `self_messages`). Se il dato non è disponibile,
      degradare con grazia (omettere la parentesi, non inventare).
- [ ] Timestamp relativo usa il meccanismo "now" del ticket 03.
- [ ] Il blocco resta dentro il fence con prefisso `| `.
- [ ] Test aggiornati in `tests/test_prompt_builder.py` (+ `test_reactor.py` per
      il passaggio arricchito dei self-messages).

## Blocked By

- Blocked by [01-research-transcribe-screenshots.md](./01-research-transcribe-screenshots.md)
- Blocked by [03-task-perception-line-format.md](./03-task-perception-line-format.md)
  (riusa il meccanismo dei timestamp relativi).

## Frontier

Dipende dal meccanismo timestamp (03) e richiede una piccola modifica al contratto
Reactor→prompt per portare il contesto "rispondevi a". È l'unico punto che tocca
l'interfaccia fra Reactor e PromptBuilder.

## Work Plan

1. Estendere il tipo dei self-messages passati dal Reactor per includere
   reason/target (o una struttura equivalente), mantenendo il degrado con grazia.
2. Aggiornare `_self_messages_block` (`prompt.py:546-558`) al nuovo header e
   formato riga.
3. Applicare il timestamp relativo dal meccanismo del ticket 03.
4. Aggiornare i test di prompt builder e reactor.

## Evidence to Capture

- Diff di `prompt.py` e del punto Reactor che passa i self-messages.
- Test verdi.

## Out of Scope

- Formato delle righe di percezione altrui (ticket 03).
- Summarizer (ticket 06).
