# 06 — Task: migrare gli altri stili (operator/meeting/suggester)

## Parent Spec

[prompt-externalization-wayfinder.md](../../specs/prompt-externalization-wayfinder.md)

## Type

task

## Outcome

I template di regole degli stili non-original-chat vivono in file esterni via il
loader: `_COMMENTATOR_RULES_TEMPLATE`, `_MEETING_SYNTHESIZER_RULES_TEMPLATE`,
`_SUGGESTER_RULES_TEMPLATE`, con il placeholder `{language}` gestito dal
meccanismo di templating deciso. Costanti rimosse.

## Acceptance Criteria

- [ ] I tre template servite da file; costanti rimosse.
- [ ] `{language}` (o la decisione presa in 02 sul suo destino) funziona per questi
      stili.
- [ ] Le etichette di sezione di questi stili (`## RIASSUNTO`, `## CONVERSAZIONE
      RECENTE`, `## SITUAZIONE`) gestite coerentemente con la decisione su header
      esterni vs cablati.
- [ ] Regole di sicurezza ancora cablate anche per questi stili.
- [ ] Byte-invarianza dei rispettivi prefissi stabili preservata.
- [ ] Test di prompt builder per operator/meeting/suggester aggiornati; suite verde.

## Blocked By

- Blocked by [03-task-prompt-source-loader.md](./03-task-prompt-source-loader.md)

## Frontier

Ultima fetta di contenuto; chiude l'esternalizzazione dei prompt tunabili.

## Work Plan

1. Creare i file dei tre template (default) col testo attuale + `{language}`.
2. Sostituire le costanti con letture dal loader.
3. Aggiornare i test dei tre stili.

## Evidence to Capture

- Diff `prompt.py` + nuovi file.
- Test verdi; prompt identici a prima (default) per i tre stili.

## Out of Scope

- Original-chat (04) e summarizer (05).
