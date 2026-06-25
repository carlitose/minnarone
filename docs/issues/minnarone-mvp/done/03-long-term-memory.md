## Parent PRD

[minnarone-mvp.md](../../prds/minnarone-mvp.md)

## What to build

La **memoria a lungo termine**: il modulo `Memory` carica l'identità dell'agente (`soul`) e i fatti su interlocutori/canale (`facts`) da file e li inietta come blocchi del prompt. Dopo questo slice l'agente risponde coerentemente a domande tipo "chi sei / chi sono io / cosa hai studiato", attingendo a questi file. L'hook `Memory.update` resta no-op (auto-memoria = v2).

Demo: chiedo in chat "chi sei?" → l'agente risponde con i dati del `soul`.

Riferimenti PRD: *Step-by-Step* 7; *Implementation Decisions* (Memory, struttura prompt §2 Memoria permanente); FR12.

## Step-by-step implementation plan

1. **Implementa `Memory.load()`** che legge `soul` e `facts/*` e li espone come blocchi testuali pronti per il prompt. Perché ora: il PromptBuilder ha già la sezione "memoria permanente" predisposta nello slice 01. Verifica: i file diventano blocchi corretti; assenza di un file degrada con grazia (blocco vuoto, non crash).
2. **Collega i blocchi al `PromptBuilder`** nella sezione "memoria permanente" (parte del prefisso stabile/cacheable). Trappola: la memoria permanente cambia di rado → tenerla nella parte cacheable, non nel dinamico.
3. **Esponi `Memory.update(facts_delta)` come no-op documentato** (hook v2). Verifica: esiste e non altera lo stato.
4. **Verifica end-to-end** con un `soul`/`facts` d'esempio: l'agente risponde a domande identitarie in modo coerente.

## Acceptance criteria

- [ ] `soul` e `facts` vengono caricati e iniettati nel prompt come memoria permanente.
- [ ] L'agente risponde coerentemente a domande su identità e fatti noti.
- [ ] L'assenza di un file di memoria degrada con grazia, senza crash.
- [ ] La memoria permanente è nella parte cacheable del prompt.
- [ ] Test unit su `Memory` (load → blocchi; `update` no-op presente).

## Blocked by

- Blocked by [01-walking-skeleton.md](./01-walking-skeleton.md)

## User stories addressed

- User story 1
- User story 2
- User story 20
