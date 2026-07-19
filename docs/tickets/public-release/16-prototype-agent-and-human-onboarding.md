# Prototipare onboarding per code agent e utente normale

## Parent Spec

[public-release-wayfinder.md](../../specs/public-release-wayfinder.md)

## Type

prototype

## Outcome

Confrontare con una prova reversibile tre superfici — skill repo-local, tutorial
con template e comando `minnarone init/doctor` — e scegliere il minimo insieme
che porta sia un code agent sia un utente normale a una shadow run corretta.

## Acceptance Criteria

- [ ] Il prototipo applica il catalogo/naming deciso nel ticket 10 e usa la
      skill rinominata del ticket 11.
- [ ] È provata almeno una skill onboarding/persona/Twitch e una skill/runtime
      doctor, oppure è documentato perché una delle due non serve.
- [ ] Il flusso pone le domande del ticket 13 prima di scrivere soul/facts.
- [ ] Il flusso applica i guardrail del ticket 14 e i profili del ticket 15.
- [ ] Il prototipo termina a shadow e verifica account bot dedicato, consenso
      broadcaster, disclosure e artifact/retention senza promuovere live.
- [ ] Il runtime doctor prova P0, P2 e almeno uno fra P3–P5, verifica digest e
      revision del manifest e rifiuta mismatch speaker 192/512.
- [ ] Un test comparativo registra passaggi, errori evitati e duplicazione tra
      skill, CLI e docs; la scelta finale è esplicita.

## Blocked By

- [10-grilling-skill-catalog-and-rename.md](done/10-grilling-skill-catalog-and-rename.md) — done
- [11-task-rename-prompts-skill.md](done/11-task-rename-prompts-skill.md) — done
- [13-grilling-persona-facts-onboarding.md](done/13-grilling-persona-facts-onboarding.md) — done
- [14-research-public-twitch-safety.md](done/14-research-public-twitch-safety.md) — done
- [15-research-runtime-model-profiles.md](done/15-research-runtime-model-profiles.md) — done

## Frontier

Scrivere subito molte skill rischia di duplicare README e CLI; scrivere solo
docs lascia i code agent senza workflow eseguibili. Serve una prova piccola
prima di scegliere la superficie pubblica.

## Work Plan

1. Preparare due scenari: code agent su clone pulito e umano che segue solo il
   README.
2. Prototipare la minima skill onboarding e la minima diagnostica/doctor.
3. Eseguire entrambi gli scenari fino a `--check` e shadow senza promuovere live.
4. Misurare numero di decisioni manuali, errori, duplicazione e chiarezza.
5. Registrare la scelta e creare input concreti per il ticket 17.

## Evidence to Capture

- Transcript/checklist dei due scenari.
- File generati dal prototipo in directory temporanee.
- Comandi, failure e decisione finale sull'interfaccia.

## Out of Scope

- Produzione definitiva delle skill/CLI.
- Invio live.
- Supporto a use case non-Twitch nel primo golden path.
