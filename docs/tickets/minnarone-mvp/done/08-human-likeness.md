## Parent PRD

[minnarone-mvp.md](../../prds/minnarone-mvp.md)

## What to build

Il layer **human-likeness**, filtro finale prima dell'output: stima un **typing delay** plausibile (per evitare risposte istantanee innaturali), scarta i messaggi **quasi-duplicati** (dedup), fornisce al prompt gli ultimi messaggi propri per evitare la **fissazione** sullo stesso tema, e interpreta il comando `#end_conv` per **chiudere** una conversazione quando l'agente non ha più nulla di utile da dire.

Demo: l'agente non risponde istantaneamente; non manda due messaggi quasi identici; quando decide, chiude la conversazione.

Riferimenti PRD: *Step-by-Step* 10; FR22, FR23, FR24(anti-ripetizione), FR25; UC09; EC04, EC05, EC06.

## Step-by-step implementation plan

1. **Implementa `HumanLikeness.process(message, recent_self_msgs) -> {message, send_after_delay, drop?}`** come modulo puro. Perché ora: è l'ultimo stadio prima dell'OutputRouter; isolabile e deterministico. Verifica: delay cresce con la lunghezza del messaggio.
2. **Implementa il dedup** dei messaggi quasi-identici rispetto agli ultimi inviati. Verifica: un messaggio troppo simile a uno recente viene scartato (`drop=true`).
3. **Alimenta l'anti-ripetizione**: fornisci gli ultimi messaggi propri alla sezione dedicata del prompt. Verifica: l'agente evita di fissarsi sullo stesso tema.
4. **Interpreta `#end_conv`**: se l'LLM lo emette, chiudi la finestra di conversazione corrispondente (coordinandoti col Senser dello slice 07). Verifica: dopo `#end_conv` la finestra risulta chiusa.
5. **Collega `HumanLikeness` tra LLMProvider e OutputRouter** nel Reactor. Trappola: il delay non deve bloccare il loop (schedulare l'invio, non fare sleep bloccante).

## Acceptance criteria

- [ ] L'invio avviene dopo un ritardo plausibile, proporzionato alla lunghezza del messaggio.
- [ ] Messaggi quasi-identici a quelli recenti vengono scartati.
- [ ] L'agente evita la fissazione vedendo i propri ultimi messaggi.
- [ ] `#end_conv` chiude la finestra di conversazione corrispondente.
- [ ] Il typing delay non blocca il loop del Reactor.
- [ ] Test unit su `HumanLikeness`: dedup, delay ∝ lunghezza, gestione `#end_conv`.

## Blocked by

- Blocked by [01-walking-skeleton.md](./01-walking-skeleton.md)

## User stories addressed

- User story 21
- User story 22
- User story 23
- User story 24
