## Parent PRD

[os-capture-teams-commentator.md](../../prds/os-capture-teams-commentator.md)

## What to build

La documentazione operatore per l'uso di Minnarone come commentatore locale su
Teams via OS-capture: una sezione nel README (o guida operatore) che spiega il
setup hardware e la diagnostica. Copre l'audio di sistema (loopback), i permessi
di cattura schermo, il comando smoke e i limiti multi-platform. Vedi *Solution*,
*Further Notes* e user story 9/10/14 nel PRD.

## Step-by-step implementation plan

1. Scrivere la sezione operatore: come impostare l'**uscita audio di default** sul
   dispositivo su cui gira Teams (perché il loopback cattura l'uscita di default);
   permessi di **cattura schermo**; selezione del **monitor** (`os_capture.monitor`).
   *Perché ora:* dipende dai backend reali (07/08) e dalla CLI smoke (10), che
   sono ciò che l'operatore deve saper usare.
2. Documentare il flusso di **diagnostica** con `minnarone-oscapture-smoke`
   (capture-only): come verificare separatamente che audio e schermo vengano
   catturati prima di attivare ASR/VLM.
3. Documentare i **limiti multi-platform**: loopback nativo su Windows (WASAPI) e
   Linux (monitor PulseAudio); su macOS serve un device di loopback esterno (es.
   BlackHole).
4. Rimandare al preset `examples/teams-commentator.yaml` e al comando `--check`.
   *Verifica:* i comandi citati nel doc esistono e funzionano come descritto.

Trappole: non inventare flag/URL; allineare i nomi dei flag a quelli reali della
CLI (slice 10) e i default a quelli della config (slice 03).

## Acceptance criteria

- [ ] Sezione operatore che copre uscita audio di default, permessi schermo, monitor.
- [ ] Flusso diagnostico con `minnarone-oscapture-smoke` documentato.
- [ ] Limiti multi-platform (Windows/Linux/macOS) documentati.
- [ ] Riferimenti a preset e `--check` corretti e verificati.

## Blocked by

- Blocked by [08-screen-device-backend.md](./08-screen-device-backend.md)
- Blocked by [10-smoke-cli.md](./10-smoke-cli.md)

## User stories addressed

- User story 9
- User story 10
- User story 14
