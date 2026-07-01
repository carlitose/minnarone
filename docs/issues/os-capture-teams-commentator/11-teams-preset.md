## Parent PRD

[os-capture-teams-commentator.md](../../prds/os-capture-teams-commentator.md)

## What to build

Il preset di configurazione `examples/teams-commentator.yaml`: un file YAML
pronto all'uso per il commentatore locale su meeting Teams, con
`adapter: os_capture`, `mode: private`, `commentator.enabled: true`, audio+video
abilitati. `python -m minnarone examples/teams-commentator.yaml --check` deve
passare completamente. Vedi *Solution* e user story 1/4 nel PRD.

## Step-by-step implementation plan

1. Creare `examples/teams-commentator.yaml` con: `adapter: os_capture`,
   `mode: private`, sezione `commentator:` (`enabled: true`, lingua, stile),
   sezione `os_capture:` (`audio: true`, `video: true`, `monitor`,
   `audio_chunk_seconds`, `video_fps`), e i percorsi `soul_path`/`facts_dir` di
   esempio (riusando gli asset di esempio già presenti nel repo). *Perché ora:*
   dipende dal wiring completo (06) perché `--check` costruisce l'agente sul ramo
   `os_capture`.
2. Impostare valori conservativi (es. `video_fps` basso) coerenti con la policy
   di backpressure dell'ADR.
3. *Verifica:* `--check` sul preset ritorna successo senza aprire hardware;
   opzionale test che il preset è valido e parsabile.

Trappole: coerenza fra `commentator.enabled: true` e `mode: private` (la config
lo richiede già); non puntare a soul/facts inesistenti (rompe il build).

## Acceptance criteria

- [ ] Esiste `examples/teams-commentator.yaml` (os_capture + private + commentator).
- [ ] `--check` sul preset passa senza aprire hardware.
- [ ] Valori conservativi coerenti con la policy di backpressure.

## Blocked by

- Blocked by [06-app-wiring-oscapture.md](./06-app-wiring-oscapture.md)

## User stories addressed

- User story 1
- User story 4
