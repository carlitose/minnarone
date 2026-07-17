# 03 — Task: header esternalizzati con riferimenti via placeholder

## Parent Spec

[prompt-externalization-followups-wayfinder.md](../../specs/prompt-externalization-followups-wayfinder.md)

## Type

task

## Outcome

Un prompt-set in un'altra lingua può essere **completo**: anche gli header di
sezione (`[REGOLE]`, `[FORMATO RISPOSTA]`, `[SITUAZIONE]`, `[MEMORIA] (...)`,
`[I TUOI ULTIMI MESSAGGI]`, `[CONVERSAZIONE RECENTE]`, `[CHAT/PARLATO/SCHERMO
RECENTE]`, e `## RIASSUNTO`/`## CONVERSAZIONE RECENTE`/`## SITUAZIONE` degli
altri stili) vengono dai file, SENZA che i riferimenti incrociati possano
divergere.

**Meccanismo (dalla mappa)**: gli header vivono in un file a chiavi
(`headers.md`); i corpi che citano un header (es. le situazioni che citano
`[I TUOI ULTIMI MESSAGGI]` e `[MEMORIA]`) non scrivono più il nome letterale ma
un placeholder (`{{header_self_messages}}`, `{{header_memoria}}`) risolto dal
loader dagli STESSI valori usati per rendere gli header → coerenza garantita
per costruzione.

## Acceptance Criteria

- [ ] `headers.md` (a chiavi, vincoli per-sezione dal ticket 02) con tutti gli
      header tunabili; default byte-identici agli attuali.
- [ ] I corpi in `situations.md` citano gli header via placeholder; il render
      con i default è byte-identico a prima.
- [ ] I marcatori di SICUREZZA (fence `DATI_PERCEPITI`, `| `, `[REGOLE]`?) —
      decidere quali header sono davvero tunabili e quali restano cablati per
      sicurezza; la decisione va scritta nel ticket. Il fence resta cablato
      SEMPRE.
- [ ] `examples/prompts-en/` esteso a set completo (header inclusi) come prova
      dello swap totale di lingua.
- [ ] Byte-invarianza del prefisso stabile coi default preservata.
- [ ] Suite verde; test: header custom → riferimenti nei corpi aggiornati da
      soli; header mancante in `headers.md` → fail-fast.

## Blocked By

- Blocked by [02-task-per-section-validation.md](./02-task-per-section-validation.md)
  (i vincoli per chiave devono coprire `headers.md`).

## Frontier

È il pezzo col rischio di design più alto del gruppo (tocca byte-invarianza,
validazione e tutti gli stili): va per ultimo dei punti-prompt, su base stabile.

## Work Plan

1. Censire ogni header e ogni riferimento incrociato (grep su `prompt.py` +
   `prompts/*.md`).
2. RED: test che con `headers.md` custom il riferimento nel corpo segua l'header.
3. Introdurre `headers.md` + placeholder nei corpi; sostituire le ancore cablate
   con lookup dal set.
4. Estendere `examples/prompts-en/`; verificare swap completo.
5. Byte-invarianza + suite.

## Evidence to Capture

- Tabella header → chiave → chi lo cita.
- Render EN completo d'esempio.

## Out of Scope

- Esternalizzare fence/regole di sicurezza.
- Tradurre altri contenuti oltre l'esempio dimostrativo.
