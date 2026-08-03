---
ticket_schema: 1
ticket_id: "08"
execution_mode: HITL
blocked_by:
  - "05"
  - "07"
---

# Eseguire l'accettazione bounded shadow e live YouTube

## Parent Spec

[youtube-live-wayfinder.md](../../specs/youtube-live-wayfinder.md)

## Question / Outcome

Il percorso YouTube completo è operativo e sicuro su una live autorizzata, e
l'evidenza giustifica continuare, rivedere il design o fermare il workstream?

Output atteso: audit sanitizzato di una prova full shadow e, solo dopo tutti i
gate, di una breve live attended; aggiornamento della mappa con decisione
`advance`, `revise` o `stop`.

## What to Build

Preparare ed eseguire una procedura HITL in due fasi: full multimodal shadow
bounded, review umana, poi eventuale live chat con consenso/autorità verificati,
sessione nuova, warm-up shadow, doppia conferma `p` e kill-switch disponibile.

Sezioni coperte: evidenza operativa finale della `Frontier` e raggiungibilità
della `Destination`.

## Evidence Required

- Preflight config/tool/model/token/capability senza stampare valori segreti.
- Consenso/autorità sanitizzati, target allow-listed, disclosure scelta,
  retention/cancellazione e stop conditions.
- Conteggi per canale, queue/drop, latenze, chat pacing/quota, decisioni shadow,
  messaggi sent/failed e transizioni promote/kill in run events redatti.
- Confronto messaggi effettivi vs audit locale e prova di assenza self-trigger.

## Acceptance Criteria

- [ ] Tutti i test/quality check e i preflight di readiness pertinenti passano
  sul candidate congelato prima della rete, senza failure ignorate.
- [ ] La shadow run ha durata concordata, produce chat e i media abilitati o
  una diagnosi esplicita, rispetta budget e non invia.
- [ ] L'umano approva la review shadow; senza approvazione il ticket termina
  con esito `revise/stop` e nessuna live.
- [ ] La live usa un target autorizzato, parte in shadow, viene promossa
  manualmente e resta attended con kill-switch provato almeno una volta.
- [ ] Nessun invio è over-budget, stale, duplicato o self-triggered; auth/quota
  failure degrada/ferma come progettato.
- [ ] Audit, artifact e mappa non contengono token, auth code, client secret o
  chat privata/non necessaria e registrano cancellazione/retention.
- [ ] La mappa rimuove unknown risolti e registra la decisione advance/revise/stop;
  nessuna espansione automatica viene inferita da un solo canary.

## Frontier

HITL, dependency-blocked by 05 and 07. Richiede credenziali, live disponibile,
consenso/autorità e approvazione umana; è l'unico ticket che può esercitare un
send reale.

## Step-by-Step Implementation Plan

1. Congelare candidate e verificare test, config, modelli, tool, target,
   capability, consenso, disclosure, retention e kill-switch.
2. Eseguire smoke isolate e full multimodal shadow bounded; salvare solo
   evidenza sanitizzata e fermarsi per review umana.
3. Se approvato, avviare una nuova sessione live-armed che parte in shadow,
   attendere contesto sufficiente e promuovere dalla TUI.
4. Osservare ogni decisione, esercitare kill-switch, non ri-promuovere in caso
   di auth/revoca/stop request e terminare entro il limite.
5. Confrontare run events e chat, cancellare artifact secondo policy e
   aggiornare mappa/spec con esito e follow-up giustificati.

## Testing Plan

Quality suite preflight; smoke isolate; full-shadow acceptance; live canary
manuale solo se autorizzato; audit post-run di eventi, budget, self-echo,
redazione, retention e cleanup.

## Out of Scope

- Live unattended, lunga durata o su canale non autorizzato.
- Più live/canali, rollout, outreach o promozione del repository.
- Cambi di codice durante il canary senza tornare a test e shadow.
- Dichiarare production readiness generale da una singola prova.
